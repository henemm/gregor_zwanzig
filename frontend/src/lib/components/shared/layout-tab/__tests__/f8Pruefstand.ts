// Issue #2657 (i18n F8, Epic #2644) — gemeinsamer SSR-Pruefstand fuer den
// geteilten Layout-Reiter (LayoutTab + LTCapNote/LTChannelPicker/LTCutLine,
// OutputLayoutEditor), den Korridor-Editor (Wertebereiche, Desktop UND mobil,
// Trip UND Ortsvergleich), Ausblick-Steuerung, Mail-Inhalt und die GPX-Seite.
// Echte Svelte-Komponenten, gerendert mit svelte/server. Zustaende, die die
// Komponenten erst in `$effect`/Klick-Handlern setzen, kommen ueber den Hook
// f8VarianteHook.mjs (exakte Umlenkung benannter `$state`-Startwerte) — Markup und
// Helfer bleiben der echte Quelltext.
// Nutzer `golden-de`. Golden: tests/golden/f8_layout_korridor/<fall>.de.(html|txt)
// = Ist-Stand VOR der Umstellung (nie neu schreiben); <fall>.en.* = Review-Hilfe:
//   cd frontend && GZ_GOLDEN_SCHREIBEN=en npm test -- src/lib/components/shared/layout-tab/__tests__/layout_korridor_sprache.test.ts
// Spec: docs/specs/modules/i18n_f8_layout_korridor_2657.md
// Pfadregel #1409: alles relativ zu DIESER Datei.

import { register } from 'node:module';
import { mkdirSync, writeFileSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

export const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> layout-tab -> shared -> components -> lib -> src -> frontend
export const FRONTEND = path.resolve(HERE, '../../../../../..');
export const SHARED = path.resolve(HERE, '../..');
export const LT = path.join(SHARED, 'layout-tab');
export const CE = path.join(SHARED, 'corridor-editor');
export const GPX_SEITE = path.join(FRONTEND, 'src', 'routes', 'gpx-upload', '+page.svelte');
export const GOLDEN_DIR = path.resolve(FRONTEND, '..', 'tests', 'golden', 'f8_layout_korridor');
const basis = pathToFileURL(FRONTEND + '/').href;
register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, basis);
register(pathToFileURL(path.join(HERE, 'f8VarianteHook.mjs')).href, basis);

const { render } = await import('svelte/server');
const imp = async (datei: string) => await import(pathToFileURL(datei).href);
const komp = async (datei: string) => (await imp(datei)).default;
/** Komponente mit umgelenkten `$state`-Startwerten (s. f8VarianteHook.mjs). */
const variante = async (datei: string, ersetzungen: [string, string][]) =>
	(await import(`${pathToFileURL(datei).href}?f8variante=${Buffer.from(JSON.stringify(ersetzungen)).toString('base64url')}`)).default;

export const { locale, tr, trFor } = await imp(path.join(FRONTEND, 'src/lib/i18n/index.ts'));
export const lt = await imp(path.join(LT, 'ltChannels.ts'));
export const ce = await imp(path.join(CE, 'corridorEditorState.ts'));
export const { CONTENT_MODULE_DESCRIPTIONS } = await imp(path.join(SHARED, 'mailInhaltKonstanten.ts'));

const LayoutTabPruefstand = await komp(path.join(HERE, 'LayoutTabPruefstand.svelte'));
const LTCutLine = await komp(path.join(LT, 'LTCutLine.svelte'));
const OutlookLayoutControls = await komp(path.join(SHARED, 'OutlookLayoutControls.svelte'));
const MailInhaltCard = await komp(path.join(SHARED, 'MailInhaltCard.svelte'));

// Korridor-Editor: Zeilen, Pool und Ladezustand setzt der Editor erst nach dem
// Katalog-Laden ($effect) — hier aus globalThis.__F8_KORRIDOR (Feldnamen = Variablen).
const KORRIDOR_ZUSTAND: [string, string][] = [
	['let rows = $state<CorridorRowState[]>([]);', 'let rows = $state<CorridorRowState[]>(globalThis.__F8_KORRIDOR.rows);'],
	['let poolLeft = $state<(RouteMetricDef | CompareMetricDef)[]>([]);', 'let poolLeft = $state<(RouteMetricDef | CompareMetricDef)[]>(globalThis.__F8_KORRIDOR.poolLeft);'],
	['let unknownCorridors = $state<Corridor[]>([]);', 'let unknownCorridors = $state<Corridor[]>(globalThis.__F8_KORRIDOR.unknownCorridors);'],
	['let compareDefs = $state<CompareMetricDef[] | null>(null);', 'let compareDefs = $state<CompareMetricDef[] | null>(globalThis.__F8_KORRIDOR.compareDefs);'],
	['let compareDefsError = $state<string | null>(null);', 'let compareDefsError = $state<string | null>(globalThis.__F8_KORRIDOR.compareDefsError);'],
	['let routeExtraDefs = $state<RouteMetricDef[] | null>(null);', 'let routeExtraDefs = $state<RouteMetricDef[] | null>(globalThis.__F8_KORRIDOR.routeExtraDefs);'],
	['let routeDefsFailed = $state(false);', 'let routeDefsFailed = $state(globalThis.__F8_KORRIDOR.routeDefsFailed);']
];
const CorridorEditor = await variante(path.join(CE, 'CorridorEditor.svelte'), KORRIDOR_ZUSTAND);
const CorridorEditorMobile = await variante(path.join(CE, 'CorridorEditorMobile.svelte'), KORRIDOR_ZUSTAND);

// GPX-Seite: Vorschau/Speichern erscheinen erst nach dem Hochladen (Klick).
const GPX_ZUSTAND: [string, string][] = [
	['let parsedStage: ParsedStage | null = $state(null);', 'let parsedStage: ParsedStage | null = $state(globalThis.__F8_GPX.parsedStage);'],
	["let tripName: string = $state('');", 'let tripName: string = $state(globalThis.__F8_GPX.tripName);'],
	['let savedTripId: string | null = $state(null);', 'let savedTripId: string | null = $state(globalThis.__F8_GPX.savedTripId);']
];
const GpxSeite = await variante(GPX_SEITE, GPX_ZUSTAND);

export type Kontext = 'route' | 'vergleich';
const nix = () => {};
const g = globalThis as unknown as Record<string, unknown>;
const ohneKommentare = (html: string) => html.replace(/<!--[\s\S]*?-->/g, '');
const html = (k: unknown, props: Record<string, unknown> = {}) => ohneKommentare(render(k as never, { props } as never).body);

// ── Layout-Reiter ────────────────────────────────────────────────────────────

/** Metrik-Katalog wie GET /api/metrics (Labels sind API-Daten, nicht Paket-Texte). */
const KATALOG = {
	temperature: [{ id: 'temperature', label: 'Temperatur', unit: '°C', category: 'temperature', default_enabled: true, col_label: 'Temp' }],
	wind: [
		{ id: 'wind', label: 'Wind', unit: 'km/h', category: 'wind', default_enabled: true, col_label: 'Wind' },
		{ id: 'gust', label: 'Böen', unit: 'km/h', category: 'wind', default_enabled: true, col_label: 'Gust' }
	],
	precipitation: [{ id: 'precipitation', label: 'Niederschlag', unit: 'mm', category: 'precipitation', default_enabled: true, col_label: 'Rain' }]
};
export const COL_LABELS = ['Temp', 'Wind', 'Gust', 'Rain'];
const BUCKETS = { primary: ['temperature', 'wind', 'gust'], secondary: ['precipitation'], off: [] as string[] };

/** Layout-Reiter eines Kontexts fuer einen Kanal (Trip: Metriken, Vergleich: Orte als Spalten). */
export function layoutTabRendern(context: Kontext, channel: 'email' | 'telegram' | 'sms', colCount = 3): string {
	const props =
		context === 'route'
			? { context, channel, colCount, subjectLabel: 'Metriken', hasLabelColumn: false }
			: { context, channel, colCount, subjectLabel: '4 Orte', hasLabelColumn: true, smsCharLimit: lt.SMS_COMPARE_CHAR_LIMIT };
	return html(LayoutTabPruefstand, {
		...props,
		catalog: KATALOG,
		buckets: BUCKETS,
		templates: [{ id: 'wandern', label: 'Wandern', metrics: ['temperature', 'wind'] }]
	});
}

/** Ausblick-Steuerung, Mail-Inhalt, Schnittlinie und Leer-/Sonderzustaende des Ausgabe-Layouts. */
export function bausteineRendern(): string {
	const katalog = [
		{ metric: 'temp_max_c', label: 'Temperatur', metric_id: 'temperature', aggregation: 'max', aggregation_label: 'max', col_label: 'Temp' },
		{ metric: 'wind_max_kmh', label: 'Wind', metric_id: 'wind', aggregation: 'max', aggregation_label: 'max', col_label: 'Wind' }
	];
	const ausblick = (p: Record<string, unknown>) =>
		html(OutlookLayoutControls, { metricKeys: null, catalog: katalog, onMetricKeys: nix, ...p });
	const leer = { primary: [] as string[], secondary: [] as string[], off: ['temperature'] };
	return [
		html(LTCutLine, { label: 'Telegram', max: 7 }),
		ausblick({ enabled: true, onEnabledChange: nix }),
		ausblick({ title: '3-Tages-Vorschau', showEmailOnlyHint: false }),
		html(MailInhaltCard, { reportConfig: { email_format: 'full', show_outlook: true } }),
		html(MailInhaltCard, { reportConfig: { email_format: 'compact' } }),
		html(LayoutTabPruefstand, { context: 'route', channel: 'sms', colCount: 0, subjectLabel: 'Metriken', hasLabelColumn: false, catalog: KATALOG, buckets: leer }),
		html(LayoutTabPruefstand, { context: 'route', channel: 'email', colCount: 9, subjectLabel: 'Metriken', hasLabelColumn: false, catalog: KATALOG, buckets: BUCKETS, hideDetailBucket: true })
	].join('\n');
}

// ── Korridor-Editor ──────────────────────────────────────────────────────────

/** Gespeicherte Trip-Korridore (Nutzer golden-de): offen links, offen rechts, beidseitig offen (Pflicht-Fehler), Ordinal. */
export const ROUTE_KORRIDORE = [
	{ metric: 'wind_gust', range: [null, 70], notify: true, mark: true },
	{ metric: 'temperature_min', range: [-5, null], notify: true, mark: false },
	{ metric: 'snow_line', range: [null, null], notify: true, mark: false },
	{ metric: 'thunder_level_max', range: [0, 1], notify: false, mark: true }
];
/** Zusatz-Metriken aus GET /api/compare/metrics (Labels und Stufen sind API-Daten, F5). */
export const ROUTE_EXTRA = [
	{ metric: 'thunder_level_max', label: 'Gewitter', aggregationLabel: 'max', unit: '', scale: [0, 2], step: 1, kind: 'ordinal', ordinalLabels: ['kein', 'mittel', 'hoch'], defaultMin: null, defaultMax: 0 },
	{ metric: 'visibility_min_m', label: 'Sichtweite', aggregationLabel: 'min', unit: 'm', scale: [0, 10000], step: 500, defaultMin: 2000, defaultMax: null }
];
export const VERGLEICH_DEFS = [
	{ metric: 'wind_max_kmh', label: 'Wind', aggregationLabel: 'max', unit: 'km/h', scale: [0, 100], step: 5, kind: 'range', alarmCapable: true, defaultMin: 0, defaultMax: 50 },
	{ metric: 'thunder_level_max', label: 'Gewitter', aggregationLabel: 'max', unit: '', scale: [0, 2], step: 1, kind: 'ordinal', ordinalLabels: ['kein', 'mittel', 'hoch'], alarmCapable: true, defaultMin: null, defaultMax: 0 },
	{ metric: 'snow_depth_cm', label: 'Schneehöhe', unit: 'cm', scale: [0, 300], step: 10, kind: 'range', alarmCapable: false, defaultMin: 30, defaultMax: 200 }
];
export const VERGLEICH_KORRIDORE = [
	{ metric: 'wind_max_kmh', range: [0, 40], notify: true, mark: true },
	{ metric: 'thunder_level_max', range: [null, 1], notify: true, mark: true },
	{ metric: 'zukunft_metrik_a', range: [1, 2], notify: false, mark: true },
	{ metric: 'zukunft_metrik_b', range: [3, 4], notify: false, mark: true }
];

type Zustand = Record<string, unknown>;
const LEER: Zustand = { rows: [], poolLeft: [], unknownCorridors: [], compareDefs: null, compareDefsError: null, routeExtraDefs: null, routeDefsFailed: false };

/** Zustand nach dem Katalog-Laden, gebaut mit den ECHTEN Pool-Funktionen. */
export function routeZustand(routeDefsFailed = false): Zustand {
	const pool = ce.buildRoutePool(ROUTE_KORRIDORE, undefined, ROUTE_EXTRA);
	return { ...LEER, rows: pool.rows, poolLeft: pool.poolLeft, routeExtraDefs: ROUTE_EXTRA, routeDefsFailed };
}
export function vergleichZustand(anzahlUnbekannt: 1 | 2): Zustand {
	const pool = ce.buildComparePool(VERGLEICH_KORRIDORE.slice(0, 2 + anzahlUnbekannt), VERGLEICH_DEFS);
	return { ...LEER, rows: pool.rows, poolLeft: pool.poolLeft, unknownCorridors: pool.unknownCorridors, compareDefs: VERGLEICH_DEFS };
}

export function korridorRendern(context: Kontext, fassung: 'desktop' | 'mobil', zustand: Zustand): string {
	g.__F8_KORRIDOR = zustand;
	try {
		const props = context === 'route' ? { context, trip: { id: 't1', corridors: ROUTE_KORRIDORE, stages: [] } } : { context, corridors: VERGLEICH_KORRIDORE, isEditMode: true };
		return html(fassung === 'desktop' ? CorridorEditor : CorridorEditorMobile, props);
	} finally {
		delete g.__F8_KORRIDOR;
	}
}

/** Lade- und Fehlerzustaende beider Fassungen. */
export function korridorLadenRendern(): string {
	const teile: string[] = [];
	for (const fassung of ['desktop', 'mobil'] as const) {
		teile.push(korridorRendern('route', fassung, LEER));
		teile.push(korridorRendern('vergleich', fassung, LEER));
		teile.push(korridorRendern('vergleich', fassung, { ...LEER, compareDefsError: 'HTTP 503' }));
	}
	return teile.join('\n');
}

// ── GPX-Seite ────────────────────────────────────────────────────────────────

export const GPX_ETAPPE = {
	name: 'GR20 Etappe 1',
	date: '2026-06-01',
	waypoints: [
		{ name: 'Calenzana', lat: 42.50812, lon: 8.85543, elevation_m: 275, time_window: '08:00-10:00' },
		{ name: 'Ortu di u Piobbu', lat: 42.45012, lon: 8.92401, elevation_m: null }
	]
};

export function gpxRendern(zustand: Zustand = {}): string {
	g.__F8_GPX = { parsedStage: null, tripName: '', savedTripId: null, ...zustand };
	try {
		return html(GpxSeite);
	} finally {
		delete g.__F8_GPX;
	}
}

// ── Golden ───────────────────────────────────────────────────────────────────

/** Golden-Faelle HTML (Spec Implementation Details 6). */
export function htmlFaelle(): Record<string, () => string> {
	return {
		layout_tab_route: () => (['email', 'telegram', 'sms'] as const).map((k) => layoutTabRendern('route', k)).join('\n'),
		layout_tab_vergleich: () => (['email', 'telegram', 'sms'] as const).map((k) => layoutTabRendern('vergleich', k, 9)).join('\n'),
		korridor_route_desktop: () => korridorRendern('route', 'desktop', routeZustand(true)),
		korridor_route_mobil: () => korridorRendern('route', 'mobil', routeZustand(true)),
		korridor_vergleich_desktop: () => korridorRendern('vergleich', 'desktop', vergleichZustand(1)) + '\n' + korridorRendern('vergleich', 'desktop', vergleichZustand(2)),
		korridor_vergleich_mobil: () => korridorRendern('vergleich', 'mobil', vergleichZustand(1)) + '\n' + korridorRendern('vergleich', 'mobil', vergleichZustand(2)),
		korridor_laden: korridorLadenRendern,
		bausteine: bausteineRendern,
		gpx_start: () => gpxRendern(),
		gpx_vorschau: () => gpxRendern({ parsedStage: GPX_ETAPPE, tripName: GPX_ETAPPE.name }),
		gpx_gespeichert: () => gpxRendern({ parsedStage: GPX_ETAPPE, tripName: GPX_ETAPPE.name, savedTripId: 'gr20-etappe-1' })
	};
}

/** Kappungs-Hinweis je Kanal/Zaehlweise (Eingabe → Ausgabe). */
export const CAP_FAELLE: [string, Record<string, unknown>][] = [
	['email', { channel: 'email', limit: { kind: 'none' }, colCount: 5, subject: 'Metriken', hasLabelColumn: false }],
	['telegram_passt', { channel: 'telegram', limit: { kind: 'columns', value: 7 }, colCount: 5, subject: 'Metriken', hasLabelColumn: false }],
	['telegram_zu_breit', { channel: 'telegram', limit: { kind: 'columns', value: 7 }, colCount: 9, subject: 'Metriken', hasLabelColumn: false }],
	['telegram_label_passt', { channel: 'telegram', limit: { kind: 'columns', value: 7 }, colCount: 5, subject: '4 Orte', hasLabelColumn: true }],
	['telegram_label_eine', { channel: 'telegram', limit: { kind: 'columns', value: 7 }, colCount: 1, subject: '0 Orte', hasLabelColumn: true }],
	['telegram_label_zu_breit', { channel: 'telegram', limit: { kind: 'columns', value: 7 }, colCount: 9, subject: '8 Orte', hasLabelColumn: true }],
	['sms_trip', { channel: 'sms', limit: { kind: 'chars', value: 160 }, colCount: 6, subject: 'Metriken', hasLabelColumn: false }],
	['sms_vergleich', { channel: 'sms', limit: { kind: 'chars', value: 153 }, colCount: 6, subject: '4 Orte', hasLabelColumn: true }]
];

/** Funktionsergebnisse als Tabelle `Eingabe → Ausgabe` (eine Zeile je Fall). */
export function funktionsTabelle(): string {
	const z: string[] = [];
	const j = (v: unknown) => JSON.stringify(v);
	for (const [k, p] of CAP_FAELLE) z.push(`ltCapNoteText(${k}) → ${j(lt.ltCapNoteText(p))}`);
	z.push(`ltKanalAbwahlHinweisText() → ${j(lt.ltKanalAbwahlHinweisText())}`);
	for (const d of ce.ROUTE_METRIC_DEFS) {
		z.push(`ROUTE_METRIC_DEFS(${d.metric}) → ${j({ label: d.label, note: d.note, unit: d.unit, scale: d.scale, step: d.step, defaultMin: d.defaultMin, defaultMax: d.defaultMax })}`);
	}
	for (const [profil, liste] of Object.entries(ce.PROFILE_METRICS_WITH_SCALES as Record<string, { key: string; label: string }[]>))
		z.push(`PROFILE_METRICS_WITH_SCALES(${profil}) → ${j(liste.map((m) => ({ key: m.key, label: m.label })))}`);
	for (const k of Object.keys(CONTENT_MODULE_DESCRIPTIONS))
		z.push(`CONTENT_MODULE_DESCRIPTIONS(${k}) → ${j({ label: CONTENT_MODULE_DESCRIPTIONS[k].label, description: CONTENT_MODULE_DESCRIPTIONS[k].description })}`);
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
