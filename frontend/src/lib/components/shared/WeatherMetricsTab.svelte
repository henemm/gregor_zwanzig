<script lang="ts">
	// Issue #587 v2 — Wetter-Metriken-Tab: 4-Abschnitte-Editor + Live-Mail-Vorschau (Desktop).
	// Issue #618 — Mobile: 4 Abschnitte vertikal + Mail-Bottom-Sheet (Legacy #415 entfernt).
	// LÖST AB: OutputLayoutEditor-basiertes Layout (Issue #364/#431).
	// BEWAHRT: initFromTrip, handleSave, bucketsToColumns-Migration, telegramKurzform,
	//          read-modify-write-Payload, SavePresetDialog.
	// SCHÜTZT: OutputLayoutEditor, BucketSection*, ActiveMetricRow bleiben UNVERÄNDERT
	//          (Wizard + Orts-Vergleich nutzen sie).
	// Spec: docs/specs/modules/issue_587_weather_tab_v2.md
	// Spec: docs/specs/modules/issue_618_mobile_weather_tab.md
	import { api } from '$lib/api.js';
	import type { Trip, MetricPreset, Horizons, ReportConfig } from '$lib/types';
	import { HORIZONS_ALL } from '$lib/types';
	import { Btn, Card, Eyebrow, Pill } from '$lib/components/atoms';
	// Issue #1311 (C1, Fix-Loop 1 / F001): private Sub-Komponenten von
	// WeatherMetricsTab mitverschoben nach shared/weather-metrics-tab/ (kein
	// weiterer Importeur, s. grep-Beweis in der Fix-Loop-Rueckmeldung).
	// metricsEditor.ts/weatherSaveGate.ts bleiben bewusst in trip-detail/ —
	// beide sind breit geteilt (CompareEditor.svelte Legacy, CompareTabs.svelte,
	// OutputLayoutEditor.svelte, ltChannels.ts u.a.) und wurden NICHT von C1
	// eingefuehrt; sie umzuziehen haette CompareEditor.svelte (Legacy) beruehrt,
	// was ausserhalb des C1-Scopes liegt (CLAUDE.md: "NICHT anfassen").
	import SavePresetDialog from './weather-metrics-tab/SavePresetDialog.svelte';
	import Sheet from '$lib/components/mobile/Sheet.svelte';
	// v2 Sub-Komponenten (neu, standalone, keine Abhängigkeit von OutputLayoutEditor)
	import WeatherV2PresetBar from './weather-metrics-tab/WeatherV2PresetBar.svelte';
	import WeatherV2Grundauswahl from './weather-metrics-tab/WeatherV2Grundauswahl.svelte';
	import WeatherV2Reihenfolge from './weather-metrics-tab/WeatherV2Reihenfolge.svelte';
	// WeatherV2Kanaele entfernt in Issue #736 (Kanal-Config → Versand-Reiter)
	import WeatherV2MailPreview from './weather-metrics-tab/WeatherV2MailPreview.svelte';
	// Issue #1232 Scheibe 3b: geteilter Layout-Organism (Scheibe 3a) ersetzt das
	// bisherige `.v2-layout`-Grid für den Ausgabe-Teil (Reihenfolge + Vorschau).
	import LayoutTab from '$lib/components/shared/layout-tab/LayoutTab.svelte';
	import type { ChannelId } from '$lib/components/shared/layout-tab/ltChannels';
	import ThresholdMetricRow from './weather-metrics-tab/ThresholdMetricRow.svelte';
	import EditReportConfigSection from '$lib/components/edit/EditReportConfigSection.svelte';
	// Issue #1117: „Amtliche Warnungen"-Checkbox auch im Inhalt-Tab (eigener Block,
	// EditReportConfigSection bleibt unverändert).
	import * as UiCard from '$lib/components/ui/card/index.js';
	import { Checkbox } from '$lib/components/ui/checkbox';
	import {
		autoAssign, bucketsToColumns, move, buildWeatherConfigMetrics,
		diffHighlight,
		CATEGORY_LABELS, CATEGORY_ORDER, indicatorCapable,
		type Buckets, type MetricEntry, type MetricCatalog, type Highlight, type WeatherSnapshot,
	} from '../trip-detail/metricsEditor.ts';
	// Issue #1234: Daten-/Absichts-Gate gegen stillen Metrik-Leerungs-Autosave.
	import { weatherSaveGate } from '../trip-detail/weatherSaveGate.ts';
	// Issue #1269 (a): Mount-Kanonisierung (EditReportConfigSection) darf nicht
	// als Nutzeraenderung zaehlen — geteilter Baustein (Trip + Ortsvergleich).
	import { reportConfigChangedByUser } from '$lib/components/shared/reportConfigDirty';
	// Issue #1311 (C1 von Epic #1301): geteilter Baustein Trip + Ortsvergleich
	// (Vorbild AlarmeTab.svelte) — context-Dispatch + Vergleich-Grundauswahl.
	import type { CompareWizardState } from '$lib/components/compare/compareWizardState.svelte';
	import { weatherMetricsTabSections, type WeatherMetricsContext } from './weather-metrics-tab/weatherMetricsTabSections.ts';
	// Issue #1350 Teil 2: Vergleich-Auswahlliste kommt jetzt aus GET
	// /api/compare/metrics statt aus COMPARE_METRIC_DEFS (bleibt fuer
	// Schwellen-Slider/Winner-Box/Save-Default-Fallback unveraendert, Teil 3).
	import { toCompareSelectionEntries, type CompareSelectionEntry } from './weather-metrics-tab/compareMetricSelection.ts';
	import type { CompareMetricCatalogResponse } from '$lib/types';

	interface Template {
		id: string;
		label: string;
		metrics: string[];
	}
	interface ChannelConfig {
		email: boolean;
		telegram: boolean;
		sms: boolean;
	}
	import type { SaveStatus } from '$lib/stores/saveStatusStore.svelte';

	interface SmsSymbolEntry {
		metric_id: string;
		sms_symbol: string;
	}
	interface SmsSymbolCatalog {
		metrics: SmsSymbolEntry[];
		hazards: { hazard: string; sms_symbol: string; label: string }[];
	}

	interface Props {
		/** Issue #1311: 'route' (Trip, Default) | 'vergleich' (Ortsvergleich). */
		context?: WeatherMetricsContext;
		// route (unveraendert)
		trip?: Trip;
		/** Issue #622: Create-Modus — kein PUT; Kanäle per onChannelsChange nach oben emittieren */
		createMode?: boolean;
		onChannelsChange?: (c: ChannelConfig) => void;
		/** Issue #694: Trip-State in +page.svelte nach erfolgreichem PUT aktualisieren */
		onTripUpdate?: (t: Trip) => void;
		/** Issue #758: SaveStatus controller — wenn gesetzt, entfällt der explizite Speichern-Button. */
		saveController?: SaveStatus;
		// vergleich (neu, Issue #1311)
		wiz?: CompareWizardState;
	}
	let { context = 'route', trip, createMode = false, onChannelsChange, onTripUpdate, saveController, wiz }: Props = $props();

	// Issue #1311: Abschnittsreihenfolge kommt aus einer reinen Funktion, kein
	// Duplikat der Reihenfolge im Markup (AC-1, AC-8-Attrappen-Verbot).
	const sections = $derived(weatherMetricsTabSections(context));

	let catalog: MetricCatalog = $state({});
	// Issue #1318 AC-9: SMS-Kuerzel kommen ausschliesslich aus dem Backend
	// (/api/sms-symbols -> hazard_symbols.py + sms_trip.py). Hier steht bewusst
	// KEINE Zuordnung Gefahrenart/Metrik -> Kuerzel — eine zweite Liste im
	// Frontend koennte still von der SMS abweichen, die der Nutzer wirklich
	// bekommt.
	let smsSymbols = $state<SmsSymbolCatalog | null>(null);
	const metricSymbols = $derived(
		Object.fromEntries(
			(smsSymbols?.metrics ?? []).map((m: SmsSymbolEntry) => [m.metric_id, m.sms_symbol])
		)
	);
	let templates: Template[] = $state([]);
	let userPresets: MetricPreset[] = $state([]);
	// Issue #1234 (2a): wird NUR bei erfolgreichem Katalog-Fetch wahr (nicht im
	// finally-Block) — der Render-Guard haengt daran statt an einem separaten
	// `loading`-Flag (Fix-Loop 2 / F002: totes `loading`-State entfernt, es
	// wurde nirgends gelesen).
	let catalogLoaded = $state(false);
	// Issue #1234 (2b): eigener Zustand fuer Ladefehler, getrennt von saveError
	// (Speicherfehler) — sonst wuerde ein Ladefehler durch einen spaeteren
	// Speicherstatus ueberschrieben werden bzw. umgekehrt.
	let loadError: string | null = $state(null);
	// Issue #1350 Teil 2: eigenstaendiger Ladezustand fuer die Vergleich-
	// Auswahlliste (GET /api/compare/metrics) — bewusst getrennt vom Route-
	// Zustand (catalog/catalogLoaded/loadError) oben, damit der Route-Fetch
	// unangetastet bleibt (Spec compare_metric_selection_source.md § 2).
	let compareCatalog: CompareSelectionEntry[] = $state([]);
	let compareCatalogLoaded = $state(false);
	let compareCatalogError: string | null = $state(null);
	// Issue #1234 (2c, Fix-Loop 1 / F001): Absichts-Merker — AUSSCHLIESSLICH aus
	// echten DOM-Ereignissen gesetzt (Interaktions-Handler oder Capture-Phase-
	// Listener auf der Report-Config-Karte), niemals in einem $effect.
	let userTouched = $state(false);
	let saving = $state(false);
	let saveSuccess = $state(false);
	let saveError: string | null = $state(null);

	// Bucket-State (secondary IMMER leer nach #587 — kein Detail-Bucket).
	let buckets: Buckets = $state({ primary: [], secondary: [], off: [] });
	let friendlyMap: Record<string, boolean> = $state({});
	let horizonsMap: Record<string, Horizons> = $state({});
	let selectedTemplate = $state('');
	// Issue #587: Kanal-Konfiguration (kein Signal). display_config ist additiv
	// — channels wird als unbekanntes Feld durchgereicht, daher Cast über unknown.
	let channels: ChannelConfig = $state(
		((trip?.display_config as unknown as Record<string, unknown>)?.channels as ChannelConfig | undefined)
			?? { email: true, telegram: true, sms: false }
	);
	// Issue #614: Telegram Kurzform-Toggle (SMS-Tages-Max als Anhang).
	let telegramKurzform = $state<boolean>(trip?.display_config?.telegram_kurzform ?? false);
	// Issue #1117: Amtliche Warnungen im E-Mail-Briefing (zweiter Einstiegspunkt neben
	// Alerts-Tab). Default true matcht den Backend-Default.
	let officialAlertsEnabled = $state<boolean>(trip?.official_alerts_enabled ?? true);
	// Issue #624: konfigurierbare Schwellwerte pro Metrik (nur threshold-fähige).
	const SMS_THRESHOLD_METRIC_IDS = ['precipitation', 'rain_probability', 'wind', 'gust', 'thunder', 'snow_depth', 'snowfall_limit'];
	let smsThresholds = $state<Record<string, string>>({});
	let savedSnapshot = $state('');
	let showSavePresetDialog = $state(false);
	let mailSheetOpen = $state(false);
	let pendingPreset: string | null = $state(null);
	let profile = $state<{ mail_to?: string; telegram_chat_id?: string; sms_to?: string } | null>(null);
	// Issue #736: E-Mail-Inhalt-Karte im Inhalt-Reiter (analog BriefingScheduleTab).
	let reportConfig = $state<ReportConfig>(
		trip?.report_config ? JSON.parse(JSON.stringify(trip.report_config)) : {}
	);

	// availableChannels entfernt in Issue #736 (WeatherV2Kanaele nicht mehr im Inhalt-Reiter)

	// Issue #1232 Scheibe 3b: Kanal des geteilten LayoutTab-Organism — reiner
	// View-State (analog Scheibe 3a im Compare-Editor), NIE in snapshot()/isDirty.
	let activeChannel = $state<ChannelId>('email');

	// AC-2 Diff-Highlight: 2,5s Aufleuchten nach jeder Änderung.
	let highlight: Highlight | null = $state(null);
	let highlightTimer: ReturnType<typeof setTimeout> | null = null;

	function flash(h: Highlight | null) {
		if (highlightTimer) clearTimeout(highlightTimer);
		highlight = h;
		if (h) {
			highlightTimer = setTimeout(() => { highlight = null; highlightTimer = null; }, 2500);
		}
	}

	function prevSnapshot(): WeatherSnapshot {
		return {
			columns: [...buckets.primary],
			mode: Object.fromEntries(
				buckets.primary.map(id => [id, friendlyMap[id] === true ? 'indicator' : 'raw'])
			) as Record<string, 'raw' | 'indicator'>,
			presetId: selectedTemplate,
		};
	}

	function applyDiff(nextCols: string[], nextMode: Record<string, boolean>, nextPresetId: string) {
		const prev = prevSnapshot();
		const next: WeatherSnapshot = {
			columns: nextCols,
			mode: Object.fromEntries(nextCols.map(id => [id, nextMode[id] === true ? 'indicator' : 'raw'])) as Record<string, 'raw' | 'indicator'>,
			presetId: nextPresetId,
		};
		flash(diffHighlight(prev, next));
	}

	// Abgeleitete Lookups.
	const metricById = $derived.by(() => {
		const map: Record<string, MetricEntry> = {};
		for (const ms of Object.values(catalog)) for (const m of ms) map[m.id] = m;
		return map;
	});
	const shortById = $derived.by(() => {
		const map: Record<string, string> = {};
		for (const id of Object.keys(metricById)) {
			const label = metricById[id].label;
			map[id] = label.length > 6 ? label.slice(0, 6) : label;
		}
		return map;
	});

	// Issue #736: channels aus isDirty + snapshot entfernt (Kanal-Config lebt jetzt im Versand-Reiter).
	// Issue #776/#774: reportConfig in isDirty einschliessen (Toggle-Persistenz, Checkbox-Änderung macht Tab dirty).
	const isDirty = $derived(
		JSON.stringify({ buckets, friendlyMap, horizonsMap, telegramKurzform, smsThresholds, reportConfig, officialAlertsEnabled }) !== savedSnapshot,
	);

	function snapshot(
		b: Buckets, f: Record<string, boolean>, h: Record<string, Horizons>,
		tk: boolean, st: Record<string, string>, rc: ReportConfig | undefined, oae: boolean
	): string {
		return JSON.stringify({ buckets: b, friendlyMap: f, horizonsMap: h, telegramKurzform: tk, smsThresholds: st, reportConfig: rc ?? {}, officialAlertsEnabled: oae });
	}

	function allCatalogIds(): string[] {
		return CATEGORY_ORDER.filter((c) => c in catalog)
			.concat(Object.keys(catalog).filter((c) => !CATEGORY_ORDER.includes(c)))
			.flatMap((c) => (catalog[c] ?? []).map((m) => m.id));
	}

	function initFromTrip() {
		const fMap: Record<string, boolean> = {};
		const hMap: Record<string, Horizons> = {};
		for (const id of allCatalogIds()) {
			fMap[id] = true;
			hMap[id] = { ...HORIZONS_ALL };
		}

		// initFromTrip() ist ausschliesslich ueber load() (route-only, s.
		// $effect-Guard) oder handleDiscard() (route-only Button) erreichbar —
		// trip! ist hier sicher (Issue #1311, Fix-Loop 1: context-Prop optional).
		const savedMetrics = trip!.display_config?.metrics;
		let b: Buckets;
		const hasBuckets = savedMetrics?.some((m) => m.bucket || m.order !== undefined);

		if (savedMetrics && hasBuckets) {
			const prim = savedMetrics
				.filter((m) => m.enabled && m.bucket === 'primary')
				.sort((a, b2) => (a.order ?? 0) - (b2.order ?? 0));
			const sec = savedMetrics
				.filter((m) => m.enabled && m.bucket === 'secondary')
				.sort((a, b2) => (a.order ?? 0) - (b2.order ?? 0));
			const looseActive = savedMetrics.filter(
				(m) => m.enabled && m.bucket !== 'primary' && m.bucket !== 'secondary',
			);
			const activeIds = new Set([...prim, ...sec, ...looseActive].map((m) => m.metric_id));
			b = {
				primary: prim.map((m) => m.metric_id),
				secondary: [...sec.map((m) => m.metric_id), ...looseActive.map((m) => m.metric_id)],
				off: allCatalogIds().filter((id) => !activeIds.has(id)),
			};
		} else if (savedMetrics && savedMetrics.length) {
			const activeIds = savedMetrics.filter((m) => m.enabled).map((m) => m.metric_id);
			b = autoAssign(activeIds, catalog);
		} else {
			const activeIds = allCatalogIds().filter((id) => metricById[id]?.default_enabled);
			b = autoAssign(activeIds, catalog);
		}

		const thrMap: Record<string, string> = {};
		if (savedMetrics) {
			for (const m of savedMetrics) {
				fMap[m.metric_id] = m.use_friendly_format ?? true;
				hMap[m.metric_id] = m.horizons ? { ...m.horizons } : { ...HORIZONS_ALL };
				// Issue #624: sms_threshold laden (nur threshold-fähige Metriken).
				if (SMS_THRESHOLD_METRIC_IDS.includes(m.metric_id) && m.sms_threshold != null) {
					thrMap[m.metric_id] = String(m.sms_threshold);
				}
			}
		}

		// Issue #587: WeatherMetricsTab arbeitet ohne Detail-Bucket (hideDetailBucket=true).
		// Bestehende secondary-Metriken werden verlustfrei nach primary migriert.
		const mergedColumns = bucketsToColumns(b);
		b = { primary: mergedColumns, secondary: [], off: b.off };

		const savedPreset = trip!.display_config?.preset_name;
		selectedTemplate = savedPreset ?? '';
		buckets = b;
		friendlyMap = fMap;
		horizonsMap = hMap;
		// Issue #736: channels nicht mehr im snapshot (Conflict 2 entfällt).
		// Issue #774: reportConfig in snapshot aufnehmen.
		smsThresholds = thrMap;
		savedSnapshot = snapshot(b, fMap, hMap, telegramKurzform, thrMap, reportConfig, officialAlertsEnabled);
	}

	// Issue #1332 F003 (Fix-Loop 2): eigener, idempotenter Ladepfad fuer die
	// Kuerzel-Legende — load() (Route) und der Vergleich-$effect unten teilen
	// sich diese Funktion, statt dass der Vergleich-Zweig (der load() nie
	// aufruft) ohne smsSymbols bleibt.
	async function loadSmsSymbols() {
		if (smsSymbols) return;
		// Fail-soft: ohne Kuerzel-Katalog bleibt der Reiter voll bedienbar,
		// nur die Kuerzel-Anzeige entfaellt.
		smsSymbols = await api.get<SmsSymbolCatalog>('/api/sms-symbols').catch(() => null);
	}

	async function load() {
		loadError = null;
		try {
			const [catalogData, templateData, presetData, profileData] = await Promise.all([
				api.get<MetricCatalog>('/api/metrics'),
				api.get<Template[]>('/api/templates').catch(() => [] as Template[]),
				api.get<MetricPreset[]>('/api/metric-presets').catch(() => [] as MetricPreset[]),
				fetch('/api/auth/profile', { credentials: 'same-origin' })
					.then((r) => (r.ok ? r.json() : null))
					.catch(() => null),
				loadSmsSymbols(),
			]);
			catalog = catalogData;
			templates = templateData;
			userPresets = presetData;
			profile = profileData;
			initFromTrip();
			// Issue #1234 (2c): Baseline NACH dem Laden/der ersten Normalisierung neu
			// setzen — verhindert, dass der reportConfig-Watch einen Ladevorgang als
			// Nutzeraenderung wertet. Kein scheduleAutoSave() hier (ohne zu speichern).
			_lastReportConfig = reportConfig;
			// Issue #1234 (2a): erst nach vollstaendigem Erfolg wahr — der Render-
			// Guard haengt daran, damit Kindkomponenten (EditReportConfigSection) nie
			// vor geladenem Katalog mounten.
			catalogLoaded = true;
		} catch (e: unknown) {
			console.error(e);
			loadError = (e as { error?: string })?.error ?? 'Fehler beim Laden der Metriken';
		}
	}

	// Issue #1350 Teil 2: laedt die Compare-Metrik-Auswahlliste aus dem SSoT-
	// Endpoint. Reines Lesen — kein scheduleAutoSave()/PUT (AC-5).
	async function loadCompareMetricCatalog() {
		compareCatalogError = null;
		try {
			const res = await api.get<CompareMetricCatalogResponse>('/api/compare/metrics');
			compareCatalog = toCompareSelectionEntries(res);
			compareCatalogLoaded = true;
		} catch (e: unknown) {
			compareCatalogError = (e as { error?: string })?.error ?? 'Fehler beim Laden der Metriken';
		}
	}

	$effect(() => {
		// Issue #1311: der Vergleich-Zweig braucht keinen Trip-Katalog-Fetch —
		// die Grundauswahl im vergleich-Kontext arbeitet auf COMPARE_METRIC_DEFS.
		if (context === 'route' && Object.keys(catalog).length === 0) load();
	});

	$effect(() => {
		// Issue #1350 Teil 2: analog dem Route-Guard oben, aber fuer den
		// Vergleich-Zweig — greift auch im createMode (/compare/new), da beide
		// dieselbe Komponenten-Instanz teilen.
		// F001-Fix: compareCatalogError bewusst NICHT im Guard lesen (wie beim
		// Route-Guard oben, der loadError ebenfalls nicht trackt). Wuerde der
		// Effect compareCatalogError tracken, setzt loadCompareMetricCatalog()
		// es als Erstes auf null zurueck — das aendert eine getrackte Dependency
		// und der Effect feuert einen zweiten, konkurrierenden Fetch (Doppel-
		// Fetch bei "Wiederholen" bzw. Auto-Retry-Loop bei jedem Fehlschlag).
		if (context === 'vergleich' && !compareCatalogLoaded) {
			loadCompareMetricCatalog();
		}
	});

	$effect(() => {
		// Issue #1332 F003: load() wird im Vergleich-Kontext nie aufgerufen (s.o.),
		// die Kuerzel-Legende (officialAlertsToggle-Snippet) braucht smsSymbols
		// aber auch hier. Guard !smsSymbols verhindert Endlosschleife: nach
		// erfolgreichem Fetch ist smsSymbols gesetzt, nach Fehlschlag bleibt es
		// null und der naechste Effect-Lauf faengt sich nur bei einer echten
		// Dependency-Aenderung (context) erneut ein.
		if (context === 'vergleich' && !smsSymbols) loadSmsSymbols();
	});

	// Issue #932: Activity-Typ → Template vorauswählen (nur createMode, einmalig).
	const ACTIVITY_TO_TEMPLATE: Record<string, string> = {
		trekking: 'alpen-trekking',
		hochtour: 'alpen-trekking',
		klettersteig: 'alpen-trekking',
		mountaineering: 'alpen-trekking',
		ski_touring: 'skitouren',
		skitour: 'skitouren',
		hiking: 'wandern',
		fahrrad_15: 'radtour',
		fahrrad_20: 'radtour',
		fahrrad_25: 'radtour',
		mtb: 'radtour',
	};

	$effect(() => {
		if (!createMode || !trip?.activity || isDirty || templates.length === 0) return;
		const tmplId = ACTIVITY_TO_TEMPLATE[trip.activity];
		if (tmplId && templates.some(t => t.id === tmplId)) {
			applyPreset(tmplId);
		}
	});

	// Issue #622: Create-Modus — Kanal-Änderungen nach oben propagieren.
	$effect(() => {
		if (createMode && onChannelsChange) {
			onChannelsChange({ ...channels });
		}
	});

	// Preset-Auswahl
	function applyPreset(id: string) {
		// Issue #1234 (2c): Preset anwenden ist eine echte Nutzerabsicht (auch wenn
		// die einmalige Activity-Vorauswahl im createMode denselben Pfad nutzt —
		// dort greift scheduleAutoSave ohnehin nie, s. createMode-Guard).
		userTouched = true;
		const userP = userPresets.find((p) => p.id === id);
		const tmpl = templates.find((t) => t.id === id);
		const activeIds = userP
			? userP.metrics.filter((m) => m.enabled).map((m) => m.metric_id)
			: (tmpl ? tmpl.metrics : []);
		let newBuckets = autoAssign(activeIds, catalog);
		newBuckets = { primary: bucketsToColumns(newBuckets), secondary: [], off: newBuckets.off };
		const newFriendly = { ...friendlyMap };
		if (userP) {
			for (const m of userP.metrics) {
				newFriendly[m.metric_id] = m.use_friendly_format;
			}
		}
		applyDiff(newBuckets.primary, newFriendly, id);
		buckets = newBuckets;
		friendlyMap = newFriendly;
		selectedTemplate = id;
	}

	function onSelectPreset(id: string) {
		if (isDirty) { pendingPreset = id; return; }
		applyPreset(id);
	}

	function confirmPreset() {
		if (pendingPreset) applyPreset(pendingPreset);
		pendingPreset = null;
	}

	function onMode(id: string, useIndicator: boolean) {
		userTouched = true;
		const newFriendly = { ...friendlyMap, [id]: useIndicator };
		applyDiff(buckets.primary, newFriendly, selectedTemplate);
		friendlyMap = newFriendly;
		scheduleAutoSave();
	}

	// Toggle: Metrik aktivieren (→ primary) oder deaktivieren (→ off).
	// secondary ist nach #587 immer leer — kein secondary-Zweig nötig (F002).
	function onToggleMetric(id: string, wasOn: boolean) {
		userTouched = true;
		const from: keyof Buckets = buckets.primary.includes(id) ? 'primary' : 'off';
		const to: keyof Buckets = wasOn ? 'off' : 'primary';
		if (from !== to) {
			const newBuckets = move(buckets, id, from, to);
			applyDiff(newBuckets.primary, friendlyMap, selectedTemplate);
			buckets = newBuckets;
		}
		if (selectedTemplate) selectedTemplate = '';
		scheduleAutoSave();
	}

	// Issue #1117: Amtliche-Warnungen-Checkbox — named handler (kein Loop-Closure,
	// Safari-sicher), setzt State und triggert denselben debounce-Auto-Save.
	function onToggleOfficialAlerts(e: Event) {
		userTouched = true;
		officialAlertsEnabled = (e.target as HTMLInputElement).checked;
		scheduleAutoSave();
	}

	// Aus Abschnitt 3 entfernen (→ off).
	function onRemove(id: string) {
		userTouched = true;
		const newBuckets = move(buckets, id, 'primary', 'off');
		applyDiff(newBuckets.primary, friendlyMap, selectedTemplate);
		buckets = newBuckets;
		if (selectedTemplate) selectedTemplate = '';
		scheduleAutoSave();
	}

	// Reihenfolge per Drag & Drop (#848). Issue #1272: der geteilte SortableList
	// liefert die vollstaendige neue Reihenfolge — die splice/indexOf-Rueckrechnung
	// aus (fromId, toId) entfaellt.
	function onDndReorder(newOrder: string[]) {
		userTouched = true;
		const newBuckets = { ...buckets, primary: newOrder };
		applyDiff(newBuckets.primary, friendlyMap, selectedTemplate);
		buckets = newBuckets;
		scheduleAutoSave();
	}

	function handleDiscard() {
		try {
			const snap = JSON.parse(savedSnapshot);
			buckets = snap.buckets;
			friendlyMap = snap.friendlyMap;
			horizonsMap = snap.horizonsMap ?? {};
			telegramKurzform = snap.telegramKurzform ?? false;
			// Issue #736: channels nicht mehr im snapshot (Conflict 3 entfällt).
			smsThresholds = snap.smsThresholds ?? {};
			// Issue #774: reportConfig wiederherstellen (sonst bleibt Tab dirty nach Verwerfen).
			reportConfig = snap.reportConfig ?? {};
			// Issue #1117: officialAlertsEnabled wiederherstellen (Konsistenz-Vollständigkeit).
			officialAlertsEnabled = snap.officialAlertsEnabled ?? true;
		} catch (e) {
			console.error(e);
			initFromTrip();
			telegramKurzform = trip!.display_config?.telegram_kurzform ?? false;
			smsThresholds = {};
			reportConfig = trip!.report_config ? JSON.parse(JSON.stringify(trip!.report_config)) : {};
			officialAlertsEnabled = trip!.official_alerts_enabled ?? true;
		}
	}

	function buildWeatherPayload() {
		const baseMetrics = buildWeatherConfigMetrics(buckets, friendlyMap, horizonsMap, catalog);
		const metrics = baseMetrics.map((m) => {
			if (!SMS_THRESHOLD_METRIC_IDS.includes(m.metric_id)) return m;
			const rawThr = smsThresholds[m.metric_id];
			const parsed = rawThr !== undefined && rawThr !== '' ? parseFloat(rawThr) : null;
			if (parsed !== null && !isNaN(parsed)) {
				return { ...m, sms_threshold: parsed };
			}
			return m;
		});
		return {
			...(trip!.display_config ?? {}),
			metrics,
			preset_name: selectedTemplate || undefined,
			telegram_kurzform: telegramKurzform,
		};
	}

	async function handleSave() {
		const payload = buildWeatherPayload();
		// Issue #1234 (Fix-Loop 1 / F001): Gate VOR jedem Speicherversuch — ohne
		// echte Nutzergeste (userTouched) wird nie geschrieben, unabhaengig davon,
		// ob der Payload leer waere oder nicht (AC-1/AC-2/AC-6). Die bewusste
		// Abwahl aller Metriken bleibt moeglich, weil das Abwaehlen selbst die
		// Geste ist, die userTouched setzt (AC-4).
		const gateDecision = weatherSaveGate({ catalogLoaded, userTouched });
		if (gateDecision === 'skip') {
			saveController?.setDirty();
			return;
		}
		saving = true;
		saveSuccess = false;
		saveError = null;
		try {
			// Issue #622: Create-Modus — kein PUT, State per Binding gehalten.
			if (!createMode) {
				await api.put(`/api/trips/${trip!.id}/weather-config`, payload);
				// Issue #776/#774: report_config separat persistieren (zweiter PUT, Read-Modify-Write im Backend).
				// Issue #850: Server-Response enthält aktualisierte alert_rules (via SyncAlertRules) — nie manuell konstruieren.
				// Issue #1117: official_alerts_enabled im selben zweiten PUT persistieren.
				const updated = await api.put<Trip>(`/api/trips/${trip!.id}`, { report_config: reportConfig, official_alerts_enabled: officialAlertsEnabled });
				onTripUpdate?.(updated);
			}
			saveSuccess = true;
			// Issue #736: channels aus snapshot entfernt (Conflict 4 entfällt).
			savedSnapshot = snapshot(buckets, friendlyMap, horizonsMap, telegramKurzform, smsThresholds, reportConfig, officialAlertsEnabled);
			setTimeout(() => { saveSuccess = false; }, 3000);
		} catch (e: unknown) {
			console.error(e);
			saveError = (e as { error?: string })?.error ?? 'Speichern fehlgeschlagen';
		} finally {
			saving = false;
		}
	}

	// Issue #758: schedule auto-save via controller when metrics change.
	// Issue #1234: Gate VOR dem Schedulen — s. handleSave() fuer Begruendung.
	function scheduleAutoSave() {
		if (!saveController || createMode) return;
		const payload = buildWeatherPayload();
		const gateDecision = weatherSaveGate({ catalogLoaded, userTouched });
		if (gateDecision === 'skip') {
			saveController.setDirty();
			return;
		}
		saveController.schedule(async () => {
			await api.put(`/api/trips/${trip!.id}/weather-config`, payload);
			// Issue #850: Server-Response enthält aktualisierte alert_rules — nie manuell konstruieren.
			const updated = await api.put<Trip>(`/api/trips/${trip!.id}`, { report_config: reportConfig, official_alerts_enabled: officialAlertsEnabled });
			onTripUpdate?.(updated);
			savedSnapshot = snapshot(buckets, friendlyMap, horizonsMap, telegramKurzform, smsThresholds, reportConfig, officialAlertsEnabled);
		});
	}

	// Issue #774: reportConfig-Änderungen (Checkboxen) triggern Auto-Save.
	// Nicht-reaktive Vergleichsvariable vermeidet Rekursion.
	// Issue #1269 (a): reportConfigChangedByUser() statt rohem JSON-Vergleich —
	// die Mount-Kanonisierung von EditReportConfigSection (toHHMMSS,
	// Default-Materialisierung) erzeugt einen neuen `reportConfig`-Objektwert,
	// OHNE dass der Nutzer etwas geaendert hat; der rohe String-/Referenz-
	// Vergleich wertete das faelschlich als Aenderung.
	let _lastReportConfig: ReportConfig = reportConfig;
	$effect(() => {
		const cur = reportConfig;
		if (cur !== _lastReportConfig) {
			const changed = reportConfigChangedByUser(_lastReportConfig, cur);
			_lastReportConfig = cur;
			if (changed) {
				scheduleAutoSave();
			}
		}
	});

	// Issue #1234 (Fix-Loop 2 / F003+F004): Capture-Listener auf dem
	// Report-Config-Touch-Scope (s. Markup unten). Zwei Ereignis-Paare mit
	// unterschiedlicher Aufgabe — beide noetig, keins ersetzt das andere:
	//   - pointerdown/keydown: deckt Quick-Pick-BUTTONS ab (EditReportConfigSection
	//     Z. 219-228), die reportConfig aendern OHNE ein change/input-Ereignis
	//     auszuloesen. Gefiltert auf tatsaechlich bedienbare Elemente (F003),
	//     sonst wuerde ein Streuklick auf Ueberschrift/Beschreibungstext/Leerraum
	//     das Gate fuer den Rest der Sitzung entwaffnen.
	//   - change/input: deckt Aktivierungswege ab, bei denen KEIN vorheriges
	//     pointerdown/keydown auf dem Teilbaum feuert (Screenreader-/AT-
	//     synthetisierte Aktivierung, bestimmte Touch-Pfade) — F004. Bewusst
	//     ungefiltert: change/input feuern per Definition nur bei einer echten
	//     Wertaenderung eines Formular-Bedienelements, nie auf Ueberschriften
	//     oder Text.
	const REPORT_CONFIG_INTERACTIVE_SELECTOR =
		'input, button, select, textarea, label, [role="checkbox"], [role="radio"], [role="switch"]';
	function onReportConfigTouchGesture(e: Event) {
		if ((e.target as HTMLElement | null)?.closest?.(REPORT_CONFIG_INTERACTIVE_SELECTOR)) {
			userTouched = true;
		}
	}
	function onReportConfigValueChange() {
		userTouched = true;
	}

	async function onPresetSaved(preset: MetricPreset) {
		userPresets = [preset, ...userPresets];
		applyPreset(preset.id);
		// F004: wenn saveController vorhanden, über scheduleAutoSave routen,
		// damit der Indikator korrekt Feedback gibt (handleSave kennt den Controller nicht).
		if (saveController && !createMode) {
			scheduleAutoSave();
		} else {
			await handleSave();
		}
	}

	// Für SavePresetDialog (erwartet enabledMap): aktive = primary.
	const enabledMap = $derived.by(() => {
		const map: Record<string, boolean> = {};
		for (const id of allCatalogIds()) map[id] = false;
		for (const id of buckets.primary) map[id] = true;
		return map;
	});

	// ── Issue #1311 (C1): Vergleich-Zweig — nur an/aus, kein Zwei-PUT-Muster ──
	// Metrik-Pool = COMPARE_METRIC_DEFS (dieselben 14, die der Wertebereiche-Tab
	// im vergleich-Kontext anbietet — deckt sich mit dem Namensraum von
	// display_config.active_metrics, s. compare_metric_ids.py). Persistenz
	// macht CompareTabs.svelte (Hub-Hydrate/-Flush-Muster), diese Komponente
	// mutiert nur wiz.activeMetricKeys direkt (kein Self-Save, analog
	// AlarmeTab.svelte context="vergleich").
	function toggleCompareMetric(metric: string) {
		if (!wiz) return;
		const active = new Set(wiz.activeMetricKeys);
		if (active.has(metric)) active.delete(metric);
		else active.add(metric);
		wiz.activeMetricKeys = [...active];
	}

	// D2-Fix-Loop 2 (AC-6, Staging-Befund BROKEN): Amtliche-Warnungen-Toggle im
	// Vergleich-Zweig — kein Self-Save (analog toggleCompareMetric oben),
	// CompareTabs.svelte (`.hub-wetter-metriken-wrap` onchange-Bubble) persistiert
	// via flushPendingWeatherMetricsSave. Spec: d2_1301_official_alerts_single_
	// control.md § Punkt 6, AC-6.
	function onToggleVergleichOfficialAlerts(e: Event) {
		if (!wiz) return;
		wiz.officialAlertsEnabled = (e.target as HTMLInputElement).checked;
	}
</script>

{#snippet officialAlertsToggle(checked: boolean, onToggle: (e: Event) => void)}
	<!-- Issue #1117 (Trip) / #1301 D2-Fix-Loop 2 (Vergleich, AC-6): Amtliche-
	     Warnungen — geteiltes Markup fuer beide Kontexte (ein Label, eine
	     Optik), context-abhaengig nur verdrahtet (route: lokaler State + Trip-
	     PUT; vergleich: wiz.officialAlertsEnabled + Compare-Hub-Save). -->
	<UiCard.Root class="p-3 space-y-2 hover:translate-y-0 hover:shadow-none">
		<div class="text-sm">
			<span data-testid="report-show-official-alerts" class="inline-flex items-center gap-2">
				<Checkbox {checked} onchange={onToggle}>Amtliche Warnungen im Bericht</Checkbox>
			</span>
			<p class="pl-6 text-xs text-muted-foreground mt-0.5">Amtliche Wetterwarnungen (z. B. Unwetterwarnung) im E-Mail-Briefing anzeigen.</p>
		</div>
		<!-- Issue #1318 AC-9 / #1332: Kuerzel-Legende zur SMS-/Telegram-Kurzform.
		     Alle Kuerzel stammen aus dem Backend-Katalog (smsSymbols), damit die
		     Legende nicht von der tatsaechlich versendeten SMS abweichen kann.
		     Auch im Vergleich-Kontext sichtbar: seit #1332 filtert die
		     Vergleichs-SMS (render_compare_sms) amtliche Warnungen ab orange und
		     zeigt denselben '!'-Kuerzel-Marker wie der Trip-Pfad, und die
		     Vergleichs-Telegram-Nachricht (render_compare_telegram) traegt
		     dasselbe Kuerzel/Stufe -- die Legende trifft damit fuer beide
		     Kontexte zu (die vormalige Ausblendung war ein Bug, kein Feature). -->
		{#if smsSymbols}
			<div data-testid="official-alerts-symbol-legend" class="pl-6 text-xs text-muted-foreground space-y-1">
				<p>In SMS und Telegram-Kurzform beginnt der Warn-Block mit <code>!</code> — alles dahinter ist eine amtliche Warnung, nicht die eigene Vorhersage.</p>
				<ul class="legend-symbols">
					{#each smsSymbols.hazards as h (h.hazard)}
						<li><code>{h.sms_symbol}</code> {h.label}</li>
					{/each}
				</ul>
				<p>
					Die Warnstufe steht nach dem Doppelpunkt: <code>L</code> = gelb,
					<code>M</code> = orange, <code>H</code> = rot (z. B. <code>TH:H</code> =
					rote Gewitterwarnung).
				</p>
			</div>
		{/if}
	</UiCard.Root>
{/snippet}

{#if context === 'vergleich'}
	<!-- Issue #1311 (C1): Vergleich-Grundauswahl — NUR an/aus je Metrik, keine
	     Buckets/Reihenfolge/Horizonte/SMS-Schwellen/Report-Config (AC-1, AC-8
	     Attrappen-Verbot: jedes hier sichtbare Element hat Mail-Wirkung). -->
	<!-- D2-Fix-Loop 2 (AC-6): 'official_alerts' ist die einzige Ausnahme —
	     einzig erreichbare Inhalt-Heimat fuer official_alerts_enabled bei
	     bestehenden Vergleichen, s. weatherMetricsTabSections.ts. -->
	<div data-testid="weather-metrics-tab-vergleich" class="metrics-tab metrics-tab-vergleich">
		{#if compareCatalogError}
			<!-- Issue #1350 Teil 2 (AC-4): sichtbarer Fehlerpfad, kein stiller leerer
			     Editor — der Endpoint ist die einzige Quelle, ohne ihn kein Zugriff. -->
			<div class="metrics-tab load-error-shell" data-testid="weather-metrics-vergleich-load-error">
				<p class="load-error-msg">{compareCatalogError}</p>
				<Btn variant="primary" size="sm" data-testid="weather-metrics-vergleich-load-retry" onclick={loadCompareMetricCatalog}>Wiederholen</Btn>
			</div>
		{:else if !compareCatalogLoaded}
			<div class="metrics-tab loading-shell" aria-busy="true" data-testid="weather-metrics-vergleich-loading">
				<p class="loading-msg">Lade Metriken…</p>
			</div>
		{:else}
			<Card padding={18}>
				<Eyebrow style="margin-bottom:4px">Wetter-Metriken</Eyebrow>
				<p class="option-hint">Nur angewählte Metriken erscheinen in der Vergleichs-Mail.</p>
				<div class="vergleich-metric-list" data-testid="weather-metrics-vergleich-list">
					{#each compareCatalog as entry (entry.metric)}
						<label class="vergleich-metric-row" data-testid="weather-metrics-vergleich-row-{entry.metric}">
							<input
								type="checkbox"
								checked={wiz?.activeMetricKeys.includes(entry.metric) ?? false}
								onchange={() => toggleCompareMetric(entry.metric)}
							/>
							<span>{entry.label}</span>
						</label>
					{/each}
				</div>
			</Card>
		{/if}
		<!-- Issue #1350 Teil 2: Amtliche-Warnungen-Toggle haengt nicht am
		     Metrik-Katalog-Fetch (Known Limitations: "nur die Auswahl-UI ist
		     betroffen") — bleibt unabhaengig vom Lade-/Fehlerzustand sichtbar. -->
		{#if sections.includes('official_alerts')}
			{@render officialAlertsToggle(wiz?.officialAlertsEnabled ?? true, onToggleVergleichOfficialAlerts)}
		{/if}
	</div>
{:else if loadError}
	<!-- Issue #1234 (2b): sichtbarer Fehlerpfad, unabhaengig vom saveController —
	     kein leerer Editor, kein Schreibzugriff (AC-3). -->
	<div class="metrics-tab load-error-shell" data-testid="weather-metrics-load-error">
		<p class="load-error-msg">{loadError}</p>
		<Btn variant="primary" size="sm" data-testid="weather-metrics-load-retry" onclick={load}>Wiederholen</Btn>
	</div>
{:else if !catalogLoaded}
	<div class="metrics-tab loading-shell" aria-busy="true">
		<p class="loading-msg">Lade Metriken…</p>
	</div>
{:else}
	<div data-testid="weather-metrics-tab" class="metrics-tab">
		<!-- Save-Bar (oben, schmal) — expliziter Button nur ohne saveController (#758) -->
		<div class="save-bar">
			{#if isDirty && !saveController && !createMode}
				<Pill tone="warning" data-testid="weather-metrics-dirty-pill">Ungespeicherte Änderungen</Pill>
				<Btn variant="ghost" size="sm" data-testid="weather-metrics-discard" onclick={handleDiscard}>Verwerfen</Btn>
			{/if}
			{#if saveSuccess && !saveController && !createMode}
				<span data-testid="weather-metrics-tab-success" class="save-success">Gespeichert</span>
			{/if}
			{#if saveError && !saveController && !createMode}
				<span data-testid="weather-metrics-tab-error" class="save-error">{saveError}</span>
			{/if}
			{#if !saveController && !createMode}
				<Btn variant="primary" size="sm" data-testid="weather-metrics-tab-save" disabled={saving || !isDirty} onclick={handleSave}>
					{saving ? 'Speichern…' : 'Speichern'}
				</Btn>
			{/if}
		</div>

		<!-- Issue #1232 Scheibe 3b: 01/02 oben unverändert; darunter der geteilte -->
		<!-- LayoutTab-Organism (Reihenfolge + Vorschau); darunter 04/Mail-Inhalt/ -->
		<!-- Official-Toggle unverändert einspaltig (KL-4). -->
		<div class="route-editor-body">
			<div class="top-section">
				<!-- 01 Profil -->
				<Card padding={18}>
					<Eyebrow style="margin-bottom:10px">01 — Profil</Eyebrow>
					<WeatherV2PresetBar
						{selectedTemplate}
						dirty={isDirty}
						{templates}
						{userPresets}
						onSelectPreset={onSelectPreset}
						onOpenSaveDialog={() => (showSavePresetDialog = true)}
					/>
				</Card>

				<!-- 02 Grundauswahl -->
				<Card padding={18}>
					<Eyebrow style="margin-bottom:4px">02 — Grundauswahl</Eyebrow>
					<WeatherV2Grundauswahl
						{catalog}
						primaryColumns={buckets.primary}
						{highlight}
						onToggle={(id, wasOn) => onToggleMetric(id, wasOn)}
					/>
				</Card>
			</div>

			<!-- Fresh-Eyes-Fund #1232-3b: colCount zählt reine Metriken (ohne "+1"
			     Label-Spalte, die aus dem vergleich-Kontext stammt und dort
			     Orte-als-Spalten korrekt mitzählt) — die Trip-Kappung
			     (WeatherV2Reihenfolge/WeatherV2MailPreview: tgBudget = Anzahl
			     Metriken, Zeitspalte zählt nicht mit) erwartet dieselbe reine
			     Metriken-Zählung, sonst weicht der Overflow-Chip von Cut-Line
			     und Vorschau-Hinweis ab. -->
			{#if sections.includes('reihenfolge')}
			<LayoutTab
				context="route"
				bind:channel={activeChannel}
				colCount={buckets.primary.length}
				subjectLabel="Metriken"
			>
				{#snippet editor({ channel })}
					<Card padding={0}>
						<WeatherV2Reihenfolge
							primaryColumns={buckets.primary}
							{metricById}
							{friendlyMap}
							activeChannel={channel}
							{highlight}
							onRemove={onRemove}
							onDndReorder={onDndReorder}
							{onMode}
						/>
					</Card>
				{/snippet}
				{#snippet preview({ channel })}
					<WeatherV2MailPreview
						primaryColumns={buckets.primary}
						{metricById}
						{friendlyMap}
						{telegramKurzform}
						{highlight}
						{channel}
					/>
				{/snippet}
			</LayoutTab>
			{/if}

			<div class="bottom-section">
				{#if sections.includes('sms_schwellen')}
				<!-- 04 Schwellwerte (Issue #624, umbenannt in #736) -->
				<Card padding={18}>
					<Eyebrow style="margin-bottom:8px">04 — Schwellwerte</Eyebrow>
					<p class="option-hint">
						Gelten für SMS-Token, Telegram-Kurzform und den E-Mail-Ausblick/Trend-Block
					</p>
					<div class="sms-thresholds" data-testid="sms-thresholds">
						<table class="threshold-table">
							<tbody>
								{#if !buckets.off.includes('wind')}
								<ThresholdMetricRow
									metricId="wind"
									smsSymbol={metricSymbols['wind']}
									label="Wind (km/h)"
									levels={[
										{ id: 'sensibel', label: 'Sensibel', float: 15 },
										{ id: 'standard', label: 'Standard', float: 20 },
										{ id: 'robust', label: 'Robust', float: 30 }
									]}
									currentFloat={smsThresholds['wind'] !== undefined && smsThresholds['wind'] !== '' ? parseFloat(smsThresholds['wind']) : null}
									onChange={(id, f) => { userTouched = true; smsThresholds = { ...smsThresholds, [id]: String(f) }; scheduleAutoSave(); }}
								/>
								{/if}
								{#if !buckets.off.includes('gust')}
								<ThresholdMetricRow
									metricId="gust"
									smsSymbol={metricSymbols['gust']}
									label="Böen (km/h)"
									levels={[
										{ id: 'sensibel', label: 'Sensibel', float: 30 },
										{ id: 'standard', label: 'Standard', float: 40 },
										{ id: 'robust', label: 'Robust', float: 50 }
									]}
									currentFloat={smsThresholds['gust'] !== undefined && smsThresholds['gust'] !== '' ? parseFloat(smsThresholds['gust']) : null}
									onChange={(id, f) => { userTouched = true; smsThresholds = { ...smsThresholds, [id]: String(f) }; scheduleAutoSave(); }}
								/>
								{/if}
								{#if !buckets.off.includes('precipitation')}
								<ThresholdMetricRow
									metricId="precipitation"
									smsSymbol={metricSymbols['precipitation']}
									label="Niederschlag (mm)"
									levels={[
										{ id: 'sensibel', label: 'Sensibel', float: 0.3 },
										{ id: 'standard', label: 'Standard', float: 0.8 },
										{ id: 'robust', label: 'Robust', float: 1.5 }
									]}
									currentFloat={smsThresholds['precipitation'] !== undefined && smsThresholds['precipitation'] !== '' ? parseFloat(smsThresholds['precipitation']) : null}
									onChange={(id, f) => { userTouched = true; smsThresholds = { ...smsThresholds, [id]: String(f) }; scheduleAutoSave(); }}
								/>
								{/if}
								{#if !buckets.off.includes('rain_probability')}
								<ThresholdMetricRow
									metricId="rain_probability"
									smsSymbol={metricSymbols['rain_probability']}
									label="Regenwahrsch. (%)"
									levels={[
										{ id: 'sensibel', label: 'Sensibel', float: 25 },
										{ id: 'standard', label: 'Standard', float: 40 },
										{ id: 'robust', label: 'Robust', float: 60 }
									]}
									currentFloat={smsThresholds['rain_probability'] !== undefined && smsThresholds['rain_probability'] !== '' ? parseFloat(smsThresholds['rain_probability']) : null}
									onChange={(id, f) => { userTouched = true; smsThresholds = { ...smsThresholds, [id]: String(f) }; scheduleAutoSave(); }}
								/>
								{/if}
								{#if !buckets.off.includes('thunder')}
								<ThresholdMetricRow
									metricId="thunder"
									smsSymbol={metricSymbols['thunder']}
									label="Gewitter"
									levels={[
										{ id: 'med', label: 'MED', float: 1.0 },
										{ id: 'high', label: 'HIGH', float: 2.0 }
									]}
									currentFloat={smsThresholds['thunder'] !== undefined && smsThresholds['thunder'] !== '' ? parseFloat(smsThresholds['thunder']) : null}
									onChange={(id, f) => { userTouched = true; smsThresholds = { ...smsThresholds, [id]: String(f) }; scheduleAutoSave(); }}
								/>
								{/if}
								{#if !buckets.off.includes('snow_depth')}
								<ThresholdMetricRow
									metricId="snow_depth"
									smsSymbol={metricSymbols['snow_depth']}
									label="Schneehöhe (cm)"
									levels={[
										{ id: 'sensibel', label: 'Sensibel', float: 5 },
										{ id: 'standard', label: 'Standard', float: 10 },
										{ id: 'robust', label: 'Robust', float: 20 }
									]}
									currentFloat={smsThresholds['snow_depth'] !== undefined && smsThresholds['snow_depth'] !== '' ? parseFloat(smsThresholds['snow_depth']) : null}
									onChange={(id, f) => { userTouched = true; smsThresholds = { ...smsThresholds, ['snow_depth']: String(f) }; scheduleAutoSave(); }}
								/>
								{/if}
								{#if !buckets.off.includes('snowfall_limit')}
								<ThresholdMetricRow
									metricId="snowfall_limit"
									smsSymbol={metricSymbols['snowfall_limit']}
									label="Schneefallgrenze (m)"
									levels={[
										{ id: 'sensibel', label: 'Sensibel', float: 2000 },
										{ id: 'standard', label: 'Standard', float: 1500 },
										{ id: 'robust', label: 'Robust', float: 1000 }
									]}
									currentFloat={smsThresholds['snowfall_limit'] !== undefined && smsThresholds['snowfall_limit'] !== '' ? parseFloat(smsThresholds['snowfall_limit']) : null}
									onChange={(id, f) => { userTouched = true; smsThresholds = { ...smsThresholds, ['snowfall_limit']: String(f) }; scheduleAutoSave(); }}
								/>
								{/if}
							</tbody>
						</table>
					</div>
				</Card>
				{/if}

				{#if !createMode && sections.includes('report_config')}
				<!-- Issue #1234 (Fix-Loop 1 / F001, Fix-Loop 2 / F003+F004): EditReportConfigSection
				     normalisiert reportConfig in einem eigenen $effect beim Mounten und
				     schreibt es zurueck — das darf NICHT als Nutzergeste zaehlen (AC-6).
				     Eine echte Interaktion des Nutzers MUSS aber weiterhin speichern
				     (#774). EditReportConfigSection selbst darf laut Spec nicht geaendert
				     werden, daher: vier Capture-Phase-Listener auf dem umschliessenden
				     Container (s. onReportConfigTouchGesture/onReportConfigValueChange
				     oben fuer die Aufgabenteilung). Alle vier feuern in der Capture-Phase
				     noch VOR dem Ziel-Handler der Checkbox/des Buttons und damit erst
				     recht vor dem $effect, der reportConfig zurueckschreibt und den
				     aeusseren reportConfig-Watch (Z. ~520) ausloest — die Geste geht dem
				     daraus folgenden State-Update also immer zeitlich voraus. Ein $effect
				     setzt userTouched nie; hier sind es echte DOM-Event-Handler. -->
				<div
					class="report-config-touch-scope"
					onpointerdowncapture={onReportConfigTouchGesture}
					onkeydowncapture={onReportConfigTouchGesture}
					onchangecapture={onReportConfigValueChange}
					oninputcapture={onReportConfigValueChange}
				>
					<EditReportConfigSection
						bind:reportConfig
						mode="edit"
						showMailContent={true}
						showChannels={false}
						showSchedule={false}
					/>
				</div>
				{/if}

				{#if !createMode && sections.includes('official_alerts')}
				<!-- Issue #1117: Amtliche Warnungen — zweiter Einstiegspunkt neben dem -->
				<!-- Alerts-Tab, gleiche Optik wie die Content-Bausteine oben. Eigener  -->
				<!-- 'official_alerts'-Abschnitt (D2-Fix-Loop 2), unabhaengig von       -->
				<!-- 'report_config', damit derselbe Baustein auch im vergleich-        -->
				<!-- Kontext (kein report_config dort) sichtbar sein kann.              -->
				{@render officialAlertsToggle(officialAlertsEnabled, onToggleOfficialAlerts)}
				{/if}
			</div>
		</div>

		<!-- Mobile: fixierter "So kommt es an"-Button → Mail-Vorschau als Bottom-Sheet (#618) -->
		<button class="mobile-mail-fab" data-testid="mobile-mail-fab" onclick={() => (mailSheetOpen = true)}>
			<span>So kommt es an</span>
			<span class="mobile-mail-fab__badge">{buckets.primary.length + (buckets.secondary?.length ?? 0)} Metriken</span>
		</button>
		<Sheet open={mailSheetOpen} onClose={() => (mailSheetOpen = false)} title="So kommt es an">
			<div data-testid="mobile-mail-sheet" style="padding: 4px 16px 24px;">
				<WeatherV2MailPreview
					primaryColumns={buckets.primary}
					{metricById}
					{friendlyMap}
					{telegramKurzform}
					{highlight}
					channel={activeChannel}
				/>
			</div>
		</Sheet>

		<!-- Dialoge & Overlays -->
		<SavePresetDialog
			bind:open={showSavePresetDialog}
			{enabledMap}
			{friendlyMap}
			{horizonsMap}
			{catalog}
			{indicatorCapable}
			{buckets}
			existingNames={userPresets.map(p => p.name)}
			onClose={() => (showSavePresetDialog = false)}
			onSaved={onPresetSaved}
		/>

		{#if pendingPreset}
			<div class="confirm-overlay" role="dialog" aria-modal="true" data-testid="preset-confirm">
				<div class="confirm-box">
					<Eyebrow>Preset anwenden</Eyebrow>
					<p>Du hast ungespeicherte Änderungen. Das Preset überschreibt die aktuelle Auswahl.</p>
					<div class="confirm-actions">
						<Btn variant="ghost" size="sm" data-testid="preset-confirm-cancel" onclick={() => (pendingPreset = null)}>Abbrechen</Btn>
						<Btn variant="primary" size="sm" data-testid="preset-confirm-ok" onclick={confirmPreset}>Überschreiben</Btn>
					</div>
				</div>
			</div>
		{/if}
	</div>
{/if}

<style>
	.loading-shell {
		padding: var(--g-s-4);
	}
	/* Issue #1234 (2b): sichtbarer Ladefehler-Zustand. */
	.load-error-shell {
		padding: var(--g-s-4);
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: var(--g-s-2);
	}
	.load-error-msg {
		color: var(--g-danger);
		font-size: var(--g-text-sm);
	}
	/* Issue #618: FAB auf Desktop versteckt */
	.mobile-mail-fab {
		display: none;
	}
	.save-bar {
		display: flex;
		gap: var(--g-s-2);
		align-items: center;
		flex-wrap: wrap;
		padding: var(--g-s-3) var(--g-s-10);
		border-bottom: 1px solid var(--g-rule-soft);
		margin-bottom: 0;
	}
	/* Issue #1234 (Fix-Loop 1): reiner Event-Capture-Container fuer die Report-
	   Config-Karte — bewusst OHNE eigenes CSS. Ein normaler Block-Div verhaelt
	   sich als Flex-Item von .bottom-section (column, gap:20px) identisch zum
	   vorherigen direkten Kind (EditReportConfigSection-Wurzel-Div), daher kein
	   `display:contents` (das hat in aelteren WebKit-Versionen Nebenwirkungen
	   auf Event-/ARIA-Semantik — unnoetiges Risiko fuer einen reinen Layout-No-op). */
	.save-success {
		font-size: var(--g-text-sm);
		color: var(--g-success);
	}
	.save-error {
		font-size: var(--g-text-sm);
		color: var(--g-danger);
	}
	/* Issue #1232 Scheibe 3b: .v2-layout-Grid entfällt für den Ausgabe-Teil —
	   die Zwei-Spalten-Shell kommt jetzt aus dem geteilten LayoutTab-Organism.
	   01/02 (top-section) und 04/Mail-Inhalt/Official (bottom-section) bleiben
	   einspaltig, analog dem bisherigen .editor-col. */
	.route-editor-body {
		display: flex;
		flex-direction: column;
		gap: 20px;
		padding: 28px 40px 60px;
		max-width: 1480px;
	}
	.top-section,
	.bottom-section {
		display: flex;
		flex-direction: column;
		gap: 20px;
	}
	.confirm-overlay {
		position: fixed;
		inset: 0;
		background: color-mix(in srgb, var(--g-ink) 45%, transparent);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 100;
	}
	.confirm-box {
		width: 420px;
		max-width: 90vw;
		background: var(--g-paper);
		border: 1px solid var(--g-ink-faint);
		border-radius: var(--g-radius-md);
		padding: var(--g-s-5);
		box-shadow: var(--g-elev-3);
	}
	.confirm-box p {
		font-size: var(--g-text-sm);
		color: var(--g-ink-muted);
		margin: var(--g-s-2) 0 var(--g-s-4);
		line-height: 1.5;
	}
	.confirm-actions {
		display: flex;
		justify-content: flex-end;
		gap: var(--g-s-2);
	}
	/* Conflict 6 resolved: v2-CSS + #624-Klassen, ohne telegram-options */
	.option-hint {
		font-size: var(--g-text-sm);
		color: var(--g-ink-muted);
		line-height: 1.5;
		margin: 0 0 var(--g-s-3);
	}
	/* Issue #624: SMS-Schwellwerte */
	.sms-thresholds {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-2);
	}
	.threshold-table {
		width: 100%;
		border-collapse: collapse;
	}
	@media (max-width: 899px) {
		.route-editor-body {
			gap: var(--g-s-6);
			padding: var(--g-s-4);
			padding-bottom: 88px;
		}
		.save-bar {
			padding: var(--g-s-3) var(--g-s-4);
		}
		/* Inline-Vorschau auf Mobil verstecken (kommt stattdessen als Sheet, #618).
		   Ersetzt das bisherige .preview-col{display:none} — jetzt die
		   LayoutTab-eigene Vorschau-Spalte (KL-1). */
		:global(.layout-tab[data-context='route'] .lt-col-preview) {
			display: none;
		}
		/* Issue #618: Floating FAB mobil.
		   F001 (Staging-Adversary #1232-3b): z-index:20/bottom:16px lag HINTER
		   der globalen BottomNav (z-index:50, 64px + safe-area, BottomNav.svelte
		   Z.27/28) — echte Klicks trafen den Nav-Link statt den FAB. Fix nach
		   etabliertem Muster (SaveIndicator.svelte Z.74-78: „Mobile: über
		   BottomNav (64px Höhe + safe-area)"): bottom-Offset über die Nav-Höhe
		   heben, z-index über 50 (unter Sheet.svelte 60/61, damit der FAB beim
		   offenen Bottom-Sheet dahinter bleibt). */
		.mobile-mail-fab {
			position: fixed;
			bottom: calc(64px + env(safe-area-inset-bottom) + 16px);
			left: 14px;
			right: 14px;
			z-index: 55;
			display: flex;
			align-items: center;
			justify-content: center;
			gap: 10px;
			padding: 14px;
			border: none;
			border-radius: var(--g-r-pill);
			background: var(--g-ink);
			color: var(--g-paper);
			font-size: 14px;
			font-weight: 600;
			cursor: pointer;
			box-shadow: 0 4px 20px rgba(26, 26, 24, 0.25);
		}
		.mobile-mail-fab__badge {
			font-family: var(--g-font-mono);
			font-size: 11px;
			opacity: 0.7;
			background: rgba(255, 255, 255, 0.15);
			padding: 2px 8px;
			border-radius: 999px;
		}
	}
	/* Issue #1311 (C1): Vergleich-Grundauswahl — schlanke Checkbox-Liste. */
	.metrics-tab-vergleich {
		padding: 28px 40px 60px;
		max-width: 640px;
	}
	.vergleich-metric-list {
		display: flex;
		flex-direction: column;
		gap: 10px;
		margin-top: 10px;
	}
	.vergleich-metric-row {
		display: flex;
		align-items: center;
		gap: 10px;
		font-size: 14px;
		color: var(--g-ink);
		cursor: pointer;
	}
	@media (max-width: 899px) {
		.metrics-tab-vergleich {
			padding: 20px 16px 48px;
		}
	}
</style>
