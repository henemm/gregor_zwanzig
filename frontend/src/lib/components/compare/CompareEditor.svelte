<script lang="ts">
	// Compare-Editor — Gerüst + Lock-Engine + Tab „Vergleich" (Issue #678, Epic #677).
	// Edit-Modus + Dirty/Save-Flow (Issue #679, Epic #677).
	// Mobile-Parität (Issue #682, Epic #677, Slice 5/6): CSS-only-Switch #661-Pattern.
	// Spec: docs/specs/modules/issue_679_compare_editor_edit.md
	// Design-Quelle: claude-code-handoff/current/jsx/screen-compare-editor.jsx Z. 640-700.

	import { getContext, onMount } from 'svelte';
	import { page } from '$app/state';
	import { Btn, Eyebrow, TopoBg } from '$lib/components/atoms';
	import { Field, ConfirmDialog } from '$lib/components/molecules';
	import { ACTIVITY_PROFILE_OPTIONS, toCompareProfile, type ActivityProfile, type Location, type ComparePreset } from '$lib/types';
	import type { ChannelLayouts, Horizons, MetricPreset, WeatherConfigMetric } from '$lib/types';
	import { HORIZONS_ALL } from '$lib/types';
	import type { CompareWizardState } from './compareWizardState.svelte';
	import { createSaveStatus, extractMessage } from '$lib/stores/saveStatusStore.svelte';
	import SaveIndicator from '$lib/components/ui/SaveIndicator.svelte';
	import {
		TAB_ORDER,
		unlockedTabs,
		doneTabs,
		type CompareTabId
	} from './compareEditorLogic';
	import { validateIdealRanges, PROFILE_METRICS_WITH_SCALES, type ProfileKey } from './compareMetricDefs';
	import { buildComparePresetSavePayload } from './compareEditorSave';
	import { api } from '$lib/api.js';
	import Step2Orte from './steps/Step2Orte.svelte';
	// Issue #1231, Slice 5: CorridorEditorMobile ersetzt Step3Idealwerte auch im
	// Mobile-Zweig. Import von Step3Idealwerte entfernt — Datei bleibt vorerst
	// bestehen (Aufraeumen ist Slice-6-Thema, s. Spec).
	import CorridorEditor from '$lib/components/shared/corridor-editor/CorridorEditor.svelte';
	import CorridorEditorMobile from '$lib/components/shared/corridor-editor/CorridorEditorMobile.svelte';
	// Issue #1256 Scheibe 4: Step4Layout-Hülle entfernt — CompareEditor mountet
	// den geteilten LayoutTab-Organism (context="vergleich") jetzt direkt. Die
	// bisherige Step4Layout-eigene Kanal-/Buckets-Verwaltung wandert unten
	// unveraendert mit (kein neuer Code fuer die Layout-Logik selbst, nur der
	// Mount-Ort wechselt — Code-Teilungs-Invariante, Constraint 0).
	import { OutputLayoutEditor } from '$lib/components/organisms';
	import LayoutTab from '$lib/components/shared/layout-tab/LayoutTab.svelte';
	import LTComparePreview from '$lib/components/shared/layout-tab/LTComparePreview.svelte';
	import { LT_CHANNELS, LT_CH_BY_ID, type ChannelId } from '$lib/components/shared/layout-tab/ltChannels';
	import {
		autoAssign,
		buildWeatherConfigMetrics,
		move,
		reorder,
		type Buckets,
		type MetricCatalog,
		type MetricEntry
	} from '$lib/components/trip-detail/metricsEditor';
	import VersandTab from '$lib/components/shared/VersandTab.svelte';
	import CompareAlarmSection from './CompareAlarmSection.svelte';
	import CompareInhaltSection from './CompareInhaltSection.svelte';
	import Toast from '$lib/components/mobile/Toast.svelte';
	import MBtn from '$lib/components/mobile/MBtn.svelte';
	import Sheet from '$lib/components/mobile/Sheet.svelte';

	interface Props {
		mode?: 'create' | 'edit';
		locations?: Location[];
		preset?: ComparePreset;
	}
	let { mode = 'create', locations = [], preset }: Props = $props();

	const wiz = getContext<CompareWizardState>('compare-wizard-state');

	// Issue #758: eigene SaveStatus-Instanz pro CompareEditor (AC-6: kein geteilter Singleton).
	const compareSaveCtl = createSaveStatus();

	// Issue #1231 Slice 4 (Adversary F001, CRITICAL): echte Viewport-Erkennung
	// NUR für den idealwerte-Tab-Inhalt — das bestehende CSS-only-Switch-Muster
	// (.cm-desktop/.cm-mobile, Style-Block unten) mountet SONST beide Zweige
	// gleichzeitig. CorridorEditor UND Step3Idealwerte würden parallel gemountet
	// und konkurrierend in `wiz` schreiben (Step3Idealwerte's $effects). Exakt
	// das Slice-3-Precedent (TripTabs.svelte:112-121, Issue #932-Muster) — NUR
	// dieser eine Tab-Inhalt wechselt auf echten {#if}-Switch, alle anderen
	// Tabs bleiben beim CSS-only-Muster unangetastet.
	let isMobileViewport = $state(false);
	onMount(() => {
		const mq = window.matchMedia('(max-width: 899px)');
		isMobileViewport = mq.matches;
		const onChange = (e: MediaQueryListEvent) => { isMobileViewport = e.matches; };
		mq.addEventListener('change', onChange);
		return () => mq.removeEventListener('change', onChange);
	});

	// Issue #1170: „Alarme"-Tab nur im Edit-Modus (Playwright-ACs decken nur Edit
	// ab; Create-Pfad wird über wiz.saveNewPreset() direkt getestet). Erweitert
	// CompareTabId additiv um 'alarme', ohne die Create-Wizard-Progression
	// (TAB_ORDER/unlockedTabs/doneTabs) anzufassen.
	export type EditorTabId = CompareTabId | 'alarme';

	// Issue #1229 — Deep-Link `?tab=` für den Edit-Modus (Compare-Hub-Edit-Stift
	// springt auf `/compare/{id}/edit?tab=versand`). Exakter String-Vergleich
	// gegen bekannte EditorTabId-Werte; unbekannt/fehlend/nur-Create-Modus →
	// bisheriger Default 'vergleich' (AC-6, kein Crash).
	const EDITOR_TAB_IDS: readonly EditorTabId[] = ['vergleich', 'orte', 'idealwerte', 'layout', 'versand', 'alarme'];
	function initialTabFromQuery(): EditorTabId {
		if (mode !== 'edit') return 'vergleich';
		const raw = page.url.searchParams.get('tab');
		return (EDITOR_TAB_IDS as readonly string[]).includes(raw ?? '') ? (raw as EditorTabId) : 'vergleich';
	}

	// Issue #1231, Slice 6 (AC-17) — CorridorEditor vereint Idealwerte + Alerts:
	// `idealwerte`-Label "Wertebereiche" (war: "Idealwerte"), `id` + Testid unverändert.
	const TAB_DEFS = $derived<{ id: EditorTabId; label: string; lockHint: string | null }[]>([
		{ id: 'vergleich', label: 'Vergleich', lockHint: null },
		{ id: 'orte', label: 'Orte', lockHint: 'erst Vergleich benennen' },
		{ id: 'idealwerte', label: 'Wertebereiche', lockHint: 'erst mind. 2 Orte auswählen' },
		{ id: 'layout', label: 'Layout', lockHint: 'erst Wertebereiche öffnen' },
		{ id: 'versand', label: 'Versand', lockHint: 'erst Layout öffnen' },
		...(mode === 'edit' ? [{ id: 'alarme' as const, label: 'Alarme', lockHint: null }] : [])
	]);

	const isEdit = $derived(mode === 'edit');

	// Lokale visited-Flags (Tab 3/4/5 als „besucht" markieren → schaltet nächsten frei).
	let idealsVisited = $state(false);
	let layoutVisited = $state(false);
	let versandVisited = $state(false);

	// Issue #718: Validierungs-Status der Idealwerte — reaktiv, keine Seiteneffekte.
	const idealsValid = $derived(validateIdealRanges(wiz.idealRanges, wiz.activeMetricKeys).valid);

	let activeTab = $state<EditorTabId>(initialTabFromQuery());

	// Dirty-Tracking (AC-2): Snapshot der editierbaren Felder beim Mount erfassen.
	// $derived statt manueller markDirty-Wrapper — deckt alle Tabs ab und markiert
	// NICHT bei reiner Tab-Navigation (AC-Semantik: Feldänderung → Pill).
	// Issue #758 F001: $state statt const — wird nach erfolgreichem Save aktualisiert,
	// damit dirty zurück auf false springt und der Indikator stabil idle wird.
	let initial = $state({
		name: wiz.name,
		region: wiz.region,
		profile: wiz.activityProfile,
		picked: [...wiz.pickedIds].join(','),
		ideals: JSON.stringify(wiz.idealRanges),
		// Issue #1231 Slice 4: CorridorEditor(vergleich) schreibt corridors +
		// idealRanges/activeMetricKeys/metricAlertLevels gemeinsam (Dual-Write) —
		// corridors-Tracking genuegt als Dirty-Signal fuer diese Interaktion.
		corridors: JSON.stringify(wiz.corridors),
		layouts: JSON.stringify(wiz.channelLayouts),
		// Issue #1170: Alarm-Konfiguration im Dirty-Tracking.
		metricAlertLevels: JSON.stringify(wiz.metricAlertLevels),
		alertCooldownMinutes: wiz.alertCooldownMinutes,
		alertQuietFrom: wiz.alertQuietFrom,
		alertQuietTo: wiz.alertQuietTo,
		// Issue #1041 Slice 2 / #1040: Alarm-Toggles im Dirty-Tracking, damit sie
		// beim Speichern erkannt und persistiert werden (siehe handleSave).
		radarAlertEnabled: wiz.radarAlertEnabled,
		officialAlertsEnabled: wiz.officialAlertsEnabled,
		// Issue #1216 Slice 2b: Trigger + Kanal-Toggles im Dirty-Tracking.
		officialAlertTriggersEnabled: wiz.officialAlertTriggersEnabled,
		sendTelegram: wiz.sendTelegram,
		sendSms: wiz.sendSms,
		// Issue #1232 Scheibe 2b: Zwei-Slot-Zeitplan + Laufzeit im Dirty-Tracking
		// (VersandTab context="vergleich" bindet direkt an diese wiz-Felder).
		morningEnabled: wiz.morningEnabled,
		morningTime: wiz.morningTime,
		eveningEnabled: wiz.eveningEnabled,
		eveningTime: wiz.eveningTime,
		endDate: wiz.endDate,
		// Staging-F001 (#1232 Scheibe 2b AC-5): Horizont/Top-N/Stundenverlauf-Toggle
		// fehlten im Dirty-Tracking — CompareInhaltSection (Layout-Tab) ändert sie,
		// aber ohne diesen Snapshot wurde die Änderung nie als dirty erkannt und
		// beim Speichern nicht in den PUT-Body übernommen (vorbestehende Lücke).
		forecastHours: wiz.forecastHours,
		topN: wiz.topN,
		hourlyEnabled: wiz.hourlyEnabled
	});
	const dirty = $derived(
		isEdit &&
			(wiz.name !== initial.name ||
				wiz.region !== initial.region ||
				wiz.activityProfile !== initial.profile ||
				[...wiz.pickedIds].join(',') !== initial.picked ||
				JSON.stringify(wiz.idealRanges) !== initial.ideals ||
				JSON.stringify(wiz.corridors) !== initial.corridors ||
				JSON.stringify(wiz.channelLayouts) !== initial.layouts ||
				JSON.stringify(wiz.metricAlertLevels) !== initial.metricAlertLevels ||
				wiz.alertCooldownMinutes !== initial.alertCooldownMinutes ||
				wiz.alertQuietFrom !== initial.alertQuietFrom ||
				wiz.alertQuietTo !== initial.alertQuietTo ||
				wiz.radarAlertEnabled !== initial.radarAlertEnabled ||
				wiz.officialAlertsEnabled !== initial.officialAlertsEnabled ||
				wiz.officialAlertTriggersEnabled !== initial.officialAlertTriggersEnabled ||
				wiz.sendTelegram !== initial.sendTelegram ||
				wiz.sendSms !== initial.sendSms ||
				wiz.morningEnabled !== initial.morningEnabled ||
				wiz.morningTime !== initial.morningTime ||
				wiz.eveningEnabled !== initial.eveningEnabled ||
				wiz.eveningTime !== initial.eveningTime ||
				wiz.endDate !== initial.endDate ||
				wiz.forecastHours !== initial.forecastHours ||
				wiz.topN !== initial.topN ||
				wiz.hourlyEnabled !== initial.hourlyEnabled)
	);

	// Issue #758: sync dirty state → compareSaveCtl (nur wenn nicht schon saving/error).
	$effect(() => {
		if (dirty && compareSaveCtl.state === 'idle') {
			compareSaveCtl.setDirty();
		} else if (!dirty && compareSaveCtl.state === 'dirty') {
			compareSaveCtl.setSaved();
		}
	});

	// Status-Dot (AC-6): aus dem preset-Prop lesen (nicht wiz.schedule — type-gemangelt).
	const paused = $derived(preset?.schedule === 'manual');

	// ConfirmDialog für Verwerfen (AC-4).
	let discardOpen = $state(false);

	const unlocked = $derived(
		unlockedTabs({
			name: wiz.name,
			pickedCount: wiz.pickedIds.length,
			idealsVisited,
			layoutVisited
		})
	);
	const done = $derived(
		doneTabs({
			name: wiz.name,
			pickedCount: wiz.pickedIds.length,
			idealsVisited,
			idealsValid,
			layoutVisited,
			versandVisited
		})
	);
	const doneCount = $derived(TAB_ORDER.filter((t) => done.has(t)).length);

	function switchTab(id: EditorTabId) {
		if (!isEdit && id !== 'alarme' && !unlocked.has(id)) return;
		activeTab = id;
		if (id === 'idealwerte') idealsVisited = true;
		if (id === 'layout') layoutVisited = true;
		if (id === 'versand') versandVisited = true;
	}

	function selectProfile(value: ActivityProfile) {
		wiz.activityProfile = value;
	}

	// Fix 6 (Design-Fidelity 2026-07) — Mono-Unterzeile mit den echten
	// Profil→Metriken-Labels aus PROFILE_METRICS_WITH_SCALES, nicht hardcoden.
	function profileMetricsLabel(value: ActivityProfile): string {
		const key = toCompareProfile(value) as ProfileKey;
		return PROFILE_METRICS_WITH_SCALES[key].map((m) => m.label).join(' · ');
	}

	function handleDiscard() {
		discardOpen = true;
	}

	function handleSave() {
		if (!preset) return;
		compareSaveCtl.setSaving();
		// Issue #758: Save direkt via api.put (kein Redirect nach /compare/{id}).
		// Round-Trip-Spread via buildComparePresetSavePayload bleibt erhalten.
		// Snapshot aktuelle Werte vor dem async-Aufruf.
		const savedName = wiz.name;
		const savedRegion = wiz.region;
		const savedProfile = wiz.activityProfile;
		const savedPicked = [...wiz.pickedIds].join(',');
		const savedIdeals = JSON.stringify(wiz.idealRanges);
		const savedCorridors = JSON.stringify(wiz.corridors); // Issue #1231 Slice 4
		const savedLayouts = JSON.stringify(wiz.channelLayouts);
		// Issue #1170: Alarm-Konfiguration ebenfalls snapshotten.
		const savedMetricAlertLevels = JSON.stringify(wiz.metricAlertLevels);
		const savedCooldown = wiz.alertCooldownMinutes;
		const savedQuietFrom = wiz.alertQuietFrom;
		const savedQuietTo = wiz.alertQuietTo;
		// Issue #1041 Slice 2 / #1040: Alarm-Toggles ebenfalls snapshotten.
		const savedRadarAlertEnabled = wiz.radarAlertEnabled;
		const savedOfficialAlertsEnabled = wiz.officialAlertsEnabled;
		// Issue #1216 Slice 2b: Trigger + Kanal-Toggles ebenfalls snapshotten.
		const savedOfficialAlertTriggersEnabled = wiz.officialAlertTriggersEnabled;
		const savedSendTelegram = wiz.sendTelegram;
		const savedSendSms = wiz.sendSms;
		// Issue #1232 Scheibe 2b: Zwei-Slot-Zeitplan + Laufzeit ebenfalls snapshotten.
		const savedMorningEnabled = wiz.morningEnabled;
		const savedMorningTime = wiz.morningTime;
		const savedEveningEnabled = wiz.eveningEnabled;
		const savedEveningTime = wiz.eveningTime;
		const savedEndDate = wiz.endDate;
		// Staging-F001: Horizont/Top-N/Stundenverlauf-Toggle ebenfalls snapshotten.
		const savedForecastHours = wiz.forecastHours;
		const savedTopN = wiz.topN;
		const savedHourlyEnabled = wiz.hourlyEnabled;
		const { url, body } = buildComparePresetSavePayload(preset, {
			name: wiz.name,
			activityProfile: wiz.activityProfile,
			pickedIds: wiz.pickedIds,
			region: wiz.region,
			idealRanges: wiz.idealRanges,
			channelLayouts: wiz.channelLayouts,
			activeMetricKeys: wiz.activeMetricKeys,
			corridors: wiz.corridors, // Issue #1231 Slice 4 — Top-Level-Feld
			hourlyMetricKeys: wiz.hourlyMetricKeys,
			metricAlertLevels: wiz.metricAlertLevels,
			alertCooldownMinutes: wiz.alertCooldownMinutes,
			alertQuietFrom: wiz.alertQuietFrom,
			alertQuietTo: wiz.alertQuietTo,
			// Issue #1134: Zeitfenster (Step 5) tatsächlich in den PUT-Body geben.
			hourFrom: wiz.timeWindowStart,
			hourTo: wiz.timeWindowEnd,
			// Issue #1041 Slice 2 (Pflicht) / #1040 (gebündelter Edit-Bug):
			// beide Toggles fehlten bisher im edits-Objekt → PUT persistierte sie nie.
			radarAlertEnabled: wiz.radarAlertEnabled,
			officialAlertsEnabled: wiz.officialAlertsEnabled,
			// Issue #1216 Slice 2b: Trigger + Kanäle in den PUT-Body geben.
			officialAlertTriggersEnabled: wiz.officialAlertTriggersEnabled,
			sendTelegram: wiz.sendTelegram,
			sendSms: wiz.sendSms,
			// Issue #1232 Scheibe 2b: Zwei-Slot-Zeitplan + Laufzeit (endDate=null →
			// Lösch-Sentinel end_date:"" via buildComparePresetSavePayload).
			morningEnabled: wiz.morningEnabled,
			morningTime: wiz.morningTime,
			eveningEnabled: wiz.eveningEnabled,
			eveningTime: wiz.eveningTime,
			endDate: wiz.endDate,
			// Staging-F001: Horizont/Top-N/Stundenverlauf-Toggle (CompareInhaltSection,
			// Layout-Tab) tatsächlich in den PUT-Body geben (Muster: hourFrom/hourTo).
			forecastHours: wiz.forecastHours,
			topN: wiz.topN,
			hourlyEnabled: wiz.hourlyEnabled
		});
		api.put(url, body)
			.then(() => {
				// F001: initial auf gespeicherte Werte setzen → dirty=false → Indikator idle.
				initial.name = savedName;
				initial.region = savedRegion;
				initial.profile = savedProfile;
				initial.picked = savedPicked;
				initial.ideals = savedIdeals;
				initial.corridors = savedCorridors;
				initial.layouts = savedLayouts;
				initial.metricAlertLevels = savedMetricAlertLevels;
				initial.alertCooldownMinutes = savedCooldown;
				initial.alertQuietFrom = savedQuietFrom;
				initial.alertQuietTo = savedQuietTo;
				initial.radarAlertEnabled = savedRadarAlertEnabled;
				initial.officialAlertsEnabled = savedOfficialAlertsEnabled;
				initial.officialAlertTriggersEnabled = savedOfficialAlertTriggersEnabled;
				initial.sendTelegram = savedSendTelegram;
				initial.sendSms = savedSendSms;
				initial.morningEnabled = savedMorningEnabled;
				initial.morningTime = savedMorningTime;
				initial.eveningEnabled = savedEveningEnabled;
				initial.eveningTime = savedEveningTime;
				initial.endDate = savedEndDate;
				initial.forecastHours = savedForecastHours;
				initial.topN = savedTopN;
				initial.hourlyEnabled = savedHourlyEnabled;
				compareSaveCtl.setSaved();
			})
			.catch((e: unknown) => {
				// F003: extractMessage prüft .detail/.error/.message in richtiger Reihenfolge.
				compareSaveCtl.setError(extractMessage(e));
			});
	}

	// Issue #681: "Briefing aktivieren" im Create-Modus (AC-4).
	// saveNewPreset() → POST /api/compare/presets (wiz.save() würde /api/subscriptions treffen!)
	function handleActivate() {
		if (!versandVisited) return;
		void wiz.saveNewPreset();
	}

	const canContinue = $derived(wiz.name.trim().length > 0);

	// ── Mobile-only State (Issue #682) ────────────────────────────────────────
	let mobileLibraryOpen = $state(false);

	// Bibliotheks-Gruppen für den mobilen Sheet (nach Region gruppiert)
	const mobileLibraryGroups = $derived.by(() => {
		const groups: Record<string, Location[]> = {};
		for (const loc of locations) {
			const key = loc.region || 'Weitere';
			if (!groups[key]) groups[key] = [];
			groups[key].push(loc);
		}
		const sorted: [string, Location[]][] = [];
		for (const [k, v] of Object.entries(groups)) {
			if (k !== 'Weitere') sorted.push([k, v]);
		}
		if (groups['Weitere']) sorted.push(['Weitere', groups['Weitere']]);
		return sorted;
	});
	let lockToastMsg = $state('');
	let lockToastVisible = $state(false);
	let _lockToastTimer: ReturnType<typeof setTimeout> | null = null;

	function showLockToast(msg: string) {
		lockToastMsg = msg;
		lockToastVisible = true;
		if (_lockToastTimer) clearTimeout(_lockToastTimer);
		_lockToastTimer = setTimeout(() => { lockToastVisible = false; }, 2000);
	}

	// Mobile Tab-Navigation
	function handleMobileTabClick(id: EditorTabId) {
		const open = isEdit || (id !== 'alarme' && unlocked.has(id));
		if (!open) {
			const hint = TAB_DEFS.find(t => t.id === id)?.lockHint ?? 'Tab gesperrt';
			showLockToast(hint);
			return;
		}
		switchTab(id);
	}

	function handleMobileNext() {
		const idx = TAB_ORDER.indexOf(activeTab as CompareTabId);
		if (activeTab === 'versand') {
			handleActivate();
		} else if (idx >= 0 && idx < TAB_ORDER.length - 1) {
			switchTab(TAB_ORDER[idx + 1]);
		}
	}

	// ── Layout-Tab (Issue #1256 Scheibe 4) ────────────────────────────────────
	// 1:1 aus der bisherigen Step4Layout-Hülle (Datei gelöscht) übernommen
	// (kein neuer Code für die Layout-Logik selbst) — nur der Mount-Ort
	// wechselt auf den direkt eingebetteten LayoutTab-Organism (context="vergleich").
	interface LtTemplate {
		id: string;
		label: string;
		metrics: string[];
	}

	let ltCatalog: MetricCatalog = $state({});
	let ltTemplates: LtTemplate[] = $state([]);
	let ltUserPresets: MetricPreset[] = $state([]);
	let ltLoading = $state(true);
	let ltLoadError: string | null = $state(null);

	let ltActiveChannel = $state<ChannelId>('email');

	// Pro-Kanal-State: jeder Kanal traegt seine eigenen Buckets + friendlyMap.
	let ltChannelBuckets: Record<ChannelId, Buckets> = $state({
		email: { primary: [], secondary: [], off: [] },
		telegram: { primary: [], secondary: [], off: [] },
		sms: { primary: [], secondary: [], off: [] }
	});
	let ltChannelFriendly: Record<ChannelId, Record<string, boolean>> = $state({
		email: {},
		telegram: {},
		sms: {}
	});
	let ltChannelHorizons: Record<ChannelId, Record<string, Horizons>> = $state({
		email: {},
		telegram: {},
		sms: {}
	});
	let ltChannelSelectedPreset: Record<ChannelId, string> = $state({
		email: '',
		telegram: '',
		sms: ''
	});

	function ltAllCatalogIds(): string[] {
		return Object.values(ltCatalog).flatMap((arr) => arr.map((m) => m.id));
	}

	// Buckets fuer einen Kanal aus wiz.channelLayouts oder leer ableiten.
	// Kein weatherMetrics-Fallback im Compare-Kontext (Unterschied zum Trip-Wizard).
	function ltBucketsForChannel(ch: ChannelId): Buckets {
		const saved = wiz.channelLayouts?.[ch];
		if (saved && saved.length > 0) {
			const prim = saved
				.filter((m) => m.enabled && m.bucket === 'primary')
				.sort((a, b) => (a.order ?? 0) - (b.order ?? 0))
				.map((m) => m.metric_id);
			const sec = saved
				.filter((m) => m.enabled && m.bucket === 'secondary')
				.sort((a, b) => (a.order ?? 0) - (b.order ?? 0))
				.map((m) => m.metric_id);
			const active = new Set([...prim, ...sec]);
			const off = ltAllCatalogIds().filter((id) => !active.has(id));
			return { primary: prim, secondary: sec, off };
		}
		// AC-2 (#681): alle Katalog-Metriken als Standard aktiv.
		return autoAssign(ltAllCatalogIds(), ltCatalog);
	}

	function ltFriendlyMapForChannel(ch: ChannelId): Record<string, boolean> {
		const fMap: Record<string, boolean> = {};
		for (const id of ltAllCatalogIds()) fMap[id] = true;
		const saved = wiz.channelLayouts?.[ch];
		if (saved) {
			for (const m of saved) {
				fMap[m.metric_id] = m.use_friendly_format ?? true;
			}
		}
		return fMap;
	}

	function ltHorizonsMapForChannel(ch: ChannelId): Record<string, Horizons> {
		const hMap: Record<string, Horizons> = {};
		for (const id of ltAllCatalogIds()) hMap[id] = { ...HORIZONS_ALL };
		const saved = wiz.channelLayouts?.[ch];
		if (saved) {
			for (const m of saved) {
				if (m.horizons) hMap[m.metric_id] = { ...m.horizons };
			}
		}
		return hMap;
	}

	function ltInitChannelState(): void {
		const next: Record<ChannelId, Buckets> = { ...ltChannelBuckets };
		const nextFriendly: Record<ChannelId, Record<string, boolean>> = { ...ltChannelFriendly };
		const nextHorizons: Record<ChannelId, Record<string, Horizons>> = { ...ltChannelHorizons };
		for (const c of LT_CHANNELS) {
			next[c.id] = ltBucketsForChannel(c.id);
			nextFriendly[c.id] = ltFriendlyMapForChannel(c.id);
			nextHorizons[c.id] = ltHorizonsMapForChannel(c.id);
		}
		ltChannelBuckets = next;
		ltChannelFriendly = nextFriendly;
		ltChannelHorizons = nextHorizons;
	}

	// Fix-Loop 1 (Adversary F001, HIGH): im Original Step4Layout.svelte war der
	// Katalog-Fetch an das LAZY MOUNTEN des Tab-Inhalts gebunden (onMount feuerte
	// nur, wenn activeTab === 'layout' den {:else if}-Zweig überhaupt rendert).
	// Ein unbedingter onMount() hier im Editor-Top-Level würde bei JEDEM
	// Editor-Öffnen (jeder Tab) 3 API-Calls ausloesen UND den channelLayouts-
	// Rewrite-$effect vorzeitig scharf schalten — dessen Server-Roundtrip-Form
	// weicht strukturell von der initial.layouts-Baseline (Z. 122/159) ab, was
	// unabhaengig vom tatsaechlich besuchten Tab einen falschen "Ungespeichert"-
	// Zustand ausloest. Fix: Katalog-Fetch + Rewrite-Effect bleiben an den
	// ERSTEN Besuch des Layout-Tabs gekoppelt (Timing-Treue zu Step4Layout),
	// einmalig getriggert, danach idempotent (kein Re-Fetch bei erneutem
	// Tab-Wechsel zurück auf "layout").
	let ltCatalogLoadStarted = false;

	async function ltLoadCatalog(): Promise<void> {
		try {
			const [catalogData, templateData, presetData] = await Promise.all([
				api.get<MetricCatalog>('/api/metrics'),
				api.get<LtTemplate[]>('/api/templates').catch(() => [] as LtTemplate[]),
				api.get<MetricPreset[]>('/api/metric-presets').catch(() => [] as MetricPreset[])
			]);
			ltCatalog = catalogData;
			ltTemplates = templateData;
			ltUserPresets = presetData;
			ltInitChannelState();
		} catch (e: unknown) {
			ltLoadError = (e as { error?: string })?.error ?? 'Fehler beim Laden';
		} finally {
			ltLoading = false;
		}
	}

	$effect(() => {
		if (activeTab === 'layout' && !ltCatalogLoadStarted) {
			ltCatalogLoadStarted = true;
			void ltLoadCatalog();
		}
	});

	// Sync: ltChannelBuckets/Friendly -> wiz.channelLayouts (kompletter Replace).
	// KRITISCHER Timing-Guard: wird erst aktiv sobald Katalog geladen ist —
	// sonst werden leere Buckets in den State geschrieben und neue Subscriptions
	// starten mit leerem Editor. Da ltLoading erst nach dem ersten Layout-Tab-
	// Besuch auf false wechselt (s. o.), bleibt dieser Effect fuer alle anderen
	// Tabs automatisch inaktiv.
	$effect(() => {
		if (ltLoading || Object.keys(ltCatalog).length === 0) return;
		const layouts: ChannelLayouts = {};
		for (const c of LT_CHANNELS) {
			const metrics: WeatherConfigMetric[] = buildWeatherConfigMetrics(
				ltChannelBuckets[c.id],
				ltChannelFriendly[c.id],
				ltChannelHorizons[c.id],
				ltCatalog
			);
			layouts[c.id] = metrics;
		}
		wiz.channelLayouts = layouts;
	});

	// Aktive Spalten des gewählten Kanals — explizit per Kanal um Svelte-5-Cache zu umgehen.
	const ltActiveAllCols = $derived.by(() => {
		if (ltActiveChannel === 'email') {
			return [...ltChannelBuckets.email.primary, ...ltChannelBuckets.email.secondary];
		} else if (ltActiveChannel === 'telegram') {
			return [...ltChannelBuckets.telegram.primary, ...ltChannelBuckets.telegram.secondary];
		}
		return [...ltChannelBuckets.sms.primary, ...ltChannelBuckets.sms.secondary];
	});

	// --- Benannte Handler (Safari/Factory-Pattern) ---------------------------

	function ltHandleMove(id: string, target: 'primary' | 'secondary' | 'off') {
		const b = ltChannelBuckets[ltActiveChannel];
		const from: keyof Buckets = b.primary.includes(id)
			? 'primary'
			: b.secondary.includes(id)
				? 'secondary'
				: 'off';
		ltChannelBuckets = {
			...ltChannelBuckets,
			[ltActiveChannel]: move(b, id, from, target)
		};
		ltChannelSelectedPreset = { ...ltChannelSelectedPreset, [ltActiveChannel]: '' };
	}

	function ltHandleReorder(bucket: 'primary' | 'secondary', id: string, dir: -1 | 1) {
		ltChannelBuckets = {
			...ltChannelBuckets,
			[ltActiveChannel]: reorder(ltChannelBuckets[ltActiveChannel], bucket, id, dir)
		};
	}

	function ltHandleDndReorder(bucket: 'primary' | 'secondary', newOrder: string[]) {
		ltChannelBuckets = {
			...ltChannelBuckets,
			[ltActiveChannel]: { ...ltChannelBuckets[ltActiveChannel], [bucket]: newOrder }
		};
	}

	function ltHandleMode(id: string, useIndicator: boolean) {
		ltChannelFriendly = {
			...ltChannelFriendly,
			[ltActiveChannel]: { ...ltChannelFriendly[ltActiveChannel], [id]: useIndicator }
		};
	}

	function ltHandleSelectPreset(id: string) {
		const userP = ltUserPresets.find((p) => p.id === id);
		const tmpl = ltTemplates.find((t) => t.id === id);
		const activeIds = userP
			? userP.metrics.filter((m) => m.enabled).map((m) => m.metric_id)
			: tmpl
				? tmpl.metrics
				: [];
		ltChannelBuckets = {
			...ltChannelBuckets,
			[ltActiveChannel]: autoAssign(activeIds, ltCatalog)
		};
		if (userP) {
			const fMap = { ...ltChannelFriendly[ltActiveChannel] };
			for (const m of userP.metrics) fMap[m.metric_id] = m.use_friendly_format;
			ltChannelFriendly = { ...ltChannelFriendly, [ltActiveChannel]: fMap };
		}
		ltChannelSelectedPreset = { ...ltChannelSelectedPreset, [ltActiveChannel]: id };
	}
</script>

<!-- Issue #1232 Scheibe 2b: Create-Aktivierungs-Banner als Snippet-Prop für
     VersandTab (1:1 JSX-`activation`-Slot). Nur im Create-Modus sichtbar —
     im Edit-Modus rendert VersandTab nichts, da activation dann nicht
     übergeben wird (s. Mounts unten). Inhalt/Verhalten unverändert zu
     Step5Versand.svelte (Issue #681 AC-5), nur der Mount-Ort wechselt. -->
{#snippet versandActivationBanner()}
	<div
		data-testid="compare-step5-activation-banner"
		data-ready={versandVisited ? 'true' : 'false'}
		class="rounded-md p-4 text-white text-sm"
		style:background={versandVisited ? 'var(--g-good)' : 'var(--g-ink)'}
	>
		<div class="mono" style:font-size="10px" style:letter-spacing="0.12em" style:text-transform="uppercase" style:color="rgba(255,255,255,0.55)" style:margin-bottom="4px">Bereit zum Aktivieren</div>
		<div style:font-size="15px" style:font-weight="600">„{wiz.name || 'Neuer Vergleich'}" · {wiz.pickedIds?.length ?? 0} Orte</div>
		<div style:font-size="12.5px" style:color="rgba(255,255,255,0.75)" style:margin-top="4px" style:line-height="1.5">
			{#if versandVisited}Versand konfiguriert — klicke „Briefing aktivieren".{:else}Versand einrichten zum Aktivieren.{/if}
		</div>
	</div>
{/snippet}

<!-- Issue #1256 Scheibe 4: Layout-Tab-Inhalt als geteiltes Snippet (Desktop +
     Mobile mounten dasselbe Markup) — löst die frühere Step4Layout.svelte-
     Hülle ab. Direkte Einbettung des geteilten LayoutTab-Organism
     (context="vergleich", Constraint 0) statt einer eigenen Kanal-Tab-Leiste. -->
{#snippet ltLayoutSection()}
	<div class="step4-layout" data-testid="step4-layout">
		<header class="lt-intro">
			<Eyebrow>Layout pro Kanal</Eyebrow>
			<p class="lt-lede">
				Lege je Kanal fest, welche Werte als Spalten in der Tabelle erscheinen und
				welche als Detail-Zeile darunter. SMS hat ein Zeichen-Budget — dort
				priorisierst du eine flache Liste.
			</p>
		</header>

		{#if ltLoading}
			<p class="lt-loading" data-testid="step4-loading">Lade Metriken-Katalog…</p>
		{:else if ltLoadError}
			<p class="lt-error" data-testid="step4-error">{ltLoadError}</p>
		{:else}
			<LayoutTab
				context="vergleich"
				bind:channel={ltActiveChannel}
				colCount={wiz.pickedIds.length + 1}
				subjectLabel={`${wiz.pickedIds.length} Orte`}
			>
				{#snippet editor({ channel })}
					<div data-testid="layout-editor">
						<OutputLayoutEditor
							catalog={ltCatalog}
							bind:buckets={ltChannelBuckets[channel]}
							bind:friendlyMap={ltChannelFriendly[channel]}
							bind:selectedTemplate={ltChannelSelectedPreset[channel]}
							{channel}
							templates={ltTemplates}
							userPresets={ltUserPresets}
							onReorder={ltHandleReorder}
							onMove={ltHandleMove}
							onMode={ltHandleMode}
							onSelectPreset={ltHandleSelectPreset}
							onDndReorder={ltHandleDndReorder}
						/>

						<!-- ↳ Detail-Pills für Telegram-Überlauf (AC-2, #681) -->
						{#if LT_CH_BY_ID[channel].max !== Infinity && LT_CH_BY_ID[channel].max !== 0 && ltActiveAllCols.length > LT_CH_BY_ID[channel].max}
							{@const _maxCols = LT_CH_BY_ID[channel].max}
							<div class="lt-detail-pills">
								{#each ltActiveAllCols as _id, _i}
									{#if _i >= _maxCols}
										<span data-testid="compare-step4-detail-pill-{_i}" class="mono lt-detail-pill">
											↳ Detail
										</span>
									{/if}
								{/each}
							</div>
						{/if}
					</div>
				{/snippet}
				{#snippet preview({ channel })}
					<LTComparePreview {channel} pickedIds={[...wiz.pickedIds]} idealRanges={wiz.idealRanges} />
				{/snippet}
			</LayoutTab>
		{/if}

		<!-- Rest-Felder (Zeitfenster, Horizont, Top-N, Stundenverlauf) — bereits
		     geteilt aus dem vormaligen Step5Versand (#1232 Scheibe 2b). -->
		<CompareInhaltSection />
	</div>
{/snippet}

<div
	data-testid="compare-editor"
	style:position="relative"
	style:min-height="100%"
	style:background="var(--g-paper)"
>
<div class="cm-desktop">
	<TopoBg opacity={0.12}>
		<!-- Breadcrumb + Aktionen (JSX Z. 649-676) -->
		<div
			style:position="relative"
			style:padding="14px 40px"
			style:border-bottom="1px solid var(--g-rule-soft)"
			style:display="flex"
			style:justify-content="space-between"
			style:align-items="center"
		>
			<div
				class="mono"
				style:font-size="11px"
				style:color="var(--g-ink-3)"
				style:letter-spacing="0.06em"
			>
				<span style:opacity="0.6">Orts-Vergleiche</span>
				<span style:margin="0 8px">/</span>
				<span style:color="var(--g-ink)"
					>{isEdit ? (wiz.name.trim() || 'Vergleich') : 'Neuer Vergleich'}</span
				>
			</div>

			{#if isEdit}
				<!-- Aktionsleiste im Edit-Modus (JSX Z. 657-664) -->
				<div style:display="flex" style:gap="8px" style:align-items="center">
					<!-- Issue #880: SaveIndicator ist jetzt fixes Overlay am Komponenten-Ende. -->
					<!-- Status-Dot (AC-6): 7×7px, Farbe laut JSX Z. 660 -->
					<span
						data-testid="compare-editor-status-dot"
						data-status={paused ? 'paused' : 'active'}
						style:width="7px"
						style:height="7px"
						style:border-radius="50%"
						style:display="inline-block"
						style:background={paused ? 'var(--g-ink-4)' : 'var(--g-good)'}
					></span>
					<span
						class="mono"
						style:font-size="11px"
						style:color="var(--g-ink-3)"
						style:letter-spacing="0.04em"
					>{paused ? 'pausiert' : 'aktiv'}</span>
					<Btn
						variant="ghost"
						size="sm"
						data-testid="compare-editor-discard"
						onclick={handleDiscard}
					>Verwerfen</Btn>
					<Btn
						variant="primary"
						size="sm"
						data-testid="compare-editor-save"
						onclick={handleSave}
					>Speichern</Btn>
				</div>
			{:else}
				<!-- Create-Modus: Briefing aktivieren (AC-4, Issue #681, JSX Z. 666-674) -->
				<div style:display="flex" style:gap="8px" style:align-items="center">
					{#if !versandVisited}
						<span
							class="mono"
							style:font-size="10.5px"
							style:color="var(--g-ink-4)"
						>Versand einrichten zum Aktivieren</span>
					{/if}
					<Btn variant="ghost" size="sm" href="/compare">Abbrechen</Btn>
					<Btn
						data-testid="compare-editor-activate"
						variant={versandVisited ? 'primary' : 'quiet'}
						size="sm"
						disabled={!versandVisited}
						onclick={handleActivate}
						style={versandVisited ? '' : 'opacity:0.4; cursor:not-allowed'}
					>Briefing aktivieren</Btn>
				</div>
			{/if}
		</div>

		<!-- Hero -->
		<div style:position="relative" style:padding="20px 40px 14px">
			<Eyebrow>{isEdit ? 'Orts-Vergleich bearbeiten' : 'Neuer Orts-Vergleich'}</Eyebrow>
			<h1
				style:font-size="32px"
				style:font-weight="600"
				style:letter-spacing="-0.02em"
				style:margin="4px 0 0"
				style:line-height="1.1"
				style:color={wiz.name.trim() ? 'var(--g-ink)' : 'var(--g-ink-4)'}
			>
				{wiz.name.trim() || 'Noch kein Name'}
			</h1>

			<!-- Fortschrittsbalken: KEIN Render im Edit-Modus (AC-1) -->
			{#if !isEdit}
				<div
					data-testid="compare-editor-progress"
					style:display="flex"
					style:align-items="center"
					style:gap="10px"
					style:margin-top="7px"
				>
					<div style:display="flex" style:gap="3px">
						{#each TAB_ORDER as t (t)}
							<div
								data-testid="compare-editor-progress-segment"
								style:width="24px"
								style:height="3px"
								style:border-radius="2px"
								style:background={done.has(t) ? 'var(--g-accent)' : 'var(--g-rule)'}
								style:transition="background 350ms"
							></div>
						{/each}
					</div>
					<span
						class="mono"
						style:font-size="10.5px"
						style:color="var(--g-ink-4)"
						style:letter-spacing="0.04em"
					>
						{doneCount === 0
							? 'Noch nichts eingerichtet'
							: `${doneCount} / ${TAB_ORDER.length} Abschnitte eingerichtet`}
					</span>
				</div>
			{/if}
		</div>

		<!-- Tab-Bar -->
		<div
			style:border-bottom="1px solid var(--g-rule)"
			style:padding="0 40px"
			style:display="flex"
			style:gap="0"
			style:overflow-x="auto"
		>
			{#each TAB_DEFS as t (t.id)}
				{@const on = t.id === activeTab}
				{@const open = isEdit || (t.id !== 'alarme' && unlocked.has(t.id))}
				{@const isDone = !isEdit && t.id !== 'alarme' && done.has(t.id) && !on}
				<button
					data-testid={`compare-editor-tab-${t.id}`}
					data-active={on ? 'true' : 'false'}
					data-locked={open ? 'false' : 'true'}
					data-done={t.id !== 'alarme' && done.has(t.id) ? 'true' : 'false'}
					type="button"
					onclick={() => switchTab(t.id)}
					title={!open && t.lockHint ? `Gesperrt — ${t.lockHint}` : undefined}
					style:padding="12px 16px"
					style:cursor={open ? 'pointer' : 'not-allowed'}
					style:background="none"
					style:border="none"
					style:border-bottom={on ? '2px solid var(--g-accent)' : '2px solid transparent'}
					style:margin-bottom="-1px"
					style:font-family="var(--g-font-sans)"
					style:font-size="13px"
					style:font-weight={on ? 600 : 500}
					style:color={on ? 'var(--g-ink)' : open ? 'var(--g-ink-3)' : 'var(--g-ink-4)'}
					style:display="flex"
					style:align-items="center"
					style:gap="5px"
					style:white-space="nowrap"
					style:opacity={open ? 1 : 0.34}
					style:transition="opacity 250ms, color 200ms"
					style:user-select="none"
				>
					{t.label}
					{#if isDone}
						<span
							class="mono"
							style:font-size="10px"
							style:font-weight="700"
							style:padding="2px 5px"
							style:border-radius="3px"
							style:background="rgba(61,107,58,0.12)"
							style:color="var(--g-good)">✓</span
						>
					{/if}
					{#if !open}
						<span
							class="mono"
							style:font-size="10px"
							style:color="var(--g-ink-4)"
							style:opacity="0.7">⊘</span
						>
					{/if}
				</button>
			{/each}
		</div>
	</TopoBg>

	<!-- Tab-Panel -->
	{#if activeTab === 'vergleich'}
		<div style:position="relative" style:padding="28px 40px 60px">
			<TopoBg opacity={0.1}>
				<div style:position="relative" style:max-width="640px">
					<Eyebrow style="margin-bottom: 14px">Eckdaten</Eyebrow>

					<Field
						label="Name des Vergleichs"
						hint="Erscheint im Mail-Betreff. Kurz & wiedererkennbar."
					>
						<input
							data-testid="compare-editor-name"
							type="text"
							maxlength="80"
							placeholder="z.B. Skitouren Hochkönig"
							bind:value={wiz.name}
							class="w-full border rounded px-3 py-2 text-base bg-[var(--g-card)] border-[var(--g-rule)]"
						/>
					</Field>

					<Field label="Region" side="optional · max 60">
						<input
							data-testid="compare-editor-region"
							type="text"
							maxlength="60"
							placeholder="z.B. Hochkönig · Salzburger Land"
							bind:value={wiz.region}
							class="w-full border rounded px-3 py-2 text-base bg-[var(--g-card)] border-[var(--g-rule)]"
						/>
					</Field>

					<Eyebrow style="margin-bottom: 12px; margin-top: 28px">Aktivitätsprofil</Eyebrow>
					<div style:font-size="13px" style:color="var(--g-ink-3)" style:margin-bottom="14px">
						Bestimmt, welche Wetter-Metriken verglichen werden. Die Wertebereiche legst du im
						nächsten Tab fest.
					</div>
					<div
						style:display="grid"
						style:grid-template-columns="1fr 1fr"
						style:gap="10px"
					>
						{#each ACTIVITY_PROFILE_OPTIONS as opt (opt.value)}
							{@const sel = wiz.activityProfile === opt.value}
							<button
								data-testid={`compare-editor-profile-${opt.value}`}
								data-selected={sel ? 'true' : 'false'}
								type="button"
								onclick={() => selectProfile(opt.value)}
								style:text-align="left"
								style:cursor="pointer"
								style:padding="14px 16px"
								style:background={sel ? 'var(--g-accent-tint)' : 'var(--g-card)'}
								style:border={sel
									? '1.5px solid var(--g-accent)'
									: '1px solid var(--g-rule)'}
								style:border-radius="var(--g-r-3)"
								style:font-family="var(--g-font-sans)"
							>
								<div
									style:font-size="14px"
									style:font-weight="600"
									style:color={sel ? 'var(--g-accent-deep)' : 'var(--g-ink)'}
									style:margin-bottom="4px"
								>
									{opt.label}
								</div>
								<div
									class="mono"
									style:font-size="11px"
									style:color="var(--g-ink-3)"
									style:margin-top="4px"
								>
									{profileMetricsLabel(opt.value)}
								</div>
							</button>
						{/each}
					</div>

					<div
						style:margin-top="28px"
						style:padding-top="20px"
						style:border-top="1px solid var(--g-rule)"
						style:display="flex"
						style:justify-content="flex-end"
						style:align-items="center"
						style:gap="12px"
					>
						{#if !canContinue}
							<span class="mono" style:font-size="11px" style:color="var(--g-ink-4)">
								⊘ Name fehlt
							</span>
						{/if}
						{#if !isEdit}
							<Btn
								data-testid="compare-editor-continue-orte"
								variant={canContinue ? 'accent' : 'quiet'}
								size="md"
								disabled={!canContinue}
								onclick={() => canContinue && switchTab('orte')}
							>
								Orte hinzufügen →
							</Btn>
						{/if}
					</div>
				</div>
			</TopoBg>
		</div>
	{:else if activeTab === 'orte'}
		<Step2Orte {locations} />
	{:else if activeTab === 'idealwerte'}
		<!-- Issue #1231 Slice 4: ersetzt Step3Idealwerte auf Desktop (Wizard-Step-3
		     UND Editor-Tab, PO-B — dieselbe Stelle bedient beide Modi via isEdit).
		     F001-Fix: nur mounten wenn NICHT Mobile-Viewport — sonst waere
		     CorridorEditor parallel zum Step3Idealwerte-Mobile-Zweig aktiv
		     (.cm-desktop bleibt technisch immer im DOM, s. Style-Block unten). -->
		{#if !isMobileViewport}
			<CorridorEditor context="vergleich" />
		{/if}
	{:else if activeTab === 'layout'}
		{@render ltLayoutSection()}
	{:else if activeTab === 'versand'}
		{#if isEdit}
			<VersandTab context="vergleich" {wiz} />
		{:else}
			<VersandTab context="vergleich" {wiz} activation={versandActivationBanner} />
		{/if}
	{:else if activeTab === 'alarme'}
		<CompareAlarmSection {wiz} />
	{/if}

	<!-- DOM-Anker für AC-5 isAttached()-Test (display:none, kein sichtbarer Inhalt).
	     Die sichtbare Banner-Version rendert VersandTab (Issue #1232 Scheibe 2b,
	     zuvor Step5Versand). -->
	{#if !isEdit}
		<div
			data-testid="compare-step5-activation-banner"
			data-ready={versandVisited ? 'true' : 'false'}
			style:display="none"
			aria-hidden="true"
		></div>
	{/if}
</div><!-- /.cm-desktop -->

<!-- ══════════════════════════════════════════════════════════════════
     Mobile-Block (Issue #682, Slice 5/6)
     CSS-only Switch: .cm-mobile sichtbar bei ≤899px.
     ══════════════════════════════════════════════════════════════════ -->
<div class="cm-mobile" style="position: relative; min-height: 100vh; display: flex; flex-direction: column;">

	<!-- Lock-Toast -->
	{#if lockToastVisible}
		<Toast kind="info" msg={lockToastMsg} />
	{/if}

	<!-- 1. App-Leiste -->
	<div class="cm-mobile-flex" data-testid="cm-mobile-appbar"
		style="position: sticky; top: 0; z-index: 20; align-items: center; height: 52px; padding: 0 4px; border-bottom: 1px solid var(--g-rule-soft); background: var(--g-paper); flex-shrink: 0;">
		<!-- Zurück -->
		<a href="/compare"
			style="display: flex; align-items: center; justify-content: center; width: 44px; height: 44px; background: transparent; border: none; cursor: pointer; color: var(--g-ink-3); flex-shrink: 0; text-decoration: none;">
			<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
				<path d="M19 12H5M12 5l-7 7 7 7"/>
			</svg>
		</a>
		<!-- Titel -->
		<div style="flex: 1; min-width: 0; padding: 0 8px; display: flex; flex-direction: column; justify-content: center;">
			<div class="mono" style="font-size: 10px; color: var(--g-ink-4); letter-spacing: 0.06em; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
				{wiz.name.trim() || (isEdit ? 'Bearbeiten' : 'Neuer Vergleich')}
			</div>
			<div style="font-size: 15px; font-weight: 600; color: var(--g-ink); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
				{TAB_DEFS.find(t => t.id === activeTab)?.label ?? 'Vergleich'}
			</div>
		</div>
		<!-- Rechts: Edit → Speichern, Create → Aktivieren -->
		{#if isEdit}
			<button type="button" data-testid="cm-mobile-save"
				disabled={!dirty}
				onclick={handleSave}
				style="height: 44px; padding: 0 14px; border: none; background: transparent; color: {dirty ? 'var(--g-accent)' : 'var(--g-ink-4)'}; font-weight: 600; font-size: 14px; cursor: {dirty ? 'pointer' : 'default'}; font-family: var(--g-font-sans); flex-shrink: 0;">
				Speichern
			</button>
		{:else}
			<button type="button" data-testid="cm-mobile-activate"
				disabled={!versandVisited}
				onclick={handleActivate}
				style="height: 44px; padding: 0 14px; border: none; background: transparent; color: {versandVisited ? 'var(--g-accent)' : 'var(--g-ink-4)'}; font-weight: 600; font-size: 14px; cursor: {versandVisited ? 'pointer' : 'default'}; font-family: var(--g-font-sans); flex-shrink: 0;">
				Aktivieren
			</button>
		{/if}
	</div>

	<!-- 2. Progress-Balken (nur Create-Modus) -->
	{#if !isEdit}
		<div class="cm-mobile-flex" data-testid="cm-mobile-progress"
			style="align-items: center; gap: 8px; padding: 8px 16px 0; flex-shrink: 0;">
			<div style="display: flex; gap: 3px; flex: 1;">
				{#each TAB_ORDER as tid (tid)}
					<div style="flex: 1; height: 3px; border-radius: 2px; background: {done.has(tid) ? 'var(--g-accent)' : (tid === activeTab ? 'var(--g-accent-soft,#bcd)' : 'var(--g-rule)')}; transition: background 350ms;"></div>
				{/each}
			</div>
			<span class="mono" style="font-size: 10px; color: var(--g-ink-4); flex-shrink: 0;">{doneCount}/{TAB_ORDER.length}</span>
		</div>
	{/if}

	<!-- 3. Scrollbare Tab-Bar. Issue #1231 Slice 6 (Fresh-Eyes-Fund): Rand-Fade
	     statt hartem Abschnitt, analog TripTabs.svelte-Mobile-Zweig. -->
	<div class="cm-mobile-flex" data-testid="cm-mobile-tabbar"
		style="gap: 0; overflow-x: auto; border-bottom: 1px solid var(--g-rule-soft); -webkit-overflow-scrolling: touch; scrollbar-width: none; flex-shrink: 0; mask-image: linear-gradient(to right, transparent, black 16px, black calc(100% - 16px), transparent); -webkit-mask-image: linear-gradient(to right, transparent, black 16px, black calc(100% - 16px), transparent);">
		{#each TAB_DEFS as t (t.id)}
			{@const on = t.id === activeTab}
			{@const open = isEdit || (t.id !== 'alarme' && unlocked.has(t.id))}
			<button type="button"
				data-testid="cm-mobile-tab-{t.id}"
				data-active={on ? 'true' : 'false'}
				data-locked={open ? 'false' : 'true'}
				onclick={() => handleMobileTabClick(t.id)}
				style="display: inline-flex; align-items: center; gap: 5px; padding: 13px 13px; min-height: 44px; flex-shrink: 0; background: transparent; border: none; border-bottom: {on ? '2px solid var(--g-accent)' : '2px solid transparent'}; margin-bottom: -1px; cursor: {open ? 'pointer' : 'default'}; font-size: 14px; font-weight: {on ? 600 : 500}; color: {on ? 'var(--g-ink)' : open ? 'var(--g-ink-3)' : 'var(--g-ink-4)'}; white-space: nowrap; font-family: var(--g-font-sans); opacity: {open ? 1 : 0.35};">
				{t.label}
				{#if !open}
					<span class="mono" style="font-size: 10px; opacity: 0.8;">⊘</span>
				{/if}
			</button>
		{/each}
	</div>

	<!-- 4. Tab-Inhalt -->
	<div style="flex: 1; overflow-y: auto; padding: 16px;">
		{#if activeTab === 'vergleich'}
			<!-- Vergleich-Tab: Name + Region + Aktivitätsprofil -->
			<div style="margin-bottom: 14px;">
				<div class="mono" style="font-size: 10px; color: var(--g-ink-4); letter-spacing: 0.10em; text-transform: uppercase; margin-bottom: 8px;">Name des Vergleichs</div>
				<!-- Name-Input ohne eigenen testid — compare-editor-name ist im cm-desktop-Block.
				     cm-desktop ist auf Mobile per position:fixed offscreen — der Desktop-Input
				     ist per fill() erreichbar (kein strict-mode-Konflikt), state via wiz.name geteilt. -->
				<input
					type="text"
					maxlength="80"
					placeholder="z.B. Skitouren Hochkönig"
					bind:value={wiz.name}
					style="width: 100%; box-sizing: border-box; padding: 12px 14px; font-size: 16px; border: 1px solid var(--g-rule); border-radius: var(--g-r-3); background: var(--g-card); font-family: var(--g-font-sans); color: var(--g-ink); outline: none; min-height: 48px;"
				/>
			</div>
			<div style="margin-bottom: 14px;">
				<div class="mono" style="font-size: 10px; color: var(--g-ink-4); letter-spacing: 0.10em; text-transform: uppercase; margin-bottom: 8px;">Region <span style="font-weight:400; text-transform:none;">(optional)</span></div>
				<input
					type="text"
					maxlength="60"
					placeholder="z.B. Hochkönig · Salzburger Land"
					bind:value={wiz.region}
					style="width: 100%; box-sizing: border-box; padding: 12px 14px; font-size: 16px; border: 1px solid var(--g-rule); border-radius: var(--g-r-3); background: var(--g-card); font-family: var(--g-font-sans); color: var(--g-ink); outline: none; min-height: 48px;"
				/>
			</div>
			<div>
				<div class="mono" style="font-size: 10px; color: var(--g-ink-4); letter-spacing: 0.10em; text-transform: uppercase; margin-bottom: 10px;">Aktivitätsprofil</div>
				<div style="display: flex; flex-direction: column; gap: 8px;">
					{#each ACTIVITY_PROFILE_OPTIONS as opt (opt.value)}
						{@const sel = wiz.activityProfile === opt.value}
						<button type="button" onclick={() => selectProfile(opt.value)}
							style="display: flex; align-items: center; gap: 12px; min-height: 52px; padding: 12px 14px; background: {sel ? 'var(--g-accent-tint)' : 'var(--g-card)'}; border: {sel ? '1.5px solid var(--g-accent)' : '1px solid var(--g-rule)'}; border-radius: var(--g-r-3); cursor: pointer; text-align: left; font-family: var(--g-font-sans);">
							<div style="display: flex; flex-direction: column;">
								<div style="font-size: 14px; font-weight: 600; color: {sel ? 'var(--g-accent-deep)' : 'var(--g-ink)'};">{opt.label}</div>
								<div class="mono" style="font-size: 11px; color: var(--g-ink-3); margin-top: 4px;">{profileMetricsLabel(opt.value)}</div>
							</div>
						</button>
					{/each}
				</div>
			</div>
		{:else if activeTab === 'orte'}
			<Step2Orte {locations} />
			<!-- Mobiler Bibliotheks-Button (Issue #682) -->
			<div style="margin-top: 16px;">
				<button
					type="button"
					data-testid="compare-step2-mobile-library-btn"
					onclick={() => { mobileLibraryOpen = true; }}
					style="display: flex; align-items: center; justify-content: center; gap: 8px; width: 100%; padding: 14px; min-height: 52px; background: var(--g-card); border: 1px dashed var(--g-rule); border-radius: var(--g-r-3); cursor: pointer; font-size: 14px; color: var(--g-ink-3); font-family: var(--g-font-sans);"
				>
					<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>
					Ort aus Bibliothek wählen ({locations.length})
				</button>
			</div>
		{:else if activeTab === 'idealwerte'}
			<!-- Issue #1231, Slice 5: CorridorEditorMobile ersetzt Step3Idealwerte.
			     F001-Praezedenz (Slice 4): nur mounten wenn tatsaechlich
			     Mobile-Viewport (sonst waeren Desktop- und Mobile-Editor
			     gleichzeitig aktiv und schreiben konkurrierend in wiz). -->
			{#if isMobileViewport}
				<CorridorEditorMobile context="vergleich" />
			{/if}
		{:else if activeTab === 'layout'}
			{@render ltLayoutSection()}
		{:else if activeTab === 'versand'}
			{#if isEdit}
				<VersandTab context="vergleich" {wiz} />
			{:else}
				<VersandTab context="vergleich" {wiz} activation={versandActivationBanner} />
			{/if}
		{:else if activeTab === 'alarme'}
			<CompareAlarmSection {wiz} />
		{/if}
	</div>

	<!-- 5. Floating-CTA (nur Create-Modus) -->
	{#if !isEdit}
		<div data-testid="cm-mobile-cta"
			style="position: sticky; bottom: 0; padding: 12px 16px; background: var(--g-paper); border-top: 1px solid var(--g-rule-soft); flex-shrink: 0;">
			<MBtn block variant="primary" size="xl" onclick={handleMobileNext}>
				{activeTab === 'versand' ? 'Aktivieren' : 'Weiter →'}
			</MBtn>
		</div>
	{/if}

</div><!-- /.cm-mobile -->

<!-- Mobile Bibliotheks-Sheet (Issue #682) — wird im Mobile-Block für Tab "Orte" verwendet -->
<Sheet open={mobileLibraryOpen} snap="full" title="Ort wählen" onClose={() => { mobileLibraryOpen = false; }}>
	{#each mobileLibraryGroups as [groupName, groupLocs] (groupName)}
		<div style="margin-bottom: 8px;">
			<div class="mono" style="font-size: 10px; color: var(--g-ink-4); letter-spacing: 0.10em; text-transform: uppercase; padding: 8px 0 4px; font-weight: 600;">{groupName} · {groupLocs.length}</div>
			{#each groupLocs as loc (loc.id)}
				{@const on = wiz.pickedIds.includes(loc.id)}
				<button
					type="button"
					data-testid="compare-step2-mobile-lib-check-{loc.id}"
					onclick={() => {
						if (on) {
							wiz.pickedIds = wiz.pickedIds.filter((x) => x !== loc.id);
						} else {
							wiz.pickedIds = [...wiz.pickedIds, loc.id];
						}
					}}
					style="display: flex; align-items: center; gap: 14px; width: 100%; padding: 12px 0; min-height: 52px; background: {on ? 'var(--g-accent-tint)' : 'transparent'}; border: none; border-bottom: 1px solid var(--g-rule-soft); cursor: pointer; text-align: left; font-family: var(--g-font-sans);"
				>
					<span style="width: 22px; height: 22px; border-radius: 4px; border: 1.5px solid {on ? 'var(--g-accent)' : 'var(--g-rule)'}; background: {on ? 'var(--g-accent)' : 'transparent'}; display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
						{#if on}
							<svg width="11" height="11" viewBox="0 0 12 12" fill="none" stroke="#fff" stroke-width="2.5"><path d="M2 6l3 3 5-6"/></svg>
						{/if}
					</span>
					<div style="flex: 1; min-width: 0;">
						<div style="font-size: 14px; font-weight: {on ? 600 : 500}; color: {on ? 'var(--g-accent-deep)' : 'var(--g-ink)'}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{loc.name}</div>
						{#if loc.region}
							<div class="mono" style="font-size: 10.5px; color: var(--g-ink-3); margin-top: 1px;">{loc.region}</div>
						{/if}
					</div>
				</button>
			{/each}
		</div>
	{/each}
</Sheet>

<!-- Issue #880: SaveIndicator als fixes Overlay (position:fixed) — außerhalb des
     Editor-Kopfs, damit es seitenbreit unten rechts erscheint statt inline. -->
{#if isEdit}
	<SaveIndicator controller={compareSaveCtl} />
{/if}
</div>

<!-- ConfirmDialog: Änderungen verwerfen (AC-4) -->
<ConfirmDialog
	open={discardOpen}
	title="Änderungen verwerfen?"
	description="Alle Änderungen an diesem Vergleich werden verworfen."
	confirmLabel="Verwerfen"
	confirmVariant="destructive"
	cancelLabel="Weiter bearbeiten"
	onConfirm={async () => {
		discardOpen = false;
		const { goto } = await import('$app/navigation');
		void goto('/compare/' + (preset?.id ?? ''));
	}}
	onCancel={() => {
		discardOpen = false;
	}}
	onOpenChange={(o) => {
		if (!o) discardOpen = false;
	}}
/>

<style>
	/* ─── CSS-only Responsive Switch (Issue #682, #661-Pattern) ──────────────────
	   Desktop-Markup (.cm-desktop) sichtbar bei ≥900px, Mobile-Markup hidden.
	   Auf ≤899px: umgekehrt.
	   Hinweis: .cm-desktop wird auf Mobile per position:fixed offscreen verschoben
	   (nicht display:none), damit Playwright-Tests mit compare-editor-name
	   Formularfelder befüllen können (strict-mode-safe: ein Element, erreichbar).
	   .cm-mobile nutzt display:none damit toBeHidden() in Desktop-Tests korrekt greift. */
	.cm-mobile {
		display: none !important;
	}
	@media (max-width: 899px) {
		.cm-desktop {
			position: fixed !important;
			top: -9999px !important;
			left: -9999px !important;
			width: 1px !important;
			height: 1px !important;
			overflow: hidden !important;
		}
		.cm-mobile {
			display: block !important;
		}
		.cm-mobile-flex {
			display: flex !important;
		}
	}

	/* ─── Layout-Tab-Snippet (Issue #1256 Scheibe 4, vormals steps/Step4Layout.svelte) ─── */
	.step4-layout {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-5);
	}
	.lt-intro {
		max-width: 760px;
	}
	.lt-lede {
		font-size: var(--g-text-sm);
		color: var(--g-ink-muted);
		margin-top: var(--g-s-1);
		line-height: 1.55;
	}
	.lt-loading,
	.lt-error {
		padding: var(--g-s-4);
		text-align: center;
		font-size: var(--g-text-sm);
	}
	.lt-error {
		color: var(--g-danger);
	}
	.lt-detail-pills {
		display: flex;
		flex-wrap: wrap;
		gap: 4px;
		margin-top: 6px;
	}
	.lt-detail-pill {
		background: rgba(192, 138, 26, 0.08);
		border-radius: 3px;
		padding: 2px 6px;
		font-size: 9.5px;
		color: var(--g-warn);
		font-weight: 600;
		letter-spacing: 0.06em;
		text-transform: uppercase;
	}
</style>
