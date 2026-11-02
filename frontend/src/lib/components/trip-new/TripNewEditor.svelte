<script lang="ts">
	// Issue #622 — Progressive Tab Editor für /trips/new (Desktop, Slice 1).
	// Issue #661 — Mobile-Parität (AC-9): paralleles Mobile-Markup per CSS.
	// Spec: docs/specs/modules/issue_622_trip_new_progressive_editor.md
	// Spec: docs/specs/modules/issue_661_trip_new_mobile.md
	// Design: docs/design-requests/trip-anlegen-2026-06-06/screen-trip-new-v2.jsx
	// Design: docs/design-requests/trip-anlegen-2026-06-06/screen-trip-new-v2-mobile.jsx
	// Factory-Pattern für alle Event-Handler (Safari-Closure-Schutz, CLAUDE.md).

	import { onMount, untrack } from 'svelte';
	import { goto, beforeNavigate } from '$app/navigation';
	import { api } from '$lib/api.js';
	import { Eyebrow, Btn, Input, TopoBg, PageHeader } from '$lib/components/atoms';
	import EditorStickyFooter from '$lib/components/shared/EditorStickyFooter.svelte';
	import WetterMetrikenVersandPanel from '$lib/components/shared/WetterMetrikenVersandPanel.svelte';
	import { anlegeKette } from '$lib/components/shared/subscriptionTabs';
	import MailInhaltCard from '$lib/components/shared/MailInhaltCard.svelte';
	import EditStagesPanelNew from '$lib/components/edit/EditStagesPanelNew.svelte';
	import AlarmeTab from '$lib/components/shared/AlarmeTab.svelte';
	import CorridorEditor from '$lib/components/shared/corridor-editor/CorridorEditor.svelte';
	import Infobox from '$lib/components/molecules/Infobox.svelte';
	import type { ChannelKind, ChannelThreshold } from '$lib/components/shared/alarme-tab/alertChannelState';
	import { deriveActiveAlertMetricsForTrip } from '$lib/components/shared/alarme-tab/tripAlertMetricsFromCatalog';
	import type { MetricCatalog } from '$lib/components/trip-detail/metricsEditor';
	import Sheet from '$lib/components/mobile/Sheet.svelte';
	import MBtn from '$lib/components/mobile/MBtn.svelte';
	import MInput from '$lib/components/mobile/MInput.svelte';
	import MField from '$lib/components/mobile/MField.svelte';
	import Toast from '$lib/components/mobile/Toast.svelte';
	import Select from '$lib/components/ui/select/Select.svelte';
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import type { Trip, ReportConfig, WeatherConfigMetric, Stage, Waypoint, ActivityType, AlertMetric, SensLevel, Corridor } from '$lib/types';
	import {
		type TabId,
		type CreateTripState,
		type CreateTripAlarmState,
		initialCreateTripAlarmState,
		applyAlarmChannelToggle,
		applyAlarmThresholdChange,
		applyAlarmMetricLevelChange,
		unlockedTabs,
		doneTabs,
		stageDate,
		progressCount,
		PROGRESS_STEPS,
		canSave,
		buildCreateTripPayload,
		ergaenzeStandardwerteReportConfig,
		ergaenzeVersandStandard,
	} from './tripNewLogic.ts';
	import { canFinishMitStandardwerten } from '$lib/components/shared/anlegeLockEngine';
	import StandardwerteSpeichernKnopf from '$lib/components/shared/StandardwerteSpeichernKnopf.svelte';
	import { t, tn, locale, type MessageKey } from '$lib/i18n';

	// i18n F9: Aktivitaetsliste des Anlegens (Kennungen unveraendert, Namen je Sprache).
	const AKTIVITAETEN: { value: string; key: MessageKey }[] = [
		{ value: '', key: 'trip.aktivitaet.standard' },
		{ value: 'trekking', key: 'trip.aktivitaet.alpen_trekking' },
		{ value: 'hiking', key: 'trip.aktivitaet.wandern' },
		{ value: 'ski_touring', key: 'trip.aktivitaet.skitouren' },
		{ value: 'hochtour', key: 'trip.aktivitaet.hochtour' },
		{ value: 'klettersteig', key: 'trip.aktivitaet.klettersteig' },
		{ value: 'mtb', key: 'trip.aktivitaet.mtb' },
		{ value: 'fahrrad_15', key: 'trip.aktivitaet.fahrrad_15' },
		{ value: 'fahrrad_20', key: 'trip.aktivitaet.fahrrad_20' },
		{ value: 'fahrrad_25', key: 'trip.aktivitaet.fahrrad_25' }
	];

	// ── Test-Seam (Issue #1738, Muster `profileOverride` aus #1510) ──────────
	// Der gesamte Anlege-Zustand lebt in internem `$state`; `isMobileViewport`
	// entsteht sogar erst in `onMount`, das `svelte/server` nie ausfuehrt. Ohne
	// Vorbelegung ist der Zeitplan-Tab serverseitig gar nicht erreichbar und die
	// Ein-Instanz-Zusicherung (AC-5) nicht messbar. OHNE Uebergabe ist das
	// Verhalten unveraendert — insbesondere kommt `isMobileViewport` dann
	// weiterhin aus `matchMedia`.
	interface TripNewStateOverride {
		activeTab?: TabId;
		isMobileViewport?: boolean;
		channels?: { email: boolean; telegram: boolean; sms: boolean };
		reportConfig?: ReportConfig;
		name?: string;
		startDate?: string;
		stageNames?: string[];
		// #2277 S4: Besuchs-Flags vorbelegen (Wirkstelle der Reiterleiste testbar).
		wtVisited?: boolean;
		wbVisited?: boolean;
		alVisited?: boolean;
	}
	let { stateOverride }: { stateOverride?: TripNewStateOverride } = $props();
	// Einmal-Lesung beim Erzeugen (untrack, wie `profileOverride` in
	// VTBriefingChannels.svelte) — die Vorbelegung ist ein Startwert, kein
	// reaktiver Bezug.
	const seed: TripNewStateOverride = untrack(() => stateOverride ?? {});

	// ── Tab-Definitionen — Issue #1743: aus der EINEN Reiter-Definition
	// (`subscriptionTabs.anlegeKette`), keine Zweitliste. Versand ist kein Schritt
	// mehr, sondern der Abschnitt unten im Schritt Wetter-Metriken.
	// i18n F9: Namen/Sperr-Hinweise entstehen in anlegeKette per tr() — `$locale` haelt sie reaktiv.
	const TAB_DEFS = $derived.by(() => (void $locale, anlegeKette('trip').map((r) => ({
		id: r.id as TabId,
		label: r.label,
		lockHint: r.lockHint ?? null,
		optional: r.optional ?? false,
	}))));

	// ── Lokaler Anlege-State ──────────────────────────────────────────────────
	let name = $state(seed.name ?? '');
	let region = $state('');
	let startDate = $state(seed.startDate ?? '');

	interface StageLocal { id: number; name: string; gpx: { file: string; km: number; asc: number } | null; waypoints: Waypoint[] }
	let stages = $state<StageLocal[]>(
		seed.stageNames
			? seed.stageNames.map((n, i) => ({ id: i + 1, name: n, gpx: null, waypoints: [] }))
			: [
					{ id: 1, name: '', gpx: null, waypoints: [] },
					{ id: 2, name: '', gpx: null, waypoints: [] },
				]
	);
	// Bug #708 — Etappen-Löschen mit Bestätigungs-Dialog
	let pendingRemoveStageId = $state<number | null>(null);

	let weatherMetrics = $state<WeatherConfigMetric[]>([]);
	let channels = $state(seed.channels ?? { email: true, telegram: true, sms: false });
	let reportConfig = $state<ReportConfig | undefined>(seed.reportConfig);
	// Issue #2277 S1 — Alarm-Schatten-State fuer den geteilten AlarmeTab (createMode).
	// Fliesst bewusst NICHT in stubTrip ein (neue trip-Referenz je Klick = Effekt-Schleife).
	let alarm = $state<CreateTripAlarmState>(initialCreateTripAlarmState());
	// Issue #2277 S2a — Wertebereiche-Schatten-State fuer den geteilten
	// CorridorEditor (createMode). Fliesst bewusst NICHT in stubTrip ein
	// (dieselbe Effekt-Schleifen-Gefahr wie beim Alarm-Schatten-State oben).
	let corridors = $state<Corridor[]>([]);
	// Metrik-Katalog fuer die Alarm-Metrik-Zeilen (fail-soft, Muster WeatherMetricsTab).
	let metricsCatalog = $state<MetricCatalog>({});
	// #2521 S3: Voraussetzung fuer „Mit Standardwerten speichern" (defaultsBereit):
	// Metrik-Katalog geladen UND Standardauswahl vom Wetter-Metriken-Reiter
	// gemeldet (gesetzt in handleWeatherMetricsChange).
	let catalogLoaded = $state(false);
	// #2347 S4 (AC-20, Race): die Wertebereiche-Vorbelegung des CorridorEditors
	// wartet zusaetzlich auf dessen eigenen Katalog-Abruf. Erst wenn sie gelaufen
	// ist (gesetzt in handleVorbelegungFertig), traegt „Mit Standardwerten
	// speichern" dieselben Korridore wie der durchgeklickte Trip.
	let wertebereicheVorbelegt = $state(false);
	onMount(() => {
		api.get<MetricCatalog>('/api/metrics').then((c) => { metricsCatalog = c; }).catch(() => {});
	});
	const activeAlertMetrics = $derived(deriveActiveAlertMetricsForTrip(weatherMetrics, metricsCatalog));
	// Issue #674 — Aktivitätstyp aus WeatherMetricsTab übernehmen (Fahrrad/Wanderer).
	let selectedActivity = $state<ActivityType | undefined>(undefined);

	// Visited-Flags (Tab-Besuch setzt done)
	let wtVisited = $state(seed.wtVisited ?? false);
	let wbVisited = $state(seed.wbVisited ?? false);
	let alVisited = $state(seed.alVisited ?? false);

	let activeTab = $state<TabId>(seed.activeTab ?? 'route');

	// Issue #932 — Viewport-Flag, damit das Aktivitätstyp-Dropdown nur EINMAL
	// im DOM existiert (desktop XOR mobile). Spiegelt die CSS-Breakpoint-Grenze
	// (≤899px = mobile) der .tn-mobile/.tn-desktop-Umschaltung.
	let isMobileViewport = $state(seed.isMobileViewport ?? false);
	onMount(() => {
		// Issue #1738: nur der Test-Seam schaltet die Viewport-Erkennung ab —
		// ohne Uebergabe bleibt matchMedia die einzige Quelle.
		if (seed.isMobileViewport !== undefined) return;
		const mq = window.matchMedia('(max-width: 899px)');
		isMobileViewport = mq.matches;
		const onChange = (e: MediaQueryListEvent) => { isMobileViewport = e.matches; };
		mq.addEventListener('change', onChange);
		return () => mq.removeEventListener('change', onChange);
	});

	// Stub-Trip für WeatherMetricsTab und VersandTab (createMode — kein PUT).
	// Issue #1738: `stages` ist nicht mehr leer — VTLaufzeitRoute leitet das
	// Trip-Ende über `computeTripEnd` aus `stage.date` (ISO) ab. Quelle ist
	// dieselbe Datums-Arithmetik wie im Speicher-Payload (`stageDateISO` /
	// `addDaysISO`, beide UTC + idx Tage); `stageDate()` liefert `dd.mm.` ohne
	// Jahr und ist dafür unbrauchbar.
	const stubTrip = $derived<Trip>({
		id: '__new__',
		name: name || $t('trip.anlegen.neuer_trip'),
		stages: buildEditorStages(),
		activity: selectedActivity,
		display_config: { channels, metrics: weatherMetrics } as unknown as Trip['display_config'],
		report_config: reportConfig,
	});

	// Saving state
	let saving = $state(false);
	let saveError: string | null = $state(null);
	let savedTripId: string | null = $state(null);
	// intentionalCancel: plain let (not $state) — read synchronously before goto
	let intentionalCancel = false;

	// ── Abgeleitete Zustandsgrößen ────────────────────────────────────────────
	const etDone = $derived(stages.length > 0 && stages.every(s => s.gpx !== null));
	const unlocked = $derived(unlockedTabs(name, startDate, etDone, wtVisited, wbVisited, alVisited));
	const done = $derived(doneTabs(name, startDate, etDone, wtVisited, wbVisited, alVisited));
	const ready = $derived(canSave(done));
	// #2521 S3: eigenes Gate des Standardwerte-Knopfs (Bestandsknopf bleibt an `ready`).
	const standardwerteFrei = $derived(canFinishMitStandardwerten({
		pflichtErfuellt: name.trim().length > 0 && !!startDate && etDone,
		// Ohne aktive Metrik gibt es nichts vorzubelegen (CorridorEditor bricht dann
		// vor der Vorbelegung ab) — sonst bliebe der Knopf dauerhaft gesperrt.
		defaultsBereit: catalogLoaded && (wertebereicheVorbelegt || weatherMetrics.length === 0),
		bestandFrei: ready,
	}));
	const gpxCount = $derived(stages.filter(s => s.gpx !== null).length);
	const progressN = $derived(progressCount(done));

	// Flash-State für gesperrte Tabs
	let flashTab = $state<TabId | null>(null);

	// ── Mobile-only State (Issue #661) ────────────────────────────────────────
	// Lock-Toast (2s bei Tap auf gesperrten Tab)
	// i18n F9: der Toast haelt die Schritt-Kennung; der Hinweis entsteht beim Rendern.
	let lockToastMsg = $state<TabId | null>(null);
	const lockToastText = $derived(lockToastMsg ? (TAB_DEFS.find((d) => d.id === lockToastMsg)?.lockHint ?? $t('trip.anlegen.schritt_gesperrt')) : null);
	let lockToastTimer: ReturnType<typeof setTimeout> | null = null;
	// Stage-Sheet (Bottom-Sheet für Etappenname-Eingabe)
	let mobileSheetStageId = $state<number | null>(null);
	// Temp-Input für den aktuell im Sheet bearbeiteten Etappennamen
	let mobileSheetStageName = $state('');

	// ── Tab-Wechsel (Factory-Pattern) ─────────────────────────────────────────
	function makeTabHandler(id: TabId) {
		return function doSwitch() {
			if (unlocked.has(id)) {
				switchTab(id);
			} else {
				flashTab = id;
				setTimeout(() => { flashTab = null; }, 500);
			}
		};
	}

	// Mobile Tab-Handler: gesperrter Tab → Toast statt Flash (Issue #661)
	function makeMobileTabHandler(id: TabId) {
		return function doMobileSwitch() {
			if (unlocked.has(id)) {
				switchTab(id);
			} else {
				if (lockToastTimer) clearTimeout(lockToastTimer);
				lockToastMsg = id;
				lockToastTimer = setTimeout(() => { lockToastMsg = null; }, 2000);
			}
		};
	}

	// Mobile Stage-Sheet: öffnen (Factory-Pattern)
	function makeMobileOpenSheetHandler(stageId: number, stageName: string) {
		return function doOpenSheet() {
			mobileSheetStageId = stageId;
			mobileSheetStageName = stageName;
		};
	}

	// Mobile Stage-Sheet: Übernehmen (Factory-Pattern)
	function makeMobileApplySheetHandler() {
		return function doApplySheet() {
			if (mobileSheetStageId !== null) {
				stages = stages.map(s => s.id === mobileSheetStageId
					? { ...s, name: mobileSheetStageName }
					: s
				);
			}
			mobileSheetStageId = null;
		};
	}

	// Mobile Route-CTA: weiter zu Etappen (Factory-Pattern)
	// Guard: nur weiterschalten wenn Name+Datum gesetzt — spiegelt Desktop-disabled-CTA (AC-3).
	function makeMobileRouteContinueHandler() {
		return () => { if (name.trim() && startDate) switchTab('etappen'); };
	}

	// Mobile Wegpunkte CTA: weiter zu metriken (Factory-Pattern)
	function makeMobileWegpunkteContinueHandler() {
		return () => switchTab('wetter-metriken');
	}

	function switchTab(id: TabId) {
		const prev = activeTab;
		// Issue #658 — beim Verlassen des Wegpunkte-Tabs Editor-Edits zurückschreiben.
		if (prev === 'wegpunkte' && id !== 'wegpunkte') syncEditorBack();
		activeTab = id;
		// Issue #658 F001-Fix: Rebuild nur bei echtem Tab-EINTRITT (prev !== 'wegpunkte'),
		// damit ein erneuter Klick auf den bereits aktiven Tab keine ungespeicherten
		// Wegpunkt-Edits verwirft.
		if (id === 'wegpunkte' && prev !== 'wegpunkte') editorStages = buildEditorStages();
		if (id === 'wetter-metriken') wtVisited = true;
		if (id === 'wertebereiche') wbVisited = true;
		if (id === 'alarme') alVisited = true;
	}

	// ── Stage-Brücke: lokaler Create-State ⇄ EditStagesPanelNew (Issue #658) ──
	// EditStagesPanelNew arbeitet auf Stage[] (string-IDs, waypoints[]) und mutiert
	// das Array per bind:stages in place. Wir spiegeln den kanonischen lokalen State
	// (StageLocal, numerische IDs) beim Öffnen des Tabs in `editorStages` und
	// schreiben Wegpunkt-Edits per Index zurück — kein PUT (kein tripId), Persistenz
	// erst beim finalen POST. String-ID = `s<numerische id>` (stabile Brücke).
	let editorStages = $state<Stage[]>([]);

	function buildEditorStages(): Stage[] {
		return stages.map((s, idx) => ({
			id: `s${s.id}`,
			name: s.name || `Etappe ${idx + 1}`,
			date: stageDateISO(startDate, idx),
			waypoints: s.waypoints ?? [],
		}));
	}

	function stageDateISO(start: string, offset: number): string {
		if (!start) return '';
		const parts = start.split('-').map(Number);
		const dt = new Date(Date.UTC(parts[0], parts[1] - 1, parts[2]));
		dt.setUTCDate(dt.getUTCDate() + offset);
		return `${dt.getUTCFullYear()}-${String(dt.getUTCMonth() + 1).padStart(2, '0')}-${String(dt.getUTCDate()).padStart(2, '0')}`;
	}

	// Editor-Mutationen (Wegpunkt-Edits) per Index in den kanonischen State zurück.
	function syncEditorBack(): void {
		if (editorStages.length === 0) return;
		stages = stages.map((s, idx) => {
			const es = editorStages[idx];
			return es ? { ...s, waypoints: es.waypoints } : s;
		});
	}

	// ── Route-Tab-Handlers ────────────────────────────────────────────────────
	function makeNameHandler() { return (e: Event) => { name = (e.target as HTMLInputElement).value; }; }
	function makeRegionHandler() { return (e: Event) => { region = (e.target as HTMLInputElement).value.slice(0, 50); }; }
	function makeDateHandler() { return (e: Event) => { startDate = (e.target as HTMLInputElement).value; }; }
	function makeContinueToEtappenHandler() { return () => switchTab('etappen'); }

	// ── Etappen-Tab-Handlers ──────────────────────────────────────────────────
	function makeStageNameHandler(id: number) {
		return (e: Event) => {
			stages = stages.map(s => s.id === id ? { ...s, name: (e.target as HTMLInputElement).value } : s);
		};
	}

	function makeGpxUploadHandler(idx: number, stageId: number) {
		return async (e: Event) => {
			const file = (e.target as HTMLInputElement).files?.[0];
			if (!file) return;
			const iso = startDate ? (() => {
				const parts = startDate.split('-').map(Number);
				const dt = new Date(Date.UTC(parts[0], parts[1]-1, parts[2]));
				dt.setUTCDate(dt.getUTCDate() + idx);
				return `${dt.getUTCFullYear()}-${String(dt.getUTCMonth()+1).padStart(2,'0')}-${String(dt.getUTCDate()).padStart(2,'0')}`;
			})() : '';
			try {
				const fd = new FormData();
				fd.append('file', file);
				const resp = await fetch(`/api/gpx/parse?stage_date=${iso}&start_hour=7`, { method: 'POST', body: fd });
				if (resp.ok) {
					const data = await resp.json();
					const km = data.distance_km ?? data.km ?? '–';
					const asc = data.ascent_m ?? data.asc ?? '–';
					// Issue #658 — aus GPX berechnete Wegpunkte je Etappe in den lokalen State.
					const waypoints: Waypoint[] = (data.waypoints ?? []) as Waypoint[];
					stages = stages.map(s => s.id === stageId ? { ...s, gpx: { file: file.name, km, asc }, waypoints } : s);
				}
			} catch {
				// Upload fehlgeschlagen — GPX-Slot bleibt leer
			}
		};
	}

	function makeGpxRemoveHandler(stageId: number) {
		return () => { stages = stages.map(s => s.id === stageId ? { ...s, gpx: null } : s); };
	}

	function makeRemoveStageHandler(stageId: number) {
		// Bug #708 — zeigt Bestätigungs-Dialog statt sofort löschen
		return () => { pendingRemoveStageId = stageId; };
	}

	function confirmRemoveStage() {
		if (pendingRemoveStageId === null) return;
		stages = stages.filter(s => s.id !== pendingRemoveStageId);
		pendingRemoveStageId = null;
	}

	function makeAddStageHandler() {
		return () => {
			const nextId = (stages.length ? Math.max(...stages.map(s => s.id)) : 0) + 1;
			stages = [...stages, { id: nextId, name: '', gpx: null, waypoints: [] }];
		};
	}

	function makeEtappenContinueHandler(target: TabId) {
		return () => switchTab(target);
	}

	// ── Sprung aus dem geteilten VersandTab (Issue #1738) ─────────────────────
	// Issue #2287: Hub und Anlege-Flow fuehren dieselbe Kennung 'etappen'.
	function makeVersandJumpHandler() {
		return function doJump(tab: string) {
			if (tab === 'etappen') switchTab('etappen');
		};
	}
	const onVersandJump = makeVersandJumpHandler();

	// ── Kanal-Änderung aus WeatherMetricsTab ──────────────────────────────────
	function handleChannelsChange(c: { email: boolean; telegram: boolean; sms: boolean }) {
		channels = { ...c };
	}

	// ── Wetter-Metrik-Änderung aus WeatherMetricsTab (Issue #1552) ────────────
	// Rückkanal analog handleChannelsChange — ohne ihn verwirft der Anlege-
	// Dialog die sichtbar angehakte Auswahl still beim Speichern.
	function handleWeatherMetricsChange(m: WeatherConfigMetric[]) {
		// #2521 S3: der Reiter meldet erst nach SEINEM Katalog-Laden — erst dann
		// liegt die Standard-Metrikauswahl vor (defaultsBereit des Standardwerte-Knopfs).
		catalogLoaded = true;
		// Fix-Loop 2 (Staging-Befund effect_update_depth_exceeded): defensiv
		// zusaetzlich zum Effect-Scope-Fix in WeatherMetricsTab.svelte --
		// inhaltsgleicher Aufruf darf KEINE neue Array-Referenz erzeugen, sonst
		// rechnet `stubTrip` ($derived) unnoetig neu und schleust eine neue
		// `trip`-Prop-Referenz durch, die einen kuenftigen trip-lesenden Effect
		// erneut ausloesen koennte. Schliesst die ganze Schleifen-Klasse aus,
		// unabhaengig davon, was WeatherMetricsTab intern liest.
		if (JSON.stringify(m) === JSON.stringify(weatherMetrics)) return;
		weatherMetrics = [...m];
	}

	// ── Tagesfenster-Änderung aus WeatherMetricsTab (Issue #1775) ─────────────
	// Rückkanal analog handleChannelsChange/handleWeatherMetricsChange —
	// additiv mergen statt Feld für Feld separat zu halten, da reportConfig
	// hier bereits das EINE Objekt ist, das auch MailInhaltCard per
	// bind:reportConfig haelt.
	function handleDayWindowChange(w: { day_window_start_hour: number; day_window_end_hour: number }) {
		// Fix-Loop 2 (Staging-Regression #1775 nach Merge): gleiche Fehlerklasse
		// wie handleWeatherMetricsChange oben -- ohne Inhaltsgleichheits-Guard
		// erzeugt jeder Effect-Lauf in WeatherMetricsTab eine neue reportConfig-
		// Referenz -> neue stubTrip-Referenz -> effect_update_depth_exceeded.
		if (
			reportConfig?.day_window_start_hour === w.day_window_start_hour &&
			reportConfig?.day_window_end_hour === w.day_window_end_hour
		) {
			return;
		}
		reportConfig = { ...(reportConfig ?? {}), ...w };
	}

	// ── Wertebereiche-Rueckruf aus CorridorEditor (Issue #2277 S2a) ───────────
	// Muster handleChannelsChange: reine Uebernahme, kein Inhaltsgleichheits-
	// Guard noetig (corridors fliesst nicht in stubTrip zurueck).
	function handleCorridorsChange(c: Corridor[]) { corridors = [...c]; }
	// #2347 S4 (AC-20, Race): Vorbelegung gelaufen (mit oder ohne Zeilen) — erst
	// jetzt gibt der Standardwerte-Knopf frei (defaultsBereit).
	function handleVorbelegungFertig() { wertebereicheVorbelegt = true; }

	// ── Alarm-Rueckrufe aus AlarmeTab (Issue #2277 S1) ────────────────────────
	// Delta-Logik liegt in tripNewLogic.ts (gleicher Code wie im Payload-Test).
	function handleAlarmChannelToggle(kind: ChannelKind) { alarm = applyAlarmChannelToggle(alarm, kind); }
	function handleAlarmThresholdChange(kind: ChannelKind, level: ChannelThreshold) { alarm = applyAlarmThresholdChange(alarm, kind, level); }
	function handleAlarmMetricLevelChange(metric: AlertMetric, level: SensLevel) { alarm = applyAlarmMetricLevelChange(alarm, metric, level); }
	function handleAlarmOfficialWarningsChange(an: boolean) { alarm = { ...alarm, officialWarningsEnabled: an }; }
	function handleAlarmCooldownChange(minuten: number | undefined) { alarm = { ...alarm, cooldownMinutes: minuten }; }
	function handleAlarmQuietHoursChange(von: string | undefined, bis: string | undefined) { alarm = { ...alarm, quietFrom: von, quietTo: bis }; }

	// ── Speichern ─────────────────────────────────────────────────────────────
	// #2521 S3: `mitStandardwerten` = Weg des Standardwerte-Knopfs — eigenes Gate
	// statt `ready`, report_config wie nach unveraendertem Durchklicken ergaenzt.
	async function buildAndSave(mitStandardwerten = false): Promise<string | null> {
		if (!(mitStandardwerten ? standardwerteFrei : ready) || saving || savedTripId) return null;
		saveError = null;
		saving = true;
		// Issue #658 — etwaige offene Editor-Edits vor dem POST in den State holen.
		if (activeTab === 'wegpunkte') syncEditorBack();
		try {
			const state: CreateTripState = {
				name,
				region: region || undefined,
				startDate,
				stages: stages.map(s => ({ id: s.id, name: s.name, waypoints: s.waypoints })),
				weatherMetrics,
				channels,
				// #1743 AC-21: Standard-Versandeinstellungen entstehen im Speicherweg,
				// auch wenn der Versand-Abschnitt nie beruehrt wurde.
				reportConfig: mitStandardwerten ? ergaenzeStandardwerteReportConfig(reportConfig) : ergaenzeVersandStandard(reportConfig),
				alarm,
				corridors,
				activity: selectedActivity,
			};
			const payload = buildCreateTripPayload(state);
			const created = await api.post<Trip>('/api/trips', payload);
			savedTripId = created.id;
			return created.id;
		} catch (e: unknown) {
			const err = e as { detail?: string; error?: string };
			// i18n F9: ohne Server-Text bleibt das Flag (''), die Meldung entsteht beim Rendern.
			saveError = err.detail ?? err.error ?? '';
			return null;
		} finally {
			saving = false;
		}
	}

	// beforeNavigate: auto-save when ready and not yet saved, skip on intentional cancel.
	beforeNavigate(({ cancel, to }) => {
		if (!ready || savedTripId || saving || !to || intentionalCancel) return;
		cancel();
		void (async () => {
			const id = await buildAndSave();
			if (id) await goto(to.url.href);
		})();
	});

	function makeSaveHandler() {
		return async function doSave() {
			const id = await buildAndSave();
			if (id) await goto(`/trips/${id}`);
		};
	}

	function makeCancelHandler() {
		return () => { intentionalCancel = true; goto('/trips'); };
	}

	function makeStandardwerteHandler() {
		return async function doSaveStandardwerte() {
			if (!standardwerteFrei) return;
			const id = await buildAndSave(true);
			if (id) await goto(`/trips/${id}`);
		};
	}

	const onSave = makeSaveHandler();
	const onStandardwerte = makeStandardwerteHandler();
	const onCancel = makeCancelHandler();

	// Die Karte im Wegpunkte-Reiter muss ueber dem Speichern-Footer enden (Attribution).
	let mobileTreeEl = $state<HTMLDivElement | null>(null);
	let mobileFooterHeightPx = $state(0);
	$effect(() => {
		const footer = mobileTreeEl?.querySelector<HTMLElement>('[data-testid="tn-mobile-footer"]');
		if (!footer) return;
		const ro = new ResizeObserver(() => { mobileFooterHeightPx = footer.offsetHeight; });
		ro.observe(footer);
		return () => ro.disconnect();
	});
</script>

<div data-testid="trip-new-editor" style="display: flex; min-height: 100%; background: var(--g-paper);">
	<!-- Kein eigener Scroll-Container (clip statt hidden/auto): sonst greift das
	     sticky des Speichern-Footers nie, weil dieses main mit dem Inhalt waechst. -->
	<main style="flex: 1; min-width: 0; position: relative; overflow-x: clip; display: flex; flex-direction: column;">
		<TopoBg opacity={0.12} />

		<!-- Kopfleiste Desktop: Zurück über den geteilten PageHeader (onCancel ⇒ kein Autosave) -->
		<div class="tn-desktop" data-testid="tn-desktop-breadcrumb" style="position: relative; padding: 0 40px;">
			<PageHeader back={{ href: '/trips', label: 'Trips', onclick: onCancel }} compact />
		</div>

		<!-- Kopfleiste Mobile (Issue #661): gleiche Bauart wie /compare/new -->
		<div class="tn-mobile" data-testid="tn-mobile-appbar" style="position: relative; padding: 0 16px; background: var(--g-paper); flex-shrink: 0; z-index: 10;">
			<PageHeader
				back={{ href: '/trips', label: $t('listen.trips.titel'), onclick: onCancel }}
				eyebrow={name.trim() || $t('trip.anlegen.neuer_trip')}
				title={TAB_DEFS.find(d => d.id === activeTab)?.label ?? $t('trip.anlegen.reiter_route')}
				compact
			/>
		</div>

		<!-- Hero (Desktop only) -->
		<div class="tn-desktop" style="position: relative; padding: 20px 40px 14px;">
			<Eyebrow>{$t('trip.anlegen.titel')}</Eyebrow>
			<h1 style="font-size: 32px; font-weight: 600; letter-spacing: -0.02em; margin: 4px 0 0; line-height: 1.1; color: {name.trim() ? 'var(--g-ink)' : 'var(--g-ink-4)'};">
				{name.trim() || $t('trip.anlegen.kein_name')}
			</h1>
			<!-- Fortschrittsbalken (TN_Progress); Kennungen wie compare-editor-progress (#2347 S4, AN-2) -->
			<div data-testid="trip-new-progress" style="display: flex; align-items: center; gap: 10px; margin-top: 7px;">
				<div style="display: flex; gap: 3px;">
					{#each PROGRESS_STEPS as step}
						<div data-testid="trip-new-progress-segment" style="width: 24px; height: 3px; border-radius: 2px; background: {done.has(step) ? 'var(--g-accent)' : 'var(--g-rule)'}; transition: background 350ms;"></div>
					{/each}
				</div>
				<span class="mono" style="font-size: 11px; color: var(--g-ink-4); letter-spacing: 0.04em;">
					{progressN === 0 ? $t('trip.anlegen.nichts_eingerichtet') : $t('trip.anlegen.abschnitte', { n: progressN, gesamt: PROGRESS_STEPS.length })}
				</span>
			</div>
		</div>

		<!-- Mobile Fortschrittsbalken (TNM_Progress, Issue #661) -->
		<div class="tn-mobile tn-mobile-flex" style="align-items: center; gap: 8px; padding: 8px 16px 0;">
			<div style="display: flex; gap: 3px; flex: 1;">
				{#each PROGRESS_STEPS as step}
					<div style="flex: 1; height: 3px; border-radius: 2px; background: {done.has(step) ? 'var(--g-accent)' : 'var(--g-rule)'}; transition: background 350ms;"></div>
				{/each}
			</div>
			<span class="mono" style="font-size: 11px; color: var(--g-ink-4); flex-shrink: 0;">{progressN}/{PROGRESS_STEPS.length}</span>
		</div>

		<!-- Tab-Bar (Desktop only, TN_TabBar) -->
		<div class="tn-desktop" style="border-bottom: 1px solid var(--g-rule); padding: 0 40px; display: flex; gap: 0; overflow-x: auto;">
			{#each TAB_DEFS as tab}
				{@const isActive = tab.id === activeTab}
				{@const isOpen = unlocked.has(tab.id)}
				{@const isDone = done.has(tab.id) && !isActive}
				<div
					role="tab"
					tabindex={isOpen ? 0 : -1}
					aria-selected={isActive}
					onclick={makeTabHandler(tab.id)}
					onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') makeTabHandler(tab.id)(); }}
					title={!isOpen && tab.lockHint ? $t('trip.anlegen.gesperrt', { hinweis: tab.lockHint }) : undefined}
					style="padding: 12px 16px; cursor: {isOpen ? 'pointer' : 'not-allowed'}; font-size: 13px; font-weight: {isActive ? 600 : 500}; color: {isActive ? 'var(--g-ink)' : isOpen ? 'var(--g-ink-3)' : 'var(--g-ink-4)'}; border-bottom: {isActive ? '2px solid var(--g-accent)' : '2px solid transparent'}; margin-bottom: -1px; display: flex; align-items: center; gap: 5px; white-space: nowrap; opacity: {isOpen ? 1 : 0.34}; transition: opacity 250ms, color 200ms; transform: {flashTab === tab.id ? 'translateX(2px)' : 'none'}; user-select: none;">
					{tab.label}
					{#if tab.optional && isOpen}
						<span class="mono" style="font-size: 11px; font-weight: 600; letter-spacing: 0.06em; padding: 1px 5px; border-radius: 3px; background: rgba(196,90,42,0.10); color: var(--g-accent-deep); text-transform: uppercase;">{$t('trip.anlegen.optional')}</span>
					{/if}
					{#if isDone}
						<span style="font-size: 11px; font-weight: 700; padding: 2px 5px; border-radius: 3px; background: rgba(61,107,58,0.12); color: var(--g-good); font-family: var(--g-font-mono);">✓</span>
					{/if}
					{#if !isOpen}
						<span style="font-size: 11px; color: var(--g-ink-4); font-family: var(--g-font-mono); opacity: 0.7;">⊘</span>
					{/if}
				</div>
			{/each}
		</div>

		<!-- Mobile Tab-Bar (TNM_TabBar, Issue #661) -->
		<div class="tn-mobile tn-mobile-flex" data-testid="tn-mobile-tabbar" style="gap: 0; overflow-x: auto; border-bottom: 1px solid var(--g-rule-soft); -webkit-overflow-scrolling: touch; scrollbar-width: none; flex-shrink: 0; mask-image: linear-gradient(to right, transparent, black 16px, black calc(100% - 16px), transparent); -webkit-mask-image: linear-gradient(to right, transparent, black 16px, black calc(100% - 16px), transparent);">
			{#each TAB_DEFS as tab}
				{@const isActive = tab.id === activeTab}
				{@const isOpen = unlocked.has(tab.id)}
				{@const isDone = done.has(tab.id) && !isActive}
				<button
					type="button"
					role="tab"
					aria-selected={isActive}
					onclick={makeMobileTabHandler(tab.id)}
					style="display: inline-flex; align-items: center; gap: 5px; padding: 13px 13px; min-height: 44px; flex-shrink: 0; background: transparent; border: none; border-bottom: {isActive ? '2px solid var(--g-accent)' : '2px solid transparent'}; margin-bottom: -1px; cursor: {isOpen ? 'pointer' : 'default'}; font-size: 14px; font-weight: {isActive ? 600 : 500}; color: {isActive ? 'var(--g-ink)' : isOpen ? 'var(--g-ink-3)' : 'var(--g-ink-4)'}; white-space: nowrap; font-family: var(--g-font-sans); opacity: {isOpen ? 1 : 0.35};">
					{tab.label}
					{#if tab.optional && isOpen}
						<span class="mono" style="font-size: 11px; font-weight: 700; padding: 1px 5px; border-radius: 3px; background: rgba(196,90,42,0.12); color: var(--g-accent-deep); letter-spacing: 0.06em; text-transform: uppercase;">{$t('trip.anlegen.opt')}</span>
					{/if}
					{#if !isOpen}
						<span class="mono" style="font-size: 11px; opacity: 0.8;">⊘</span>
					{/if}
				</button>
			{/each}
		</div>

		<!-- Fehler-Banner -->
		{#if saveError !== null}
			<div style="padding: 10px 40px; background: rgba(180,30,30,0.08); border-bottom: 1px solid rgba(180,30,30,0.2);">
				<span class="mono" style="font-size: 11px; color: var(--g-bad);">⚠ {saveError || $t('trip.fehler_speichern')}</span>
			</div>
		{/if}

		<!-- ══════════════════════════════════════════════════════
		     Desktop Tab-Inhalt (Issue #622, Slice 1)
		     ══════════════════════════════════════════════════════ -->
		<div class="tn-desktop" style="flex: 1 0 auto; display: flex; flex-direction: column;">
		<div style="flex: 1 0 auto;">
		{#if activeTab === 'route'}
			<!-- Route-Tab (TN_RouteTab) -->
			<div style="position: relative; padding: 28px 40px 60px;">
				<TopoBg opacity={0.10} />
				<div style="position: relative; max-width: 640px;">
					<Eyebrow style="margin-bottom: 14px;">{$t('trip.anlegen.grunddaten')}</Eyebrow>

					<div style="margin-bottom: 18px;">
						<label style="display: block; font-size: 12px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; color: var(--g-ink-3); margin-bottom: 6px;">
							{$t('trip.anlegen.trip_name')} <span style="color: var(--g-bad);">*</span>
						</label>
						<input type="text" value={name} oninput={makeNameHandler()}
							placeholder={$t('trip.anlegen.name_beispiel')}
							autofocus
							data-testid="trip-new-name-input-desktop"
							style="width: 100%; box-sizing: border-box; padding: 9px 12px; font-size: 14px; font-family: var(--g-font-sans); border: 1.5px solid var(--g-rule); border-radius: var(--g-r-2); background: var(--g-card); color: var(--g-ink); outline: none;" />
					</div>

					<div style="margin-bottom: 18px;">
						<label style="display: block; font-size: 12px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; color: var(--g-ink-3); margin-bottom: 6px;">
							{$t('trip.anlegen.region')}
							<span class="mono" style="font-size: 11px; color: var(--g-ink-4); text-transform: none; letter-spacing: normal; font-weight: 400; margin-left: 6px;">{$t('trip.anlegen.optional_max')}</span>
						</label>
						<input type="text" value={region} oninput={makeRegionHandler()}
							placeholder={$t('trip.anlegen.region_beispiel')}
							maxlength="50"
							style="width: 100%; box-sizing: border-box; padding: 9px 12px; font-size: 14px; font-family: var(--g-font-sans); border: 1.5px solid var(--g-rule); border-radius: var(--g-r-2); background: var(--g-card); color: var(--g-ink); outline: none;" />
					</div>

					<div style="margin-bottom: 18px;">
						<label style="display: block; font-size: 12px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; color: var(--g-ink-3); margin-bottom: 6px;">
							{$t('trip.startdatum')} <span style="color: var(--g-bad);">*</span>
						</label>
						<input type="date" value={startDate} onchange={makeDateHandler()}
							style="width: 100%; box-sizing: border-box; padding: 9px 12px; font-size: 14px; font-family: var(--g-font-mono); border: 1.5px solid var(--g-rule); border-radius: var(--g-r-2); background: var(--g-card); color: var(--g-ink); outline: none; appearance: none; -webkit-appearance: none;" />
						{#if startDate}
							<div class="mono" style="font-size: 11px; color: var(--g-ink-3); margin-top: 6px;">
								{$t('trip.anlegen.start_hinweis', { datum: stageDate(startDate, 0, $locale)?.replace(/\.$/, '') ?? '' })}
							</div>
						{/if}
					</div>

					<!-- Issue #932 — Aktivitätstyp (verschoben aus Metriken-Tab). -->
					<!-- Nur auf Desktop-Viewport rendern, damit das Dropdown nur einmal im DOM existiert. -->
					{#if !isMobileViewport}
					<div style="margin-bottom: 18px;">
						<label style="display: block; font-size: 12px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; color: var(--g-ink-3); margin-bottom: 6px;">
							{$t('trip.anlegen.aktivitaetstyp')}
							<span class="mono" style="font-size: 11px; color: var(--g-ink-4); text-transform: none; letter-spacing: normal; font-weight: 400; margin-left: 6px;">{$t('trip.anlegen.optional')}</span>
						</label>
						<Select data-testid="activity-dropdown"
							value={selectedActivity ?? ''}
							onchange={(e) => { selectedActivity = (e.target as HTMLSelectElement).value as ActivityType || undefined; }}
							style="width: 100%; max-width: 320px;">
							{#each AKTIVITAETEN as a, i (a.value)}{#if i > 0}{' '}{/if}<option value={a.value}>{$t(a.key)}</option>{/each}
						</Select>
					</div>
					{/if}

					<div style="margin-top: 12px; padding: 12px 16px; border-radius: var(--g-r-2); background: var(--g-accent-tint); border: 1px solid var(--g-accent-rule);">
						<div class="mono" style="font-size: 11px; color: var(--g-accent-deep); line-height: 1.6;">
							{$t('trip.anlegen.gpx_hinweis')}
						</div>
					</div>

					<div style="margin-top: 28px; padding-top: 20px; border-top: 1px solid var(--g-rule); display: flex; justify-content: flex-end; align-items: center; gap: 12px;">
						{#if !name.trim()}
							<span class="mono" style="font-size: 11px; color: var(--g-ink-4);">{$t('trip.anlegen.name_fehlt')}</span>
						{:else if !startDate}
							<span class="mono" style="font-size: 11px; color: var(--g-ink-4);">{$t('trip.anlegen.datum_fehlt')}</span>
						{/if}
						<button type="button"
							disabled={!name.trim() || !startDate}
							onclick={makeContinueToEtappenHandler()}
							data-testid="trip-new-continue-etappen"
							style="padding: 8px 16px; border-radius: var(--g-r-2); border: none; background: {name.trim() && startDate ? 'var(--g-accent)' : 'var(--g-ink-4)'}; color: #fff; font-size: 13px; font-weight: 600; cursor: {name.trim() && startDate ? 'pointer' : 'not-allowed'}; opacity: {name.trim() && startDate ? 1 : 0.45};">
							{$t('trip.anlegen.etappen_anlegen')}
						</button>
					</div>
				</div>
			</div>

		{:else if activeTab === 'etappen'}
			<!-- Etappen-Tab (TN_EtappenTab) -->
			<div style="position: relative; padding: 28px 40px 60px;">
				<TopoBg opacity={0.10} />
				<div style="position: relative; max-width: 900px;">
					<div style="display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 20px;">
						<div>
							<Eyebrow style="margin-bottom: 2px;">{$t('trip.etappen')}</Eyebrow>
							<h2 style="font-size: 20px; font-weight: 600; letter-spacing: -0.01em; margin: 0;">
								{$t('trip.anlegen.etappen_titel')}
							</h2>
						</div>
						<div style="display: flex; flex-direction: column; align-items: flex-end; gap: 3px;">
							<span class="mono" style="font-size: 11px; color: {etDone && stages.length > 0 ? 'var(--g-good)' : 'var(--g-ink-4)'};">
								{$t('trip.anlegen.gpx_geladen', { n: gpxCount, gesamt: stages.length })}
							</span>
							{#if startDate}
								<span class="mono" style="font-size: 11px; color: var(--g-ink-4);">
									{$t('trip.anlegen.start', { datum: stageDate(startDate, 0, $locale)?.replace(/\.$/, '') ?? '' })}
								</span>
							{/if}
						</div>
					</div>

					<!-- Spaltenheader -->
					<div style="display: grid; grid-template-columns: 36px 1fr 60px minmax(170px, 200px) 28px; gap: 10px; padding: 0 14px 5px;">
						{#each ['', $t('trip.anlegen.etappenname'), $t('trip.datum'), $t('trip.anlegen.gpx_datei'), ''] as h}
							<span class="mono" style="font-size: 11px; color: var(--g-ink-4); letter-spacing: 0.06em; text-transform: uppercase;">{h}</span>
						{/each}
					</div>

					<div style="display: flex; flex-direction: column; gap: 3px; margin-bottom: 14px;">
						{#each stages as s, idx}
							{@const dateStr = stageDate(startDate, idx, $locale)}
							{@const hasGpx = s.gpx !== null}
							<div style="display: grid; grid-template-columns: 36px 1fr 60px minmax(170px, 200px) 28px; gap: 10px; align-items: center; padding: 8px 14px; background: var(--g-card); border: 1px solid {hasGpx ? 'rgba(61,107,58,0.2)' : 'var(--g-rule)'}; border-radius: var(--g-r-2); transition: border-color 200ms;">
								<!-- T-Badge -->
								<span class="mono" style="font-size: 11px; font-weight: 700; text-align: center; color: var(--g-accent-deep); background: var(--g-accent-tint); padding: 2px 4px; border-radius: 999px;">
									T{String(idx + 1).padStart(2, '0')}
								</span>

								<!-- Inline-Name -->
								<input type="text" value={s.name} oninput={makeStageNameHandler(s.id)}
									placeholder={$t('trip.anlegen.etappe_benennen', { nr: idx + 1 })}
									style="width: 100%; box-sizing: border-box; background: transparent; border: 1.5px solid transparent; border-radius: var(--g-r-1); padding: 4px 2px; font-size: 13.5px; font-weight: {s.name ? 500 : 400}; font-family: var(--g-font-sans); color: {s.name ? 'var(--g-ink)' : 'var(--g-ink-4)'}; outline: none;" />

								<!-- Auto-Datum -->
								<span class="mono" style="font-size: 11px; color: {dateStr ? 'var(--g-ink-3)' : 'var(--g-ink-4)'}; white-space: nowrap;">
									{dateStr || '–'}
								</span>

								<!-- GPX-Slot -->
								{#if s.gpx}
									<div style="display: flex; align-items: center; gap: 7px; padding: 5px 10px; border-radius: var(--g-r-2); background: rgba(61,107,58,0.08); border: 1px solid rgba(61,107,58,0.22);">
										<span style="width: 16px; height: 16px; border-radius: 3px; flex-shrink: 0; background: var(--g-good); display: flex; align-items: center; justify-content: center;">
											<svg width="9" height="9" viewBox="0 0 10 10" fill="none"><polyline points="1.5,5.5 4,8 8.5,2" stroke="#fff" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>
										</span>
										<div style="flex: 1; min-width: 0;">
											<div class="mono" style="font-size: 11px; font-weight: 600; color: var(--g-ink-2); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{s.gpx.file}</div>
											<div class="mono" style="font-size: 11px; color: var(--g-ink-3);">{`${s.gpx.km} km · ↑${s.gpx.asc} m`}</div>
										</div>
										<button type="button" onclick={makeGpxRemoveHandler(s.id)} title={$t('trip.anlegen.gpx_entfernen')}
											style="background: transparent; border: none; cursor: pointer; color: var(--g-ink-4); font-size: 13px; padding: 1px 3px; line-height: 1; flex-shrink: 0;">×</button>
									</div>
								{:else}
									<label style="padding: 6px 11px; border-radius: var(--g-r-2); border: 1.5px dashed var(--g-rule); background: transparent; cursor: pointer; display: flex; align-items: center; gap: 6px;">
										<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="var(--g-ink-4)" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
											<path d="M12 16V4M7 9l5-5 5 5"/><path d="M4 16v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3"/>
										</svg>
										<span class="mono" style="font-size: 11px; font-weight: 600; letter-spacing: 0.02em; color: var(--g-ink-4); white-space: nowrap;">{$t('trip.anlegen.gpx_hochladen')}</span>
										<input type="file" accept=".gpx" style="display: none;" onchange={makeGpxUploadHandler(idx, s.id)} />
									</label>
								{/if}

								<!-- Entfernen -->
								<button type="button" onclick={makeRemoveStageHandler(s.id)}
									aria-label={$t('trip.etappe_entfernen')}
									data-testid={`tn-stage-remove-${idx}`}
									style="background: transparent; border: none; cursor: pointer; color: var(--g-ink-4); font-size: 15px; padding: 2px 4px; line-height: 1; text-align: center;">×</button>
							</div>
						{/each}
					</div>

					<div style="display: flex; gap: 8px; margin-bottom: 24px;">
						<button type="button" onclick={makeAddStageHandler()}
							style="padding: 6px 12px; border-radius: var(--g-r-2); border: 1px solid var(--g-rule); background: transparent; font-size: 12px; font-weight: 500; cursor: pointer; color: var(--g-ink-3);">
							{$t('trip.anlegen.etappe_hinzufuegen')}
						</button>
					</div>

					<!-- Hinweis GPX fehlen -->
					{#if !etDone && stages.length > 0}
						<div style="padding: 10px 15px; border-radius: var(--g-r-2); background: var(--g-paper); border: 1px solid var(--g-rule); margin-bottom: 20px;">
							<span class="mono" style="font-size: 11px; color: var(--g-ink-3);">
								{$tn('trip.anlegen.ohne_gpx', stages.length - gpxCount)}
							</span>
						</div>
					{/if}

					<!-- Hinweis alle GPX geladen -->
					{#if etDone && stages.length > 0}
						<div style="padding: 10px 15px; border-radius: var(--g-r-2); background: rgba(61,107,58,0.07); border: 1px solid rgba(61,107,58,0.2); margin-bottom: 20px;">
							<span class="mono" style="font-size: 11px; color: var(--g-good);">
								{$t('trip.anlegen.alle_gpx')}
							</span>
						</div>
					{/if}

					<div style="padding-top: 20px; border-top: 1px solid var(--g-rule); display: flex; justify-content: flex-end; align-items: center; gap: 8px;">
						{#if etDone}
							<button type="button" onclick={makeEtappenContinueHandler('wetter-metriken')}
								style="padding: 8px 16px; border-radius: var(--g-r-2); border: 1px solid var(--g-rule); background: transparent; font-size: 13px; font-weight: 500; cursor: pointer; color: var(--g-ink-3);">
								{$t('trip.anlegen.wetter_direkt')}
							</button>
						{/if}
						<button type="button"
							disabled={!etDone}
							onclick={makeEtappenContinueHandler('wegpunkte')}
							style="padding: 8px 16px; border-radius: var(--g-r-2); border: none; background: {etDone ? 'var(--g-accent)' : 'var(--g-ink-4)'}; color: #fff; font-size: 13px; font-weight: 600; cursor: {etDone ? 'pointer' : 'not-allowed'}; opacity: {etDone ? 1 : 0.45};">
							{$t('trip.anlegen.wegpunkte_pruefen')}
						</button>
					</div>
				</div>
			</div>

		{:else if activeTab === 'wegpunkte'}
			<!-- Wegpunkte-Tab (Issue #658) — Info-Banner + eingebetteter Editor + Footer -->
			<div style="position: relative;">
				<!-- Issue #2521 S1 (AC-4): Infobox oben im optionalen Reiter. -->
				{#if !isMobileViewport}<div style="padding: 14px 40px 0;"><Infobox reiter="wegpunkte" context="route" /></div>{/if}
				<!-- Info-Banner (1:1 TN_WegpunkteTab) -->
				<div style="padding: 14px 40px; background: var(--g-card); border-bottom: 1px solid var(--g-rule-soft); display: flex; justify-content: space-between; align-items: center; gap: 24px;">
					<div style="flex: 1;">
						<div style="font-size: 13.5px; font-weight: 600; margin-bottom: 3px;">
							{$t('trip.anlegen.wegpunkte_berechnet')}
						</div>
						<div class="mono" style="font-size: 11px; color: var(--g-ink-3); line-height: 1.55;">
							{$t('trip.anlegen.wegpunkte_text')}
						</div>
					</div>
					<div style="display: flex; gap: 8px; flex-shrink: 0;">
						<button type="button" onclick={makeEtappenContinueHandler('wetter-metriken')}
							style="padding: 6px 12px; border-radius: var(--g-r-2); border: 1px solid var(--g-rule); background: transparent; font-size: 13px; font-weight: 500; cursor: pointer; color: var(--g-ink-3);">
							{$t('trip.anlegen.ueberspringen_pfeil')}
						</button>
						<button type="button" onclick={makeEtappenContinueHandler('wetter-metriken')}
							style="padding: 6px 12px; border-radius: var(--g-r-2); border: none; background: var(--g-accent); color: #fff; font-size: 13px; font-weight: 600; cursor: pointer;">
							{$t('trip.anlegen.wegpunkte_uebernehmen')}
						</button>
					</div>
				</div>

				<!-- Eingebetteter Wegpunkt-Editor: kein tripId → kein PUT, kein Save-Bar -->
				<!-- Issue #674 — activityType für korrekte Naismith-Ankunftszeiten im Editor -->
				<EditStagesPanelNew bind:stages={editorStages} showSave={false} activityType={selectedActivity} />

				<!-- Footer (1:1 TN_WegpunkteTab) -->
				<div style="padding: 20px 40px; border-top: 1px solid var(--g-rule); background: var(--g-card); display: flex; justify-content: flex-end; align-items: center; gap: 8px;">
					<button type="button" onclick={makeEtappenContinueHandler('wetter-metriken')}
						style="padding: 8px 16px; border-radius: var(--g-r-2); border: 1px solid var(--g-rule); background: transparent; font-size: 13px; font-weight: 500; cursor: pointer; color: var(--g-ink-3);">
						{$t('trip.anlegen.ueberspringen')}
					</button>
					<button type="button" onclick={makeEtappenContinueHandler('wetter-metriken')}
						style="padding: 8px 16px; border-radius: var(--g-r-2); border: none; background: var(--g-accent); color: #fff; font-size: 13px; font-weight: 600; cursor: pointer;">
						{$t('trip.anlegen.wegpunkte_uebernehmen')}
					</button>
				</div>
			</div>

		{/if}

		<!-- Wetter-Tab: reuse WeatherMetricsTab im createMode -->
		<!-- Issue #932 — Aktivitätstyp-Dropdown lebt jetzt im Route-Tab. -->
		<!-- Issue #941 — WeatherMetricsTab bleibt beim Tab-Wechsel gemountet (per
		     display ausgeblendet), damit isDirty/buckets/savedSnapshot erhalten
		     bleiben. Fix-Loop 4 (Staging-Befund #1552, effect_update_depth_exceeded
		     bei jedem Checkbox-Klick): NEU per isMobileViewport-Gate (Vorbild
		     activity-dropdown, Issue #932) nur EINE Instanz im DOM -- Desktop UND
		     Mobile hielten sonst je eine EIGENE Kopie von buckets/friendlyMap/... und
		     schrieben unabhaengig in denselben Rueckkanal (weatherMetrics); nach einem
		     Klick auf NUR einer Seite blieben beide Kopien dauerhaft verschieden und
		     ueberschrieben sich gegenseitig unbegrenzt. catalogLoaded-Gate und
		     Inhaltsgleichheitspruefung (Fix-Loop 2/3) bleiben als Zusatzschutz
		     bestehen (Resize-Grenzfall: Tab kann kurzzeitig neu mounten). -->
		{#if !isMobileViewport}
		<div style:display={activeTab === 'wetter-metriken' ? '' : 'none'}>
			<!-- Issue #1743: geteilter Baustein „Wetter-Metriken + Versand" (createMode,
			     kein PUT). Der Versand-Abschnitt haelt den report_config-Blob per
			     bind:reportConfig; die Mail-Inhalt-Karte folgt darunter (im createMode
			     blendet WeatherMetricsTab sie aus). -->
			<WetterMetrikenVersandPanel context="route" trip={stubTrip} createMode={true} showInfobox={true} onChannelsChange={handleChannelsChange} onWeatherMetricsChange={handleWeatherMetricsChange} onDayWindowChange={handleDayWindowChange} bind:reportConfig onJump={onVersandJump} />
			<div style="padding: 0 40px 60px; max-width: 720px;">
				<MailInhaltCard bind:reportConfig />
				<!-- #2347 S4 (AC-20): Weiter-Fuß wie compare-editor-continue-wertebereiche im Vergleich. -->
				<div style="margin-top: 28px; padding-top: 20px; border-top: 1px solid var(--g-rule); display: flex; justify-content: flex-end;">
					<Btn data-testid="trip-new-continue-wertebereiche" variant="accent" size="md" onclick={makeEtappenContinueHandler('wertebereiche')}>{$t('trip.anlegen.wertebereiche_festlegen')}</Btn>
				</div>
			</div>
		</div>
		{/if}

		<!-- Issue #2277 S2a — geteilter CorridorEditor (createMode, kein PUT),
		     Muster WeatherMetricsTab/AlarmeTab: EINE dauerhafte Instanz (Desktop
		     XOR Mobile), Sichtbarkeit ueber style:display. -->
		{#if !isMobileViewport}
		<div style:display={activeTab === 'wertebereiche' ? '' : 'none'}>
			<CorridorEditor context="route" trip={stubTrip} createMode={true} showInfobox={true} {corridors} onCorridorsChange={handleCorridorsChange} onVorbelegungFertig={handleVorbelegungFertig} />
			<!-- #2347 S4 (AC-20): Weiter-Fuß wie compare-editor-continue-alarme im Vergleich. -->
			<div style="padding: 0 40px 60px; display: flex; justify-content: flex-end;">
				<Btn data-testid="trip-new-continue-alarme" variant="accent" size="md" onclick={makeEtappenContinueHandler('alarme')}>{$t('trip.anlegen.alarme_einrichten')}</Btn>
			</div>
		</div>
		{/if}

		<!-- Issue #2277 S1 — geteilter AlarmeTab (createMode, kein PUT), Muster
		     WeatherMetricsTab: EINE dauerhafte Instanz (Desktop XOR Mobile),
		     Sichtbarkeit ueber style:display, damit der interne State beim
		     Tab-Wechsel erhalten bleibt. Kanal-Wertprops bewusst NICHT gesetzt. -->
		{#if !isMobileViewport}
		<div style:display={activeTab === 'alarme' ? '' : 'none'}>
			<div style="padding: 32px 40px 60px;">
				<AlarmeTab context="route" trip={stubTrip} createMode={true} showInfobox={true}
					officialWarningsEnabled={alarm.officialWarningsEnabled}
					onOfficialWarningsChange={handleAlarmOfficialWarningsChange}
					cooldownMinutes={alarm.cooldownMinutes}
					onCooldownChange={handleAlarmCooldownChange}
					quietFrom={alarm.quietFrom}
					quietTo={alarm.quietTo}
					onQuietHoursChange={handleAlarmQuietHoursChange}
					onChannelToggle={handleAlarmChannelToggle}
					onThresholdChange={handleAlarmThresholdChange}
					activeMetrics={activeAlertMetrics}
					onMetricLevelChange={handleAlarmMetricLevelChange}
				/>
			</div>
		</div>
		{/if}
		</div>

		<!-- Speichern (geteilter Sticky-Footer; BottomNav ist auf Anlege-Seiten ausgeblendet) -->
		<EditorStickyFooter context="route" navClearance={false} testid="tn-desktop-footer">
			<div style="display: flex; gap: 8px; align-items: center; justify-content: flex-end;">
				{#if !ready}
					<!-- #2347 S4 (AN-5): Hinweis am gesperrten Abschluss, wie „Alarme einrichten zum Aktivieren" im Vergleich -->
					<span class="mono" style="font-size: 11px; color: var(--g-ink-4);">{$t('trip.anlegen.alarme_zum_speichern')}</span>
					<StandardwerteSpeichernKnopf enabled={standardwerteFrei} {saving} onclick={onStandardwerte} testid="trip-new-standardwerte-btn" />
				{/if}
				<button type="button" onclick={onSave} disabled={!ready || saving}
					data-testid="trip-new-save-btn"
					style="padding: 6px 12px; border-radius: var(--g-r-2); border: none; background: var(--g-ink); color: var(--g-paper); font-size: 13px; font-weight: 500; cursor: {ready && !saving ? 'pointer' : 'not-allowed'}; opacity: {ready && !saving ? 1 : 0.4};">
					{saving ? $t('trip.anlegen.speichere') : savedTripId ? $t('trip.anlegen.gespeichert') : $t('trip.anlegen.speichern')}
				</button>
			</div>
		</EditorStickyFooter>
		</div><!-- /.tn-desktop -->

		<!-- ══════════════════════════════════════════════════════
		     Mobile Tab-Inhalt (Issue #661, AC-9)
		     CSS-only Switch: .tn-mobile sichtbar bei ≤899px.
		     ══════════════════════════════════════════════════════ -->
		<div class="tn-mobile tn-mobile-flex" bind:this={mobileTreeEl} style="position: relative; min-height: 100vh; flex: 1 0 auto; flex-direction: column;">
		<div style="flex: 1 0 auto;">

			{#if activeTab === 'route'}
				<!-- Mobile Route-Tab (TNM_RouteTab) -->
				<div style="position: relative; padding: 16px 16px 88px;">
					<MField label={$t('trip.anlegen.trip_name')}>
						<!-- data-testid geteilt: Desktop-Input im .tn-desktop ist display:none auf ≤899px,
						     dieser hier ist sichtbar → Playwright findet genau diesen einen sichtbaren. -->
						<div style="display: flex; align-items: center; gap: 10px; background: var(--g-card); border: 1px solid var(--g-rule); border-radius: var(--g-r-3); padding: 0 14px; min-height: 48px;">
							<input type="text" value={name} oninput={makeNameHandler()}
								placeholder={$t('trip.anlegen.name_beispiel')}
								data-testid="trip-new-name-input-mobile"
								style="flex: 1; border: none; outline: none; background: transparent; font-size: 16px; font-family: var(--g-font-sans); color: var(--g-ink); min-height: 44px; padding: 0;" />
						</div>
					</MField>

					<MField label={$t('trip.anlegen.region')} sub={$t('trip.anlegen.optional_max_zeichen')}>
						<MInput bind:value={region} oninput={makeRegionHandler()} placeholder={$t('trip.anlegen.region_beispiel')} />
					</MField>

					<MField label={$t('trip.startdatum')} sub={startDate ? $t('trip.anlegen.start_hinweis_kurz', { datum: stageDate(startDate, 0, $locale)?.replace(/\.$/, '') ?? '' }) : undefined}>
						<input type="date" value={startDate} onchange={makeDateHandler()}
							data-testid="trip-new-date-input"
							style="display: block; width: 100%; box-sizing: border-box; background: var(--g-card); border: 1px solid var(--g-rule); border-radius: var(--g-r-3); padding: 12px 14px; font-size: 16px; font-family: var(--g-font-mono); color: var(--g-ink); outline: none; min-height: 48px; appearance: none; -webkit-appearance: none;" />
					</MField>

					<!-- Issue #932 — Aktivitätstyp (verschoben aus Metriken-Tab). -->
					<!-- Nur auf Mobile-Viewport rendern, damit das Dropdown nur einmal im DOM existiert. -->
					{#if isMobileViewport}
					<MField label={$t('trip.anlegen.aktivitaetstyp')} sub={$t('trip.anlegen.optional')}>
						<Select data-testid="activity-dropdown"
							value={selectedActivity ?? ''}
							onchange={(e) => { selectedActivity = (e.target as HTMLSelectElement).value as ActivityType || undefined; }}
							style="width: 100%;">
							{#each AKTIVITAETEN as a, i (a.value)}{#if i > 0}{' '}{/if}<option value={a.value}>{$t(a.key)}</option>{/each}
						</Select>
					</MField>
					{/if}

					<div style="padding: 12px 14px; border-radius: var(--g-r-2); background: var(--g-accent-tint); border: 1px solid var(--g-accent-rule); margin-bottom: 20px;">
						<div class="mono" style="font-size: 11px; color: var(--g-accent-deep); line-height: 1.6;">
							{$t('trip.anlegen.gpx_hinweis')}
						</div>
					</div>
				</div>

			{:else if activeTab === 'etappen'}
				<!-- Mobile Etappen-Tab (TNM_EtappenTab) -->
				<div style="position: relative; padding: 14px 14px 88px;">

					<!-- Counter -->
					<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
						<div class="mono" style="font-size: 11px; color: var(--g-ink-3); font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase;">{$tn('trip.anlegen.etappen_anzahl', stages.length)}</div>
						<span class="mono" style="font-size: 11px; color: {etDone ? 'var(--g-good)' : 'var(--g-ink-4)'};">{`${gpxCount}/${stages.length} GPX`}</span>
					</div>

					<!-- Etappen-Karten -->
					<div style="display: flex; flex-direction: column; gap: 10px;">
						{#each stages as s, idx}
							{@const dateStr = stageDate(startDate, idx, $locale)}
							{@const hasName = s.name.trim().length > 0}
							<div data-testid="tn-mobile-stage-card" style="background: var(--g-card); border: 1px solid {s.gpx ? 'rgba(61,107,58,0.2)' : 'var(--g-rule)'}; border-radius: var(--g-r-3); overflow: hidden; transition: border-color 200ms;">
								<!-- Header-Zeile -->
								<div style="display: flex; align-items: center; padding: 11px 14px 7px; gap: 10px;">
									<span class="mono" style="font-size: 11px; font-weight: 700; flex-shrink: 0; color: var(--g-accent-deep); background: var(--g-accent-tint); padding: 2px 6px; border-radius: 999px;">
										T{String(idx + 1).padStart(2, '0')}
									</span>
									<button type="button" data-testid="tn-mobile-stage-name"
										onclick={makeMobileOpenSheetHandler(s.id, s.name)}
										style="flex: 1; text-align: left; background: transparent; border: none; cursor: pointer; min-height: 36px; padding: 0;">
										<div style="font-size: 14.5px; font-weight: {hasName ? 500 : 400}; color: {hasName ? 'var(--g-ink)' : 'var(--g-ink-4)'};">
											{hasName ? s.name : $t('trip.anlegen.etappe_benennen', { nr: idx + 1 })}
										</div>
									</button>
									{#if dateStr}
										<span class="mono" style="font-size: 11px; color: var(--g-ink-3); flex-shrink: 0;">{dateStr}</span>
									{/if}
									<!-- #719 — Etappen-Lösch-Button (löst #708-Bestätigungsdialog aus) -->
									<button type="button"
										data-testid="tn-mobile-stage-remove-{idx}"
										aria-label={$t('trip.etappe_entfernen')}
										onclick={makeRemoveStageHandler(s.id)}
										style="background: transparent; border: none; cursor: pointer; color: var(--g-ink-4); font-size: 18px; padding: 0; min-width: 44px; min-height: 44px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; line-height: 1;">×</button>
								</div>
								<!-- GPX-Slot (volle Zeile) -->
								<div style="padding: 0 12px 12px;">
									{#if s.gpx}
										<div style="display: flex; align-items: center; gap: 12px; padding: 10px 14px; min-height: 56px; background: rgba(61,107,58,0.07); border: 1px solid rgba(61,107,58,0.22); border-radius: var(--g-r-2);">
											<div style="width: 32px; height: 32px; border-radius: 6px; flex-shrink: 0; background: var(--g-good); display: flex; align-items: center; justify-content: center;">
												<svg width="14" height="14" viewBox="0 0 10 10" fill="none"><polyline points="1.5,5.5 4,8 8.5,2" stroke="#fff" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>
											</div>
											<div style="flex: 1; min-width: 0;">
												<div class="mono" style="font-size: 12px; font-weight: 600; color: var(--g-ink-2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{s.gpx.file}</div>
												<div class="mono" style="font-size: 11px; color: var(--g-ink-3); margin-top: 1px;">{`${s.gpx.km} km · ↑${s.gpx.asc} m`}</div>
											</div>
											<button type="button" onclick={makeGpxRemoveHandler(s.id)}
												style="background: transparent; border: none; cursor: pointer; color: var(--g-ink-4); font-size: 18px; padding: 4px 6px; line-height: 1; min-height: 44px; flex-shrink: 0;">×</button>
										</div>
									{:else}
										<label style="display: flex; align-items: center; gap: 12px; width: 100%; padding: 12px 14px; min-height: 52px; background: var(--g-card); border: 1.5px dashed var(--g-rule); border-radius: var(--g-r-2); cursor: pointer; box-sizing: border-box;">
											<div style="width: 32px; height: 32px; border-radius: 6px; flex-shrink: 0; background: var(--g-accent-tint); border: 1px dashed var(--g-accent); display: flex; align-items: center; justify-content: center;">
												<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--g-accent-deep)" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
													<path d="M12 16V4M7 9l5-5 5 5"/><path d="M4 16v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3"/>
												</svg>
											</div>
											<span class="mono" style="font-size: 13px; font-weight: 600; color: var(--g-accent-deep); letter-spacing: 0.02em;">{$t('trip.anlegen.gpx_hochladen')}</span>
											<input type="file" accept=".gpx" style="display: none;" onchange={makeGpxUploadHandler(idx, s.id)} />
										</label>
									{/if}
								</div>
							</div>
						{/each}
					</div>

					<!-- Etappe hinzufügen -->
					<button type="button" onclick={makeAddStageHandler()}
						style="display: block; width: 100%; margin-top: 10px; padding: 13px; border: 1px dashed var(--g-rule); border-radius: var(--g-r-3); background: transparent; color: var(--g-ink-3); font-size: 14px; cursor: pointer; min-height: 48px;">
						{$t('trip.anlegen.etappe_hinzufuegen')}
					</button>

					{#if !etDone && stages.length > 0}
						<div style="margin-top: 14px; padding: 11px 14px; border-radius: var(--g-r-2); background: var(--g-paper-deep, var(--g-paper)); border: 1px solid var(--g-rule);">
							<span class="mono" style="font-size: 11px; color: var(--g-ink-3);">{$t('trip.anlegen.noch_gpx', { anzahl: stages.length - gpxCount })}</span>
						</div>
					{/if}
					{#if etDone && stages.length > 0}
						<div style="margin-top: 14px; padding: 11px 14px; border-radius: var(--g-r-2); background: rgba(61,107,58,0.08); border: 1px solid rgba(61,107,58,0.2);">
							<span class="mono" style="font-size: 11px; color: var(--g-good);">{$t('trip.anlegen.alle_gpx_kurz')}</span>
						</div>
					{/if}
				</div>

				<!-- Stage-Name-Sheet (Bottom-Sheet)
				     data-testid="tn-mobile-stage-sheet" auf dem äusseren Wrapper (vor Sheet),
				     damit scoped locator sheet.getByTestId('tn-mobile-stage-sheet-input') und
				     sheet.getByTestId('tn-mobile-stage-sheet-apply') beide gefunden werden. -->
				{#if mobileSheetStageId !== null}
					<div data-testid="tn-mobile-stage-sheet">
						<Sheet open={mobileSheetStageId !== null} onClose={() => { mobileSheetStageId = null; }}
							title={$t('trip.anlegen.etappenname')} snap="half">
							{#snippet footer()}
								<button type="button" data-testid="tn-mobile-stage-sheet-apply"
									onclick={makeMobileApplySheetHandler()}
									style="display: flex; align-items: center; justify-content: center; width: 100%; min-height: 48px; padding: 14px 18px; background: var(--g-ink); color: var(--g-paper); border: none; border-radius: var(--g-r-3); font-size: 15px; font-weight: 600; font-family: var(--g-font-sans); cursor: pointer;">
									{$t('trip.anlegen.uebernehmen')}
								</button>
							{/snippet}
							<div style="padding-top: 8px;">
								<input type="text" data-testid="tn-mobile-stage-sheet-input"
									value={mobileSheetStageName}
									oninput={(e) => { mobileSheetStageName = (e.target as HTMLInputElement).value; }}
									placeholder={$t('trip.anlegen.etappe_beispiel')}
									style="display: block; width: 100%; box-sizing: border-box; background: var(--g-card); border: 1px solid var(--g-rule); border-radius: var(--g-r-3); padding: 12px 14px; font-size: 16px; font-family: var(--g-font-sans); color: var(--g-ink); outline: none; min-height: 48px;" />
							</div>
						</Sheet>
					</div>
				{/if}

			{:else if activeTab === 'wegpunkte'}
				<!-- Mobile Wegpunkte-Tab: eingebetteter Editor mit eigenem Mobile-Layout (L1) -->
				<div style="position: relative; padding: 0 0 80px;">
					<!-- Issue #2521 S1 (AC-4): Infobox oben im optionalen Reiter. -->
					{#if isMobileViewport}<div style="padding: 12px 16px 0;"><Infobox reiter="wegpunkte" context="route" /></div>{/if}
					<div style="padding: 12px 16px; background: var(--g-accent-tint); border-bottom: 1px solid var(--g-accent-rule);">
						<div class="mono" style="font-size: 11px; color: var(--g-accent-deep); line-height: 1.55;">
							{$t('trip.anlegen.wegpunkte_auto')}
						</div>
					</div>
					<EditStagesPanelNew bind:stages={editorStages} showSave={false} bottomReservePx={mobileFooterHeightPx || undefined} />
				</div>

			{/if}

			<!-- Mobile Wetter-Tab: WeatherMetricsTab (bereits mobil, #618) -->
			<!-- Issue #932 — Aktivitätstyp-Dropdown lebt jetzt im Route-Tab. -->
			<!-- Issue #941 — WeatherMetricsTab bleibt beim Tab-Wechsel gemountet (per
			     display ausgeblendet). Fix-Loop 4 (s. Desktop-Mount oben): per
			     isMobileViewport-Gate nur EINE Instanz im DOM (Desktop XOR Mobile). -->
			{#if isMobileViewport}
			<div style:display={activeTab === 'wetter-metriken' ? '' : 'none'}>
				<!-- Issue #1743: geteilter Baustein, XOR zum Desktop-Mount oben. -->
				<WetterMetrikenVersandPanel context="route" trip={stubTrip} createMode={true} showInfobox={true} onChannelsChange={handleChannelsChange} onWeatherMetricsChange={handleWeatherMetricsChange} onDayWindowChange={handleDayWindowChange} bind:reportConfig onJump={onVersandJump} />
				<div style="padding: 0 16px 60px;">
					<MailInhaltCard bind:reportConfig />
				</div>
			</div>
			{/if}

			<!-- Issue #2277 S2a — Mobile CorridorEditor, XOR zum Desktop-Mount oben. -->
			{#if isMobileViewport}
			<div style:display={activeTab === 'wertebereiche' ? '' : 'none'}>
				<CorridorEditor context="route" trip={stubTrip} createMode={true} showInfobox={true} {corridors} onCorridorsChange={handleCorridorsChange} onVorbelegungFertig={handleVorbelegungFertig} />
			</div>
			{/if}

			<!-- Issue #2277 S1 — Mobile AlarmeTab, XOR zum Desktop-Mount oben. -->
			{#if isMobileViewport}
			<div style:display={activeTab === 'alarme' ? '' : 'none'}>
				<div style="padding: 16px 16px 60px;">
					<AlarmeTab context="route" trip={stubTrip} createMode={true} showInfobox={true}
						officialWarningsEnabled={alarm.officialWarningsEnabled}
						onOfficialWarningsChange={handleAlarmOfficialWarningsChange}
						cooldownMinutes={alarm.cooldownMinutes}
						onCooldownChange={handleAlarmCooldownChange}
						quietFrom={alarm.quietFrom}
						quietTo={alarm.quietTo}
						onQuietHoursChange={handleAlarmQuietHoursChange}
						onChannelToggle={handleAlarmChannelToggle}
						onThresholdChange={handleAlarmThresholdChange}
						activeMetrics={activeAlertMetrics}
						onMetricLevelChange={handleAlarmMetricLevelChange}
					/>
				</div>
			</div>
			{/if}

			<!-- Lock-Toast (2s bei Tap auf gesperrten Tab) -->
			{#if lockToastMsg}
				<div data-testid="tn-lock-toast">
					<Toast kind="info" msg={lockToastText ?? ''} />
				</div>
			{/if}
		</div>

			<!-- Sticky-Footer (geteilter Baustein; BottomNav ist auf Anlege-Seiten ausgeblendet):
			     Weiter-Aktion des Schritts, im letzten Schritt Alarme „Speichern" —
			     gleich gebaut wie cm-mobile-cta im Vergleich (#2347 S4, AN-9). -->
			<EditorStickyFooter context="route" navClearance={false} testid="tn-mobile-footer">
				{#if !ready}
					<div style="display: flex; justify-content: center; margin-bottom: 8px;">
						<StandardwerteSpeichernKnopf enabled={standardwerteFrei} {saving} onclick={onStandardwerte} testid="tn-mobile-standardwerte" />
					</div>
				{/if}
				{#if activeTab === 'alarme'}
					<MBtn block variant={ready ? 'primary' : 'quiet'} size="xl" disabled={!ready || saving} onclick={onSave} testid="tn-mobile-save">
						{saving ? $t('trip.anlegen.speichere') : savedTripId ? $t('trip.anlegen.gespeichert') : $t('aktionen.speichern')}
					</MBtn>
				{:else if activeTab === 'route'}
					<div data-testid="tn-mobile-route-cta">
						<!-- #2347 S4 (AC-20): gesperrt wie cm-mobile-cta im Vergleich — gleiche Bedingung wie der Handler. -->
						<MBtn block variant={name.trim() && startDate ? 'primary' : 'quiet'} size="xl"
							disabled={!(name.trim() && startDate)}
							onclick={makeMobileRouteContinueHandler()}>
							{name.trim() && startDate ? $t('trip.anlegen.etappen_anlegen') : (!name.trim() ? $t('trip.anlegen.name_eingeben') : $t('trip.anlegen.datum_waehlen'))}
						</MBtn>
					</div>
				{:else if activeTab === 'etappen'}
					{#if etDone}
						<div style="display: flex; flex-direction: column; gap: 8px;">
							<MBtn block variant="primary" size="xl" onclick={makeEtappenContinueHandler('wegpunkte')}>{$t('trip.anlegen.wegpunkte_pruefen')}</MBtn>
							<MBtn block variant="ghost" size="lg" onclick={makeEtappenContinueHandler('wetter-metriken')}>{$t('trip.anlegen.direkt_wetter')}</MBtn>
						</div>
					{:else}
						{@const restGpx = stages.length - gpxCount}
						<MBtn block variant="quiet" size="xl" disabled>{stages.length === 0 ? $t('trip.anlegen.etappe_hinzufuegen_kurz') : $t('trip.anlegen.gpx_noetig', { anzahl: restGpx })}</MBtn>
					{/if}
				{:else if activeTab === 'wegpunkte'}
					<div style="display: flex; flex-direction: column; gap: 8px;">
						<MBtn block variant="primary" size="xl" onclick={makeMobileWegpunkteContinueHandler()}>{$t('trip.anlegen.wegpunkte_uebernehmen')}</MBtn>
						<MBtn block variant="ghost" size="lg" onclick={makeMobileWegpunkteContinueHandler()}>{$t('trip.anlegen.ueberspringen')}</MBtn>
					</div>
				{:else if activeTab === 'wetter-metriken'}
					<MBtn block variant="primary" size="xl" onclick={makeEtappenContinueHandler('wertebereiche')}>{$t('trip.anlegen.wertebereiche_festlegen')}</MBtn>
				{:else if activeTab === 'wertebereiche'}
					<MBtn block variant="primary" size="xl" onclick={makeEtappenContinueHandler('alarme')}>{$t('trip.anlegen.alarme_einrichten')}</MBtn>
				{/if}
			</EditorStickyFooter>
		</div><!-- /.tn-mobile -->

	</main>
</div>

<!-- Bug #708 — Bestätigungs-Dialog für Etappen-Löschen (/trips/new) -->
<Dialog.Root
	open={pendingRemoveStageId !== null}
	onOpenChange={(open) => { if (!open) pendingRemoveStageId = null; }}
>
	<Dialog.Content>
		<Dialog.Header>
			<Dialog.Title>{$t('trip.etappe_loeschen')}</Dialog.Title>
			<Dialog.Description>
				{$t('trip.anlegen.loeschen_frage')}
			</Dialog.Description>
		</Dialog.Header>
		<Dialog.Footer>
			<Btn variant="outline" data-testid="cancel-delete-stage" onclick={() => { pendingRemoveStageId = null; }}>{$t('aktionen.abbrechen')}</Btn>
			<Btn variant="destructive" data-testid="confirm-delete-stage" onclick={confirmRemoveStage}>{$t('aktionen.delete')}</Btn>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>

<style>
	/* ── Issue #661: Responsive Mobile/Desktop Switching ────────────────────
	   Desktop-Markup ist sichtbar (≥900px), Mobile-Markup hidden.
	   Auf ≤899px: umgekehrt. CSS-only, kein JS-Viewport-Switch.
	   !important nötig, da .tn-mobile Elemente teilweise inline display:flex
	   haben (z.B. AppBar, TabBar) — !important schlägt Inline-Styles.
	   ─────────────────────────────────────────────────────────────────────── */
	.tn-mobile {
		display: none !important;
	}
	@media (max-width: 899px) {
		.tn-desktop {
			display: none !important;
		}
		/* Inline-style-Override: Elemente mit display:flex bleiben flex, andere block. */
		.tn-mobile {
			display: block !important;
		}
		.tn-mobile-flex {
			display: flex !important;
		}
	}
</style>
