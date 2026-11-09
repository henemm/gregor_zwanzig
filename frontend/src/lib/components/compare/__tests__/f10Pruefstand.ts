// Issue #2659 (i18n F10, Epic #2644) — gemeinsamer SSR-Pruefstand fuer die
// Ortsvergleich-Flaechen: Hub (Reiterleiste, Uebersicht, Orte-Reiter, Seite
// /compare/[id]), transponierte Uebersicht (Stundenverlauf-Steuerung), Anlegen
// (CompareNewEditor, Orte-Schritt, Neuer Ort) und die Kleinbausteine. Echte
// Svelte-Komponenten, gerendert mit svelte/server. Zustaende, die die Komponenten
// erst in `$effect`/`onMount`/Klick-Handlern setzen, kommen ueber den F8-Hook
// (f8VarianteHook.mjs: exakte Umlenkung benannter `$state`-Startwerte) — Markup
// und Helfer bleiben der echte Quelltext.
// Nutzer `golden-de`: ein aktiver, ein pausierter und ein Entwurf-Ortsvergleich,
// je 3 Orte, Kanaele E-Mail und Telegram.
// Golden: tests/golden/f10_vergleich_flaechen/<fall>.de.html = Ist-Stand VOR der
// Umstellung (nie neu schreiben); <fall>.en.html = Review-Hilfe:
//   cd frontend && GZ_GOLDEN_SCHREIBEN=en npm test -- src/lib/components/compare/__tests__/vergleich_hub_sprache.test.ts
// Spec: docs/specs/modules/i18n_f10_vergleich_flaechen_2659.md
// Pfadregel #1409: alles relativ zu DIESER Datei.

import { register } from 'node:module';
import { mkdirSync, writeFileSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

process.env.TZ = 'Europe/Berlin';

export const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> compare -> components -> lib -> src -> frontend
export const FRONTEND = path.resolve(HERE, '../../../../..');
export const KOMP = path.resolve(HERE, '../..');
export const CMP = path.join(KOMP, 'compare');
export const GOLDEN_DIR = path.resolve(FRONTEND, '..', 'tests', 'golden', 'f10_vergleich_flaechen');
const basis = pathToFileURL(FRONTEND + '/').href;
const hook = (p: string) => register(pathToFileURL(path.join(FRONTEND, p)).href, basis);
hook('test-env-dynamic-private-stub-hooks.mjs');
hook('test-app-environment-stub-hooks.mjs');
hook('src/routes/__tests__/layout-ssr-hooks.mjs');
hook('src/lib/components/trip-new/__tests__/ssrRunesHook.mjs');
hook('test-svelte-ssr-hooks.mjs');
hook('src/lib/components/shared/__tests__/svelteTsModulHook.mjs');
hook('src/lib/components/shared/layout-tab/__tests__/f8VarianteHook.mjs');

const { render } = await import('svelte/server');
const imp = async (datei: string) => await import(pathToFileURL(datei).href);
const komp = async (datei: string) => (await imp(datei)).default;
/** Komponente mit umgelenkten `$state`-Startwerten (s. f8VarianteHook.mjs). */
const variante = async (datei: string, ersetzungen: [string, string][]) =>
	(await import(`${pathToFileURL(datei).href}?f8variante=${Buffer.from(JSON.stringify(ersetzungen)).toString('base64url')}`)).default;

export const { locale, tr, trFor, trnFor } = await imp(path.join(FRONTEND, 'src/lib/i18n/index.ts'));
export const helfer = await imp(path.join(CMP, 'subscriptionHelpers.ts'));
export const persistenz = await imp(path.join(CMP, 'compareHubPersistenz.ts'));
export const modell = await imp(path.join(KOMP, 'shared/hub-uebersicht/hubUebersichtModell.ts'));
export const aktionen = await imp(path.join(KOMP, 'shared/subscriptionActions.ts'));
export const reiter = await imp(path.join(KOMP, 'shared/subscriptionTabs.ts'));

const ohneKommentare = (html: string) => html.replace(/<!--[\s\S]*?-->/g, '');
/** Feste Uhr fuer jeden Render und jede Funktionszeile: Golden bleibt tagesunabhaengig. */
const ECHT_DATE = Date;
export const JETZT_ISO = '2026-10-29T09:30:00';
export function mitUhr<T>(f: () => T): T {
	const fest = new ECHT_DATE(JETZT_ISO).getTime();
	class Uhr extends ECHT_DATE {
		constructor(...a: unknown[]) {
			if (a.length === 0) super(fest);
			else super(...(a as [string]));
		}
		static now() {
			return fest;
		}
	}
	globalThis.Date = Uhr as unknown as DateConstructor;
	try {
		return f();
	} finally {
		globalThis.Date = ECHT_DATE;
	}
}
const html = (k: unknown, props: Record<string, unknown> = {}, context?: Map<unknown, unknown>) =>
	mitUhr(() => ohneKommentare(render(k as never, { props, ...(context ? { context } : {}) } as never).body));
const cmp = (n: string) => path.join(CMP, n);

// ── Fixture golden-de ────────────────────────────────────────────────────────

export const ORTE = [
	{ id: 'l-hx', name: 'Hintertux', lat: 47.0789, lon: 11.6856, elevation_m: 3250, group_id: 'g-zt', region: 'Tirol' },
	{ id: 'l-ka', name: 'Kaunertal', lat: 46.8611, lon: 10.7172, elevation_m: 2750, group_id: 'g-zt', region: 'Tirol' },
	{ id: 'l-ob', name: 'Obergurgl', lat: 46.8697, lon: 11.0272, elevation_m: 1907 },
	{ id: 'l-sf', name: 'Sölden', lat: 46.9655, lon: 11.0076, elevation_m: 1368 }
];
export const GRUPPEN = [{ id: 'g-zt', name: 'Zillertal', order: 0 }];
const BASIS = {
	location_ids: ['l-hx', 'l-ka', 'l-ob'],
	profil: 'wintersport',
	hour_from: 6,
	hour_to: 9,
	empfaenger: [],
	forecast_hours: 48,
	created_at: '2026-10-01T00:00:00Z',
	send_telegram: true,
	morning_enabled: true,
	morning_time: '07:00:00',
	evening_enabled: true,
	evening_time: '18:00:00',
	display_config: { region: 'Tirol', ideal_ranges: { snow_depth_cm: { min: 30, max: 200 }, wind_max_kmh: { min: 0, max: 40 } } }
};
export const vergleichAktiv = (extra: Record<string, unknown> = {}) => ({ ...BASIS, id: 'gd-aktiv', name: 'Skitouren Tirol', schedule: 'daily', letzter_versand: '2026-10-27T05:00:00Z', ...extra });
export const vergleichPausiert = () => vergleichAktiv({ id: 'gd-pause', name: 'Gletscher Herbst', schedule: 'manual', previous_schedule: 'daily', paused_at: '2026-10-20T08:00:00Z', end_date: '2026-10-25', letzter_versand: undefined });
export const vergleichEntwurf = () => vergleichAktiv({ id: 'gd-entwurf', name: '', letzter_versand: undefined, location_ids: ['l-hx', 'l-ka', 'l-ob'] });
export const VERGLEICHE = { aktiv: vergleichAktiv, pausiert: vergleichPausiert, entwurf: vergleichEntwurf };

/** Katalog wie GET /api/compare/metrics (Namen nur deutsch) — Stundenverlauf/Ausblick. */
export const VERGLEICHS_KATALOG = [
	{ metric: 'temp_max_c', label: 'Temperatur', metric_id: 'temperature', aggregation: 'max', aggregation_label: 'Maximum', col_label: 'Temp', sms_code: 'T', hourlyDefault: true },
	{ metric: 'wind_max_kmh', label: 'Wind', metric_id: 'wind', aggregation: 'max', aggregation_label: 'Maximum', col_label: 'Wind', sms_code: 'W', hourlyDefault: true },
	{ metric: 'cloud_avg_pct', label: 'Bewölkung', metric_id: 'cloud_total', aggregation: 'avg', aggregation_label: 'Mittel', col_label: 'Cloud', sms_code: 'C', hourlyDefault: false },
	{ metric: 'sunny_hours_h', label: 'Sonnenstunden', metric_id: 'sunshine', aggregation: 'sum', aggregation_label: 'Summe', col_label: 'Sun', hourlySelectable: false, hourlyNotSelectableReason: 'nur als Tageswert' }
];
/** Register wie GET /api/metrics (F5): mit und ohne label_en. */
export const REGISTER = {
	temperature: { id: 'temperature', label: 'Temperatur', label_en: 'Temperature', col_label: 'Temp' },
	wind: { id: 'wind', label: 'Wind', label_en: 'Wind', col_label: 'Wind' },
	cloud_total: { id: 'cloud_total', label: 'Bewölkung', col_label: 'Cloud' },
	sunshine: { id: 'sunshine', label: 'Sonnenstunden', label_en: 'Sunshine hours', col_label: 'Sun' }
};
export const COL_LABELS = ['Temp', 'Wind', 'Cloud', 'Sun'];

// ── Komponenten ──────────────────────────────────────────────────────────────

const K = {
	CompareTabs: await komp(cmp('CompareTabs.svelte')),
	CompareTabsMobil: await variante(cmp('CompareTabs.svelte'), [['let isMobileViewport = $state(false);', 'let isMobileViewport = $state(true);']]),
	CompareTabsPanel: await variante(cmp('CompareTabs.svelte'), [
		['let addPanelOpen = $state(false);', 'let addPanelOpen = $state(true);'],
		['let allLocationsForAdd = $state<Location[]>([]);', 'let allLocationsForAdd = $state<Location[]>(globalThis.__f10Orte ?? []);'],
		['let groupsForAdd = $state<Group[]>([]);', 'let groupsForAdd = $state<Group[]>(globalThis.__f10Gruppen ?? []);']
	]),
	HubUebersichtMobil: await variante(path.join(KOMP, 'shared/hub-uebersicht/HubUebersicht.svelte'), [['let isMobileViewport = $state(false);', 'let isMobileViewport = $state(true);']]),
	// #2837 S1b: CompareStatusPill ist im geteilten StatusSchild aufgegangen.
	StatusSchild: await komp(path.join(KOMP, 'shared/status-schild/StatusSchild.svelte')),
	AddReportCard: await komp(cmp('AddReportCard.svelte')),
	LocationPreviewMap: await komp(cmp('LocationPreviewMap.svelte')),
	CompareHourly: await komp(cmp('CompareHourlyLayoutControls.svelte')),
	LocationNewModal: await komp(cmp('LocationNewModal.svelte')),
	LocationNewModalErkannt: await variante(cmp('LocationNewModal.svelte'), [
		['let resolvedPreview: ResolveResult | null = $state(null);', "let resolvedPreview: ResolveResult | null = $state({ lat: 47.0789, lon: 11.6856, elevation_m: 3250, timezone: 'Europe/Vienna', region: 'Tirol', source_type: 'komoot' });"],
		['let saving = $state(false);', 'let saving = $state(true);']
	]),
	Step2Orte: await komp(cmp('steps/Step2Orte.svelte')),
	Step2OrteVorschau: await variante(cmp('steps/Step2Orte.svelte'), [
		['let preview = $state<ResolveResult | null>(null);', "let preview = $state<ResolveResult | null>({ lat: 47.0789, lon: 11.6856, elevation_m: 3250, timezone: 'Europe/Vienna', source_type: 'komoot' });"],
		["let nameDraft = $state('');", "let nameDraft = $state('Hintertux');"]
	]),
	Step2OrteHinzufuegen: await variante(cmp('steps/Step2Orte.svelte'), [
		['let preview = $state<ResolveResult | null>(null);', "let preview = $state<ResolveResult | null>({ lat: 47.0789, lon: 11.6856, timezone: 'Europe/Vienna', source_type: 'dec' });"],
		['let adding = $state(false);', 'let adding = $state(true);']
	]),
	CompareNewEditor: await komp(path.join(KOMP, 'compare-new', 'CompareNewEditor.svelte')),
	// Gesperrter Reiter (mobil): der Toast zeigt den Sperr-Hinweis der Anlege-Kette.
	CompareNewToast: await variante(path.join(KOMP, 'compare-new', 'CompareNewEditor.svelte'), [
		// Bestand hielt den Hinweistext; seit F10 die Reiter-Kennung (Hinweis beim Rendern).
		['let lockToastTab = $state<CompareNewTabId | null>(null);', "let lockToastTab = $state<CompareNewTabId | null>('orte');"],
		['let lockToastVisible = $state(false);', 'let lockToastVisible = $state(true);']
	])
};

// #2727: Startwerte des Anlegens reisen als Props (Step2Orte `pickedIds`) bzw. ueber
// `stateOverride` (CompareNewEditor), nicht mehr ueber einen Context.

// ── Faelle ───────────────────────────────────────────────────────────────────

/** Hub: Reiterleiste + Uebersicht (Desktop) der drei Vergleiche, mobile Uebersicht ueber den geteilten Baustein. */
export function hubUebersichtRendern(): string {
	const teile: string[] = [];
	for (const v of Object.values(VERGLEICHE)) teile.push(html(K.CompareTabs, { preset: v(), locations: ORTE, initialTab: 'uebersicht' }));
	for (const [status, v] of [['active', vergleichAktiv], ['paused', vergleichPausiert], ['draft', vergleichEntwurf]] as const) {
		const p = v();
		const orte = p.location_ids.map((id: string, i: number) => ({ rank: i + 1, loc: ORTE.find((o) => o.id === id) }));
		teile.push(html(K.HubUebersichtMobil, { context: 'vergleich', preset: p, status, orte }));
	}
	return teile.join('\n');
}

/** Orte-Reiter: Desktop, mobil, leer, Hinzufuegen-Panel mit Gruppen bzw. ohne weitere Orte. */
export function hubOrteRendern(): string {
	const g = globalThis as unknown as Record<string, unknown>;
	const teile = [
		html(K.CompareTabs, { preset: vergleichAktiv(), locations: ORTE, initialTab: 'orte' }),
		html(K.CompareTabsMobil, { preset: vergleichAktiv(), locations: ORTE, initialTab: 'orte' }),
		html(K.CompareTabs, { preset: vergleichAktiv({ location_ids: [] }), locations: ORTE, initialTab: 'orte' })
	];
	g.__f10Orte = ORTE;
	g.__f10Gruppen = GRUPPEN;
	try {
		teile.push(html(K.CompareTabsPanel, { preset: vergleichAktiv(), locations: ORTE, initialTab: 'orte' }));
		g.__f10Orte = ORTE.slice(0, 3);
		teile.push(html(K.CompareTabsPanel, { preset: vergleichAktiv(), locations: ORTE, initialTab: 'orte' }));
	} finally {
		delete g.__f10Orte;
		delete g.__f10Gruppen;
	}
	return teile.join('\n');
}

const SEITE = path.join(FRONTEND, 'src', 'routes', 'compare', '[id]', '+page.svelte');
const seitenVariante = (extra: [string, string][] = []) => variante(SEITE, extra);
const S = {
	ruhe: await seitenVariante(),
	mobil: await seitenVariante([['let mobil = $state(false);', 'let mobil = $state(true);']]),
	senden: await seitenVariante([['let isSending = $state(false);', 'let isSending = $state(true);']]),
	meldung: await seitenVariante([
		['let sendMsg = $state<string | null>(null);', "let sendMsg = $state<string | null>('Test-Briefing gesendet');"],
		// Bestand: pauseError trug den Text; seit F10 nur das Flag (Text beim Rendern).
		['let pauseError = $state(false);', 'let pauseError = $state(true);']
	])
};
export function seiteRendern(fall: keyof typeof S, preset: Record<string, unknown> = vergleichAktiv(), orte = ORTE.slice(0, 3)): string {
	return html(S[fall], { data: { preset, locations: orte, profile: null } });
}

/** Seite /compare/[id]: Kopf, Breadcrumb, Status, Senden/Setup, Orte-Anzahl, Dialoge (alle Zustaende). */
export function hubSeiteRendern(): string {
	return [
		seiteRendern('ruhe'),
		seiteRendern('ruhe', vergleichPausiert(), ORTE.slice(0, 1)),
		seiteRendern('ruhe', vergleichEntwurf()),
		seiteRendern('mobil'),
		seiteRendern('senden'),
		seiteRendern('meldung')
	].join('\n');
}

/** Transponierte Uebersicht: Stundenverlauf-Steuerung (Schalter, Auswahl, Reihenfolge, Hinweis). */
export function stundenverlaufRendern(): string {
	return [
		html(K.CompareHourly, { metricKeys: null, onMetricKeys: () => {}, catalog: VERGLEICHS_KATALOG, enabled: true, onEnabledChange: () => {} }),
		html(K.CompareHourly, { metricKeys: ['cloud_total'], onMetricKeys: () => {}, catalog: VERGLEICHS_KATALOG, register: REGISTER }),
		html(K.CompareHourly, { metricKeys: [], onMetricKeys: () => {}, catalog: [] })
	].join('\n');
}

/** Kleinbausteine: Status-Pille, Neuer Auto-Report, Kartenvorschau. */
export function bausteineRendern(): string {
	return [
		...(['active', 'paused', 'draft'] as const).map((status) => html(K.StatusSchild, { status })),
		html(K.AddReportCard, { onclick: () => {} }),
		html(K.LocationPreviewMap, { lat: 47.0789, lon: 11.6856 })
	].join('\n');
}

/** Neuer Ort (Modal): leer und mit erkannter Vorschau beim Speichern. */
export function ortNeuRendern(): string {
	return [html(K.LocationNewModal, { onsave: () => {}, oncancel: () => {} }), html(K.LocationNewModalErkannt, { onsave: () => {}, oncancel: () => {} })].join('\n');
}

/** Orte-Schritt beim Anlegen: leer, mit Auswahl, erkannt, beim Hinzufuegen, mobil. */
export function orteSchrittRendern(): string {
	const zwei = () => ['l-hx', 'l-ob'];
	return [
		html(K.Step2Orte, { locations: ORTE, groups: GRUPPEN, pickedIds: [] }),
		html(K.Step2Orte, { locations: [], groups: [], pickedIds: [] }),
		html(K.Step2Orte, { locations: ORTE, groups: GRUPPEN, pickedIds: ['l-hx'] }),
		html(K.Step2Orte, { locations: ORTE, groups: GRUPPEN, pickedIds: ORTE.map((o) => o.id).concat(['x1', 'x2']) }),
		html(K.Step2OrteVorschau, { locations: ORTE, groups: GRUPPEN, pickedIds: zwei() }),
		html(K.Step2OrteHinzufuegen, { locations: ORTE, groups: GRUPPEN, pickedIds: zwei() }),
		html(K.Step2Orte, { locations: ORTE, groups: GRUPPEN, dense: true, pickedIds: [] }),
		html(K.Step2Orte, { locations: ORTE, groups: GRUPPEN, dense: true, pickedIds: ['l-hx'] }),
		html(K.Step2Orte, { locations: ORTE, groups: GRUPPEN, dense: true, pickedIds: zwei() })
	].join('\n');
}

export type AnlegeFall = { tab: string; mobil: boolean; name?: string; picked?: string[]; profil?: string; besucht?: boolean };
export function anlegenRendern(f: AnlegeFall): string {
	const stateOverride = {
		activeTab: f.tab, isMobileViewport: f.mobil, metrikenVisited: f.besucht, zustellungVisited: f.besucht,
		name: f.name ?? '', region: '', pickedIds: f.picked ?? [], ...(f.profil ? { activityProfile: f.profil } : {})
	};
	return html(K.CompareNewEditor, { locations: ORTE, groups: GRUPPEN, stateOverride });
}
export const ANLEGE_FAELLE: Record<string, AnlegeFall[]> = {
	anlegen_vergleich: [
		{ tab: 'vergleich', mobil: false },
		{ tab: 'vergleich', mobil: false, name: 'Skitouren Tirol', profil: 'wintersport' },
		{ tab: 'vergleich', mobil: true },
		{ tab: 'vergleich', mobil: true, name: 'Skitouren Tirol', profil: 'wandern' }
	],
	anlegen_orte: [
		{ tab: 'orte', mobil: false, name: 'Skitouren Tirol', picked: ['l-hx'] },
		{ tab: 'orte', mobil: false, name: 'Skitouren Tirol', picked: ['l-hx', 'l-ka', 'l-ob'] },
		{ tab: 'orte', mobil: true, name: 'Skitouren Tirol', picked: [] },
		{ tab: 'orte', mobil: true, name: 'Skitouren Tirol', picked: ['l-hx'] },
		{ tab: 'orte', mobil: true, name: 'Skitouren Tirol', picked: ['l-hx', 'l-ka'] }
	],
	anlegen_weiter: [
		// #2794 S3a: Schritte Wetter und Zustellung.
		{ tab: 'wetter', mobil: true, name: 'Skitouren Tirol', picked: ['l-hx', 'l-ka'] },
		{ tab: 'wetter', mobil: false, name: 'Skitouren Tirol', picked: ['l-hx', 'l-ka'], besucht: false },
		{ tab: 'zustellung', mobil: false, name: 'Skitouren Tirol', picked: ['l-hx', 'l-ka'], besucht: true },
		{ tab: 'zustellung', mobil: true, name: 'Skitouren Tirol', picked: ['l-hx', 'l-ka'], besucht: true },
		{ tab: 'zustellung', mobil: true, name: 'Skitouren Tirol', picked: ['l-hx', 'l-ka'] }
	]
};

export function anlegenToastRendern(): string {
	return html(K.CompareNewToast, { locations: ORTE, groups: GRUPPEN, stateOverride: { activeTab: 'vergleich', isMobileViewport: true } });
}

// ── Fehler-Flags (nur neuer Quelltext): ohne Server-Text halten die Bausteine nur ein
// Flag bzw. einen Schluessel; die Meldung entsteht beim Rendern in der aktuellen Sprache.
const FLAG = {
	seite: await seitenVariante([['let sendKey = $state<MessageKey | null>(null);', "let sendKey = $state<MessageKey | null>('vergleich.hub.test_gesendet');"]]),
	seiteFehler: await seitenVariante([['let sendKey = $state<MessageKey | null>(null);', "let sendKey = $state<MessageKey | null>('vergleich.hub.archivieren_fehler');"]]),
	orte: await variante(cmp('steps/Step2Orte.svelte'), [['let resolveErrorKey = $state<MessageKey | null>(null);', "let resolveErrorKey = $state<MessageKey | null>('vergleich.orte.format_unbekannt');"]]),
	ortNeu: await variante(cmp('LocationNewModal.svelte'), [['let saveError: string | null = $state(null);', "let saveError: string | null = $state('');"]])
};
export function fehlerFlagsRendern(): string[] {
	return [
		html(FLAG.seite, { data: { preset: vergleichAktiv(), locations: ORTE.slice(0, 3), profile: null } }),
		html(FLAG.seiteFehler, { data: { preset: vergleichAktiv(), locations: ORTE.slice(0, 3), profile: null } }),
		html(FLAG.orte, { locations: ORTE, groups: GRUPPEN, pickedIds: [] }),
		html(FLAG.ortNeu, { onsave: () => {}, oncancel: () => {} })
	];
}

// ── Golden ───────────────────────────────────────────────────────────────────

export function htmlFaelle(): Record<string, () => string> {
	const f: Record<string, () => string> = {
		hub_uebersicht: hubUebersichtRendern,
		hub_orte: hubOrteRendern,
		hub_seite: hubSeiteRendern,
		stundenverlauf: stundenverlaufRendern,
		bausteine: bausteineRendern,
		ort_neu: ortNeuRendern,
		orte_schritt: orteSchrittRendern
	};
	for (const [fall, liste] of Object.entries(ANLEGE_FAELLE)) f[fall] = () => liste.map(anlegenRendern).join('\n');
	f.anlegen_toast = anlegenToastRendern;
	return f;
}

/** Funktionsergebnisse als Tabelle `Eingabe → Ausgabe` (eine Zeile je Fall), feste Uhr. */
export function funktionsTabelle(): string {
	return mitUhr(() => {
		const z: string[] = [];
		const j = (v: unknown) => JSON.stringify(v);
		const H = helfer;
		const p = (extra: Record<string, unknown>) => vergleichAktiv(extra);
		z.push(`STATUS_MAP → ${j(Object.fromEntries(Object.entries(H.STATUS_MAP).map(([k, v]) => [k, tr((v as { key: string }).key)])))}`);
		for (const [name, extra] of [['daily 7–9', { hour_from: 7, hour_to: 9 }], ['weekly', { schedule: 'weekly' }], ['manual', { schedule: 'manual' }]] as const)
			z.push(`presetScheduleLabel(${name}) → ${j(H.presetScheduleLabel(p(extra)))}`);
		z.push(`formatNextSend(null) → ${j(H.formatNextSend(null))}`);
		z.push(`formatNextSend(2026-10-30 07:05) → ${j(H.formatNextSend(new Date('2026-10-30T07:05:00')))}`);
		for (const iso of [null, 'kaputt', '2026-10-27T05:00:00Z']) z.push(`formatLastSent(${iso}) → ${j(H.formatLastSent(iso))}`);
		for (const n of [0, 1, 3]) z.push(`presetLocationsLabel(${n}) → ${j(H.presetLocationsLabel(p({ location_ids: ORTE.slice(0, n).map((o) => o.id) })))}`);
		for (const profil of ['allgemein', 'wintersport', 'wandern', 'summer_trekking', 'SUMMER_TREKKING', 'unbekannt', undefined]) z.push(`presetProfileLabel(${profil}) → ${j(H.presetProfileLabel(profil))}`);
		z.push(`presetTileScheduleLabel(daily 07:00) → ${j(H.presetTileScheduleLabel(p({})))}`);
		z.push(`presetTileScheduleLabel(daily ohne Slot) → ${j(H.presetTileScheduleLabel(p({ morning_enabled: false, evening_enabled: false })))}`);
		for (const wd of [0, 1, 2, 3, 4, 5, 6, 9]) z.push(`presetTileScheduleLabel(weekly ${wd}) → ${j(H.presetTileScheduleLabel(p({ schedule: 'weekly', weekday: wd })))}`);
		z.push(`presetTileScheduleLabel(manual) → ${j(H.presetTileScheduleLabel(p({ schedule: 'manual' })))}`);
		for (const iso of [undefined, 'kaputt', '2026-10-29T06:00:00', '2026-10-28T06:00:00', '2026-10-26T06:00:00', '2026-10-23T06:00:00', '2026-10-22T06:00:00', '2026-10-15T06:00:00', '2026-09-01T06:00:00'])
			z.push(`relativeLastSent(${iso}) → ${j(H.relativeLastSent(iso))}`);
		z.push(`presetBriefingTimesLabel(beide) → ${j(H.presetBriefingTimesLabel(p({})))}`);
		z.push(`presetBriefingTimesLabel(keiner) → ${j(H.presetBriefingTimesLabel(p({ morning_enabled: false, evening_enabled: false })))}`);
		z.push(`channelNamesLabel(E-Mail+Telegram) → ${j(H.channelNamesLabel(p({})))}`);
		z.push(`channelNamesLabel(alle vier) → ${j(H.channelNamesLabel(p({ send_sms: true, send_premium_sms: true })))}`);
		for (const s of ['active', 'paused', 'draft']) z.push(`hubActivationBanner(${s}) → ${j(persistenz.hubActivationBanner(s))}`);
		for (const [s, v] of [['active', vergleichAktiv], ['paused', vergleichPausiert], ['draft', vergleichEntwurf]] as const) {
			const pr = v();
			const orte = pr.location_ids.map((id: string, i: number) => ({ rank: i + 1, loc: ORTE.find((o) => o.id === id) }));
			z.push(`deriveVergleichKennzahlen(${s}) → ${j(modell.deriveVergleichKennzahlen(pr, s, null, orte))}`);
		}
		const orteVier = ORTE.map((loc, i) => ({ rank: i + 1, loc }));
		z.push(`deriveVergleichKennzahlen(active, 4 Orte) → ${j(modell.deriveVergleichKennzahlen(vergleichAktiv({ location_ids: ORTE.map((o) => o.id) }), 'active', null, orteVier).orteKarte)}`);
		const trip = { id: 't1', name: 'GR20', stages: [], report_config: { enabled: true, morning_enabled: true, evening_enabled: true, morning_time: '07:00:00', evening_time: '18:00:00', send_email: true, send_telegram: true } };
		for (const s of ['draft', 'active', 'paused', 'finished'])
			z.push(`deriveRouteKennzahlen(${s}) → ${j(modell.deriveRouteKennzahlen(trip, s, null, { zustand: 'geladen', eintraege: [{ sent_at: '2026-10-27T05:00:00Z', kind: 'morning', channels: ['email'] }] }))}`);
		z.push(`deriveRouteKennzahlen(laedt) → ${j(modell.deriveRouteKennzahlen(trip, 'active', null, { zustand: 'laedt', eintraege: [] }).kennzahlen[3])}`);
		return z.join('\n');
	});
}

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
