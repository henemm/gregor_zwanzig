<script lang="ts">
	// CompareNewEditor — Progressive-Tab-Anlege-Editor für /compare/new.
	// Epic #1301 Scheibe F2a. Spec: docs/specs/modules/feat_1301_f2a_compare_new_trip_pattern.md
	//
	// Struktureller Spiegel von trip-new/TripNewEditor.svelte (#622): eigene
	// Anlege-Shell je Domäne (ADR-0029), zusammengesetzt aus den GETEILTEN
	// Organismen (Step2Orte, WeatherMetricsTab, CorridorEditor(Mobile),
	// AlarmeTab, VersandTab; Stundenverlauf jetzt via WeatherMetricsTab, #1360).
	// Reine Freischalt-Logik
	// im geteilten Kern shared/anlegeLockEngine.ts (#2277 S4). Lokaler Feldsatz `wiz` ($state, #2727), EIN POST bei
	// „Briefing aktivieren" über die lokale Funktion speichereNeuenVergleich() — kein Backend-Change.
	//
	// Der Alt-Editor CompareEditor.svelte wurde in Epic #1301 F2b ersatzlos
	// gelöscht (Rollback-Punkt entfallen, dieser Editor ist der einzige Anlege-Pfad).
	// Testid-Familien 1:1 erhalten (E2E-Verträge).
	// Safari-Factory-Pattern für alle Handler (CLAUDE.md).

	import { onMount, untrack } from 'svelte';
	import { goto } from '$app/navigation';
	import { Btn, Eyebrow, TopoBg } from '$lib/components/atoms';
	import { Field } from '$lib/components/molecules';
	import {
		ACTIVITY_PROFILE_OPTIONS,
		toCompareProfile,
		type ActivityProfile,
		type ComparePreset,
		type Location,
		type Group
	} from '$lib/types';
	import {
		buildNewComparePresetPayload,
		compareFeldsatzStandard,
		type CompareFeldsatz
	} from '../compare/compareEditorSave.ts';
	import { feldsatzAusVorlage } from './compareNewVorlage.ts';
	import {
		PROFILE_METRICS_WITH_SCALES,
		buildComparePrefillRows,
		buildCompareCorridorSavePayload,
		type CompareMetricDef,
		type ProfileKey
	} from '$lib/components/shared/corridor-editor/corridorEditorState';
	import { materializeActiveMetricKeys } from '$lib/components/shared/weather-metrics-tab/compareMetricOrder';
	import StandardwerteSpeichernKnopf from '$lib/components/shared/StandardwerteSpeichernKnopf.svelte';
	import type { SensLevel } from '$lib/types';
	import { api } from '$lib/api.js';
	// Issue #2659 (i18n F10): Texte aus dem Katalog; Reiter/Anlege-Kette und Sperr-Hinweise
	// werden je Sprache abgeleitet (`$locale`), nichts auf Skript-Ebene eingefroren.
	import { locale, t, tn, type MessageKey } from '$lib/i18n';
	import {
		tailUnlocked,
		tailDone,
		canFinish,
		canFinishMitStandardwerten,
		progressCount,
		type TailIds
	} from '$lib/components/shared/anlegeLockEngine';
	import Step2Orte from '$lib/components/compare/steps/Step2Orte.svelte';
	import { groupLocations } from '$lib/components/compare/locationHelpers';
	import WetterMetrikenVersandPanel from '$lib/components/shared/WetterMetrikenVersandPanel.svelte';
	import { anlegeKette } from '$lib/components/shared/subscriptionTabs';
	import CorridorEditor from '$lib/components/shared/corridor-editor/CorridorEditor.svelte';
	import CorridorEditorMobile from '$lib/components/shared/corridor-editor/CorridorEditorMobile.svelte';
	import AlarmeTab from '$lib/components/shared/AlarmeTab.svelte';
	// Issue #2276 S6c: EIN Buendel-Bauer fuer alle drei Vergleichs-Mounts.
	import { alarmePropsAus } from '../compare/alarmePropsAus.ts';
	import { corridorPropsAus } from '../compare/corridorPropsAus.ts';
	import { versandPropsAus } from '../compare/versandPropsAus.ts';
	import { wetterMetrikenPropsAus } from '../compare/wetterMetrikenPropsAus.ts';
	// #1435 E1a-2: der Alarme-Reiter leitet seine Zeilen aus dem Register-Katalog
	// ab — die Anlege-Seite muss ihn deshalb ebenfalls laden (geteilter
	// Promise-Cache, kein zweiter Netzwerk-Request) und durchreichen.
	import {
		loadCompareSelectionEntries,
		loadCompareMetricCatalog,
		loadMetricRegister,
		mitRegisterNamen
	} from '$lib/components/shared/corridor-editor/compareMetricCatalogLoader';
	import type { MetricLabelFields } from '$lib/i18n/metricLabel';
	import type { CompareSelectionEntry } from '$lib/components/shared/weather-metrics-tab/compareMetricSelection';
	import Toast from '$lib/components/mobile/Toast.svelte';
	import MBtn from '$lib/components/mobile/MBtn.svelte';
	import Sheet from '$lib/components/mobile/Sheet.svelte';
	import EditorStickyFooter from '$lib/components/shared/EditorStickyFooter.svelte';
	import AnlegeRahmen from '$lib/components/shared/anlege-rahmen/AnlegeRahmen.svelte';
	import { PageHeader } from '$lib/components/atoms';

	// Issue #1743: kein Schritt „Versand" mehr — der Versand-Abschnitt steht unten im
	// Schritt Wetter-Metriken (geteilter Baustein WetterMetrikenVersandPanel).
	type CompareNewTabId = 'vergleich' | 'orte' | 'wetter-metriken' | 'wertebereiche' | 'alarme';
	const TAIL: TailIds<CompareNewTabId> = {
		metriken: 'wetter-metriken', wertebereiche: 'wertebereiche', alarme: 'alarme'
	};

	// Test-Seam (#2277 S4, Muster TripNewEditor `stateOverride`): Startwerte fuer
	// Reiter/Viewport/Besuchs-Flags und (#2727) die Stammdaten-Startwerte.
	// Ohne Uebergabe unveraendertes Verhalten.
	interface CompareNewStateOverride {
		activeTab?: CompareNewTabId;
		isMobileViewport?: boolean;
		metrikenVisited?: boolean;
		idealsVisited?: boolean;
		alarmeVisited?: boolean;
		name?: string;
		region?: string;
		activityProfile?: ActivityProfile | null;
		pickedIds?: string[];
	}
	interface Props {
		locations?: Location[];
		groups?: Group[];
		stateOverride?: CompareNewStateOverride;
		// Issue #2277 S2c: /compare/new?from=<id> — Vorlage fuer die einmalige Vorbelegung.
		vorlage?: ComparePreset | null;
	}
	let { locations = [], groups, stateOverride, vorlage = null }: Props = $props();
	const seed: CompareNewStateOverride = untrack(() => stateOverride ?? {});

	// Issue #2727 (Epic #2345, DoD-1): der Editor haelt seinen Feldsatz selbst
	// (Muster TripNewEditor, kein Context). Startwerte: Standard < Vorlage
	// (einmalig beim Start, bewusst KEIN $effect, #2277 S2c AC-10) < stateOverride.
	const vorlagenFelder = untrack(() => (vorlage ? feldsatzAusVorlage(vorlage, locations) : {}));
	const wiz = $state<CompareFeldsatz>({
		...compareFeldsatzStandard(),
		...vorlagenFelder,
		...Object.fromEntries(
			Object.entries({
				name: seed.name,
				region: seed.region,
				activityProfile: seed.activityProfile,
				pickedIds: seed.pickedIds
			}).filter(([, wert]) => wert !== undefined)
		)
	});

	// #1435 E1a-2: Register-Katalog fuer die Empfindlichkeits-Tabelle des
	// Alarme-Reiters. Ohne ihn zeigte der Reiter hier null Zeilen.
	//
	// Fix-Loop 1 (Adversary F001): der Reiter wird — wie in CompareTabs.svelte
	// (:597-607, 1407) — erst hinter `{#if alarmeHydrated}` gemountet. Ohne
	// dieses Gatter rendert er waehrend des laufenden Fetches mit leerem
	// Katalog und behauptet faelschlich "keine Metriken" (AC-5, #1320).
	let alarmeCatalog = $state<CompareSelectionEntry[]>([]);
	let alarmeHydrated = $state(false);
	// Issue #2659 (i18n F10): englische Groessennamen aus dem Register (nicht blockierend).
	let alarmeRegister = $state<Record<string, MetricLabelFields>>({});
	const alarmeCatalogMitNamen = $derived(mitRegisterNamen(alarmeCatalog, alarmeRegister));
	async function hydrateAlarmeTab(): Promise<void> {
		void loadMetricRegister().then((r) => (alarmeRegister = r), () => {});
		// Fehlerfall gibt den Reiter ebenfalls frei (identisch CompareTabs:
		// `.catch(() => [])`) — sonst bliebe er nach einem misslungenen Laden
		// dauerhaft unerreichbar.
		alarmeCatalog = await loadCompareSelectionEntries().catch(() => []);
		alarmeHydrated = true;
	}
	onMount(() => {
		void hydrateAlarmeTab();
	});

	// #2521 S3: Vergleichs-Katalog (GET /api/compare/metrics, geteilter
	// Promise-Cache) ist Voraussetzung fuer „Mit Standardwerten speichern";
	// scheitert der Abruf, bleibt der Knopf gesperrt (null).
	let standardwerteKatalog = $state<CompareMetricDef[] | null>(null);
	async function ladeStandardwerteKatalog(): Promise<void> {
		standardwerteKatalog = await loadCompareMetricCatalog().catch(() => null);
	}
	onMount(() => {
		void ladeStandardwerteKatalog();
	});

	// ── Tab-Definitionen — Issue #1743: aus der EINEN Reiter-Definition
	// (`subscriptionTabs.anlegeKette`), keine Zweitliste. Fortschritt zaehlt
	// dieselben Schritte (5 Segmente).
	const TAB_DEFS: { id: CompareNewTabId; label: string; lockHint: string | null }[] = $derived(
		(void $locale, anlegeKette('vergleich')).map((r) => ({
			id: r.id as CompareNewTabId,
			label: r.label,
			lockHint: r.lockHint ?? null
		}))
	);
	const PROGRESS_STEPS: CompareNewTabId[] = $derived(TAB_DEFS.map((r) => r.id));

	// ── Visited-Flags (Tab-Besuch → nächster Tab frei; nie zurückgesetzt) ──────
	let metrikenVisited = $state(seed.metrikenVisited ?? false);
	let idealsVisited = $state(seed.idealsVisited ?? false);
	let alarmeVisited = $state(seed.alarmeVisited ?? false);

	let activeTab = $state<CompareNewTabId>(seed.activeTab ?? 'vergleich');

	// Echte Viewport-Erkennung (Muster #932/#1231 Slice 4): nur die
	// Wertebereiche-/Metriken-Zweige mounten viewport-exklusiv, damit nicht
	// Desktop- UND Mobile-Editor gleichzeitig in `wiz` schreiben.
	let isMobileViewport = $state(seed.isMobileViewport ?? false);
	onMount(() => {
		const mq = window.matchMedia('(max-width: 899px)');
		isMobileViewport = mq.matches;
		const onChange = (e: MediaQueryListEvent) => { isMobileViewport = e.matches; };
		mq.addEventListener('change', onChange);
		return () => mq.removeEventListener('change', onChange);
	});

	// ── Abgeleitete Freischaltung (geteilter Kern anlegeLockEngine, Vorderteil Name/≥2 Orte hier) ──────────────────────
	const nameOk = $derived(wiz.name.trim().length > 0);
	const orteOk = $derived(wiz.pickedIds.length >= 2);
	// Besuchs-Flags roh (fuer "erledigt") ...
	const tailP = $derived({
		metrikenFrei: nameOk && orteOk,
		metrikenVisited,
		wertebereicheVisited: idealsVisited,
		alarmeVisited
	});
	// ... und kumulativ (fuer "freigeschaltet"): Ortsvergleich-Semantik ist eine
	// konjunktive Kette (Wertebereiche braucht Metriken-Besuch, alarme zusaetzlich
	// Ideal-Besuch usw.), der Kern prueft je Stufe nur das direkte Vorgaenger-Flag.
	const tailPChain = $derived({
		...tailP,
		wertebereicheVisited: metrikenVisited && idealsVisited,
		alarmeVisited: metrikenVisited && idealsVisited && alarmeVisited
	});
	const unlocked = $derived.by(() => {
		const s = tailUnlocked(TAIL, tailPChain);
		s.add('vergleich');
		if (nameOk) s.add('orte');
		return s;
	});
	const done = $derived.by(() => {
		const s = tailDone(TAIL, tailP);
		if (nameOk) s.add('vergleich');
		if (orteOk) s.add('orte');
		return s;
	});
	// Zaehler gedeckelt bei der Schrittzahl (#1743: 5 Schritte).
	const doneCount = $derived(Math.min(progressCount(done, PROGRESS_STEPS), PROGRESS_STEPS.length));
	const canActivateNow = $derived(canFinish(done));
	const standardwerteFrei = $derived(canFinishMitStandardwerten({
		pflichtErfuellt: nameOk && orteOk,
		defaultsBereit: standardwerteKatalog !== null,
		bestandFrei: canActivateNow
	}));

	const canContinue = $derived(wiz.name.trim().length > 0);
	const orteContinueReady = $derived(wiz.pickedIds.length >= 2);

	// ── Gruppen (App-Group-Entity #301) — lazy beim ERSTEN Orte-Besuch ─────────
	let ceGroups = $state<Group[]>(groups ?? []);
	let ceGroupsLoadStarted = groups !== undefined;
	async function ceLoadGroups(): Promise<void> {
		try {
			ceGroups = await api.get<Group[]>('/api/groups');
		} catch {
			/* Gruppen optional — Bibliothek fällt auf „Weitere" zurück */
		}
	}
	$effect(() => {
		if (activeTab === 'orte' && !ceGroupsLoadStarted) {
			ceGroupsLoadStarted = true;
			void ceLoadGroups();
		}
	});

	const mobileLibraryGroups = $derived.by(() => {
		const { sections, ungrouped } = groupLocations(locations, ceGroups);
		const result: [string, Location[]][] = [];
		for (const s of sections) if (s.locations.length > 0) result.push([s.group.name, s.locations]);
		if (ungrouped.length > 0) result.push([$t('vergleich.orte.weitere'), ungrouped]);
		return result;
	});

	// ── Tab-Wechsel + visited-Kaskade ──────────────────────────────────────────
	function switchTab(id: CompareNewTabId) {
		if (!unlocked.has(id)) return;
		activeTab = id;
		if (id === 'wetter-metriken') metrikenVisited = true;
		if (id === 'wertebereiche') idealsVisited = true;
		if (id === 'alarme') alarmeVisited = true;
	}
	function makeTabHandler(id: CompareNewTabId) {
		return () => switchTab(id);
	}
	function makeContinueHandler(id: CompareNewTabId) {
		return () => switchTab(id);
	}
	function selectProfile(value: ActivityProfile) {
		wiz.activityProfile = value;
	}
	function profileMetricsLabel(value: ActivityProfile): string {
		void $locale; // #2657 (i18n F8): Profil-Metriknamen folgen dem Sprachwechsel ohne Neuladen
		const key = toCompareProfile(value) as ProfileKey;
		return PROFILE_METRICS_WITH_SCALES[key].map((m) => m.label).join(' · ');
	}

	// ── Speichern (Issue #681 Create-Modus, seit #2727 lokal im Editor) ────────
	// Legt das neue Preset via POST /api/compare/presets an und navigiert zum Hub.
	// Ein Fehlschlag bleibt still (Verhalten unveraendert, Nebenbefund #1199).
	async function speichereNeuenVergleich(): Promise<void> {
		const payload = buildNewComparePresetPayload({
			name: wiz.name,
			pickedIds: wiz.pickedIds,
			activityProfile: wiz.activityProfile,
			schedule: wiz.schedule,
			officialAlertsEnabled: wiz.officialAlertsEnabled, // Issue #1040
			radarAlertEnabled: wiz.radarAlertEnabled, // Issue #1041 Slice 2
			hourlyEnabled: wiz.hourlyEnabled, // Issue #1107
			outlookEnabled: wiz.outlookEnabled, // Issue #1361/#1368
			officialAlertTriggersEnabled: wiz.officialAlertTriggersEnabled, // Issue #1216 Slice 2b
			sendTelegram: wiz.sendTelegram,
			sendSms: wiz.sendSms,
			sendPremiumSms: wiz.sendPremiumSms, // Issue #1745 A (AC-11) / #2293 S2
			alertChannels: wiz.channels, // Issue #2293 Scheibe S2 (Abschnitt 1/7)
			officialWarningsEnabled: wiz.officialWarningsEnabled, // Issue #1258 S4
			morningEnabled: wiz.morningEnabled, // Issue #1232 Scheibe 2b
			morningTime: wiz.morningTime,
			eveningEnabled: wiz.eveningEnabled,
			eveningTime: wiz.eveningTime,
			endDate: wiz.endDate,
			// Issue #1361/#1372 S1b: Tagesfenster gehört von Anfang an zur Bedienfläche.
			dayWindowStartHour: wiz.dayWindowStartHour,
			dayWindowEndHour: wiz.dayWindowEndHour,
			alertCooldownMinutes: wiz.alertCooldownMinutes, // Issue #1170
			alertQuietFrom: wiz.alertQuietFrom,
			alertQuietTo: wiz.alertQuietTo,
			corridors: wiz.corridors, // Issue #1231 Slice 4
			region: wiz.region,
			idealRanges: wiz.idealRanges,
			activeMetricKeys: wiz.activeMetricKeys,
			// Issue #1703 Scheibe 8: Kanal-Overrides der Uebersichtstabelle — Kopie,
			// damit der gesendete Stand nicht spaeter noch mitmutiert.
			channelActiveMetricKeys: { ...wiz.channelActiveMetricKeys },
			hourlyMetricKeys: wiz.hourlyMetricKeys,
			outlookMetricKeys: wiz.outlookMetricKeys, // Issue #1361/#1368
			outlookMetricFormats: wiz.outlookMetricFormats, // Issue #2049
			metricAlertLevels: wiz.metricAlertLevels, // Issue #1170
			channelThresholds: wiz.channelThresholds, // Issue #1461 S3b-2b
			alertMetricChannels: wiz.alertMetricChannels, // Issue #1895 S3b1
			telegramStyle: wiz.telegramStyle // Issue #1260 S5
		});
		try {
			const created = await api.post<{ id: string }>('/api/compare/presets', payload);
			await goto('/compare/' + created.id);
		} catch {
			/* Nebenbefund #1199: Fehlermeldung wird (wie bisher) nicht angezeigt */
		}
	}

	// ── „Briefing aktivieren" — genau EIN POST, dann Redirect ──────────────────
	// Re-Entrancy-Guard nach Trip-Vorbild (TripNewEditor.buildAndSave:
	// `if (!ready || saving || savedTripId) return`) — ein Doppelklick auf
	// „Briefing aktivieren" darf NUR EIN Preset anlegen (Staging-Fund #1301 F2a:
	// 2× POST /api/compare/presets = Duplikat-Karteileiche). Während des Speicherns
	// sind beide Aktivieren-Knöpfe (Desktop + mobiler Sticky-Footer) disabled.
	let activating = $state(false);
	async function handleActivate() {
		if (!canActivateNow || activating) return;
		activating = true;
		try {
			await speichereNeuenVergleich();
		} finally {
			// Erfolg navigiert weg (Redirect nach dem POST); bei Fehler bleibt die
			// Seite und der Knopf wird für einen erneuten Versuch wieder freigegeben.
			activating = false;
		}
	}

	// ── „Mit Standardwerten speichern" (#2521 S3) ──────────────────────────────
	// Wertebereiche wie beim unveraenderten Reiter-Besuch vorbelegen (dieselbe
	// Kette und dasselbe Prefill-Profil wie CorridorEditor), ausser der Nutzer
	// hat den Reiter schon besucht — dann gelten dessen Werte. Danach derselbe
	// Speicherweg wie „Briefing aktivieren".
	function belegeWertebereicheVor(defs: CompareMetricDef[]) {
		const profileKey = wiz.activityProfile ? (toCompareProfile(wiz.activityProfile) as ProfileKey) : 'ALLGEMEIN';
		const levels = wiz.metricAlertLevels as Record<string, SensLevel | undefined> | undefined;
		const payload = buildCompareCorridorSavePayload(buildComparePrefillRows(profileKey, defs), [], {
			idealRanges: wiz.idealRanges ?? {},
			activeMetricKeys: materializeActiveMetricKeys(wiz.activeMetricKeys ?? null),
			metricAlertLevels: levels ?? {}
		}, []);
		wiz.corridors = payload.corridors;
		wiz.idealRanges = payload.idealRanges;
		wiz.activeMetricKeys = payload.activeMetricKeys;
		wiz.metricAlertLevels = payload.metricAlertLevels;
	}
	function makeStandardwerteHandler() {
		return async function doStandardwerte() {
			if (!standardwerteFrei || activating || !standardwerteKatalog) return;
			activating = true;
			try {
				if (!idealsVisited) belegeWertebereicheVor(standardwerteKatalog);
				await speichereNeuenVergleich();
			} finally {
				activating = false;
			}
		};
	}
	const onStandardwerte = makeStandardwerteHandler();

	// ── Mobile-only State ──────────────────────────────────────────────────────
	let mobileLibraryOpen = $state(false);
	// Issue #2659 (i18n F10): der Toast haelt die Reiter-Kennung; der Hinweis entsteht beim Rendern.
	let lockToastTab = $state<CompareNewTabId | null>(null);
	let lockToastVisible = $state(false);
	const lockToastMsg = $derived(
		lockToastTab ? (TAB_DEFS.find((r) => r.id === lockToastTab)?.lockHint ?? $t('vergleich.neu.tab_gesperrt')) : ''
	);
	let _lockToastTimer: ReturnType<typeof setTimeout> | null = null;
	function showLockToast(id: CompareNewTabId) {
		lockToastTab = id;
		lockToastVisible = true;
		if (_lockToastTimer) clearTimeout(_lockToastTimer);
		_lockToastTimer = setTimeout(() => { lockToastVisible = false; }, 2000);
	}
	function handleMobileTabClick(id: CompareNewTabId) {
		if (!unlocked.has(id)) {
			showLockToast(id);
			return;
		}
		switchTab(id);
	}
	function handleMobileNext() {
		const idx = TAB_DEFS.findIndex((t) => t.id === activeTab);
		if (activeTab === 'alarme') {
			handleActivate();
		} else if (idx >= 0 && idx < TAB_DEFS.length - 1) {
			switchTab(TAB_DEFS[idx + 1].id);
		}
	}

	// ── Mobile-Shell S2: Kopf im Inhalt statt globaler Kopfleiste ──────────────
	// <PageHeader back> traegt Ruecksprung + Eyebrow + Reiter-Titel; „Briefing
	// aktivieren" sitzt im geteilten Sticky-Footer (EditorStickyFooter).
	const mobileTitel = $derived(TAB_DEFS.find((r) => r.id === activeTab)?.label ?? $t('vergleich.anlegen.reiter'));
	const mobileEyebrow = $derived(wiz.name.trim() || $t('vergleich.neu.neuer_vergleich'));
</script>

<!-- Create-Aktivierungs-Banner als Snippet-Prop für VersandTab (1:1 Muster). -->
{#snippet versandActivationBanner()}
	<div
		data-testid="compare-step5-activation-banner"
		data-ready={canActivateNow ? 'true' : 'false'}
		class="rounded-md p-4 text-white text-sm"
		style:background={canActivateNow ? 'var(--g-good)' : 'var(--g-ink)'}
	>
		<div class="mono" style:font-size="11px" style:letter-spacing="0.12em" style:text-transform="uppercase" style:color="rgba(255,255,255,0.55)" style:margin-bottom="4px">{$t('vergleich.neu.bereit_titel')}</div>
		<div style:font-size="15px" style:font-weight="600">{$tn('vergleich.neu.bereit_zeile', wiz.pickedIds?.length ?? 0, { name: wiz.name || $t('vergleich.neu.neuer_vergleich') })}</div>
		<div style:font-size="12.5px" style:color="rgba(255,255,255,0.75)" style:margin-top="4px" style:line-height="1.5">
			{#if canActivateNow}{$t('vergleich.neu.bereit_text')}{:else}{$t('vergleich.neu.alarme_zum_aktivieren_punkt')}{/if}
		</div>
	</div>
{/snippet}

<div data-testid="compare-editor" style:position="relative" style:min-height="100%" style:background="var(--g-paper)">
<!-- ══════════════════ Desktop ══════════════════ -->
<div class="cm-desktop" style="position: relative; min-height: 100%; display: flex; flex-direction: column;">
	<!-- Geteilter Anlege-Rahmen (#2837 S2): Breadcrumb, Eyebrow, Titel, Fortschritt (5 Segmente),
	     Inhalt, Fuß cm-desktop-footer mit Abbrechen (Link /compare) und „Briefing aktivieren". -->
	<AnlegeRahmen
		context="vergleich"
		name={wiz.name}
		cancelHref="/compare"
		abschlussLabel={activating ? $t('trip.anlegen.speichere') : $t('vergleich.neu.aktivieren')}
		abschlussTestid="compare-editor-activate"
		canFinish={canActivateNow && !activating}
		onFinish={handleActivate}
		testidPrefix="cm"
		navClearance={false}
	>
		{#snippet fortschritt()}
			<div data-testid="compare-editor-progress" style:display="flex" style:align-items="center" style:gap="10px" style:margin-top="7px">
				<div style:display="flex" style:gap="3px">
					{#each TAB_DEFS as r (r.id)}
						<div data-testid="compare-editor-progress-segment" style:width="24px" style:height="3px" style:border-radius="2px" style:background={done.has(r.id) ? 'var(--g-accent)' : 'var(--g-rule)'} style:transition="background 350ms"></div>
					{/each}
				</div>
				<span class="mono" style:font-size="11px" style:color="var(--g-ink-4)" style:letter-spacing="0.04em">
					{doneCount === 0 ? $t('trip.anlegen.nichts_eingerichtet') : $t('trip.anlegen.abschnitte', { n: doneCount, gesamt: TAB_DEFS.length })}
				</span>
			</div>
		{/snippet}
		{#snippet hinweis()}
			{#if !canActivateNow}<span class="mono" style:font-size="11px" style:color="var(--g-ink-4)">{$t('vergleich.neu.alarme_zum_aktivieren')}</span>{/if}
		{/snippet}
		{#snippet standardwerte()}
			{#if !canActivateNow}<StandardwerteSpeichernKnopf enabled={standardwerteFrei} saving={activating} onclick={onStandardwerte} testid="compare-editor-standardwerte" />{/if}
		{/snippet}

		<!-- Tab-Bar -->
		<div style:border-bottom="1px solid var(--g-rule)" style:padding="0 40px" style:display="flex" style:gap="0" style:overflow-x="auto">
			{#each TAB_DEFS as r (r.id)}
				{@const on = r.id === activeTab}
				{@const open = unlocked.has(r.id)}
				{@const isDone = done.has(r.id) && !on}
				<button
					data-testid={`compare-editor-tab-${r.id}`}
					data-active={on ? 'true' : 'false'}
					data-locked={open ? 'false' : 'true'}
					data-done={done.has(r.id) ? 'true' : 'false'}
					type="button"
					onclick={makeTabHandler(r.id)}
					title={!open && r.lockHint ? $t('trip.anlegen.gesperrt', { hinweis: r.lockHint }) : undefined}
					style:padding="12px 16px" style:cursor={open ? 'pointer' : 'not-allowed'} style:background="none" style:border="none"
					style:border-bottom={on ? '2px solid var(--g-accent)' : '2px solid transparent'} style:margin-bottom="-1px"
					style:font-family="var(--g-font-sans)" style:font-size="13px" style:font-weight={on ? 600 : 500}
					style:color={on ? 'var(--g-ink)' : open ? 'var(--g-ink-3)' : 'var(--g-ink-4)'}
					style:display="flex" style:align-items="center" style:gap="5px" style:white-space="nowrap"
					style:opacity={open ? 1 : 0.34} style:transition="opacity 250ms, color 200ms" style:user-select="none"
				>
					{r.label}
					{#if isDone}
						<span class="mono" style:font-size="11px" style:font-weight="700" style:padding="2px 5px" style:border-radius="3px" style:background="rgba(61,107,58,0.12)" style:color="var(--g-good)">✓</span>
					{/if}
					{#if !open}
						<span class="mono" style:font-size="11px" style:color="var(--g-ink-4)" style:opacity="0.7">⊘</span>
					{/if}
				</button>
			{/each}
		</div>

	<!-- Tab-Panel -->
	{#if activeTab === 'vergleich'}
		<div style:position="relative" style:padding="28px 40px 60px">
			<TopoBg opacity={0.1}>
				<div style:position="relative" style:max-width="640px">
					<Eyebrow style="margin-bottom: 14px">{$t('vergleich.neu.eckdaten')}</Eyebrow>
					<Field label={$t('vergleich.neu.name')} hint={$t('vergleich.neu.name_hinweis')}>
						<input data-testid="compare-editor-name" type="text" maxlength="80" placeholder={$t('vergleich.neu.name_beispiel')} bind:value={wiz.name} class="w-full border rounded px-3 py-2 text-base bg-[var(--g-card)] border-[var(--g-rule)]" />
					</Field>
					<Field label={$t('trip.anlegen.region')} side={$t('vergleich.neu.optional_max')}>
						<input data-testid="compare-editor-region" type="text" maxlength="60" placeholder={$t('vergleich.neu.region_beispiel')} bind:value={wiz.region} class="w-full border rounded px-3 py-2 text-base bg-[var(--g-card)] border-[var(--g-rule)]" />
					</Field>
					<Eyebrow style="margin-bottom: 12px; margin-top: 28px">{$t('vergleich.neu.aktivitaetsprofil')}</Eyebrow>
					<div style:font-size="13px" style:color="var(--g-ink-3)" style:margin-bottom="14px">
						{$t('vergleich.neu.profil_hinweis')}
					</div>
					<div style:display="grid" style:grid-template-columns="1fr 1fr" style:gap="10px">
						{#each ACTIVITY_PROFILE_OPTIONS as opt (opt.value)}
							{@const sel = wiz.activityProfile === opt.value}
							<button data-testid={`compare-editor-profile-${opt.value}`} data-selected={sel ? 'true' : 'false'} type="button" onclick={() => selectProfile(opt.value)}
								style:text-align="left" style:cursor="pointer" style:padding="14px 16px"
								style:background={sel ? 'var(--g-accent-tint)' : 'var(--g-card)'}
								style:border={sel ? '1.5px solid var(--g-accent)' : '1px solid var(--g-rule)'}
								style:border-radius="var(--g-r-3)" style:font-family="var(--g-font-sans)">
								<div style:font-size="14px" style:font-weight="600" style:color={sel ? 'var(--g-accent-deep)' : 'var(--g-ink)'} style:margin-bottom="4px">{$t(`bausteine.profil.${opt.value}` as MessageKey)}</div>
								<div class="mono" style:font-size="11px" style:color="var(--g-ink-3)" style:margin-top="4px">{profileMetricsLabel(opt.value)}</div>
							</button>
						{/each}
					</div>
					<div style:margin-top="28px" style:padding-top="20px" style:border-top="1px solid var(--g-rule)" style:display="flex" style:justify-content="flex-end" style:align-items="center" style:gap="12px">
						{#if !canContinue}<span class="mono" style:font-size="11px" style:color="var(--g-ink-4)">{$t('vergleich.neu.name_fehlt')}</span>{/if}
						<Btn data-testid="compare-editor-continue-orte" variant="accent" size="md" disabled={!canContinue} onclick={() => canContinue && switchTab('orte')}>{$t('vergleich.neu.orte_hinzufuegen')}</Btn>
					</div>
				</div>
			</TopoBg>
		</div>
	{:else if activeTab === 'orte'}
		<Step2Orte bind:pickedIds={wiz.pickedIds} {locations} groups={ceGroups} />
		<div class="ce-cta-foot" style:max-width="980px">
			<div class="ce-cta-row">
				{#if !orteContinueReady}<span class="mono ce-cta-hint">{$t('vergleich.neu.min_orte')}</span>{/if}
				<Btn data-testid="compare-editor-continue-wetter-metriken" variant="accent" size="md" disabled={!orteContinueReady} onclick={() => orteContinueReady && switchTab('wetter-metriken')}>{$t('vergleich.neu.wetter_metriken')}</Btn>
			</div>
		</div>
	{:else if activeTab === 'wetter-metriken'}
		{#if !isMobileViewport}
			<!-- Issue #1743: geteilter Baustein „Wetter-Metriken + Versand"; ohne
			     preset/saveController/enqueueHubWrite — gespeichert wird erst per
			     „Briefing aktivieren" (ein POST). -->
			<WetterMetrikenVersandPanel context="vergleich" {...wetterMetrikenPropsAus(wiz)} versand={versandPropsAus(wiz)} vergleichTelegramStyle={wiz.telegramStyle ?? 'rich'} activation={versandActivationBanner} showInfobox={true} />
		{/if}
		<div class="ce-cta-foot" style:max-width="1040px">
			<div class="ce-cta-row">
				<Btn data-testid="compare-editor-continue-wertebereiche" variant="accent" size="md" onclick={makeContinueHandler('wertebereiche')}>{$t('trip.anlegen.wertebereiche_festlegen')}</Btn>
			</div>
		</div>
	{:else if activeTab === 'wertebereiche'}
		{#if !isMobileViewport}
			<CorridorEditor context="vergleich" {...corridorPropsAus(wiz)} showInfobox={true} />
		{/if}
		<div class="ce-cta-foot" style:max-width="1100px">
			<div class="ce-cta-row">
				<Btn data-testid="compare-editor-continue-alarme" variant="accent" size="md" onclick={makeContinueHandler('alarme')}>{$t('trip.anlegen.alarme_einrichten')}</Btn>
			</div>
		</div>
	{:else if activeTab === 'alarme'}
		{#if alarmeHydrated}
			<AlarmeTab context="vergleich" {...alarmePropsAus(wiz)} catalog={alarmeCatalogMitNamen} showInfobox={true} />
		{/if}
	{/if}
	</AnlegeRahmen>
</div><!-- /.cm-desktop -->

<!-- ══════════════════ Mobile ══════════════════ -->
<div class="cm-mobile" style="position: relative; min-height: 100vh; display: flex; flex-direction: column;">
	{#if lockToastVisible}
		<Toast kind="info" msg={lockToastMsg} />
	{/if}

	<div data-testid="cm-mobile-head" style="padding: 0 16px; flex-shrink: 0;">
		<PageHeader back={{ href: '/compare', label: $t('listen.vergleiche.titel') }} eyebrow={mobileEyebrow} title={mobileTitel} compact />
	</div>

	<!-- Fortschrittsbalken -->
	<div class="cm-mobile-flex" data-testid="cm-mobile-progress" style="align-items: center; gap: 8px; padding: 8px 16px 0; flex-shrink: 0;">
		<div style="display: flex; gap: 3px; flex: 1;">
			{#each TAB_DEFS as r (r.id)}
				<div style="flex: 1; height: 3px; border-radius: 2px; background: {done.has(r.id) ? 'var(--g-accent)' : (r.id === activeTab ? 'var(--g-accent-soft,#bcd)' : 'var(--g-rule)')}; transition: background 350ms;"></div>
			{/each}
		</div>
		<span class="mono" style="font-size: 11px; color: var(--g-ink-4); flex-shrink: 0;">{doneCount}/{TAB_DEFS.length}</span>
	</div>

	<!-- Scrollbare Tab-Bar -->
	<div class="cm-mobile-flex" data-testid="cm-mobile-tabbar" style="gap: 0; overflow-x: auto; border-bottom: 1px solid var(--g-rule-soft); -webkit-overflow-scrolling: touch; scrollbar-width: none; flex-shrink: 0; mask-image: linear-gradient(to right, transparent, black 16px, black calc(100% - 16px), transparent); -webkit-mask-image: linear-gradient(to right, transparent, black 16px, black calc(100% - 16px), transparent);">
		{#each TAB_DEFS as r (r.id)}
			{@const on = r.id === activeTab}
			{@const open = unlocked.has(r.id)}
			<button type="button" data-testid="cm-mobile-tab-{r.id}" data-active={on ? 'true' : 'false'} data-locked={open ? 'false' : 'true'} onclick={() => handleMobileTabClick(r.id)}
				style="display: inline-flex; align-items: center; gap: 5px; padding: 13px 13px; min-height: 44px; flex-shrink: 0; background: transparent; border: none; border-bottom: {on ? '2px solid var(--g-accent)' : '2px solid transparent'}; margin-bottom: -1px; cursor: {open ? 'pointer' : 'default'}; font-size: 14px; font-weight: {on ? 600 : 500}; color: {on ? 'var(--g-ink)' : open ? 'var(--g-ink-3)' : 'var(--g-ink-4)'}; white-space: nowrap; font-family: var(--g-font-sans); opacity: {open ? 1 : 0.35};">
				{r.label}
				{#if !open}<span class="mono" style="font-size: 11px; opacity: 0.8;">⊘</span>{/if}
			</button>
		{/each}
	</div>

	<!-- Tab-Inhalt -->
	<div style="flex: 1; overflow-y: auto; padding: 16px;">
		{#if activeTab === 'vergleich'}
			<div style="margin-bottom: 14px;">
				<div class="mono" style="font-size: 11px; color: var(--g-ink-4); letter-spacing: 0.10em; text-transform: uppercase; margin-bottom: 8px;">{$t('vergleich.neu.name')}</div>
				<input data-testid="compare-editor-name-mobile" type="text" maxlength="80" placeholder={$t('vergleich.neu.name_beispiel')} bind:value={wiz.name}
					style="width: 100%; box-sizing: border-box; padding: 12px 14px; font-size: 16px; border: 1px solid var(--g-rule); border-radius: var(--g-r-3); background: var(--g-card); font-family: var(--g-font-sans); color: var(--g-ink); outline: none; min-height: 48px;" />
			</div>
			<div style="margin-bottom: 14px;">
				<div class="mono" style="font-size: 11px; color: var(--g-ink-4); letter-spacing: 0.10em; text-transform: uppercase; margin-bottom: 8px;">{$t('trip.anlegen.region')} <span style="font-weight:400; text-transform:none;">({$t('trip.anlegen.optional')})</span></div>
				<input type="text" maxlength="60" placeholder={$t('vergleich.neu.region_beispiel')} bind:value={wiz.region}
					style="width: 100%; box-sizing: border-box; padding: 12px 14px; font-size: 16px; border: 1px solid var(--g-rule); border-radius: var(--g-r-3); background: var(--g-card); font-family: var(--g-font-sans); color: var(--g-ink); outline: none; min-height: 48px;" />
			</div>
			<div>
				<div class="mono" style="font-size: 11px; color: var(--g-ink-4); letter-spacing: 0.10em; text-transform: uppercase; margin-bottom: 10px;">{$t('vergleich.neu.aktivitaetsprofil')}</div>
				<div style="display: flex; flex-direction: column; gap: 8px;">
					{#each ACTIVITY_PROFILE_OPTIONS as opt (opt.value)}
						{@const sel = wiz.activityProfile === opt.value}
						{@const metricsList = profileMetricsLabel(opt.value).split(' · ')}
						<button type="button" data-testid={`compare-editor-profile-mobile-${opt.value}`} onclick={() => selectProfile(opt.value)}
							style="display: flex; align-items: center; gap: 12px; min-height: 52px; padding: 12px 14px; background: {sel ? 'var(--g-accent-tint)' : 'var(--g-card)'}; border: {sel ? '1.5px solid var(--g-accent)' : '1px solid var(--g-rule)'}; border-radius: var(--g-r-3); cursor: pointer; text-align: left; font-family: var(--g-font-sans);">
							<div style="flex: 1; min-width: 0; display: flex; flex-direction: column;">
								<div style="font-size: 14px; font-weight: 600; color: {sel ? 'var(--g-accent-deep)' : 'var(--g-ink)'};">{$t(`bausteine.profil.${opt.value}` as MessageKey)}</div>
								<div class="mono" style="font-size: 11px; color: var(--g-ink-3); margin-top: 4px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{metricsList.slice(0, 4).join(' · ')}{metricsList.length > 4 ? ' …' : ''}</div>
							</div>
							{#if sel}
								<span style="width: 20px; height: 20px; border-radius: 50%; background: var(--g-accent); display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
									<svg width="11" height="11" viewBox="0 0 12 12" fill="none" stroke="#fff" stroke-width="2.5"><path d="M2 6l3 3 5-6"/></svg>
								</span>
							{/if}
						</button>
					{/each}
				</div>
			</div>
		{:else if activeTab === 'orte'}
			<Step2Orte bind:pickedIds={wiz.pickedIds} {locations} groups={ceGroups} dense onOpenLibrary={() => { mobileLibraryOpen = true; }} />
		{:else if activeTab === 'wetter-metriken'}
			{#if isMobileViewport}
				<WetterMetrikenVersandPanel context="vergleich" {...wetterMetrikenPropsAus(wiz)} versand={versandPropsAus(wiz)} vergleichTelegramStyle={wiz.telegramStyle ?? 'rich'} activation={versandActivationBanner} showInfobox={true} />
			{/if}
		{:else if activeTab === 'wertebereiche'}
			{#if isMobileViewport}
				<CorridorEditorMobile context="vergleich" {...corridorPropsAus(wiz)} showInfobox={true} />
			{/if}
		{:else if activeTab === 'alarme'}
			{#if alarmeHydrated}
				<AlarmeTab context="vergleich" {...alarmePropsAus(wiz)} catalog={alarmeCatalogMitNamen} showInfobox={true} />
			{/if}
		{/if}
	</div>

	<!-- Sticky-Footer (geteilter Baustein): Weiter-Aktion des Reiters, im letzten
	     Schritt Alarme „Briefing aktivieren" (#1743; Mobile-Shell S2). -->
	<EditorStickyFooter context="vergleich" testid="cm-mobile-cta" navClearance={false}>
			{#if !canActivateNow}
				<div style="display: flex; justify-content: center; margin-bottom: 8px;">
					<StandardwerteSpeichernKnopf enabled={standardwerteFrei} saving={activating} onclick={onStandardwerte} testid="cm-mobile-standardwerte" />
				</div>
			{/if}
			{#if activeTab === 'alarme'}
				<MBtn block variant={canActivateNow ? 'primary' : 'quiet'} size="xl" disabled={!canActivateNow || activating} onclick={handleActivate} testid="cm-mobile-activate">{activating ? $t('trip.anlegen.speichere') : canActivateNow ? $t('vergleich.neu.aktivieren') : $t('vergleich.neu.alarme_zum_aktivieren')}</MBtn>
			{:else if activeTab === 'vergleich'}
				<MBtn block variant={canContinue ? 'accent' : 'quiet'} size="xl" disabled={!canContinue} onclick={handleMobileNext}>{canContinue ? $t('vergleich.neu.orte_hinzufuegen') : $t('vergleich.neu.name_eingeben')}</MBtn>
			{:else if activeTab === 'orte'}
				{@const restOrte = 2 - wiz.pickedIds.length}
				<MBtn block variant={orteContinueReady ? 'accent' : 'quiet'} size="xl" disabled={!orteContinueReady} onclick={handleMobileNext}>{orteContinueReady ? $t('vergleich.neu.wetter_metriken') : $tn('vergleich.neu.noch_orte', restOrte)}</MBtn>
			{:else if activeTab === 'wetter-metriken'}
				<MBtn block variant="accent" size="xl" onclick={handleMobileNext}>{$t('trip.anlegen.wertebereiche_festlegen')}</MBtn>
			{:else if activeTab === 'wertebereiche'}
				<MBtn block variant="accent" size="xl" onclick={handleMobileNext}>{$t('trip.anlegen.alarme_einrichten')}</MBtn>
			{/if}
	</EditorStickyFooter>
</div><!-- /.cm-mobile -->

<!-- Mobile Bibliotheks-Sheet (Orte-Tab) -->
<Sheet open={mobileLibraryOpen} snap="full" title={$t('vergleich.neu.ort_waehlen')} onClose={() => { mobileLibraryOpen = false; }}>
	{#each mobileLibraryGroups as [groupName, groupLocs] (groupName)}
		<div style="margin-bottom: 8px;">
			<div class="mono" style="font-size: 11px; color: var(--g-ink-4); letter-spacing: 0.10em; text-transform: uppercase; padding: 8px 0 4px; font-weight: 600;">{groupName} · {groupLocs.length}</div>
			{#each groupLocs as loc (loc.id)}
				{@const on = wiz.pickedIds.includes(loc.id)}
				<button type="button" data-testid="compare-step2-mobile-lib-check-{loc.id}"
					onclick={() => { if (on) { wiz.pickedIds = wiz.pickedIds.filter((x) => x !== loc.id); } else { wiz.pickedIds = [...wiz.pickedIds, loc.id]; } }}
					style="display: flex; align-items: center; gap: 14px; width: 100%; padding: 12px 0; min-height: 52px; background: {on ? 'var(--g-accent-tint)' : 'transparent'}; border: none; border-bottom: 1px solid var(--g-rule-soft); cursor: pointer; text-align: left; font-family: var(--g-font-sans);">
					<span style="width: 22px; height: 22px; border-radius: 4px; border: 1.5px solid {on ? 'var(--g-accent)' : 'var(--g-rule)'}; background: {on ? 'var(--g-accent)' : 'transparent'}; display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
						{#if on}<svg width="11" height="11" viewBox="0 0 12 12" fill="none" stroke="#fff" stroke-width="2.5"><path d="M2 6l3 3 5-6"/></svg>{/if}
					</span>
					<div style="flex: 1; min-width: 0;">
						<div style="font-size: 14px; font-weight: {on ? 600 : 500}; color: {on ? 'var(--g-accent-deep)' : 'var(--g-ink)'}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{loc.name}</div>
						{#if loc.region}<div class="mono" style="font-size: 11px; color: var(--g-ink-3); margin-top: 1px;">{loc.region}</div>{/if}
					</div>
				</button>
			{/each}
		</div>
	{/each}
</Sheet>
</div>

<style>
	/* CSS-only Responsive Switch, Trip-Muster #661 (Epic #1301 F3, #989).
	   Desktop-Block wird auf ≤899px per display:none versteckt (nicht mehr
	   per Offscreen-Koordinaten) — dank eigenständigem Mobile-Namensfeld
	   (compare-editor-name-mobile) entfällt die frühere Test-Krücke. */
	.cm-mobile {
		display: none !important;
	}
	@media (max-width: 899px) {
		.cm-desktop {
			display: none !important;
		}
		.cm-mobile {
			display: block !important;
		}
		.cm-mobile-flex {
			display: flex !important;
		}
	}

	.ce-cta-foot {
		padding: 0 40px 48px;
	}
	.ce-cta-row {
		padding-top: 20px;
		border-top: 1px solid var(--g-rule);
		display: flex;
		justify-content: flex-end;
		align-items: center;
		gap: 12px;
	}
	.ce-cta-hint {
		font-size: 11px;
		color: var(--g-ink-4);
	}
</style>
