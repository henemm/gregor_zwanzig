// Issue #3020 S1 — vom F5-Pruefstand abgetrennter Teil: SSR-Renders des Alt-Reiters WeatherMetricsTab
// (beide Kontexte) samt WeatherV2PresetBar/WeatherV2Reihenfolge, die kein Nutzer mehr sieht. Faellt mit S3.
// Katalog, Lade- und Fehlerzustand setzt der Reiter erst in `$effect` (laeuft beim SSR nie) — sie kommen ueber
// f5VarianteHook.mjs. Pfadregel #1409: alles relativ zu DIESER Datei.

import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { html, komp, variante, WMT, SHARED, KATALOG_ALT, SMS_SYMBOLE, VERGLEICH_KATALOG, katalogMitRegister, type Eintrag, type Katalog } from './f5Pruefstand.ts';

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
	['let activeChannel = $state<ChannelId>(\'email\');', 'let activeChannel = $state<ChannelId>(globalThis.__F5.activeChannel);'],
	// #3047 R8 F3: Kanal-Reiter im Ortsvergleich (Telegram-Trennlinie je Kontext).
	['let compareChannel = $state<ChannelId>(\'email\');', 'let compareChannel = $state<ChannelId>(globalThis.__F5.compareChannel);']
];
const WeatherMetricsTab = await variante(path.join(SHARED, 'WeatherMetricsTab.svelte'), ZUSTAND);
const WeatherV2PresetBar = await komp(path.join(WMT, 'WeatherV2PresetBar.svelte'));
const WeatherV2Reihenfolge = await komp(path.join(WMT, 'WeatherV2Reihenfolge.svelte'));
const SavePresetDialog = await komp(path.join(WMT, 'SavePresetDialog.svelte'));

/** Alt-Speicherweg (Nutzlast der Grundauswahl); untypisiert wie zuvor im Test (aufgezeichneter Katalog). */
const modul = async (n: string) => await import(pathToFileURL(path.join(WMT, n)).href);
export const { buildGlobalMetricsForSave } = await modul('weatherMetricsSavePayload.ts');
export const { toggleGlobalMetric } = await modul('channelMetricLayouts.ts');

const nix = () => {};
const g =globalThis as unknown as Record<string, unknown>;

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
	/** #3047 R8 F3: aktiver Kanal-Reiter und Telegram-Liste im Ortsvergleich. */
	compareChannel?: 'email' | 'telegram' | 'sms';
	telegramAuswahl?: string[];
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
		activeChannel: z.activeChannel ?? 'email',
		compareChannel: z.compareChannel ?? 'email'
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
		channelActiveMetricKeys: { email: null, telegram: z.telegramAuswahl ?? [aktiv[0], aktiv[2]], sms: null },
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
		html(WeatherV2PresetBar, { selectedTemplate: 'p-golden', dirty: false, templates: TEMPLATES, userPresets: USER_PRESETS, onSelectPreset: nix, onOpenSaveDialog: nix }),
		// #2794 S3a Teil-PR 3 (AC-42): Dialog auf die Ampel umgestellt (kind + ampel statt Bucket-Karten).
		html(SavePresetDialog, { open: true, kind: 'route', ampel: { template: 'allgemein' }, onClose: nix, onSaved: nix }),
		html(WeatherV2Reihenfolge, {
			primaryColumns: ['temperature', 'wind', 'gust', 'precipitation', 'thunder', 'cloud_total', 'humidity', 'dewpoint', 'wind_chill'],
			metricById: byId, friendlyMap: { wind: true }, activeChannel: 'telegram', highlight: null,
			onRemove: nix, onDndReorder: nix, onMode: nix, offColumns: ['snow_depth'], onRestore: nix,
			showAbwahlHinweis: false, kuerzelById: { temperature: ['T'], gust: ['G'], snow_depth: ['SD'] },
			context: 'route' // #3047 R8 F3: Trennlinie nur mit Kontext
		})
	].join('\n');
}

/** Golden-Faelle HTML des Alt-Reiters. */
export const altFaelle = (): Record<string, () => string> => ({
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
});
