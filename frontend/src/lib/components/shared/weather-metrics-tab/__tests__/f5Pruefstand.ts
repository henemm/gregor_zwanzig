// Issue #2654 (i18n F5, Epic #2644) — gemeinsamer SSR-Pruefstand fuer den geteilten
// Wertebereiche-/Wetter-Metriken-Reiter (WeatherMetricsTab + weather-metrics-tab/*) in
// BEIDEN Kontexten (route | vergleich). Echte Svelte-Komponenten, gerendert mit
// svelte/server. Katalog, Lade- und Fehlerzustand setzt der Reiter erst in `$effect`
// (laeuft beim SSR nie) — sie kommen ueber f5VarianteHook.mjs (exakte Umlenkung
// benannter `$state`-Startwerte); Markup und Helfer bleiben der echte Quelltext.
// Nutzer `golden-de`, Katalog `fixtures/metric_catalog_selectable.json`, feste Zeit
// 2026-10-29T06:00+02:00 (Spec Implementation Details 6). Weitere Antworten sind
// aufgezeichnete Backend-Daten (fixtures/f5_*.json, erzeugt aus api/routers/*.py):
// Register-Namen (label_en, col_label, sms_code), /api/sms-symbols, /api/compare/metrics.
// Golden: tests/golden/f5_wertebereiche/<fall>.de.(html|txt) = Ist-Stand VOR der
// Umstellung (nie neu schreiben); <fall>.en.* = Review-Hilfe:
//   cd frontend && GZ_GOLDEN_SCHREIBEN=en npm test -- src/lib/components/shared/weather-metrics-tab/__tests__/wertebereiche_sprache.test.ts
// Spec: docs/specs/modules/i18n_f5_wertebereiche_tab_2654.md
// Pfadregel #1409: alles relativ zu DIESER Datei.

import { register } from 'node:module';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

process.env.TZ = 'Europe/Berlin';

export const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> weather-metrics-tab -> shared -> components -> lib -> src -> frontend
export const FRONTEND = path.resolve(HERE, '../../../../../..');
export const WMT = path.resolve(HERE, '..');
export const SHARED = path.resolve(WMT, '..');
export const GOLDEN_DIR = path.resolve(FRONTEND, '..', 'tests', 'golden', 'f5_wertebereiche');
const basis = pathToFileURL(FRONTEND + '/').href;
register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, basis);
register(pathToFileURL(path.join(HERE, 'f5VarianteHook.mjs')).href, basis);

const { render } = await import('svelte/server');
const imp = async (datei: string) => await import(pathToFileURL(datei).href);
const komp = async (datei: string) => (await imp(datei)).default;
const variante = async (datei: string, ersetzungen: [string, string][]) =>
	(await import(`${pathToFileURL(datei).href}?f5variante=${Buffer.from(JSON.stringify(ersetzungen)).toString('base64url')}`)).default;

export const { locale, tr, trFor } = await imp(path.join(FRONTEND, 'src/lib/i18n/index.ts'));
export const { toCompareSelectionEntries } = await imp(path.join(WMT, 'compareMetricSelection.ts'));
export const { resolveTripMetricsOverviewState } = await imp(path.join(SHARED, 'trip-metrics', 'tripActiveMetricNames.ts'));
export const loader = await imp(path.join(SHARED, 'corridor-editor', 'compareMetricCatalogLoader.ts'));

const fixture = (name: string) => JSON.parse(readFileSync(path.join(HERE, 'fixtures', name), 'utf-8'));
type Eintrag = Record<string, unknown> & { id: string; label: string };
type Katalog = Record<string, Eintrag[]>;

/** GET /api/metrics laut Spec-Fixture (nur `label`, wie vor P1). */
export const KATALOG_ALT: Katalog = fixture('metric_catalog_selectable.json');
/** Aufgezeichnete Register-Namen je Kennung (label_en, col_label, sms_code). */
export const REGISTER_NAMEN: Record<string, { label_en: string; col_label: string; sms_code: string }> = fixture('f5_register_namen.json');
export const SMS_SYMBOLE = fixture('f5_sms_symbols.json');
export const VERGLEICH_ANTWORT = fixture('f5_compare_metrics.json');

/** Katalog wie GET /api/metrics nach P1: zusaetzlich label_en, col_label, sms_code. */
export function katalogMitRegister(ohneLabelEn: string[] = []): Katalog {
	const k: Katalog = {};
	for (const [cat, liste] of Object.entries(KATALOG_ALT)) {
		k[cat] = liste.map((m) => {
			const r = REGISTER_NAMEN[m.id];
			const e: Eintrag = { ...m, label_de: m.label, col_label: r.col_label, sms_code: r.sms_code };
			if (!ohneLabelEn.includes(m.id)) e.label_en = r.label_en;
			return e;
		});
	}
	return k;
}

export const VERGLEICH_KATALOG = () => toCompareSelectionEntries(VERGLEICH_ANTWORT);

const WMT_DATEI = path.join(SHARED, 'WeatherMetricsTab.svelte');
const ZUSTAND: [string, string][] = [
	['let catalog: MetricCatalog = $state({});', 'let catalog: MetricCatalog = $state(globalThis.__F5.catalog);'],
	['let smsSymbols = $state<SmsSymbolCatalog | null>(null);', 'let smsSymbols = $state<SmsSymbolCatalog | null>(globalThis.__F5.smsSymbols);'],
	['let templates: Template[] = $state([]);', 'let templates: Template[] = $state(globalThis.__F5.templates);'],
	['let userPresets: MetricPreset[] = $state([]);', 'let userPresets: MetricPreset[] = $state(globalThis.__F5.userPresets);'],
	['let catalogLoaded = $state(false);', 'let catalogLoaded = $state(globalThis.__F5.catalogLoaded);'],
	['let loadError: string | null = $state(null);', 'let loadError: string | null = $state(globalThis.__F5.loadError);'],
	['let compareCatalog: CompareSelectionEntry[] = $state([]);', 'let compareCatalog: CompareSelectionEntry[] = $state(globalThis.__F5.compareCatalog);'],
	['let compareCatalogLoaded = $state(false);', 'let compareCatalogLoaded = $state(globalThis.__F5.compareCatalogLoaded);'],
	['let compareCatalogError: string | null = $state(null);', 'let compareCatalogError: string | null = $state(globalThis.__F5.compareCatalogError);'],
	['let saveSuccess = $state(false);', 'let saveSuccess = $state(globalThis.__F5.saveSuccess);'],
	['let buckets: Buckets = $state({ primary: [], secondary: [], off: [] });', 'let buckets: Buckets = $state(globalThis.__F5.buckets);'],
	['let selectedTemplate = $state(\'\');', 'let selectedTemplate = $state(globalThis.__F5.selectedTemplate);'],
	['let showSavePresetDialog = $state(false);', 'let showSavePresetDialog = $state(globalThis.__F5.showSavePresetDialog);'],
	['let pendingPreset: string | null = $state(null);', 'let pendingPreset: string | null = $state(globalThis.__F5.pendingPreset);'],
	['let activeChannel = $state<ChannelId>(\'email\');', 'let activeChannel = $state<ChannelId>(globalThis.__F5.activeChannel);']
];
const WeatherMetricsTab = await variante(WMT_DATEI, ZUSTAND);
const DayWindowCard = await komp(path.join(WMT, 'DayWindowCard.svelte'));
const WeatherV2PresetBar = await komp(path.join(WMT, 'WeatherV2PresetBar.svelte'));
const WeatherV2Reihenfolge = await komp(path.join(WMT, 'WeatherV2Reihenfolge.svelte'));
const SavePresetDialog = await komp(path.join(WMT, 'SavePresetDialog.svelte'));

export type Kontext = 'route' | 'vergleich';
const nix = () => {};
const g = globalThis as unknown as Record<string, unknown>;
const ohneKommentare = (html: string) => html.replace(/<!--[\s\S]*?-->/g, '');
const html = (k: unknown, props: Record<string, unknown> = {}) => ohneKommentare(render(k as never, { props } as never).body);

export const TEMPLATES = [{ id: 'wandern', label: 'Wandern', metrics: ['temperature', 'wind', 'precipitation'] }];
export const USER_PRESETS = [{ id: 'p-golden', name: 'Mein GR20', metrics: [{ metric_id: 'temperature', enabled: true, use_friendly_format: false }] }];

/** Zustand eines Nutzers im Reiter (Trip-Kontext). */
export type Zustand = {
	catalog?: Katalog;
	buckets?: { primary: string[]; secondary: string[]; off: string[] };
	activeChannel?: 'email' | 'telegram' | 'sms';
	catalogLoaded?: boolean;
	loadError?: string | null;
	compareCatalogLoaded?: boolean;
	compareCatalogError?: string | null;
	saveSuccess?: boolean;
	showSavePresetDialog?: boolean;
	pendingPreset?: string | null;
	smsSymbols?: unknown;
};

export const BUCKETS_GOLDEN = {
	primary: ['temperature', 'wind_chill', 'wind', 'gust', 'precipitation', 'thunder', 'snowfall_limit', 'cloud_total', 'humidity'],
	secondary: [] as string[],
	off: ['rain_probability', 'snow_depth', 'temperature_night', 'wind_chill_night']
};

export function tripFuer(nutzer: string, buckets = BUCKETS_GOLDEN) {
	return {
		id: `trip-${nutzer}`,
		name: 'GR20 Nord',
		stages: [{ date: '2026-10-29' }],
		official_alerts_enabled: true,
		report_config: { day_window_start_hour: 6, day_window_end_hour: 18 },
		display_config: {
			metrics: [...buckets.primary.map((id) => ({ metric_id: id, enabled: true })), ...buckets.off.map((id) => ({ metric_id: id, enabled: false }))],
			telegram_kurzform: false
		}
	};
}

function setze(z: Zustand): void {
	g.__F5 = {
		catalog: z.catalog ?? KATALOG_ALT,
		smsSymbols: z.smsSymbols === undefined ? SMS_SYMBOLE : z.smsSymbols,
		templates: TEMPLATES,
		userPresets: USER_PRESETS,
		catalogLoaded: z.catalogLoaded ?? true,
		loadError: z.loadError ?? null,
		compareCatalog: VERGLEICH_KATALOG(),
		compareCatalogLoaded: z.compareCatalogLoaded ?? true,
		compareCatalogError: z.compareCatalogError ?? null,
		saveSuccess: z.saveSuccess ?? false,
		buckets: z.buckets ?? BUCKETS_GOLDEN,
		selectedTemplate: 'wandern',
		showSavePresetDialog: z.showSavePresetDialog ?? false,
		pendingPreset: z.pendingPreset ?? null,
		activeChannel: z.activeChannel ?? 'email'
	};
}

/** Der Reiter im Trip-Kontext (Trip-Hub, ohne saveController: Speichern-Leiste sichtbar). */
export function routeRendern(z: Zustand = {}, nutzer = 'golden-de'): string {
	setze(z);
	return html(WeatherMetricsTab, { context: 'route', trip: tripFuer(nutzer, z.buckets ?? BUCKETS_GOLDEN) });
}

export const VERGLEICH_AUSWAHL = ['temp_max_c', 'temp_min_c', 'wind_max_kmh', 'gust_max_kmh', 'precip_sum_mm', 'thunder_level_max', 'sunny_hours_h'];

/** Der Reiter im Ortsvergleich-Kontext (Wertprops wie wetterMetrikenPropsAus). */
export function vergleichRendern(z: Zustand = {}, aktiv: string[] = VERGLEICH_AUSWAHL): string {
	setze(z);
	return html(WeatherMetricsTab, {
		context: 'vergleich',
		activeMetricKeys: aktiv,
		channelActiveMetricKeys: { email: null, telegram: [aktiv[0], aktiv[2]], sms: null },
		officialAlertsEnabled: true,
		dayWindowStartHour: 6,
		dayWindowEndHour: 18,
		hourlyMetricKeys: null,
		hourlyEnabled: true,
		outlookMetricKeys: null,
		outlookMetricFormats: null,
		outlookEnabled: true
	});
}

/** Bausteine, die der Reiter nur in Sonderzustaenden zeigt (ohne Reiter-Zustand). */
export function bausteineRendern(): string {
	const katalog = katalogMitRegister();
	const byId: Record<string, Eintrag> = {};
	for (const liste of Object.values(katalog)) for (const m of liste) byId[m.id] = m;
	return [
		html(DayWindowCard, { startHour: 22, endHour: 2, onStartHour: nix, onEndHour: nix }),
		html(WeatherV2PresetBar, { selectedTemplate: 'p-golden', dirty: false, templates: TEMPLATES, userPresets: USER_PRESETS, onSelectPreset: nix, onOpenSaveDialog: nix }),
		html(SavePresetDialog, {
			open: true, enabledMap: {}, friendlyMap: {}, horizonsMap: {}, catalog: KATALOG_ALT,
			indicatorCapable: () => false, onClose: nix, onSaved: nix
		}),
		html(WeatherV2Reihenfolge, {
			primaryColumns: ['temperature', 'wind', 'gust', 'precipitation', 'thunder', 'cloud_total', 'humidity', 'dewpoint', 'wind_chill'],
			metricById: byId, friendlyMap: { wind: true }, activeChannel: 'telegram', highlight: null,
			onRemove: nix, onDndReorder: nix, onMode: nix, offColumns: ['snow_depth'], onRestore: nix,
			showAbwahlHinweis: false, kuerzelById: { temperature: ['T'], gust: ['G'], snow_depth: ['SD'] }
		})
	].join('\n');
}

/** Golden-Faelle HTML. */
export function htmlFaelle(): Record<string, () => string> {
	return {
		route_voll: () => routeRendern({ pendingPreset: 'wandern', showSavePresetDialog: true }),
		// Register-Katalog mit label_en: Deutsch zeigt trotzdem label (= label_de), dazu Kurzform/Kuerzel.
		route_telegram: () => routeRendern({ catalog: katalogMitRegister(), activeChannel: 'telegram', compareCatalogLoaded: false, saveSuccess: true }),
		route_sms_schwellen_fehler: () => routeRendern({ activeChannel: 'sms', compareCatalogError: 'HTTP 503' }),
		zustaende: () =>
			[
				routeRendern({ catalogLoaded: false }),
				routeRendern({ catalogLoaded: false, loadError: 'HTTP 500' }),
				vergleichRendern({ compareCatalogLoaded: false, smsSymbols: null }),
				vergleichRendern({ compareCatalogError: 'HTTP 502', smsSymbols: null })
			].join('\n'),
		vergleich_voll: () => vergleichRendern(),
		bausteine: bausteineRendern
	};
}

/** Funktionsergebnisse als Tabelle `Eingabe → Ausgabe` (eine Zeile je Fall). */
export function funktionsTabelle(): string {
	const j = (v: unknown) => JSON.stringify(v);
	const z: string[] = [];
	const metriken = (ids: string[]) => ids.map((id) => ({ metric_id: id, enabled: true }));
	z.push(`resolveTripMetricsOverviewState(auswahl) → ${j(resolveTripMetricsOverviewState(metriken(['temperature', 'gust', 'snow_depth', 'gibt_es_nicht']), katalogMitRegister()))}`);
	z.push(`resolveTripMetricsOverviewState(leer) → ${j(resolveTripMetricsOverviewState([{ metric_id: 'wind', enabled: false }], KATALOG_ALT))}`);
	z.push(`thunderThresholdLevelsFromCatalog → ${j(loader.thunderThresholdLevelsFromCatalog(VERGLEICH_KATALOG()))}`);
	z.push(`deriveThunderThresholdLevels([kein,leicht,mittel,hoch]) → ${j(loader.deriveThunderThresholdLevels(['kein', 'leicht', 'mittel', 'hoch']))}`);
	return z.join('\n');
}

/** Schreibt die Golden-Dateien einer Sprache. */
export function schreibeGolden(lang: 'de' | 'en'): void {
	mkdirSync(GOLDEN_DIR, { recursive: true });
	locale.set(lang);
	try {
		for (const [fall, f] of Object.entries(htmlFaelle())) writeFileSync(path.join(GOLDEN_DIR, `${fall}.${lang}.html`), f() + '\n');
		writeFileSync(path.join(GOLDEN_DIR, `funktionen.${lang}.txt`), funktionsTabelle() + '\n');
	} finally {
		locale.set('de');
	}
}

if (process.env.GZ_GOLDEN_SCHREIBEN === 'de' || process.env.GZ_GOLDEN_SCHREIBEN === 'en') {
	if (import.meta.url === pathToFileURL(process.argv[1] ?? '').href) schreibeGolden(process.env.GZ_GOLDEN_SCHREIBEN);
}
