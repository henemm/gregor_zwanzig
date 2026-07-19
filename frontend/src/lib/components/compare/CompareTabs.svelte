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

	import { Dot, Pill, Btn, Eyebrow, Card, SectionH } from '$lib/components/atoms';
	import CompareChannelSwitch from '$lib/components/molecules/CompareChannelSwitch.svelte';
	// Issue #1270: CompareBriefingPreview-Mount entfernt — er wurde nie mit
	// profile/data gemountet und rendert darum bedingungslos die Missing-Box
	// „Vorschau-Daten nicht verfügbar." (KB-2). Die Kanal-Anzeige läuft jetzt
	// direkt über die beiden Anzeige-Hüllen (ADR-0011).
	import CompareChatBubble from '$lib/components/molecules/CompareChatBubble.svelte';
	import CompareSmsPreview from '$lib/components/molecules/CompareSmsPreview.svelte';
	import CompareLocationRow from '$lib/components/molecules/CompareLocationRow.svelte';
	import CompareLayoutRow from '$lib/components/molecules/CompareLayoutRow.svelte';
	import VersandTab from '$lib/components/shared/VersandTab.svelte';
	// Epic #1273 S1: geteilter Save-Chip (position:fixed) + SaveStatus-Typ/Helper.
	import SaveIndicator from '$lib/components/ui/SaveIndicator.svelte';
	import type { SaveStatus } from '$lib/stores/saveStatusStore.svelte';
	import { extractMessage } from '$lib/stores/saveStatusStore.svelte';
	import { channelChipCount } from './channelChipCount.js';
	import { CHANNEL_COL_BUDGET } from '$lib/components/trip-detail/metricsEditor';
	import {
		deriveStatusWithScheduleOverride,
		presetBriefingTimesLabel,
		formatLastSent,
		formatNextSend,
		channelNamesLabel,
		presetChannels,
		presetProfileLabel,
		STATUS_MAP
	} from '$lib/components/compare/subscriptionHelpers.js';
	import { deriveNextSend } from '$lib/utils/cockpitHelpers568.js';
	import type { ComparePreset, Location, Group } from '$lib/types.js';
	import { api } from '$lib/api.js';
	import { setContext, onMount } from 'svelte';
	// Issue #1256 Scheibe 6 (AC-14/15/16/31/32/33/34): Orte-Tab-Drag +
	// eingebetteter CorridorEditor im Idealwerte-Tab.
	import SortableList from '$lib/components/shared/dnd/SortableList.svelte';
	import DragHandle from '$lib/components/shared/dnd/DragHandle.svelte';
	import CorridorEditor from '$lib/components/shared/corridor-editor/CorridorEditor.svelte';
	// Issue #1256 Scheibe 8 (AC-22): mobile Spiegelung der Idealwerte-Inline-
	// Edit-Parität, Muster TripTabs.svelte:198-202.
	import CorridorEditorMobile from '$lib/components/shared/corridor-editor/CorridorEditorMobile.svelte';
	// Issue #1258 Scheibe 5 (AC-19): geteilter Alarme-Organism im 7. Hub-Tab.
	import AlarmeTab from '$lib/components/shared/AlarmeTab.svelte';
	// Issue #1311 (C1 von Epic #1301): geteilter Wetter-Metriken-Tab (Grundauswahl,
	// vergleich-Kontext) — analog Alarme-/Versand-Bridge oben.
	import WeatherMetricsTab from '$lib/components/shared/WeatherMetricsTab.svelte';
	import {
		hydrateWeatherMetricsFromPreset,
		flushPendingWeatherMetricsSave,
		type WeatherMetricsSnapshot
	} from '../shared/weather-metrics-tab/weatherMetricsCompareSave.ts';
	// Issue #1299/#1291/#1287 (C2 von Epic #1301): Stundenverlauf-Steuerung im
	// Hub-Layout-Tab — geteiltes ChannelToggle-Bedienelement + eigenstaendiges
	// Compare-Vokabular (kein Reuse von compareMetricDefs.ts).
	import ChannelToggle from '$lib/components/shared/ChannelToggle.svelte';
	import { ALL_HOURLY_METRICS } from './compareHourlyMetricDefs.ts';
	import { CompareWizardState } from './compareWizardState.svelte';
	import {
		hydrateWizardStateFromPreset,
		buildHubPutPayload,
		flushPendingCorridorSave,
		snapshotForRollback,
		shouldFlushOnWindowPointerUp,
		buildToggleActivePutPayload,
		hydrateVersandFieldsFromPreset,
		flushPendingVersandSave,
		hydrateAlarmFieldsFromPreset,
		flushPendingAlarmSave,
		rollbackAlarmSnapshot,
		hubActivationBanner,
		createPutQueue,
		hydrateLayoutFieldsFromPreset,
		flushPendingLayoutSave,
		rollbackLayoutSnapshot,
		type VersandSnapshot,
		type AlarmSnapshot,
		type LayoutSnapshot
	} from './compareHubWizardBridge.ts';
	import { groupLocations } from './locationHelpers.js';
	import { COMPARE_TABS, resolveCompareTab } from './compareTabsResolve.js';

	interface Props {
		preset: ComparePreset;
		locations: Location[];
		initialTab?: string;
		/** Staging-Fund SF-2 (CRITICAL, AC-37): der Hub haelt seinen eigenen
		 * `localSchedule`-Zustand (Aktivierungs-Karte), waehrend die Header-
		 * Status-Pille in `compare/[id]/+page.svelte` weiterhin `data.preset`
		 * liest (nur via `invalidateAll()` im Kebab-Pfad aktualisiert) — ohne
		 * diesen Callback bleibt die Pille nach einem Pausieren/Aktivieren aus
		 * der Aktivierungs-Karte auf dem alten Status stehen, bis ein Reload
		 * erfolgt. Wird nach erfolgreichem PUT mit dem neuen `schedule` aufgerufen. */
		onScheduleChange?: (schedule: string) => void;
		/** Epic #1273 S1: geteilter Hub-SaveStatus-Controller (aus der Routen-
		 * Ebene). Wird von den 5 Commit-Handlern manuell getrieben
		 * (setSaving/setSaved/setError/markPristine), NICHT via schedule() —
		 * die Netzwerk-Serialisierung bleibt bei hubPutQueue. */
		saveController?: SaveStatus;
	}

	let { preset, locations, initialTab = 'uebersicht', onScheduleChange, saveController }: Props =
		$props();

	// Epic #1273 S3: TABS/VALID_VALUES/resolve() liegen jetzt in
	// compareTabsResolve.ts (Adversary-Fund F001 — echter Funktionsaufruf statt
	// Datei-Grep für AC-3 testbar), Verhalten unverändert.
	const TABS = COMPARE_TABS;
	function resolve(value: string): string {
		return resolveCompareTab(value);
	}

	let activeTab = $state<string>('uebersicht');
	$effect(() => {
		activeTab = resolve(initialTab);
	});

	// Issue #1256 Scheibe 8 (AC-22): Viewport-Weiche fuer den Monitoring-
	// Streifen (Desktop-5-Stat-Leiste vs. mobiles 4-Stat-2×2) und den
	// Idealwerte-Tab (CorridorEditor vs. CorridorEditorMobile) — Muster
	// TripTabs.svelte:117-124.
	let isMobileViewport = $state(false);
	onMount(() => {
		const mq = window.matchMedia('(max-width: 899px)');
		isMobileViewport = mq.matches;
		const onChange = (e: MediaQueryListEvent) => { isMobileViewport = e.matches; };
		mq.addEventListener('change', onChange);
		return () => mq.removeEventListener('change', onChange);
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

	const status = $derived(deriveStatusWithScheduleOverride(preset, localSchedule));
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

	// Issue #1256 S8c (AC-4): SummaryCard-Titel "Keine Kanäle" statt "—"
	// (Soll: screen-compare-detail.jsx:169) — abweichender Leerfall von channelsLabel.
	const layoutCardTitle = $derived(channelsLabel === '—' ? 'Keine Kanäle' : channelsLabel);

	// Issue #1256 S8c (AC-6/AC-7): lesbares Profil-Label statt rohem preset.profil
	// (Soll: JSX:163) — Fallback auf den rohen Wert, falls das Mapping leer
	// zurueckgibt (unbekanntes Profil, kein leerer Titel).
	const profileLabel = $derived(presetProfileLabel(preset.profil) || preset.profil);

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

	// Fix-Loop 1 (F002, Adversary CRITICAL): EINE gemeinsame Serialisierungs-
	// Queue fuer ALLE Hub-PUT-Pfade (Orte/Idealwerte/Versand/Toggle-Active) —
	// verhindert, dass zwei schnell aufeinanderfolgende Aktionen (z. B. eine
	// Versand-Aenderung gefolgt vom Aktivieren-Klick) zwei parallele
	// api.put()-Aufrufe mit derselben, noch veralteten currentPreset-Baseline
	// ausloesen (compareHubWizardBridge.ts: createPutQueue).
	const hubPutQueue = createPutQueue();

	// Issue #1256 Scheibe 6 (AC-14/15/31/32): lokaler, optimistischer Orte-Zustand.
	// Startet aus currentPreset.location_ids, wird bei Drag/Entfernen/Hinzufügen
	// sofort im UI aktualisiert und per PUT persistiert (Rollback bei Fehler).
	let currentLocationIds = $state<string[]>([...currentPreset.location_ids]);
	const orteCount = $derived(currentLocationIds.length);
	// Fix-Loop 2 (F003-Analogie): zuletzt ERFOLGREICH persistierter Orte-Stand,
	// analog lastPersistedCorridorSnapshot/lastPersistedVersandSnapshot — nur
	// so kann persistPickedIds beim Rollback auf den Stand NACH einem zuvor
	// in der Queue bereits erfolgreichen Edit zurueckfallen statt auf einen
	// aelteren, beim Funktionsaufruf gelesenen Stand (s. handleCorridorCommit).
	let lastPersistedLocationIds: string[] = [...currentLocationIds];

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

	// Issue #1272: DnD-State/Sync/Flip liegen jetzt im geteilten SortableList
	// (ADR-0024). Vertrag: onDndReorder(newOrder) — nur bei finalize.
	async function handleOrteDndReorder(newOrder: string[]): Promise<void> {
		await persistPickedIds(newOrder);
	}

	function orteItemLabel(id: string, i: number): string {
		return `${i + 1}. ${locationById.get(id)?.name ?? id}`;
	}

	async function removeLocation(locId: string): Promise<void> {
		await persistPickedIds(currentLocationIds.filter((id) => id !== locId));
	}

	async function persistPickedIds(newIds: string[]): Promise<void> {
		currentLocationIds = newIds;
		// Epic #1273 S1: der try/catch liegt INNERHALB des enqueue-Closures und
		// faengt den Fehler dort ab — der aeussere await wirft nie. Damit
		// setError() ueberhaupt erreichbar wird, den gefangenen Fehler in einer
		// ausserhalb deklarierten `failure`-Variable festhalten.
		let failure: unknown = null;
		saveController?.setSaving();
		// Fix-Loop 1 (F002): Payload-Bau innerhalb des enqueueten fn, damit
		// currentPreset erst zur tatsaechlichen Ausfuehrungszeit gelesen wird
		// (frisch aus einer evtl. vorher in der Queue gelaufenen PUT-Response).
		// Fix-Loop 2 (F003-Analogie): Rollback-Baseline (lastPersistedLocationIds)
		// ebenfalls erst HIER lesen — s. Begruendung an der Deklaration oben.
		const updated = await hubPutQueue.enqueue(async () => {
			try {
				const { url, body } = buildHubPutPayload(currentPreset, { pickedIds: newIds });
				const result = await api.put<ComparePreset>(url, body);
				// Fix-Loop 2 (F005): Baseline aus dem Response-Body auffrischen —
				// der PUT-Handler liefert das tatsaechlich gespeicherte Preset zurueck.
				lastPersistedLocationIds = newIds;
				return result;
			} catch (e) {
				console.error('[CompareTabs] Orte-Persistenz fehlgeschlagen, Rollback:', e);
				currentLocationIds = lastPersistedLocationIds;
				failure = e;
				return null;
			}
		});
		if (updated) {
			currentPreset = updated;
			saveController?.setSaved();
		} else if (failure) {
			saveController?.setError(extractMessage(failure));
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
		// Epic #1273 S1: `failure` trennt den No-Op-Fall (kein Diff, gar kein PUT)
		// vom Fehlerfall — beide liefern `updated === null`. No-Op bekommt
		// markPristine() (keine Speicher-Anzeige-Luege, #1269 AC-3), nur ein
		// echter Fehler setError().
		let failure: unknown = null;
		saveController?.setSaving();
		// Fix-Loop 2 (F003, Adversary MEDIUM): current/before/Diff-Check/Rollback
		// KOMPLETT innerhalb des enqueueten fn lesen bzw. ausfuehren — bei
		// tatsaechlicher Ausfuehrung ist `lastPersistedCorridorSnapshot` bereits
		// durch einen zuvor in der Queue gelaufenen, erfolgreichen Edit
		// aufgefrischt. Ein hier NEU (statt beim Funktionsaufruf) gelesenes
		// `before` faellt bei einem Fehlschlag daher korrekt nur auf den Stand
		// NACH diesem vorherigen Edit zurueck, nicht auf einen aelteren Stand
		// (sonst UI/Server-Divergenz bis Reload). `current` bleibt trotzdem
		// korrekt: wizardState wird zwischen Enqueue und Ausfuehrung von
		// niemandem ausser dem Nutzer veraendert, ein hier gelesener Snapshot
		// spiegelt also weiterhin (sogar aktueller) den Nutzerstand zum
		// Commit-Zeitpunkt.
		const updated = await hubPutQueue.enqueue(async () => {
			const current = currentCorridorSnapshot();
			const before = lastPersistedCorridorSnapshot ?? current;
			const payload = flushPendingCorridorSave(currentPreset, current, lastPersistedCorridorSnapshot);
			if (!payload) return null;
			try {
				const result = await api.put<ComparePreset>(payload.url, payload.body);
				// Fix-Loop 2 (F005): Baseline aus dem Response-Body auffrischen, s.o.
				lastPersistedCorridorSnapshot = current;
				return result;
			} catch (e) {
				console.error('[CompareTabs] Wertebereich-Persistenz fehlgeschlagen, Rollback:', e);
				wizardState.corridors = before.corridors;
				wizardState.idealRanges = before.idealRanges;
				wizardState.activeMetricKeys = before.activeMetricKeys;
				wizardState.metricAlertLevels = before.metricAlertLevels;
				failure = e;
				return null;
			}
		});
		if (updated) {
			currentPreset = updated;
			saveController?.setSaved();
		} else if (failure) {
			saveController?.setError(extractMessage(failure));
		} else {
			saveController?.markPristine();
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

	// Issue #1256 Scheibe 7 (AC-35/36): eingebetteter VersandTab (context="vergleich")
	// im Versand-Tab — analog Idealwerte-Bridge oben (S6-Muster), gleicher
	// `wizardState`/gleiche `currentPreset`-Baseline, ABER eigene Snapshot-
	// Baseline (`lastPersistedVersandSnapshot`), damit der Versand-Flush den
	// Idealwerte-Flush nicht ueberschreibt.
	let versandHydrated = $state(false);
	let lastPersistedVersandSnapshot: VersandSnapshot | null = null;

	function currentVersandSnapshot(): VersandSnapshot {
		return snapshotForRollback({
			sendTelegram: wizardState.sendTelegram,
			sendSms: wizardState.sendSms,
			morningEnabled: wizardState.morningEnabled,
			morningTime: wizardState.morningTime,
			eveningEnabled: wizardState.eveningEnabled,
			eveningTime: wizardState.eveningTime,
			endDate: wizardState.endDate,
			alertCooldownMinutes: wizardState.alertCooldownMinutes,
			alertQuietFrom: wizardState.alertQuietFrom,
			alertQuietTo: wizardState.alertQuietTo
		});
	}

	$effect(() => {
		if (activeTab !== 'versand' || versandHydrated) return;
		// F005-Muster: aus currentPreset hydrieren, damit ein vorheriger
		// Orte-/Idealwerte-Edit in derselben Sitzung nicht ueberschrieben wird.
		const hydrated = hydrateVersandFieldsFromPreset(currentPreset);
		wizardState.sendEmail = hydrated.sendEmail;
		wizardState.sendTelegram = hydrated.sendTelegram;
		wizardState.sendSms = hydrated.sendSms;
		wizardState.morningEnabled = hydrated.morningEnabled;
		wizardState.morningTime = hydrated.morningTime;
		wizardState.eveningEnabled = hydrated.eveningEnabled;
		wizardState.eveningTime = hydrated.eveningTime;
		wizardState.endDate = hydrated.endDate;
		wizardState.alertCooldownMinutes = hydrated.alertCooldownMinutes;
		wizardState.alertQuietFrom = hydrated.alertQuietFrom;
		wizardState.alertQuietTo = hydrated.alertQuietTo;
		lastPersistedVersandSnapshot = currentVersandSnapshot();
		versandHydrated = true;
	});

	// Event-diskretisierte Persistenz (KEIN Debounce/#1234): change an
	// Toggles/Zeit-/Datumsfeldern (Bubble-Phase, s. Staging-Fund SF-1 unten am
	// Wrapper-Markup), focusout an Cooldown-/Stille-Stunden-Zahlenfeldern
	// (onfocusout bubbelt, blur nicht — S6-Kommentar).
	//
	// Fix-Loop 1 (F001, Adversary HIGH): zusaetzlich onclick am Wrapper —
	// `VTLaufzeitVergleich` (Laufzeit-Control) mutiert `wiz.endDate` bei
	// „Bis auf Weiteres" rein per Klick auf einen Button, der weder ein
	// change- noch garantiert ein focusout-Event ausloest (WebKit fokussiert
	// Buttons nicht per Klick) — ohne onclick wuerde diese Aenderung nie
	// geflusht. `flushPendingVersandSave` bleibt der Waechter gegen
	// unnoetige PUTs (No-Op bei unveraendertem Snapshot), daher unkritisch,
	// dass auch andere Klicks im Subtree diesen Handler ausloesen.
	async function handleVersandCommit(): Promise<void> {
		if (!versandHydrated) return;
		// Epic #1273 S1: `failure` trennt No-Op (markPristine) vom Fehler
		// (setError), s. handleCorridorCommit.
		let failure: unknown = null;
		saveController?.setSaving();
		// Fix-Loop 2 (F003, Adversary MEDIUM): current/before/Diff-Check/Rollback
		// KOMPLETT innerhalb des enqueueten fn — identisches Prinzip wie
		// handleCorridorCommit (s. dortiger Kommentar): `lastPersistedVersandSnapshot`
		// ist zur tatsaechlichen Ausfuehrungszeit bereits durch einen zuvor in der
		// Queue gelaufenen, erfolgreichen Edit aufgefrischt — ein hier erst
		// gelesenes `before` faellt bei einem Fehlschlag daher korrekt nur auf
		// den Stand NACH diesem vorherigen Edit zurueck.
		const updated = await hubPutQueue.enqueue(async () => {
			const current = currentVersandSnapshot();
			const before = lastPersistedVersandSnapshot ?? current;
			const payload = flushPendingVersandSave(currentPreset, current, lastPersistedVersandSnapshot);
			if (!payload) return null;
			try {
				const result = await api.put<ComparePreset>(payload.url, payload.body);
				lastPersistedVersandSnapshot = current;
				return result;
			} catch (e) {
				console.error('[CompareTabs] Versand-Persistenz fehlgeschlagen, Rollback:', e);
				wizardState.sendTelegram = before.sendTelegram;
				wizardState.sendSms = before.sendSms;
				wizardState.morningEnabled = before.morningEnabled;
				wizardState.morningTime = before.morningTime;
				wizardState.eveningEnabled = before.eveningEnabled;
				wizardState.eveningTime = before.eveningTime;
				wizardState.endDate = before.endDate;
				wizardState.alertCooldownMinutes = before.alertCooldownMinutes;
				wizardState.alertQuietFrom = before.alertQuietFrom;
				wizardState.alertQuietTo = before.alertQuietTo;
				failure = e;
				return null;
			}
		});
		if (updated) {
			currentPreset = updated;
			saveController?.setSaved();
		} else if (failure) {
			saveController?.setError(extractMessage(failure));
		} else {
			saveController?.markPristine();
		}
	}

	// Issue #1258 Scheibe 5 (AC-19, AC-29, H2/H3): eingebetteter AlarmeTab
	// (context="vergleich") im 7. Hub-Tab — analog Idealwerte-/Versand-Bridge
	// oben (gleicher `wizardState`/gleiche `currentPreset`-Baseline, eigene
	// Snapshot-Baseline `lastPersistedAlarmSnapshot`). H3: der Alarme-Tab kann
	// als ERSTER Tab geoeffnet werden (Deep-Link `?tab=alarme`) — der
	// Hydrations-Effekt hydriert deshalb ALLE Alarm-Felder eigenstaendig ueber
	// `hydrateAlarmFieldsFromPreset` (statt sich auf einen bereits gelaufenen
	// idealwerte-/versand-Effekt zu verlassen).
	let alarmeHydrated = $state(false);
	let lastPersistedAlarmSnapshot: AlarmSnapshot | null = null;

	function currentAlarmSnapshot(): AlarmSnapshot {
		return snapshotForRollback({
			officialAlertsEnabled: wizardState.officialAlertsEnabled,
			officialWarningsEnabled: wizardState.officialWarningsEnabled,
			radarAlertEnabled: wizardState.radarAlertEnabled,
			metricAlertLevels: wizardState.metricAlertLevels,
			alertCooldownMinutes: wizardState.alertCooldownMinutes,
			alertQuietFrom: wizardState.alertQuietFrom,
			alertQuietTo: wizardState.alertQuietTo,
			// Issue #1260: Kurzstil-Toggle im Snapshot, damit ein reiner
			// Toggle-Klick (ohne andere Aenderung) als dirty erkannt wird und
			// handleAlarmeCommit einen PUT ausloest.
			telegramStyle: wizardState.telegramStyle
		});
	}

	$effect(() => {
		if (activeTab !== 'alarme' || alarmeHydrated) return;
		// F005-Muster: aus currentPreset hydrieren, damit ein vorheriger
		// Orte-/Idealwerte-/Versand-Edit in derselben Sitzung nicht
		// ueberschrieben wird (H3: eigenstaendige Hydration ALLER Alarm-Felder,
		// setzt KEINEN vorherigen idealwerte-/versand-Effekt voraus).
		hydrateAlarmFieldsFromPreset(wizardState, currentPreset);
		lastPersistedAlarmSnapshot = currentAlarmSnapshot();
		alarmeHydrated = true;
	});

	// Event-diskretisierte Persistenz (KEIN Debounce/#1234): change/focusout/
	// click am Wrapper, Muster identisch `handleVersandCommit` (s. dortiger
	// Kommentar SF-1/F001 zur Bubble-Phase).
	//
	// H3 Snapshot-Kreuzeffekte (Adversary-Punkt, Context Zeile 33/49):
	// `metricAlertLevels` wird auch vom Idealwerte-Snapshot
	// (`lastPersistedCorridorSnapshot`) und `alertCooldownMinutes`/
	// `alertQuietFrom/To` auch vom Versand-Snapshot (`lastPersistedVersandSnapshot`)
	// getrackt — der Alarme-Tab fuehrt (S5) die ERSTE Ueberlappung zwischen
	// zwei Hub-Snapshots ein. Fuer den ERFOLGS-Pfad unkritisch: jeder
	// Commit-Handler liest `current` IMMER frisch aus dem gemeinsamen
	// `wizardState` (nie aus dem stale `before`), ein bereits von einem
	// Nachbar-Tab persistiertes Feld wird beim naechsten Flush also korrekt
	// mitgesendet — hoechstens ein redundanter Echo-PUT desselben Werts.
	//
	// Fix-Loop 1 (F001, Adversary CRITICAL): der FEHLER-Pfad (Rollback) darf
	// deshalb NICHT pauschal alle Felder auf `before` zuruecksetzen — sonst
	// wuerde ein zwischenzeitlicher Nachbar-Tab-Edit an einem geteilten Feld
	// (z. B. Cooldown im Versand-Tab, waehrend dieser Alarme-PUT noch
	// in-flight war und dann fehlschlaegt) still verworfen. Diff-basierter
	// Rollback via `rollbackAlarmSnapshot` (compareHubWizardBridge.ts): pro
	// Feld nur zuruecksetzen, wenn `wizardState` noch den Wert traegt, den
	// DIESER gescheiterte Commit gesendet hat (`current`); ein Feld, das ein
	// Nachbar-Tab seither veraendert hat, bleibt unangetastet.
	async function handleAlarmeCommit(): Promise<void> {
		if (!alarmeHydrated) return;
		// Epic #1273 S1: `failure` trennt No-Op (markPristine) vom Fehler
		// (setError), s. handleCorridorCommit.
		let failure: unknown = null;
		saveController?.setSaving();
		const updated = await hubPutQueue.enqueue(async () => {
			const current = currentAlarmSnapshot();
			const before = lastPersistedAlarmSnapshot ?? current;
			const payload = flushPendingAlarmSave(currentPreset, current, lastPersistedAlarmSnapshot);
			if (!payload) return null;
			try {
				const result = await api.put<ComparePreset>(payload.url, payload.body);
				lastPersistedAlarmSnapshot = current;
				return result;
			} catch (e) {
				console.error('[CompareTabs] Alarme-Persistenz fehlgeschlagen, Rollback:', e);
				rollbackAlarmSnapshot(wizardState, before, current);
				failure = e;
				return null;
			}
		});
		if (updated) {
			currentPreset = updated;
			saveController?.setSaved();
		} else if (failure) {
			saveController?.setError(extractMessage(failure));
		} else {
			saveController?.markPristine();
		}
	}

	// Issue #1311 (C1): eingebetteter WeatherMetricsTab (context="vergleich")
	// im neuen Hub-Tab "Wetter-Metriken" — analog Alarme-/Versand-Bridge oben.
	// Eigene Hydrations-/Snapshot-Baseline, weil der Tab als ERSTER geoeffnet
	// werden kann (Deep-Link `?tab=wetter-metriken`), ohne dass idealwerte
	// vorher hydriert hat.
	let wetterMetrikenHydrated = $state(false);
	let lastPersistedWetterMetrikenSnapshot: WeatherMetricsSnapshot | null = null;

	function currentWetterMetrikenSnapshot(): WeatherMetricsSnapshot {
		return {
			activeMetricKeys: [...wizardState.activeMetricKeys],
			officialAlertsEnabled: wizardState.officialAlertsEnabled
		};
	}

	$effect(() => {
		if (activeTab !== 'wetter-metriken' || wetterMetrikenHydrated) return;
		wizardState.activeMetricKeys = hydrateWeatherMetricsFromPreset(currentPreset);
		// D2-Fix-Loop 2 (AC-6): officialAlertsEnabled beim Erst-Oeffnen
		// mit-hydrieren (analog hydrateAlarmFieldsFromPreset) — sonst zeigt der
		// Toggle bei einem Deep-Link ?tab=wetter-metriken den Klassen-Default
		// (true) statt des echten Preset-Werts.
		wizardState.officialAlertsEnabled = currentPreset.official_alerts_enabled ?? true;
		lastPersistedWetterMetrikenSnapshot = currentWetterMetrikenSnapshot();
		wetterMetrikenHydrated = true;
	});

	async function handleWetterMetrikenCommit(): Promise<void> {
		if (!wetterMetrikenHydrated) return;
		let failure: unknown = null;
		saveController?.setSaving();
		const updated = await hubPutQueue.enqueue(async () => {
			const current = currentWetterMetrikenSnapshot();
			const before = lastPersistedWetterMetrikenSnapshot ?? current;
			const payload = flushPendingWeatherMetricsSave(currentPreset, current, lastPersistedWetterMetrikenSnapshot);
			if (!payload) return null;
			try {
				const result = await api.put<ComparePreset>(payload.url, payload.body);
				lastPersistedWetterMetrikenSnapshot = current;
				return result;
			} catch (e) {
				console.error('[CompareTabs] Wetter-Metriken-Persistenz fehlgeschlagen, Rollback:', e);
				wizardState.activeMetricKeys = before.activeMetricKeys;
				wizardState.officialAlertsEnabled = before.officialAlertsEnabled;
				failure = e;
				return null;
			}
		});
		if (updated) {
			currentPreset = updated;
			saveController?.setSaved();
		} else if (failure) {
			saveController?.setError(extractMessage(failure));
		} else {
			saveController?.markPristine();
		}
	}

	// Issue #1299/#1291/#1287 (C2): eingebetteter Stundenverlauf-Bereich im
	// Hub-Tab "Layout" — analog Wetter-Metriken-Bridge oben. Eigene
	// Hydrations-/Snapshot-Baseline, weil der Layout-Tab als ERSTER geoeffnet
	// werden kann (Deep-Link `?tab=layout`).
	let layoutHydrated = $state(false);
	let lastPersistedLayoutSnapshot: LayoutSnapshot | null = null;

	$effect(() => {
		if (activeTab !== 'layout' || layoutHydrated) return;
		const hydrated = hydrateLayoutFieldsFromPreset(currentPreset);
		wizardState.hourlyMetricKeys = hydrated.hourlyMetricKeys;
		wizardState.hourlyEnabled = hydrated.hourlyEnabled;
		lastPersistedLayoutSnapshot = hydrated;
		layoutHydrated = true;
	});

	// Verschoben aus CompareInhaltSection.svelte:38-60 (Duplikat statt
	// Abhaengigkeit, s. Spec Known Limitations — CompareInhaltSection wird mit
	// F2 geloescht, darf keine Hub-Abhaengigkeit werden).
	function isHourlyMetricActive(key: string): boolean {
		return wizardState.hourlyMetricKeys.length === 0 || wizardState.hourlyMetricKeys.includes(key);
	}

	// Factory-Handler (Safari-Pattern): materialisiert beim ersten Abwaehlen
	// die volle Liste, damit "alle minus eine" korrekt entsteht.
	function makeHourlyMetricHandler(key: string) {
		return function handleHourlyMetric(checked: boolean): void {
			const current =
				wizardState.hourlyMetricKeys.length === 0
					? ALL_HOURLY_METRICS.map((m) => m.key)
					: [...wizardState.hourlyMetricKeys];
			if (checked) {
				if (!current.includes(key)) current.push(key);
			} else {
				const idx = current.indexOf(key);
				if (idx >= 0) current.splice(idx, 1);
			}
			wizardState.hourlyMetricKeys = current;
		};
	}

	async function handleLayoutCommit(): Promise<void> {
		if (!layoutHydrated) return;
		let failure: unknown = null;
		saveController?.setSaving();
		const updated = await hubPutQueue.enqueue(async () => {
			const current: LayoutSnapshot = {
				hourlyMetricKeys: [...wizardState.hourlyMetricKeys],
				hourlyEnabled: wizardState.hourlyEnabled
			};
			const before = lastPersistedLayoutSnapshot ?? current;
			const payload = flushPendingLayoutSave(currentPreset, current, lastPersistedLayoutSnapshot);
			if (!payload) return null;
			try {
				const result = await api.put<ComparePreset>(payload.url, payload.body);
				lastPersistedLayoutSnapshot = current;
				return result;
			} catch (e) {
				console.error('[CompareTabs] Layout-Persistenz fehlgeschlagen, Rollback:', e);
				rollbackLayoutSnapshot(wizardState, before);
				failure = e;
				return null;
			}
		});
		if (updated) {
			currentPreset = updated;
			saveController?.setSaved();
		} else if (failure) {
			saveController?.setError(extractMessage(failure));
		} else {
			saveController?.markPristine();
		}
	}

	// Issue #1258 S5 (H4): notifyCount fuer den AlarmeTab-Kopf — Korridore
	// kommen normalerweise aus dem idealwerte-Hydrat, der alarme-Effekt
	// hydriert `corridors` aber selbst mit (s. hydrateAlarmFieldsFromPreset),
	// damit die Zahl auch korrekt ist, wenn Alarme der erste geoeffnete Tab ist.
	const notifyCount = $derived((wizardState.corridors ?? []).filter((c) => c.notify).length);

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

	// Issue #1267: Layout-Tab-Chips zeigen echte Ortsnamen (nicht Zahlen).
	// Namen aus resolvedLocations (Orts-Reihenfolge), pro Kanal auf das
	// Kanal-Budget gekappt via bestehender channelChipCount-Logik.
	const layoutLocationNames = $derived(
		resolvedLocations.map((r) => r.loc?.name).filter((n): n is string => !!n)
	);
	const layoutChipNamesFor = (ch: string): string[] =>
		layoutLocationNames.slice(0, channelChipCount(CHANNEL_COLS[ch], layoutLocationNames.length));

	// Issue #1256 S8c (AC-1/AC-2): Layout-Tab-Limit-Pillen, statisch nach
	// JSX-Vorbild (screen-compare-detail.jsx:247, mobile: :150) — keine neue
	// Datenquelle, SMS-Pille mobil ohne "· 0".
	const LAYOUT_LIMIT_PILLS = ['Email · alle Spalten', 'Telegram · max 8', 'SMS · flach · 0'];
	const LAYOUT_LIMIT_PILLS_MOBILE = ['Email · alle Spalten', 'Telegram · max 8', 'SMS · flach'];

	// ── Vorschau-Tab (Issue #514, #582) ─────────────────────────────────────────
	let previewChannel = $state<'email' | 'sms' | 'telegram'>('email');
	// Issue #1256 S8b (AC-2, Rest-Inventur R1): Kanal-Liste fuer den Umschalter
	// kommt aus der Preset-Konfiguration statt hart ['email','sms'] — dieselbe
	// Ableitungsquelle wie channelNamesLabel (S3 AC-6), nur auf die von
	// CompareChannelSwitch erwarteten Kleinschreib-Keys projiziert (kein neues
	// Ableitungs-Duplikat).
	const previewConfiguredChannels = $derived(presetChannels(preset).map((c) => c.toLowerCase()));
	let emailView = $state('desktop');
	let previewHtml = $state('');
	// Issue #1270 (ADR-0011): Telegram/SMS kommen fertig gerendert aus dem
	// Backend — das Frontend rendert Kanal-Inhalte nicht nach.
	let previewTelegram = $state('');
	let previewSms = $state('');
	let previewSmsCount = $state(0);
	let previewLoading = $state(false);
	let previewError = $state<string | null>(null);
	let sendQueued = $state(false);
	let sendLoading = $state(false);
	let sendError = $state<string | null>(null);

	// Issue #1270 (AC-1/AC-2/AC-7): EIN Abruf auf /api/preview/compare/{id}
	// liefert alle Kanäle aus EINEM ComparisonEngine-Lauf über die echten Orte
	// des Presets. Vorher hing der Tab am Validator-Stub
	// (/api/_validator/compare-email-preview, #464), der einen hartcodierten
	// "Vorschau-Ort" rendert — der Endpoint selbst bleibt für den externen
	// Validator bestehen, nur dieser Tab hängt um.
	//
	// AC-7: `previewChannel` wird hier bewusst NICHT gelesen — der Effect hängt
	// nur an Tab + Preset-ID + Orte-Anzahl. Ein Kanalwechsel löst damit keinen
	// neuen Request aus, er schaltet nur die Anzeige der bereits geladenen
	// Payloads um. Vorbild: AlertPreviewCard.svelte:34-44.
	$effect(() => {
		if (activeTab !== 'vorschau') return;
		if (preset.location_ids.length === 0) return;
		const presetId = preset.id;
		previewHtml = '';
		previewTelegram = '';
		previewSms = '';
		previewSmsCount = 0;
		previewError = null;
		previewLoading = true;
		api
			.post<{
				subject: string;
				email_html: string;
				telegram: string;
				sms: string;
				sms_char_count: number;
			}>(`/api/preview/compare/${presetId}`, {})
			.then((r) => {
				previewHtml = r.email_html;
				previewTelegram = r.telegram;
				previewSms = r.sms;
				previewSmsCount = r.sms_char_count;
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

	// Liefert true/false statt zu werfen — der Hub-eigene CTA-Klick ignoriert
	// den Rueckgabewert (fire-and-forget wie bisher), der Kebab-Delegations-
	// pfad (toggleActiveFromParent, s.u.) braucht ihn dagegen, um seine eigene
	// `pauseError`-Anzeige in compare/[id]/+page.svelte zu steuern.
	async function handleToggleActive(): Promise<boolean> {
		const isPausing = localSchedule !== 'manual';
		if (isPausing) previousSchedule = localSchedule;
		const next = isPausing ? 'manual' : previousSchedule;
		// Epic #1273 S1: einziger der 5 Handler mit try/catch AUSSERHALB des
		// enqueue-Closures — ein echter Fehler propagiert normal, daher direktes
		// Wrapping ohne `failure`-Variable.
		saveController?.setSaving();
		try {
			// Fix-Loop 3 (F007, Adversary CRITICAL): Payload aus currentPreset
			// bauen (nicht der eingefrorenen preset-Prop) und die Baseline nach
			// Erfolg auffrischen — identisches Muster wie persistPickedIds/
			// handleCorridorCommit (F005), da dies einer von mehreren
			// PUT-Pfaden im selben Komponenten-Scope ist.
			// Fix-Loop 1 (F002): Payload-Bau innerhalb des enqueueten fn, damit
			// currentPreset erst zur Ausfuehrungszeit gelesen wird — verhindert
			// den Race mit handleVersandCommit im selben Versand-Tab.
			currentPreset = await hubPutQueue.enqueue(async () => {
				const { url, body } = buildToggleActivePutPayload(currentPreset, next, previousSchedule);
				return api.put<ComparePreset>(url, body);
			});
			localSchedule = next;
			// Staging-Fund SF-2: Elternkomponente ueber den neuen Schedule
			// informieren, damit die Header-Status-Pille (andere Status-Quelle,
			// s. Props-Kommentar) mitzieht, ohne dass wir hier invalidateAll()
			// aufrufen (wuerde die eingefrorene-Prop-/currentPreset-Baseline-
			// Architektur mit frisch geladenen `data` kollidieren lassen).
			onScheduleChange?.(next);
			saveController?.setSaved();
			return true;
		} catch (e) {
			console.error('[CompareTabs] toggleActive failed:', e);
			saveController?.setError(extractMessage(e));
			return false;
		}
	}

	/**
	 * Staging-Fund F004 (CRITICAL): Delegations-Einstiegspunkt fuer den
	 * Hub-Header-Kebab (compare/[id]/+page.svelte togglePause) — der Kebab
	 * rief bislang einen EIGENSTAENDIGEN fetch-Pfad mit vollem Objekt-Spread
	 * aus dem (potenziell veralteten) `data.preset` auf, komplett AUSSERHALB
	 * der `hubPutQueue`/`currentPreset`-Baseline dieser Komponente. Je nach
	 * Reihenfolge fuehrte das zu zwei Datenverlust-Varianten (Adversary-Proben
	 * probe_kebab_vs_hub_stale_data.mjs / probe_kebab_vs_hub_reverse.mjs):
	 * ein Hub-Edit (Orte/Idealwerte/Versand) konnte vom Kebab-Toggle
	 * ueberschrieben werden ODER umgekehrt. Der Kebab ruft jetzt (per
	 * `bind:this` durch CompareDetail durchgereicht) exakt denselben
	 * `handleToggleActive`-Pfad auf wie die Aktivierungs-Karte im
	 * Versand-Tab — EIN Schreibweg fuer Pausieren/Aktivieren, unabhaengig
	 * davon, von wo er ausgeloest wird.
	 */
	export function toggleActiveFromParent(): Promise<boolean> {
		return handleToggleActive();
	}

	// Staging-Fund F004 Robustheits-Zusatz (defensiv, KEIN aktuell
	// reproduzierbarer Bug): falls `preset` durch einen ECHTEN Prop-
	// Referenzwechsel aktualisiert wird (z. B. ein kuenftig wieder
	// eingefuehrter invalidateAll()-Pfad ausserhalb dieser Komponente — nach
	// F004 gibt es im Compare-Hub aktuell KEINEN solchen Pfad mehr, dieser
	// Effekt ist Verteidigung gegen zukuenftige Regressionen), synchronisiert
	// dieser Effekt `currentPreset` und setzt die Lazy-Hydration-Flags
	// zurueck. Alle Hub-Edits sind event-diskretisiert UND ueber `hubPutQueue`
	// serialisiert persistiert — ein frischer Prop-Stand traegt daher immer
	// den Server-Superset (nie einen Stand, der einen bereits bestaetigten
	// Hub-Edit rueckgaengig macht). Reagiert NUR auf `preset` (die Prop),
	// NICHT auf `currentPreset` selbst — interne PUT-Updates von
	// `currentPreset` aendern `preset` nicht und loesen diesen Effekt daher
	// nicht aus.
	$effect(() => {
		currentPreset = snapshotForRollback(preset);
		idealwerteHydrated = false;
		versandHydrated = false;
		alarmeHydrated = false;
		wetterMetrikenHydrated = false;
	});
</script>

<svelte:window onpointerup={handleWindowPointerUp} />

<!-- Epic #1273 S1: geteilter Save-Chip (position:fixed, daher Mount-Stelle frei),
     analog TripHeader.svelte:194-195. -->
{#if saveController}
	<SaveIndicator controller={saveController} />
{/if}

<div class="compare-tabs" data-testid="compare-detail-tab-list">
	<!-- Tab-Leiste — custom buttons mit Underline-Indikator (Issue #582) -->
	<div class="compare-tabs-bar" style="display: flex; gap: 0">
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
	<div class="compare-tabs-content" style="position: relative; max-width: 1320px">

	{#if activeTab === 'uebersicht'}
		<div data-testid="compare-detail-panel-uebersicht">
			<div style="display: flex; flex-direction: column; gap: 22px">
				<!-- Monitoring-Streifen — Issue #1256 Scheibe 8 (AC-22): mobil 4-Stat-2×2
				     statt 5-Stat-Desktop-Leiste (Soll: screen-compare-detail-mobile.jsx:79-85) -->
				{#if isMobileViewport}
					<div data-testid="compare-detail-monitoring-mobile" class="hub-mobile-grid">
						<Card padding={14}>
							<div class="hub-mobile-stat-label">Status</div>
							<div class="hub-mobile-stat-value">
								<!-- Issue #1256 S8c (AC-8): Kurzform statt Langform (Soll: screen-compare-detail-mobile.jsx:81). -->
								{#if status === 'active'}
									<span class="hub-mobile-stat-inline"><Dot tone="good" size={7}/>Läuft autom.</span>
								{:else if status === 'draft'}
									<span class="hub-mobile-stat-inline"><Dot tone="neutral" size={7}/>Entwurf</span>
								{:else}
									<span class="hub-mobile-stat-inline"><Dot tone="neutral" size={7}/>Pausiert</span>
								{/if}
							</div>
						</Card>
						<Card padding={14}>
							<div class="hub-mobile-stat-label">Nächster Versand</div>
							<div class="hub-mobile-stat-value">{formatNextSend(nextSend)}</div>
						</Card>
						<Card padding={14}>
							<div class="hub-mobile-stat-label">Zuletzt raus</div>
							<div class="hub-mobile-stat-value">{formatLastSent(preset.letzter_versand)}</div>
						</Card>
						<Card padding={14}>
							<div class="hub-mobile-stat-label">Kanäle</div>
							<div class="hub-mobile-stat-value" data-testid="compare-detail-stat-kanaele-mobile">
								{#if channelsLabel === '—'}
									—
								{:else}
									<span class="hub-mobile-stat-inline"><Dot tone="good" size={7}/>{channelsLabel}</span>
								{/if}
							</div>
						</Card>
					</div>
				{:else}
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
				{/if}

				<!-- 2×2 SummaryCard-Grid (Desktop) / Chevron-Summary-Stack (Mobil) —
				     Issue #1256 S8c (AC-3..AC-7, Soll Mobil:
				     screen-compare-detail-mobile.jsx:87-93,276-293). -->
				{#snippet summaryChevron()}
					<span class="hub-summary-row-chevron" aria-hidden="true">
						<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"/></svg>
					</span>
				{/snippet}
				{#if isMobileViewport}
					<div class="hub-summary-stack-mobile" data-testid="compare-detail-summary-mobile">
						<button type="button" class="hub-summary-row-mobile" data-testid="hub-summary-row-mobile" onclick={() => handleValueChange('orte')}>
							<span class="hub-summary-row-body">
								<span class="hub-summary-row-eyebrow">Orte</span>
								<span class="hub-summary-row-title">{resolvedLocations.length} Kandidaten</span>
								<span class="hub-summary-row-desc">{resolvedLocations.slice(0, 2).map(({loc}) => loc?.name ?? '—').join(' · ')}{resolvedLocations.length > 2 ? ` +${resolvedLocations.length - 2}` : ''}</span>
							</span>
							{@render summaryChevron()}
						</button>
						<button type="button" class="hub-summary-row-mobile" data-testid="hub-summary-row-mobile" onclick={() => handleValueChange('idealwerte')}>
							<span class="hub-summary-row-body">
								<span class="hub-summary-row-eyebrow">Wertebereiche</span>
								<span class="hub-summary-row-title">{profileLabel}</span>
								<span class="hub-summary-row-desc">{Object.keys(idealRanges ?? {}).length} Metriken · Markierung, kein Score</span>
							</span>
							{@render summaryChevron()}
						</button>
						<button type="button" class="hub-summary-row-mobile" data-testid="hub-summary-row-mobile" onclick={() => handleValueChange('layout')}>
							<span class="hub-summary-row-body">
								<span class="hub-summary-row-eyebrow">Layout</span>
								<span class="hub-summary-row-title">{layoutCardTitle}</span>
								<span class="hub-summary-row-desc">Übersicht pro Kanal</span>
							</span>
							{@render summaryChevron()}
						</button>
						<button type="button" class="hub-summary-row-mobile" data-testid="hub-summary-row-mobile" onclick={() => handleValueChange('versand')}>
							<span class="hub-summary-row-body">
								<span class="hub-summary-row-eyebrow">Versand</span>
								<span class="hub-summary-row-title">{status === 'draft' ? 'Nicht geplant' : presetBriefingTimesLabel(preset)}</span>
								<span class="hub-summary-row-desc">{status === 'draft' ? 'Aktivierung offen' : `Briefings ${presetBriefingTimesLabel(preset)}`}</span>
							</span>
							{@render summaryChevron()}
						</button>
					</div>
				{:else}
				<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px">
					<Card padding={20} style="display: flex; flex-direction: column">
						<div style="display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin-bottom: 4px">
							<Eyebrow>Orte</Eyebrow>
							<button onclick={() => handleValueChange('orte')} style="background: none; border: none; cursor: pointer; padding: 0; font-size: 12px; font-weight: 600; color: var(--g-accent-deep); font-family: var(--g-font-sans)">Bearbeiten →</button>
						</div>
						<div style="font-size: 16px; font-weight: 600; margin-bottom: 8px; letter-spacing: -0.01em">{preset.location_ids.length} Kandidaten</div>
						<!-- Issue #1256 S8c (AC-3): "+N weitere" bei >3 Orten (Soll: jsx:159). -->
						<div style="font-size: 13px; color: var(--g-ink-2); line-height: 1.6">{resolvedLocations.slice(0, 3).map(({loc}) => loc?.name ?? '—').join(' · ')}{resolvedLocations.length > 3 ? ` +${resolvedLocations.length - 3} weitere` : ''}</div>
					</Card>

					<Card padding={20} style="display: flex; flex-direction: column">
						<div style="display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin-bottom: 4px">
							<Eyebrow>Wertebereiche</Eyebrow>
							<button onclick={() => handleValueChange('idealwerte')} style="background: none; border: none; cursor: pointer; padding: 0; font-size: 12px; font-weight: 600; color: var(--g-accent-deep); font-family: var(--g-font-sans)">Bearbeiten →</button>
						</div>
						<!-- Issue #1256 S8c (AC-6): presetProfileLabel statt rohem preset.profil. -->
						<div style="font-size: 16px; font-weight: 600; margin-bottom: 8px; letter-spacing: -0.01em">{profileLabel}</div>
						<div style="font-size: 13px; color: var(--g-ink-2); line-height: 1.6">{Object.keys(idealRanges ?? {}).length} Metriken mit Idealbereich — im Briefing pro Wert markiert. Kein Score, kein Ranking.</div>
					</Card>

					<Card padding={20} style="display: flex; flex-direction: column">
						<div style="display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin-bottom: 4px">
							<Eyebrow>Layout pro Kanal</Eyebrow>
							<button onclick={() => handleValueChange('layout')} style="background: none; border: none; cursor: pointer; padding: 0; font-size: 12px; font-weight: 600; color: var(--g-accent-deep); font-family: var(--g-font-sans)">Bearbeiten →</button>
						</div>
						<!-- Issue #1256 S8c (AC-4): channelNamesLabel/"Keine Kanäle" statt harter Liste (Soll: jsx:169-171). -->
						<div style="font-size: 16px; font-weight: 600; margin-bottom: 8px; letter-spacing: -0.01em">{layoutCardTitle}</div>
						<div style="font-size: 13px; color: var(--g-ink-2); line-height: 1.6">Engere Kanäle zeigen automatisch weniger Spalten — Reihenfolge nach Priorität.</div>
					</Card>

					<Card padding={20} style="display: flex; flex-direction: column">
						<div style="display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin-bottom: 4px">
							<Eyebrow>Versand</Eyebrow>
							<button data-testid="compare-hub-versand-edit" onclick={() => handleValueChange('versand')} style="background: none; border: none; cursor: pointer; padding: 0; font-size: 12px; font-weight: 600; color: var(--g-accent-deep); font-family: var(--g-font-sans)">Bearbeiten →</button>
						</div>
						<!-- Issue #1256 S8c (AC-5): Draft-Sonderfall (Soll: jsx:175-177). -->
						<div style="font-size: 16px; font-weight: 600; margin-bottom: 8px; letter-spacing: -0.01em">{status === 'draft' ? 'Noch nicht geplant' : presetBriefingTimesLabel(preset)}</div>
						<div style="font-size: 13px; color: var(--g-ink-2); line-height: 1.6">{status === 'draft' ? 'Briefing-Uhrzeiten im Tab Versand festlegen.' : versandSummaryText}</div>
					</Card>
				</div>
				{/if}

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
			<!-- Issue #1256 S8c (AC-9): Section-Rahmen ueber SectionH-Atom + Card
			     um Liste UND Footer (Soll Desktop: jsx:197-216; Soll Mobil: CDM:110).
			     Fix-Loop 1 (F002): mobil ueber `eyebrow` statt `title` — kompakter
			     CDM_SectionH-Look (Soll: screen-compare-detail-mobile.jsx:267-274). -->
			{#if isMobileViewport}
				<SectionH eyebrow="Verglichene Orte">
					{#snippet right()}
						<span class="hub-section-hint">ziehen zum Sortieren</span>
					{/snippet}
				</SectionH>
			{:else}
				<SectionH title="Verglichene Orte">
					{#snippet right()}
						<span class="hub-section-hint">Reihenfolge = Spalten im Briefing · ziehen zum Sortieren</span>
					{/snippet}
				</SectionH>
			{/if}
			<Card padding={0} style="overflow: hidden">
				{#if resolvedLocations.length === 0}
					<p class="empty-state" style="padding: 0 16px">Noch keine Orte ausgewählt.</p>
				{:else}
					<SortableList
						items={currentLocationIds}
						onDndReorder={handleOrteDndReorder}
						ariaLabel="Verglichene Orte, Reihenfolge"
						itemLabel={orteItemLabel}
						flipDurationMs={150}
						zoneClass="hub-orte-list"
					>
						{#snippet row(id: string, i: number)}
							{@const loc = locationById.get(id)}
							{#if loc}
								<div class="hub-orte-row" class:alt={i % 2 === 1} data-testid="hub-orte-row" data-loc-id={id}>
									<DragHandle />
									<div class="hub-orte-row-body"><CompareLocationRow {loc} index={i + 1} /></div>
									<button
										type="button"
										class="hub-orte-remove-btn"
										data-testid="hub-orte-remove"
										title="Entfernen"
										onclick={() => removeLocation(id)}
									>✕</button>
								</div>
							{/if}
						{/snippet}
					</SortableList>
				{/if}
				<div style="padding: 14px">
					<Btn variant="ghost" size="sm" data-testid="hub-orte-add" onclick={toggleAddPanel}>Ort hinzufügen</Btn>
				</div>
			</Card>
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

	{#if activeTab === 'wetter-metriken'}
		<div class="tab-panel" data-testid="compare-detail-panel-wetter-metriken">
			{#if wetterMetrikenHydrated}
				<!-- Fix-Loop 1 (F003, Adversary HIGH): reines `onclick` am Wrapper
				     feuert VOR dem eigenen `onchange` der Checkbox (Klick-Reihenfolge:
				     click -> change) — der erste Toggle wurde dadurch nie persistiert
				     (Commit las den noch alten wizardState.activeMetricKeys). Muster
				     identisch `.hub-versand-wrap`/`.hub-alarme-wrap` (SF-1-Erkenntnis,
				     s. dortige Kommentare): `onchange` MUSS in der Bubble-Phase laufen,
				     dort ist die Checkbox-Mutation garantiert bereits abgeschlossen.
				     Kein <svelte:window onpointerup> noetig (Checkbox-Toggles ohne
				     Drag-Geste, Spec Abschnitt 2). -->
				<div
					class="hub-wetter-metriken-wrap"
					onchange={handleWetterMetrikenCommit}
					onfocusout={handleWetterMetrikenCommit}
					onclick={handleWetterMetrikenCommit}
				>
					<WeatherMetricsTab context="vergleich" wiz={wizardState} />
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
					<!-- Issue #1256 Scheibe 8 (AC-22): mobile Spiegelung der Idealwerte-
					     Inline-Edit-Paritaet, Muster TripTabs.svelte:198-202. -->
					{#if isMobileViewport}
						<CorridorEditorMobile context="vergleich" />
					{:else}
						<CorridorEditor context="vergleich" />
					{/if}
				</div>
			{/if}
		</div>
	{/if}

	{#if activeTab === 'layout'}
		<div class="tab-panel" data-testid="compare-detail-panel-layout">
			<!-- Issue #1256 S8c (AC-1/AC-2): Section-Rahmen + Limit-Pillen + Card
			     (Desktop) bzw. dense-Zeilen ohne Card (Mobil) — Soll Desktop:
			     screen-compare-detail.jsx:245-266; Soll Mobil:
			     screen-compare-detail-mobile.jsx:148-166. Fix-Loop 1 (F002): mobil
			     ueber `eyebrow` statt `title` — kompakter CDM_SectionH-Look
			     (Soll: screen-compare-detail-mobile.jsx:267-274). -->
			{#if isMobileViewport}
				<SectionH eyebrow="Spalten pro Kanal">
					{#snippet right()}
						<span class="hub-section-hint">Renderer kappt je Kanal</span>
					{/snippet}
				</SectionH>
				<div class="hub-layout-pills hub-layout-pills-mobile">
					{#each LAYOUT_LIMIT_PILLS_MOBILE as pill (pill)}
						<span class="hub-layout-pill hub-layout-pill-mobile">{pill}</span>
					{/each}
				</div>
				<div style="display: flex; flex-direction: column; gap: 10px">
					{#each channels as ch}
						<CompareLayoutRow channel={ch} cols={layoutChipNamesFor(ch)} dense />
					{/each}
				</div>
			{:else}
				<SectionH title="Übersicht pro Kanal">
					{#snippet right()}
						<span class="hub-section-hint">Metrik-Zeilen · Orte sind die Spalten — der Renderer kappt je Kanal</span>
					{/snippet}
				</SectionH>
				<div class="hub-layout-pills">
					{#each LAYOUT_LIMIT_PILLS as pill (pill)}
						<span class="hub-layout-pill">{pill}</span>
					{/each}
				</div>
				<Card padding={20} style="display: flex; flex-direction: column; gap: 16px">
					{#each channels as ch}
						<CompareLayoutRow channel={ch} cols={layoutChipNamesFor(ch)} />
					{/each}
				</Card>
			{/if}

			<!-- Issue #1299/#1291/#1287 (C2): Stundenverlauf-Steuerung — die einzige
			     Layout-Einstellung mit echter Mail-Wirkung, holt sie in den
			     erreichbaren Hub (bislang nur im weggeleiteten Legacy-Editor). Muster
			     identisch `.hub-wetter-metriken-wrap` (Bubble-Phase, SF-1-Erkenntnis)
			     — gemeinsam fuer Desktop/Mobil, ausserhalb der Viewport-Weiche. -->
			{#if layoutHydrated}
				<div
					class="hub-layout-hourly-wrap"
					onchange={handleLayoutCommit}
					onfocusout={handleLayoutCommit}
					onclick={handleLayoutCommit}
				>
					<SectionH title="Stundenverlauf" />
					<ChannelToggle
						label="Stundenverlauf"
						checked={wizardState.hourlyEnabled}
						onchange={(checked) => (wizardState.hourlyEnabled = checked)}
						testid="compare-layout-hourly-enabled-toggle"
					/>
					<div data-testid="compare-layout-hourly-metrics" style="display: flex; flex-direction: column; gap: 8px; margin-top: 10px">
						{#each ALL_HOURLY_METRICS as metric (metric.key)}
							<ChannelToggle
								label={metric.label}
								checked={isHourlyMetricActive(metric.key)}
								onchange={makeHourlyMetricHandler(metric.key)}
								testid={`compare-layout-hourly-metric-${metric.key}`}
							/>
						{/each}
					</div>
				</div>
			{/if}
		</div>
	{/if}

	{#if activeTab === 'alarme'}
		<div class="tab-panel" data-testid="compare-detail-panel-alarme">
			{#if alarmeHydrated}
				<!-- Muster identisch `.hub-versand-wrap` :987-994 (Bubble-Phase,
				     SF-1-Erkenntnis) — onchange/onfocusout/onclick am Wrapper. -->
				<div
					class="hub-alarme-wrap"
					onchange={handleAlarmeCommit}
					onfocusout={handleAlarmeCommit}
					onclick={handleAlarmeCommit}
				>
					<AlarmeTab
						context="vergleich"
						wiz={wizardState}
						{notifyCount}
						onJumpToWertebereiche={() => handleValueChange('idealwerte')}
					/>
				</div>
			{/if}
		</div>
	{/if}

	{#if activeTab === 'versand'}
		<div class="tab-panel" data-testid="compare-detail-panel-versand">
			{#if versandHydrated}
				<!-- Staging-Fund SF-1 (CRITICAL, AC-35): `onchange` MUSS in der Bubble-
				     Phase laufen, nicht `onchangecapture` — Capture liefe VOR dem
				     Checkbox-eigenen `onchange`, das `wiz.sendTelegram` (o.ä.) erst
				     setzt. Mit Capture sah `handleVersandCommit` daher noch den
				     ALTEN Wert, der Diff-Waechter erkannte keine Aenderung und der
				     PUT blieb aus, bis zufaellig ein anderes Event (focusout/click)
				     feuerte. In der Bubble-Phase ist die Ziel-Mutation garantiert
				     abgeschlossen, bevor der Wrapper-Handler laeuft. -->
				<div
					class="hub-versand-wrap"
					onchange={handleVersandCommit}
					onfocusout={handleVersandCommit}
					onclick={handleVersandCommit}
				>
					<VersandTab context="vergleich" wiz={wizardState} activation={hubActivationCard} />
				</div>
			{/if}
		</div>
	{/if}

	{#snippet hubActivationCard()}
		{@const banner = hubActivationBanner(status)}
		<Card padding={20} style="border-left: 3px solid {banner.border}" data-testid="compare-hub-activation-card">
			<div style="display: flex; align-items: center; gap: 9px; margin-bottom: 10px">
				<Dot tone={banner.dotTone} size={8} />
				<span style="font-size: 15px; font-weight: 600">{banner.statusLabel}</span>
			</div>
			<div style="font-size: 13px; color: var(--g-ink-2); line-height: 1.55; margin-bottom: 16px">{banner.text}</div>
			<Btn
				variant={status === 'active' ? 'ghost' : 'primary'}
				size="md"
				style="width: 100%; justify-content: center"
				data-testid="compare-hub-activation-cta"
				onclick={handleToggleActive}
			>
				{banner.cta}
			</Btn>
			<div style="margin-top: 10px">
				{#if sendQueued}
					<p class="send-success" data-testid="compare-send-success-versand">
						Briefing wurde zur Zustellung vorgemerkt.
					</p>
				{:else}
					<Btn
						variant="quiet"
						size="sm"
						style="width: 100%; justify-content: center"
						disabled={sendLoading}
						onclick={handleSend}
						data-testid="compare-hub-activation-testsend"
					>
						{sendLoading ? 'Wird gesendet…' : 'Test-Briefing jetzt senden'}
					</Btn>
				{/if}
				{#if sendError !== null}
					<p class="send-error">{sendError}</p>
				{/if}
			</div>
		</Card>
	{/snippet}

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
					onChange={(v: string) => (previewChannel = v as 'email' | 'sms' | 'telegram')}
					channels={previewConfiguredChannels}
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
				{#if !previewConfiguredChannels.includes(previewChannel)}
					<!-- AC-3 (Soll: screen-compare-detail.jsx:365-369): gewählter Kanal ist
					     im Preset nicht konfiguriert — Beispiel-Render bleibt sichtbar,
					     Hinweis läuft neben dem Umschalter statt die Render-Fläche zu leeren. -->
					<span class="mono" data-testid="compare-preview-channel-not-configured" style="font-size: 11px; color: var(--g-ink-4); letter-spacing: 0.04em">
						Kanal nicht konfiguriert · Beispiel-Render
					</span>
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
				{:else if previewChannel === 'email' && previewHtml !== ''}
					<div style="width: 680px; max-width: 100%;">
						<iframe
							data-testid="compare-preview-iframe"
							srcdoc={previewHtml}
							sandbox="allow-same-origin"
							title="E-Mail-Vorschau"
							style="width: 100%; min-height: 500px; border: 0; display: block"
						></iframe>
					</div>
				{:else if previewChannel === 'telegram' && previewTelegram !== ''}
					<!-- Issue #1270 (AC-2): echte Telegram-Vorschau statt Platzhalter-Copy.
					     Text kommt fertig aus dem Backend (ADR-0011), die Bubble ist reine Hülle. -->
					<div data-testid="compare-preview-telegram">
						<CompareChatBubble text={previewTelegram} />
					</div>
				{:else if previewChannel === 'sms' && previewSms !== ''}
					<!-- Issue #1270 (AC-2): echte SMS-Vorschau statt Platzhalter-Copy. -->
					<div data-testid="compare-preview-sms">
						<CompareSmsPreview text={previewSms} charCount={previewSmsCount} />
					</div>
				{:else}
					<!-- Ehrlicher Leerfall statt stiller Leere (KB-2/#1269): das Backend
					     lieferte für diesen Kanal keinen Inhalt. -->
					<p style="font-size: 0.875rem; color: var(--g-ink-3); margin: 0" data-testid="compare-preview-empty">
						Für diesen Kanal hat das Briefing keinen Inhalt geliefert.
					</p>
				{/if}
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

	.compare-tabs-content {
		padding: 28px 40px 80px;
	}

	@media (max-width: 899px) {
		/* Mobile: Tab-Leiste horizontal scrollbar. Fix-Loop 1 (Fresh-Eyes-Fund,
		   S8): Regel fehlte, "Versand"/"Vorschau" waren auf 390px unerreichbar.
		   Muster 1:1 TripTabs.svelte:330-352 (dort selbst ein Fresh-Eyes-Fund
		   #1231 S6) — Rand-Fade statt hartem Abschnitt. */
		.compare-tabs-bar {
			overflow-x: auto;
			white-space: nowrap;
			scrollbar-width: none;
			-ms-overflow-style: none;
			scroll-snap-type: x mandatory;
			scroll-padding-inline: 12px;
			mask-image: linear-gradient(to right, transparent, black 16px, black calc(100% - 16px), transparent);
			-webkit-mask-image: linear-gradient(to right, transparent, black 16px, black calc(100% - 16px), transparent);
		}
		.compare-tabs-bar::-webkit-scrollbar {
			display: none;
		}
		.compare-tabs-bar button {
			flex-shrink: 0;
			white-space: nowrap;
			scroll-snap-align: start;
		}

		/* Issue #1256 Scheibe 8 (AC-22): CompareTabs wird jetzt ueber die
		   Ein-Mount-Strategie auch mobil gerendert — schmaleres Padding statt
		   des Desktop-Werts (Ist-Befund Analyse). */
		.compare-tabs-content {
			padding: 16px 16px 60px;
		}
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

	@media (max-width: 899px) {
		.summary-grid {
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
	.hub-orte-row :global(.drag-handle) {
		padding-left: 16px;
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

	/* Issue #1256 Scheibe 8 (AC-22) — mobiler 4-Stat-2×2-Monitoring-Block */
	.hub-mobile-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 12px;
	}
	.hub-mobile-stat-label {
		font-size: 10px;
		color: var(--g-ink-4);
		letter-spacing: 0.16em;
		text-transform: uppercase;
		margin-bottom: 5px;
		font-family: var(--g-font-mono);
	}
	.hub-mobile-stat-value {
		font-size: 14px;
		color: var(--g-ink);
		font-weight: 500;
	}
	.hub-mobile-stat-inline {
		display: inline-flex;
		align-items: center;
		gap: 7px;
	}

	/* Issue #1256 S8c — Layout-/Orte-Tab Section-Hint (AC-1/AC-2/AC-9). */
	.hub-section-hint {
		font-family: var(--g-font-mono);
		font-size: 11px;
		color: var(--g-ink-3);
		letter-spacing: 0.03em;
	}

	/* Issue #1256 S8c (AC-1/AC-2) — Layout-Tab Limit-Pillen. */
	.hub-layout-pills {
		display: flex;
		gap: 8px;
		flex-wrap: wrap;
		margin-bottom: 18px;
	}
	.hub-layout-pill {
		font-family: var(--g-font-mono);
		font-size: 11px;
		padding: 5px 10px;
		border-radius: var(--g-r-pill);
		border: 1px solid var(--g-rule);
		background: var(--g-card-alt);
		color: var(--g-ink-2);
	}
	.hub-layout-pills-mobile {
		gap: 6px;
		margin-bottom: 14px;
	}
	.hub-layout-pill-mobile {
		font-size: 10.5px;
		padding: 4px 9px;
	}

	/* Issue #1256 S8c (AC-9) — Orte-Liste im Card-Rahmen: Trenner nur unter der Liste. */
	/* :global, weil `hub-orte-list` als zoneClass an SortableList durchgereicht
	   wird und dort den Scope-Hash dieser Komponente nicht traegt (#1272). */
	:global(.hub-orte-list) {
		border-bottom: 1px solid var(--g-rule-soft);
	}

	/* Issue #1256 S8c (AC-7) — mobiler Chevron-Summary-Stack (Soll:
	   screen-compare-detail-mobile.jsx:276-293). */
	.hub-summary-stack-mobile {
		background: var(--g-card);
		border: 1px solid var(--g-rule);
		border-radius: var(--g-r-3, 10px);
		overflow: hidden;
	}
	.hub-summary-row-mobile {
		display: flex;
		align-items: center;
		gap: 12px;
		width: 100%;
		text-align: left;
		padding: 13px 14px;
		background: transparent;
		border: none;
		border-top: 1px solid var(--g-rule-soft);
		cursor: pointer;
	}
	.hub-summary-stack-mobile .hub-summary-row-mobile:first-child {
		border-top: none;
	}
	.hub-summary-row-body {
		flex: 1;
		min-width: 0;
	}
	.hub-summary-row-eyebrow {
		display: block;
		font-family: var(--g-font-mono);
		font-size: 9px;
		color: var(--g-ink-4);
		letter-spacing: 0.12em;
		text-transform: uppercase;
		margin-bottom: 3px;
	}
	.hub-summary-row-title {
		display: block;
		font-size: 14.5px;
		font-weight: 600;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.hub-summary-row-desc {
		display: block;
		font-size: 12px;
		color: var(--g-ink-3);
		margin-top: 2px;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.hub-summary-row-chevron {
		flex-shrink: 0;
		color: var(--g-ink-4);
		display: flex;
	}
</style>
