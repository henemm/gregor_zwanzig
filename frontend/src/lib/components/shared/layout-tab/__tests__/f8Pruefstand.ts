// Issue #2657 (i18n F8, Epic #2644) — gemeinsamer SSR-Pruefstand fuer Kappungs- und
// Korridor-Logik, die Mail-Inhalt-Konstanten und die GPX-Seite. #3020 S1: die Alt-Bausteine
// (Layout-Reiter, Ausblick-Steuerung, Mail-Inhalt-Karte) rendert f8Altbausteine.ts.
// #2794 S3a Teil-PR 4a (AC-31): der Korridor-Editor (CorridorEditor/
// CorridorEditorMobile) ist als Oberflaeche entfernt — seine Faelle samt Golden
// entfallen; die Korridor-Logik (`ce`, shared/wetter-tab/corridorEditorState.ts)
// bleibt fuer die Funktionstabelle.
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
export const GPX_SEITE = path.join(FRONTEND, 'src', 'routes', 'gpx-upload', '+page.svelte');
export const GOLDEN_DIR = path.resolve(FRONTEND, '..', 'tests', 'golden', 'f8_layout_korridor');
const basis = pathToFileURL(FRONTEND + '/').href;
register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, basis);
register(pathToFileURL(path.join(HERE, 'f8VarianteHook.mjs')).href, basis);

const { render } = await import('svelte/server');
const imp = async (datei: string) => await import(pathToFileURL(datei).href);
export const komp = async (datei: string) => (await imp(datei)).default;
/** Komponente mit umgelenkten `$state`-Startwerten (s. f8VarianteHook.mjs). */
const variante = async (datei: string, ersetzungen: [string, string][]) =>
	(await import(`${pathToFileURL(datei).href}?f8variante=${Buffer.from(JSON.stringify(ersetzungen)).toString('base64url')}`)).default;

export const { locale, tr, trFor } = await imp(path.join(FRONTEND, 'src/lib/i18n/index.ts'));
export const lt = await imp(path.join(LT, 'ltChannels.ts'));
export const ce = await imp(path.join(SHARED, 'wetter-tab', 'corridorEditorState.ts'));
export const { CONTENT_MODULE_DESCRIPTIONS } = await imp(path.join(SHARED, 'mailInhaltKonstanten.ts'));

// GPX-Seite: Vorschau/Speichern erscheinen erst nach dem Hochladen (Klick).
const GPX_ZUSTAND: [string, string][] = [
	['let parsedStage: ParsedStage | null = $state(null);', 'let parsedStage: ParsedStage | null = $state(globalThis.__F8_GPX.parsedStage);'],
	["let tripName: string = $state('');", 'let tripName: string = $state(globalThis.__F8_GPX.tripName);'],
	['let savedTripId: string | null = $state(null);', 'let savedTripId: string | null = $state(globalThis.__F8_GPX.savedTripId);']
];
const GpxSeite = await variante(GPX_SEITE, GPX_ZUSTAND);

export type Kontext = 'route' | 'vergleich';
const g = globalThis as unknown as Record<string, unknown>;
const ohneKommentare = (html: string) => html.replace(/<!--[\s\S]*?-->/g, '');
export const html =(k: unknown, props: Record<string, unknown> = {}) => ohneKommentare(render(k as never, { props } as never).body);

// ── Korridor-Logik (Daten fuer die Speicher-Nutzlast, AC-4) ─────────────────

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

// ── GPX-Seite ────────────────────────────────────────────────────────────────

type Zustand = Record<string, unknown>;

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
export function schreibeGolden(lang: 'de' | 'en', faelle = htmlFaelle()): void {
	mkdirSync(GOLDEN_DIR, { recursive: true });
	locale.set(lang);
	try {
		for (const [fall, f] of Object.entries(faelle)) writeFileSync(path.join(GOLDEN_DIR, `${fall}.${lang}.html`), f() + '\n');
		writeFileSync(path.join(GOLDEN_DIR, `funktionen.${lang}.txt`), funktionsTabelle() + '\n');
	} finally {
		locale.set('de');
	}
}

if (process.env.GZ_GOLDEN_SCHREIBEN === 'de' || process.env.GZ_GOLDEN_SCHREIBEN === 'en') {
	if (import.meta.url === pathToFileURL(process.argv[1] ?? '').href) schreibeGolden(process.env.GZ_GOLDEN_SCHREIBEN);
}
