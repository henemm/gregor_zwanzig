<script lang="ts">
	// Issue #517 — CompareTabs: 6-Tab-Orchestrator für /compare/[id] Detail-Seite.
	//
	// Tabs: Übersicht · Orte · Wertebereiche · Layout · Versand · Vorschau
	// Issue #1231, Slice 6 (Begriffs-Konsistenz): Label „Idealwerte" -> „Wertebereiche",
	// `value`-Schlüssel unverändert (`idealwerte`). Reine Lesenansicht, keine
	// funktionale CorridorEditor-Migration hier (bleibt späterer Scope).
	//
	// URL-Sync via history.replaceState (?tab=VALUE), kein Hash wie TripTabs.
	// Mobile (<900px): scrollbare Pill-Tabs analog TripTabs.svelte.
	//
	// Spec: docs/specs/modules/issue_517_compare_hub.md

	import { Dot, Pill, Btn, Eyebrow, Card, Switch } from '$lib/components/atoms';
	import CompareChannelSwitch from '$lib/components/molecules/CompareChannelSwitch.svelte';
	import CompareBriefingPreview from '$lib/components/molecules/CompareBriefingPreview.svelte';
	import CompareLocationRow from '$lib/components/molecules/CompareLocationRow.svelte';
	import CompareLayoutRow from '$lib/components/molecules/CompareLayoutRow.svelte';
	import DetailRow from '$lib/components/molecules/DetailRow.svelte';
	import PencilIcon from '@lucide/svelte/icons/pencil';
	import { channelChipCount } from './channelChipCount.js';
	import { CHANNEL_COL_BUDGET } from '$lib/components/trip-detail/metricsEditor';
	import {
		deriveStatusFromPreset,
		presetBriefingTimesLabel,
		formatLastSent,
		formatNextSend,
		channelNamesLabel,
		STATUS_MAP
	} from '$lib/components/compare/subscriptionHelpers.js';
	import { deriveNextSend } from '$lib/utils/cockpitHelpers568.js';
	import type { ComparePreset, Location, Group } from '$lib/types.js';
	import { api } from '$lib/api.js';
	import { onMount, setContext } from 'svelte';
	// Issue #1256 Scheibe 6 (AC-14/15/16/31/32/33/34): Orte-Tab-Drag +
	// eingebetteter CorridorEditor im Idealwerte-Tab.
	import { dndzone, type DndEvent } from 'svelte-dnd-action';
	import CorridorEditor from '$lib/components/shared/corridor-editor/CorridorEditor.svelte';
	import { CompareWizardState } from './compareWizardState.svelte';
	import { hydrateWizardStateFromPreset, buildHubPutPayload, flushPendingCorridorSave, snapshotForRollback, shouldFlushOnWindowPointerUp, buildToggleActivePutPayload } from './compareHubWizardBridge.ts';
	import { groupLocations } from './locationHelpers.js';

	interface Props {
		preset: ComparePreset;
		locations: Location[];
		initialTab?: string;
	}

	let { preset, locations, initialTab = 'uebersicht' }: Props = $props();

	// Nutzerprofil für Kanal-Status (AC-8)
	let userProfile = $state<{ mail_to?: string; email?: string; telegram_chat_id?: string; sms_to?: string } | null>(null);
	onMount(async () => {
		try {
			const data = await api.get<{ mail_to?: string; email?: string; telegram_chat_id?: string; sms_to?: string }>('/api/auth/profile');
			userProfile = data;
		} catch (e) {
			console.error(e);
			// Profil nicht erreichbar — Fallback auf preset-Daten
		}
	});

	const emailConnected = $derived(
		(userProfile?.mail_to ?? userProfile?.email) ? true : preset.empfaenger.length > 0
	);
	const telegramConnected = $derived(!!userProfile?.telegram_chat_id);
	const smsConnected = $derived(!!userProfile?.sms_to);

	const TABS = [
		{ value: 'uebersicht', label: 'Übersicht' },
		{ value: 'orte', label: 'Orte' },
		{ value: 'idealwerte', label: 'Wertebereiche' },
		{ value: 'layout', label: 'Layout' },
		{ value: 'versand', label: 'Versand' },
		{ value: 'vorschau', label: 'Vorschau' }
	] as const;

	const VALID_VALUES: readonly string[] = TABS.map((t) => t.value);
	function resolve(value: string): string {
		return VALID_VALUES.includes(value) ? value : 'uebersicht';
	}

	let activeTab = $state<string>('uebersicht');
	$effect(() => {
		activeTab = resolve(initialTab);
	});

	function handleValueChange(value: string): void {
		activeTab = value;
		if (typeof window !== 'undefined') {
			const url = new URL(window.location.href);
			url.searchParams.set('tab', value);
			history.replaceState(history.state, '', url.toString());
		}
	}

	// Tab-Daten ──────────────────────────────────────────────────────────────────

	const status = $derived(deriveStatusFromPreset({ ...preset, schedule: localSchedule as ComparePreset['schedule'] }));
	const statusInfo = $derived(STATUS_MAP[status]);

	// Issue #1229 Fix-Loop 1 (F001/F002): "Nächster Versand" aus dem berechneten
	// Zeitstempel ableiten statt aus dem Rhythmus-Label (presetScheduleLabel enthält
	// einen rohen hour_from–hour_to-Bereich, den AC-4 im Versand-Tab verbietet).
	// Muster identisch zu CompareStatusRow.svelte.
	const now = new Date();
	const nextSend = $derived(deriveNextSend(preset, now));
	const versandSummaryText = $derived(
		`Briefings ${presetBriefingTimesLabel(preset)} · nächster Versand ${formatNextSend(nextSend)}.`
	);

	// Issue #1256 Scheibe 3 AC-6: Kanal-Namen statt Kanal-Anzahl in der
	// Übersicht-"Kanäle"-Stat (Soll: screen-compare-detail.jsx:147-150).
	const channelsLabel = $derived(channelNamesLabel(preset));

	// Issue #1256 Scheibe 6 Fix-Loop 2 (F005, Adversary CRITICAL): EINE lokale,
	// mutable Read-Modify-Write-Baseline fuer BEIDE S6-Speicherpfade (Orte +
	// Idealwerte). Das `preset`-Prop bleibt sonst auf den Lade-Zeitpunkt
	// eingefroren (aktualisiert nur nach togglePause()/invalidateAll() im
	// Parent, routes/compare/[id]/+page.svelte:76) — ein zweiter S6-PUT im
	// selben Seitenbesuch wuerde sonst den ersten Edit still rueckgaengig
	// machen, weil buildHubPutPayload nicht-editierte Felder aus genau dieser
	// Baseline defaultet. Wird nach JEDEM erfolgreichen S6-PUT aus dem
	// Response-Body aufgefrischt (internal/handler/compare_preset.go:390
	// liefert das gespeicherte Preset zurueck — writeJSON(w, 200, updated)).
	// Uebersicht-/Vorschau-Tab lesen bewusst weiterhin `preset` direkt
	// (bekannte, akzeptierte Stale-Anzeige, s. Fix-Vorgabe Scope).
	let currentPreset = $state<ComparePreset>(snapshotForRollback(preset));

	// Issue #1256 Scheibe 6 (AC-14/15/31/32): lokaler, optimistischer Orte-Zustand.
	// Startet aus currentPreset.location_ids, wird bei Drag/Entfernen/Hinzufügen
	// sofort im UI aktualisiert und per PUT persistiert (Rollback bei Fehler).
	let currentLocationIds = $state<string[]>([...currentPreset.location_ids]);
	const orteCount = $derived(currentLocationIds.length);

	// Orts-Auflösung: location_ids → locations[] (mit elevation_m für CompareLocationRow).
	// allLocationsForAdd ergänzt Orte, die per Inline-Add-Panel neu hinzugefügt
	// wurden und daher noch nicht im gefilterten `locations`-Prop stecken.
	const locationById = $derived.by(() => {
		const map = new Map<string, Location>();
		for (const l of locations) map.set(l.id, l);
		for (const l of allLocationsForAdd) if (!map.has(l.id)) map.set(l.id, l);
		return map;
	});
	const resolvedLocations = $derived(
		currentLocationIds.map((id, idx) => ({
			rank: idx + 1,
			loc: locationById.get(id)
		}))
	);

	// dndzone braucht Array<{id: string}> (Muster BucketSection.svelte:41-58).
	let orteItems = $state<{ id: string }[]>([]);
	$effect(() => {
		orteItems = currentLocationIds.map((id) => ({ id }));
	});

	function handleOrteDndConsider(e: CustomEvent<DndEvent<{ id: string }>>) {
		orteItems = e.detail.items;
	}

	async function handleOrteDndFinalize(e: CustomEvent<DndEvent<{ id: string }>>) {
		orteItems = e.detail.items;
		await persistPickedIds(orteItems.map((x) => x.id));
	}

	async function removeLocation(locId: string): Promise<void> {
		await persistPickedIds(currentLocationIds.filter((id) => id !== locId));
	}

	async function persistPickedIds(newIds: string[]): Promise<void> {
		const before = [...currentLocationIds];
		currentLocationIds = newIds;
		try {
			const { url, body } = buildHubPutPayload(currentPreset, { pickedIds: newIds });
			// Fix-Loop 2 (F005): Baseline aus dem Response-Body auffrischen —
			// der PUT-Handler liefert das tatsaechlich gespeicherte Preset zurueck.
			currentPreset = await api.put<ComparePreset>(url, body);
		} catch (e) {
			console.error('[CompareTabs] Orte-Persistenz fehlgeschlagen, Rollback:', e);
			currentLocationIds = before;
		}
	}

	// Inline-Add-Panel (AC-31): bespoke, kein Trip-Pendant (dokumentierte
	// Ausnahme, Programm-Spec Z.430-432). Lazy Fetch erst bei Panel-Öffnung
	// (S5-Muster), keine unbedingte Ladung beim Tab-/Seiten-Mount (S4-F001).
	let addPanelOpen = $state(false);
	let addPanelLoadStarted = false;
	let allLocationsForAdd = $state<Location[]>([]);
	let groupsForAdd = $state<Group[]>([]);

	async function toggleAddPanel(): Promise<void> {
		addPanelOpen = !addPanelOpen;
		if (!addPanelOpen || addPanelLoadStarted) return;
		addPanelLoadStarted = true;
		try {
			const [locs, groups] = await Promise.all([
				api.get<Location[]>('/api/locations'),
				api.get<Group[]>('/api/groups')
			]);
			allLocationsForAdd = locs;
			groupsForAdd = groups;
		} catch (e) {
			console.error('[CompareTabs] Orts-Bibliothek konnte nicht geladen werden:', e);
		}
	}

	const addPanelGroups = $derived.by(() => {
		const notPicked = allLocationsForAdd.filter((l) => !currentLocationIds.includes(l.id));
		const { sections, ungrouped } = groupLocations(notPicked, groupsForAdd);
		const result: [string, Location[]][] = [];
		for (const s of sections) if (s.locations.length > 0) result.push([s.group.name, s.locations]);
		if (ungrouped.length > 0) result.push(['Weitere', ungrouped]);
		return result;
	});

	async function addLocationToCompare(locId: string): Promise<void> {
		await persistPickedIds([...currentLocationIds, locId]);
	}

	// Issue #1256 Scheibe 6 (AC-16/33/34): geteilter CorridorEditor im
	// Idealwerte-Tab statt Bespoke-Liste — Bridge hydratisiert die 6 Felder,
	// die der Organism im vergleich-Kontext aus dem Wizard-State liest
	// (Entscheidung 1, C0: 0 Zeilen Diff im Organism selbst).
	const wizardState = new CompareWizardState();
	setContext('compare-wizard-state', wizardState);
	let idealwerteHydrated = $state(false);
	let lastPersistedCorridorSnapshot: {
		corridors: typeof wizardState.corridors;
		idealRanges: typeof wizardState.idealRanges;
		activeMetricKeys: typeof wizardState.activeMetricKeys;
		metricAlertLevels: typeof wizardState.metricAlertLevels;
	} | null = null;

	function currentCorridorSnapshot() {
		return snapshotForRollback({
			corridors: wizardState.corridors,
			idealRanges: wizardState.idealRanges,
			activeMetricKeys: wizardState.activeMetricKeys,
			metricAlertLevels: wizardState.metricAlertLevels
		});
	}

	$effect(() => {
		if (activeTab !== 'idealwerte' || idealwerteHydrated) return;
		// Fix-Loop 2 (F005): aus currentPreset statt preset hydrieren, damit ein
		// vorheriger Orte-Edit in derselben Sitzung nicht ueberschrieben wird.
		const hydrated = hydrateWizardStateFromPreset(currentPreset);
		wizardState.isEditMode = hydrated.isEditMode;
		wizardState.corridors = hydrated.corridors;
		wizardState.activityProfile = hydrated.activityProfile;
		wizardState.idealRanges = hydrated.idealRanges;
		if (hydrated.activeMetricKeys !== null) wizardState.activeMetricKeys = hydrated.activeMetricKeys;
		wizardState.metricAlertLevels = hydrated.metricAlertLevels;
		lastPersistedCorridorSnapshot = currentCorridorSnapshot();
		idealwerteHydrated = true;
	});

	// Event-diskretisierte Persistenz (KEIN Debounce/#1234): blur an
	// Zahlenfeldern (onfocusout bubbelt, blur nicht), click an
	// ✕/Warnen/Markieren/+Metrik, pointerup nach Slider-Drag — je EIN PUT,
	// nur wenn sich der persistenzrelevante Ausschnitt tatsächlich geändert hat.
	//
	// Fix-Loop 1 (F002, Adversary HIGH): Diff-/Payload-Entscheidung liegt in
	// `flushPendingCorridorSave` (compareHubWizardBridge.ts) — dieselbe reine
	// Funktion wird sowohl vom Wrapper-Handler (onfocusout/onclick, Z. unten)
	// als auch vom Fenster-Handler (`<svelte:window onpointerup>`) aufgerufen,
	// damit ein Band-Handle-Drag mit Pointer-Release AUSSERHALB des Wrapper-
	// Subtrees nicht mehr zu einem uebersehenen Commit fuehrt.
	async function handleCorridorCommit(): Promise<void> {
		if (!idealwerteHydrated) return;
		const current = currentCorridorSnapshot();
		const before = lastPersistedCorridorSnapshot ?? current;
		const payload = flushPendingCorridorSave(currentPreset, current, lastPersistedCorridorSnapshot);
		if (!payload) return;
		try {
			// Fix-Loop 2 (F005): Baseline aus dem Response-Body auffrischen, s.o.
			currentPreset = await api.put<ComparePreset>(payload.url, payload.body);
			lastPersistedCorridorSnapshot = current;
		} catch (e) {
			console.error('[CompareTabs] Wertebereich-Persistenz fehlgeschlagen, Rollback:', e);
			wizardState.corridors = before.corridors;
			wizardState.idealRanges = before.idealRanges;
			wizardState.activeMetricKeys = before.activeMetricKeys;
			wizardState.metricAlertLevels = before.metricAlertLevels;
		}
	}

	// Fix-Loop 1 (F002, Adversary HIGH): `<svelte:window>` muss auf Komponenten-
	// Top-Level stehen (Svelte-Constraint, nicht in {#if}-Bloecken zulaessig) —
	// die Gemountet-Bedingung ("solange der Idealwerte-Tab gemountet ist")
	// wird daher im Handler selbst geprueft. Faengt JEDEN Pointerup im
	// Dokument ab, auch wenn ein Band-Handle-Drag (CorridorEditor.svelte,
	// kein setPointerCapture) ausserhalb des `.hub-corridor-wrap`-Subtrees
	// endet (z. B. ueber der Tab-Leiste). `flushPendingCorridorSave` bleibt
	// der Waechter gegen unnoetige PUTs (No-Op bei unveraendertem Snapshot).
	//
	// Fix-Loop 2 (F006, Adversary MEDIUM): die Guard-Entscheidung selbst ist in
	// `shouldFlushOnWindowPointerUp` (reine, exportierte Funktion in
	// compareHubWizardBridge.ts) ausgelagert und dort unit-getestet — dieser
	// Handler bleibt eine reine 1-Zeilen-Delegation.
	function handleWindowPointerUp(): void {
		if (!shouldFlushOnWindowPointerUp(activeTab, idealwerteHydrated)) return;
		void handleCorridorCommit();
	}

	const idealRanges = $derived(
		preset.display_config?.ideal_ranges as
			| Record<string, { min: number; max: number; unit?: string }>
			| undefined
	);

	// Issue #1232 Scheibe 3a: einzige Kappungs-Quelle CHANNEL_COL_BUDGET
	// (metricsEditor.ts) statt eigenem Literal (bisher email:99 statt Infinity —
	// Ergebnis identisch, da Math.min(Infinity, N) === N === Math.min(99, N)
	// für jede praktisch vorkommende Orts-Anzahl N < 99).
	const CHANNEL_COLS: Record<string, number> = CHANNEL_COL_BUDGET;
	const channels = ['email', 'telegram', 'sms'];

	// ── Vorschau-Tab (Issue #514, #582) ─────────────────────────────────────────
	let previewChannel = $state<'email' | 'sms'>('email');
	let emailView = $state('desktop');
	let previewHtml = $state('');
	let previewLoading = $state(false);
	let previewError = $state<string | null>(null);
	let sendQueued = $state(false);
	let sendLoading = $state(false);
	let sendError = $state<string | null>(null);

	$effect(() => {
		if (activeTab !== 'vorschau') return;
		if (preset.location_ids.length === 0) return;
		previewHtml = '';
		previewError = null;
		previewLoading = true;
		api
			.post<{ html: string }>('/api/_validator/compare-email-preview', {
				profile: preset.profil,
				time_window: [preset.hour_from, preset.hour_to],
				target_date: new Date().toISOString().slice(0, 10),
				winner_tags: []
			})
			.then((r) => {
				previewHtml = r.html;
			})
			.catch((e: unknown) => {
				previewError =
					e && typeof e === 'object' && 'error' in e
						? String((e as { error: unknown }).error)
						: e instanceof Error
							? e.message
							: 'Vorschau konnte nicht geladen werden';
			})
			.finally(() => {
				previewLoading = false;
			});
	});

	async function handleSend() {
		if (sendLoading) return;
		sendLoading = true;
		sendError = null;
		sendQueued = false;
		try {
			await api.post(`/api/compare/presets/${preset.id}/send`, {});
			sendQueued = true;
		} catch (e: unknown) {
			const body = e as { detail?: string; error?: string };
			sendError = body?.detail ?? body?.error ?? 'Versand fehlgeschlagen';
		} finally {
			sendLoading = false;
		}
	}

	// Issue #527/#558 + #631 — Pause/Aktivieren mit Schedule-Gedächtnis (persistiert).
	// previousSchedule initialisiert aus Backend-Feld (überlebt Reload).
	let previousSchedule = $state<string>(
		preset.previous_schedule || ((preset.schedule && preset.schedule !== 'manual') ? preset.schedule : 'daily')
	);
	let localSchedule = $state<string>(preset.schedule ?? 'manual');

	async function handleToggleActive() {
		const isPausing = localSchedule !== 'manual';
		if (isPausing) previousSchedule = localSchedule;
		const next = isPausing ? 'manual' : previousSchedule;
		try {
			// Fix-Loop 3 (F007, Adversary CRITICAL): Payload aus currentPreset
			// bauen (nicht der eingefrorenen preset-Prop) und die Baseline nach
			// Erfolg auffrischen — identisches Muster wie persistPickedIds/
			// handleCorridorCommit (F005), da dies der dritte, vorbestehende
			// PUT-Pfad im selben Komponenten-Scope ist.
			const { url, body } = buildToggleActivePutPayload(currentPreset, next, previousSchedule);
			currentPreset = await api.put<ComparePreset>(url, body);
			localSchedule = next;
		} catch (e) {
			console.error('[CompareTabs] toggleActive failed:', e);
		}
	}

	// Issue #1229 — Versand-Tab-Edit-Stift: kein Inline-Edit, echter Absprung in
	// den Editor (CHub_EditIcon, JSX Z.428-434 hat bewusst keinen In-Hub-Handler).
	function goToEditVersand(): void {
		if (typeof window !== 'undefined') {
			window.location.href = `/compare/${preset.id}/edit?tab=versand`;
		}
	}
</script>

<svelte:window onpointerup={handleWindowPointerUp} />

<div class="compare-tabs" data-testid="compare-detail-tab-list">
	<!-- Tab-Leiste — custom buttons mit Underline-Indikator (Issue #582) -->
	<div style="display: flex; gap: 0">
		{#each TABS as t}
			{@const on = activeTab === t.value}
			<button
				onclick={() => handleValueChange(t.value)}
				data-testid="compare-detail-tab-{t.value}"
				style="padding: 12px 16px; cursor: pointer; font-size: 13px; font-weight: {on ? 600 : 500}; background: transparent; border: none; font-family: var(--g-font-sans); color: {on ? 'var(--g-ink)' : 'var(--g-ink-3)'}; border-bottom: {on ? '2px solid var(--g-accent)' : '2px solid transparent'}; margin-bottom: -1px; display: flex; align-items: center; gap: 7px"
			>
				{t.label}
				{#if t.value === 'orte'}
					<span style="font-size: 10px; font-weight: 600; padding: 2px 6px; border-radius: 3px; background: var(--g-paper-deep); color: var(--g-ink-3); font-family: var(--g-font-mono)">{orteCount}</span>
				{/if}
			</button>
		{/each}
	</div>

	<!-- Tab-Inhalte — Wrapper mit Padding nach JSX-Vorlage (Issue #582) -->
	<div style="position: relative; padding: 28px 40px 80px; max-width: 1320px">

	{#if activeTab === 'uebersicht'}
		<div data-testid="compare-detail-panel-uebersicht">
			<div style="display: flex; flex-direction: column; gap: 22px">
				<!-- Monitoring-Streifen -->
				<Card padding={0} style="overflow: hidden">
					<div style="padding: 18px 24px; display: flex; align-items: center; gap: 40px; flex-wrap: wrap">
						<!-- Status -->
						<div>
							<div style="font-size: 10px; color: var(--g-ink-4); letter-spacing: 0.16em; text-transform: uppercase; margin-bottom: 5px; font-family: var(--g-font-mono)">Status</div>
							<div style="font-size: 14px; color: var(--g-ink); font-weight: 500">
								{#if status === 'active'}
									<span style="display: inline-flex; align-items: center; gap: 7px"><Dot tone="good" size={7}/> Läuft automatisch</span>
								{:else if status === 'draft'}
									<span style="display: inline-flex; align-items: center; gap: 7px"><Dot tone="neutral" size={7}/> Entwurf · nicht aktiv</span>
								{:else}
									<span style="display: inline-flex; align-items: center; gap: 7px"><Dot tone="neutral" size={7}/> Pausiert</span>
								{/if}
							</div>
						</div>
						<!-- Nächster Versand -->
						<div>
							<div style="font-size: 10px; color: var(--g-ink-4); letter-spacing: 0.16em; text-transform: uppercase; margin-bottom: 5px; font-family: var(--g-font-mono)">Nächster Versand</div>
							<div style="font-size: 14px; color: var(--g-ink); font-weight: 500">{formatNextSend(nextSend)}</div>
						</div>
						<!-- Briefings -->
						<div>
							<div style="font-size: 10px; color: var(--g-ink-4); letter-spacing: 0.16em; text-transform: uppercase; margin-bottom: 5px; font-family: var(--g-font-mono)">Briefings</div>
							<div data-testid="compare-detail-stat-briefings" style="font-size: 14px; color: var(--g-ink); font-weight: 500">{presetBriefingTimesLabel(preset)}</div>
						</div>
						<!-- Zuletzt raus -->
						<div>
							<div style="font-size: 10px; color: var(--g-ink-4); letter-spacing: 0.16em; text-transform: uppercase; margin-bottom: 5px; font-family: var(--g-font-mono)">Zuletzt raus</div>
							<div style="font-size: 14px; color: var(--g-ink); font-weight: 500">{formatLastSent(preset.letzter_versand)}</div>
						</div>
						<!-- Kanäle — Issue #1256 Scheibe 3 AC-6: Namen statt Anzahl (Soll: screen-compare-detail.jsx:147-150) -->
						<div>
							<div style="font-size: 10px; color: var(--g-ink-4); letter-spacing: 0.16em; text-transform: uppercase; margin-bottom: 5px; font-family: var(--g-font-mono)">Kanäle</div>
							<div data-testid="compare-detail-stat-kanaele" style="font-size: 14px; color: var(--g-ink); font-weight: 500">
								{#if channelsLabel === '—'}
									—
								{:else}
									<span style="display: inline-flex; align-items: center; gap: 7px">
										<Dot tone="good" size={7}/>
										{channelsLabel}
									</span>
								{/if}
							</div>
						</div>
					</div>
				</Card>

				<!-- 2×2 SummaryCard-Grid -->
				<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px">
					<Card padding={20} style="display: flex; flex-direction: column">
						<div style="display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin-bottom: 4px">
							<Eyebrow>Orte</Eyebrow>
							<button onclick={() => handleValueChange('orte')} style="background: none; border: none; cursor: pointer; padding: 0; font-size: 12px; font-weight: 600; color: var(--g-accent-deep); font-family: var(--g-font-sans)">Bearbeiten →</button>
						</div>
						<div style="font-size: 16px; font-weight: 600; margin-bottom: 8px; letter-spacing: -0.01em">{preset.location_ids.length} Kandidaten</div>
						<div style="font-size: 13px; color: var(--g-ink-2); line-height: 1.6">{resolvedLocations.slice(0, 3).map(({loc}) => loc?.name ?? '—').join(' · ')}</div>
					</Card>

					<Card padding={20} style="display: flex; flex-direction: column">
						<div style="display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin-bottom: 4px">
							<Eyebrow>Wertebereiche</Eyebrow>
							<button onclick={() => handleValueChange('idealwerte')} style="background: none; border: none; cursor: pointer; padding: 0; font-size: 12px; font-weight: 600; color: var(--g-accent-deep); font-family: var(--g-font-sans)">Bearbeiten →</button>
						</div>
						<div style="font-size: 16px; font-weight: 600; margin-bottom: 8px; letter-spacing: -0.01em">{preset.profil}</div>
						<div style="font-size: 13px; color: var(--g-ink-2); line-height: 1.6">{Object.keys(idealRanges ?? {}).length} Metriken mit Idealbereich — im Briefing pro Wert markiert. Kein Score, kein Ranking.</div>
					</Card>

					<Card padding={20} style="display: flex; flex-direction: column">
						<div style="display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin-bottom: 4px">
							<Eyebrow>Layout pro Kanal</Eyebrow>
							<button onclick={() => handleValueChange('layout')} style="background: none; border: none; cursor: pointer; padding: 0; font-size: 12px; font-weight: 600; color: var(--g-accent-deep); font-family: var(--g-font-sans)">Bearbeiten →</button>
						</div>
						<div style="font-size: 16px; font-weight: 600; margin-bottom: 8px; letter-spacing: -0.01em">{channels.join(' · ')}</div>
						<div style="font-size: 13px; color: var(--g-ink-2); line-height: 1.6">Engere Kanäle zeigen automatisch weniger Spalten</div>
					</Card>

					<Card padding={20} style="display: flex; flex-direction: column">
						<div style="display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin-bottom: 4px">
							<Eyebrow>Versand</Eyebrow>
							<button onclick={() => handleValueChange('versand')} style="background: none; border: none; cursor: pointer; padding: 0; font-size: 12px; font-weight: 600; color: var(--g-accent-deep); font-family: var(--g-font-sans)">Bearbeiten →</button>
						</div>
						<div style="font-size: 16px; font-weight: 600; margin-bottom: 8px; letter-spacing: -0.01em">{presetBriefingTimesLabel(preset)}</div>
						<div style="font-size: 13px; color: var(--g-ink-2); line-height: 1.6">{versandSummaryText}</div>
					</Card>
				</div>

				<!-- Verifikations-Hinweis -->
				<div style="display: flex; align-items: center; gap: 14px; padding: 14px 18px; background: var(--g-card); border: 1px solid var(--g-rule); border-left: 3px solid var(--g-accent); border-radius: var(--g-r-3)">
					<div style="font-size: 13px; color: var(--g-ink-2); flex: 1; line-height: 1.5">
						Gelesen wird das Briefing unterwegs im Postfach — nicht hier. Der Tab <strong>Vorschau</strong> dient nur zum Prüfen der Konfiguration.
					</div>
					<Btn variant="ghost" size="sm" onclick={() => handleValueChange('vorschau')}>Vorschau prüfen →</Btn>
				</div>
			</div>
		</div>
	{/if}

	{#if activeTab === 'orte'}
		<div class="tab-panel" data-testid="compare-detail-panel-orte">
			{#if resolvedLocations.length === 0}
				<p class="empty-state">Noch keine Orte ausgewählt.</p>
			{:else}
				<div
					use:dndzone={{ items: orteItems, flipDurationMs: 150, dropTargetStyle: {} }}
					onconsider={handleOrteDndConsider}
					onfinalize={handleOrteDndFinalize}
				>
					{#each orteItems as item, i (item.id)}
						{@const loc = locationById.get(item.id)}
						{#if loc}
							<div class="hub-orte-row" class:alt={i % 2 === 1} data-testid="hub-orte-row" data-loc-id={item.id}>
								<span class="hub-orte-handle" aria-hidden="true">
									<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><circle cx="9" cy="6" r="1.6"/><circle cx="15" cy="6" r="1.6"/><circle cx="9" cy="12" r="1.6"/><circle cx="15" cy="12" r="1.6"/><circle cx="9" cy="18" r="1.6"/><circle cx="15" cy="18" r="1.6"/></svg>
								</span>
								<div class="hub-orte-row-body"><CompareLocationRow {loc} index={i + 1} /></div>
								<button
									type="button"
									class="hub-orte-remove-btn"
									data-testid="hub-orte-remove"
									title="Entfernen"
									onclick={() => removeLocation(item.id)}
								>✕</button>
							</div>
						{/if}
					{/each}
				</div>
			{/if}
			<div class="footer-link">
				<Btn variant="ghost" size="sm" data-testid="hub-orte-add" onclick={toggleAddPanel}>Ort hinzufügen</Btn>
			</div>
			{#if addPanelOpen}
				<div class="hub-add-panel" data-testid="hub-orte-panel">
					{#if addPanelGroups.length === 0}
						<p class="empty-state">Keine weiteren gespeicherten Orte verfügbar.</p>
					{:else}
						{#each addPanelGroups as [groupName, groupLocs] (groupName)}
							<div class="hub-add-group">
								<div class="hub-add-group-header">{groupName} · {groupLocs.length}</div>
								{#each groupLocs as loc (loc.id)}
									<button type="button" class="hub-add-item" onclick={() => addLocationToCompare(loc.id)}>＋ {loc.name}</button>
								{/each}
							</div>
						{/each}
					{/if}
				</div>
			{/if}
		</div>
	{/if}

	{#if activeTab === 'idealwerte'}
		<div class="tab-panel" data-testid="compare-detail-panel-idealwerte">
			{#if idealwerteHydrated}
				<div
					class="hub-corridor-wrap"
					onfocusout={handleCorridorCommit}
					onclick={handleCorridorCommit}
				>
					<CorridorEditor context="vergleich" />
				</div>
			{/if}
		</div>
	{/if}

	{#if activeTab === 'layout'}
		<div class="tab-panel" data-testid="compare-detail-panel-layout">
			{#each channels as ch}
				<CompareLayoutRow channel={ch} cols={channelChipCount(CHANNEL_COLS[ch], preset.location_ids.length)} />
			{/each}
		</div>
	{/if}

	{#if activeTab === 'versand'}
		<div class="tab-panel" data-testid="compare-detail-panel-versand">
			<div class="versand-grid">
				<!-- Linke Spalte -->
				<div class="versand-left">
					<!-- Briefing-Zeiten (Issue #1229: ersetzt "Rhythmus & Vorausschau") -->
					<Card padding={20}>
						<Eyebrow>Briefing-Zeiten</Eyebrow>
						<DetailRow label="Briefings" value={presetBriefingTimesLabel(preset)}>
							{#snippet right()}
								<button
									type="button"
									title="Bearbeiten"
									data-testid="compare-versand-edit-briefings"
									onclick={goToEditVersand}
									style="width: 30px; height: 30px; border: 1px solid var(--g-rule-soft); border-radius: var(--g-r-2); background: transparent; color: var(--g-ink-3); cursor: pointer; display: inline-flex; align-items: center; justify-content: center"
								>
									<PencilIcon size={13} />
								</button>
							{/snippet}
						</DetailRow>
						<DetailRow label="Nächster Versand" value={formatNextSend(nextSend)} divider="none" />
					</Card>

					<!-- Kanäle -->
					<Card padding={20} class="channel-card">
						<Eyebrow>Kanäle</Eyebrow>
						<div class="channel-row">
							<Dot tone={emailConnected ? 'good' : 'neutral'} />
							<span class="channel-name">Email</span>
							<span class="channel-status">{emailConnected ? 'verifiziert' : 'nicht verbunden'}</span>
							<Switch checked={emailConnected} disabled={true} size="sm" aria-label="Email-Kanal" />
						</div>
						<div class="channel-row">
							<Dot tone={telegramConnected ? 'good' : 'neutral'} />
							<span class="channel-name">Telegram</span>
							<span class="channel-status">{telegramConnected ? 'verbunden' : 'nicht verbunden'}</span>
							<Switch checked={telegramConnected} disabled={true} size="sm" aria-label="Telegram-Kanal" />
						</div>
						<div class="channel-row">
							<Dot tone={smsConnected ? 'good' : 'neutral'} />
							<span class="channel-name">SMS</span>
							<span class="channel-status">{smsConnected ? userProfile?.sms_to : 'nicht verbunden'}</span>
							<Switch checked={smsConnected} disabled={true} size="sm" aria-label="SMS-Kanal" />
						</div>
					</Card>
				</div>

				<!-- Rechte Spalte -->
				<div class="versand-right">
					<Card padding={20}>
						<Eyebrow>Aktivierung</Eyebrow>
						{#if localSchedule !== 'manual' && preset.name && preset.location_ids.length > 0}
							<div class="activation-status">
								<Dot tone="good" />
								<span class="activation-label">Aktiv</span>
							</div>
							<p class="activation-desc">Läuft automatisch</p>
							<Btn variant="quiet" size="sm" onclick={handleToggleActive}>Pausieren</Btn>
						{:else if !preset.name || preset.location_ids.length === 0}
							<div class="activation-status">
								<Dot tone="neutral" />
								<span class="activation-label">Entwurf</span>
							</div>
							<p class="activation-desc">Noch nicht aktiv</p>
							<Btn variant="primary" size="sm" onclick={handleToggleActive}>Aktivieren</Btn>
						{:else}
							<div class="activation-status">
								<Dot tone="neutral" />
								<span class="activation-label">Pausiert</span>
							</div>
							<Btn variant="primary" size="sm" onclick={handleToggleActive}>Aktivieren</Btn>
						{/if}
					</Card>

					<!-- Test-Briefing senden -->
					{#if sendQueued}
						<p class="send-success" data-testid="compare-send-success-versand">
							Briefing wurde zur Zustellung vorgemerkt.
						</p>
					{:else}
						<Btn
							variant="quiet"
							size="sm"
							disabled={sendLoading}
							onclick={handleSend}
							data-testid="compare-send-btn-versand"
						>
							{sendLoading ? 'Wird gesendet…' : 'Test-Briefing jetzt senden'}
						</Btn>
					{/if}
					{#if sendError !== null}
						<p class="send-error">{sendError}</p>
					{/if}
				</div>
			</div>
		</div>
	{/if}

	{#if activeTab === 'vorschau'}
		<div data-testid="compare-detail-panel-vorschau">
			{#if preset.location_ids.length === 0}
				<div style="padding: 32px; text-align: center; color: var(--g-ink-3); font-size: 13px">
					Noch keine Orte konfiguriert — Tab <strong>Orte</strong> besuchen um Kandidaten hinzuzufügen.
				</div>
			{:else}
			<!-- Verifikations-Hinweis (Issue #582) -->
			<div style="display: flex; align-items: center; gap: 14px; padding: 13px 18px; background: var(--g-card); border: 1px solid var(--g-rule); border-left: 3px solid var(--g-accent); border-radius: var(--g-r-3); margin-bottom: 20px">
				<Eyebrow style="flex-shrink: 0">Vorschau · Prüfung</Eyebrow>
				<div style="font-size: 13px; color: var(--g-ink-2); flex: 1; line-height: 1.5">
					So sieht dein Briefing aus — gelesen wird es unterwegs im Postfach, nicht hier.
				</div>
				<Btn variant="ghost" size="sm" onclick={handleSend} disabled={sendLoading}>
					{sendLoading ? 'Wird gesendet…' : 'Test-Briefing senden'}
				</Btn>
			</div>

			{#if sendQueued}
				<p style="font-size: 0.875rem; color: var(--g-success, #16a34a); margin: 0 0 12px" data-testid="compare-send-success">
					Briefing wurde zur Zustellung vorgemerkt.
				</p>
			{/if}
			{#if sendError !== null}
				<p style="font-size: 0.875rem; color: var(--g-danger, #dc2626); margin: 0 0 12px" data-testid="compare-send-error">{sendError}</p>
			{/if}

			<!-- Kanal-Umschalter + Email-View-Toggle (Issue #582) -->
			<div style="display: flex; align-items: center; gap: 16px; margin-bottom: 20px; flex-wrap: wrap">
				<CompareChannelSwitch
					value={previewChannel}
					onchange={(v: string) => (previewChannel = v as 'email' | 'sms')}
					channels={['email', 'sms']}
				/>
				{#if previewChannel === 'email'}
					<div style="display: inline-flex; background: var(--g-paper-deep); border: 1px solid var(--g-rule); border-radius: var(--g-r-2); padding: 3px; gap: 2px; margin-left: 12px">
						{#each [['desktop', 'Desktop-Inbox'], ['iphone', 'iPhone-Mail']] as [v, l]}
							<button onclick={() => (emailView = v)} style="padding: 7px 13px; border: none; cursor: pointer; border-radius: 4px; font-size: 12.5px; font-family: var(--g-font-sans); font-weight: {emailView === v ? 600 : 500}; background: {emailView === v ? 'var(--g-card)' : 'transparent'}; box-shadow: {emailView === v ? 'var(--g-shadow-1)' : 'none'}; color: {emailView === v ? 'var(--g-ink)' : 'var(--g-ink-3)'}">
								{l}
							</button>
						{/each}
					</div>
				{/if}
			</div>

			<!-- Render-Fläche -->
			<div style="padding: {previewChannel === 'email' && emailView === 'desktop' ? '24px' : '0'}; background: {previewChannel === 'email' && emailView === 'desktop' ? 'var(--g-paper-deep)' : 'transparent'}; border-radius: var(--g-r-3)">
				{#if previewLoading}
					<p style="font-size: 0.875rem; color: var(--g-ink-3); margin: 0" data-testid="compare-preview-loading">
						Vorschau wird geladen…
					</p>
				{:else if previewError !== null}
					<p style="font-size: 0.875rem; color: var(--g-danger, #dc2626); margin: 0" data-testid="compare-preview-error">{previewError}</p>
				{:else if previewHtml !== '' && previewChannel === 'email'}
					<div style="width: 680px; max-width: 100%;">
						<iframe
							data-testid="compare-preview-iframe"
							srcdoc={previewHtml}
							sandbox="allow-same-origin"
							title="E-Mail-Vorschau"
							style="width: 100%; min-height: 500px; border: 0; display: block"
						></iframe>
					</div>
				{/if}
				{#if previewChannel === 'sms'}
					<p style="font-size: 0.875rem; color: var(--g-ink-3); margin: 0.5rem 0 0; font-style: italic" data-testid="compare-preview-sms-hint">
						SMS-Vorschau ist noch nicht verfügbar.
					</p>
				{/if}

				<CompareBriefingPreview
					profileId={preset.profil}
					channel={previewChannel}
					subscriptionName={preset.name}
					{emailView}
				/>
			</div>
			{/if}
		</div>
	{/if}

	</div>
</div>

<style>
	/* Tab-Leiste: Segmented entfernt — custom buttons in Template (Issue #582) */

	.tab-panel {
		padding: 1.5rem 0;
	}

	.monitoring-item {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	.monitoring-item-col {
		display: flex;
		flex-direction: column;
	}
	.monitoring-label {
		font-size: 0.75rem;
		color: var(--g-ink-3);
		text-transform: uppercase;
		letter-spacing: 0.06em;
		font-family: var(--g-font-mono);
	}
	.monitoring-label-inline {
		font-weight: 500;
	}
	.monitoring-value {
		font-size: 0.875rem;
	}

	.empty-state {
		font-size: 0.875rem;
		color: var(--g-ink-3);
		padding: 1rem 0;
	}

	.footer-link {
		margin-top: 1rem;
	}
	.footer-link a {
		color: var(--g-accent);
		font-size: 0.875rem;
		text-decoration: none;
	}
	.footer-link a:hover {
		text-decoration: underline;
	}

	.placeholder {
		font-size: 0.875rem;
		color: var(--g-ink);
		margin: 0 0 0.5rem 0;
	}
	.hint {
		font-size: 0.8125rem;
		color: var(--g-ink-3);
		margin: 0 0 1rem 0;
	}

	@media (max-width: 899px) {
		/* Mobile: Tab-Leiste horizontal scrollbar */
	}

	/* ── Vorschau-Tab (Issue #514) — Design nach HubPreview ─────────────────── */
	.preview-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-end;
		gap: 24px;
		margin-bottom: 20px;
		flex-wrap: wrap;
	}
	.preview-header-text {
		max-width: 680px;
	}
	.preview-title {
		font-size: 1.5rem;
		font-weight: 600;
		letter-spacing: -0.02em;
		margin: 6px 0 6px;
		color: var(--g-ink);
	}
	.preview-subtitle {
		font-size: 0.84375rem;
		color: var(--g-ink-3);
		line-height: 1.5;
		margin: 0;
	}
	.preview-header-right {
		display: flex;
		flex-direction: column;
		align-items: flex-end;
		gap: 6px;
		flex-shrink: 0;
	}
	.preview-disclaimer {
		font-family: var(--g-font-mono);
		font-size: 0.625rem;
		color: var(--g-ink-4);
		letter-spacing: 0.04em;
		text-transform: uppercase;
	}
	.preview-stage {
		display: flex;
		justify-content: center;
		padding: 24px;
		background: #e9e6dc;
		border-radius: var(--g-r-3, 0.75rem);
		border: 1px solid var(--g-rule, #d8d3c7);
		margin-bottom: 1rem;
		min-height: 120px;
		flex-direction: column;
		align-items: center;
	}
	.preview-stage iframe {
		width: 100%;
		min-height: 500px;
		border: 0;
		display: block;
	}
	.preview-loading {
		font-size: 0.875rem;
		color: var(--g-ink-3);
		margin: 0;
	}
	.preview-error {
		font-size: 0.875rem;
		color: var(--g-danger, #dc2626);
		margin: 0;
	}
	.preview-sms-hint {
		font-size: 0.875rem;
		color: var(--g-ink-3);
		margin: 0.5rem 0 0;
		font-style: italic;
	}
	.preview-send {
		margin-top: 0.5rem;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		align-items: flex-start;
	}
	.send-success {
		font-size: 0.875rem;
		color: var(--g-success, #16a34a);
		margin: 0;
	}
	.send-error {
		font-size: 0.875rem;
		color: var(--g-danger, #dc2626);
		margin: 0;
	}

	@media (max-width: 899px) {
		.preview-header {
			flex-direction: column;
			align-items: flex-start;
		}
		.preview-header-right {
			align-items: flex-start;
		}
		.preview-stage {
			padding: 12px;
		}
	}

	/* ── Issue #526 — Übersicht-Tab ─────────────────────────────────────────── */
	.monitoring-card {
		margin-bottom: 1.5rem;
	}
	.monitoring-row {
		display: flex;
		gap: 2rem;
		flex-wrap: wrap;
		align-items: center;
	}

	.summary-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 1rem;
		margin-bottom: 1.5rem;
	}
	.summary-value {
		font-size: 1rem;
		font-weight: 600;
		margin: 0.5rem 0 0.25rem;
		color: var(--g-ink);
	}
	.summary-sub {
		font-size: 0.8125rem;
		color: var(--g-ink-3);
		margin: 0 0 0.75rem;
	}

	.hint-box {
		margin-top: 0.5rem;
	}
	.hint-text {
		font-size: 0.875rem;
		color: var(--g-ink-2);
		line-height: 1.5;
		margin: 0 0 0.75rem;
	}

	/* ── Issue #527 — Versand-Tab ────────────────────────────────────────────── */
	.versand-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 1.5rem;
		align-items: start;
	}
	.versand-left {
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}
	.versand-right {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	.channel-card {
		margin-top: 0;
	}
	.channel-row {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.5rem 0;
		border-bottom: 1px dashed var(--g-rule-soft);
	}
	.channel-row:last-child {
		border-bottom: none;
	}
	.channel-name {
		flex: 1;
		font-size: 0.875rem;
		font-weight: 500;
	}
	.channel-status {
		font-size: 0.75rem;
		color: var(--g-ink-3);
		font-family: var(--g-font-mono);
	}

	.activation-status {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 0.5rem;
	}
	.activation-label {
		font-weight: 600;
		font-size: 0.9375rem;
	}
	.activation-desc {
		font-size: 0.875rem;
		color: var(--g-ink-3);
		margin: 0 0 0.75rem;
	}

	@media (max-width: 899px) {
		.summary-grid {
			grid-template-columns: 1fr;
		}
		.versand-grid {
			grid-template-columns: 1fr;
		}
	}

	/* ── Issue #1256 Scheibe 6 — Hub-Orte-Tab (Drag/Entfernen/Add-Panel) ──── */
	.hub-orte-row {
		display: flex;
		align-items: center;
		background: transparent;
	}
	.hub-orte-row.alt {
		background: var(--g-paper-deep);
	}
	.hub-orte-handle {
		padding-left: 16px;
		color: var(--g-ink-4);
		display: flex;
		cursor: grab;
	}
	.hub-orte-row-body {
		flex: 1;
		min-width: 0;
	}
	.hub-orte-remove-btn {
		margin-right: 14px;
		width: 32px;
		height: 32px;
		flex-shrink: 0;
		border: 1px solid var(--g-rule-soft);
		border-radius: var(--g-r-2, 6px);
		background: transparent;
		color: var(--g-ink-3);
		cursor: pointer;
	}
	.hub-add-panel {
		margin-top: 12px;
		padding: 14px 16px;
		background: var(--g-card);
		border: 1px solid var(--g-rule);
		border-radius: var(--g-r-3, 10px);
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
		gap: 16px;
	}
	.hub-add-group-header {
		font-family: var(--g-font-mono);
		font-size: 10px;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		color: var(--g-ink-3);
		font-weight: 600;
		padding-bottom: 8px;
		margin-bottom: 4px;
		border-bottom: 1px solid var(--g-rule-soft);
	}
	.hub-add-item {
		display: block;
		width: 100%;
		text-align: left;
		padding: 6px 8px;
		background: transparent;
		border: none;
		border-radius: var(--g-r-2, 4px);
		font-size: 12.5px;
		color: var(--g-ink);
		cursor: pointer;
	}
	.hub-add-item:hover {
		background: var(--g-accent-tint);
	}
</style>
