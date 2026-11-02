// Issue #2658 (i18n F9, Epic #2644) — gemeinsamer SSR-Pruefstand fuer die
// Trip-Flaechen: Trip-Hub (Kopf, Status, Uebersicht, Etappen, Wegpunkte,
// Ausgabe-Layout-Bausteine, Vorschau-Rahmen, Seite /trips/[id]), Anlegen
// (/trips/new) und Etappen-Editor sowie die geteilten Bausteine
// SubscriptionHeader/BriefingHistory. Echte Svelte-Komponenten, gerendert mit
// svelte/server. Zustaende, die die Komponenten erst in `$effect`/Klick-Handlern
// setzen, kommen ueber den F8-Hook (f8VarianteHook.mjs: exakte Umlenkung
// benannter `$state`-Startwerte) — Markup und Helfer bleiben der echte Quelltext.
// Nutzer `golden-de`. Golden: tests/golden/f9_trip_flaechen/<fall>.de.html
// = Ist-Stand VOR der Umstellung (nie neu schreiben); <fall>.en.html = Review-Hilfe:
//   cd frontend && GZ_GOLDEN_SCHREIBEN=en npm test -- src/lib/components/trip-detail/__tests__/trip_hub_sprache.test.ts
// Spec: docs/specs/modules/i18n_f9_trip_flaechen_2658.md
// Pfadregel #1409: alles relativ zu DIESER Datei.

import { register } from 'node:module';
import { mkdirSync, writeFileSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

process.env.TZ = 'Europe/Berlin';

export const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> trip-detail -> components -> lib -> src -> frontend
export const FRONTEND = path.resolve(HERE, '../../../../..');
export const KOMP = path.resolve(HERE, '../..');
export const TD = path.join(KOMP, 'trip-detail');
export const GOLDEN_DIR = path.resolve(FRONTEND, '..', 'tests', 'golden', 'f9_trip_flaechen');
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
export const aktionen = await imp(path.join(KOMP, 'shared/subscriptionActions.ts'));
export const reiter = await imp(path.join(KOMP, 'shared/subscriptionTabs.ts'));
export const neuLogik = await imp(path.join(KOMP, 'trip-new/tripNewLogic.ts'));

const g = globalThis as unknown as Record<string, unknown>;
const nix = () => {};
const ohneKommentare = (html: string) => html.replace(/<!--[\s\S]*?-->/g, '');
/** Feste Uhr fuer jeden Render (Seite/Reiter lesen `new Date()` selbst): Golden bleibt tagesunabhaengig. */
const ECHT_DATE = Date;
function mitUhr<T>(f: () => T): T {
	const fest = new ECHT_DATE('2026-07-02T09:30:00').getTime();
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
const html = (k: unknown, props: Record<string, unknown> = {}) => mitUhr(() => ohneKommentare(render(k as never, { props } as never).body));
const td = (n: string) => path.join(TD, n);
const ed = (n: string) => path.join(KOMP, 'edit', n);
const wp = (n: string) => path.join(TD, 'waypoints', n);

// ── Fixture golden-de ────────────────────────────────────────────────────────

/** Feste Uhr: Etappe 2 des laufenden Trips ist heute. */
export const JETZT = new Date('2026-07-02T09:30:00'); // = Uhr in mitUhr()
const wpk = (id: string, name: string, ele: number, lat: number, extra: Record<string, unknown> = {}) => ({ id, name, lat, lon: 9.1 + lat / 100, elevation_m: ele, ...extra });
export const ETAPPEN = [
	{ id: 'e1', name: 'Calenzana – Ortu di u Piobbu', date: '2026-07-01', code: 'GR20-01', start_time: '07:00', waypoints: [wpk('w1', 'Calenzana', 275, 42.5, { type: 'start' }), wpk('w2', 'Ortu di u Piobbu', 1570, 42.45, { type: 'hut' })] },
	{ id: 'e2', name: 'Ortu – Carrozzu', date: '2026-07-02', code: 'GR20-02', waypoints: [wpk('w3', 'Bocca Piccaia', 1950, 42.42, { type: 'pass' }), wpk('w4', 'Carrozzu', 1270, 42.4, { type: 'hut' })] },
	{ id: 'e3', name: 'Carrozzu – Haut Asco', date: '2026-07-03', code: 'GR20-03', waypoints: [wpk('w5', 'Spasimata', 1190, 42.39), wpk('w6', 'Haut Asco', 1422, 42.38, { type: 'summit' })] }
];
const RC = { enabled: true, morning_enabled: true, evening_enabled: true, morning_time: '07:00:00', evening_time: '18:00:00', send_email: true, send_telegram: true, send_sms: false };
export function tripLaufend(extra: Record<string, unknown> = {}) {
	return {
		id: 'gd-gr20', name: 'GR20 Nord 2026', shortcode: 'GR20', region: 'Korsika', activity: 'trekking',
		stages: ETAPPEN, report_config: RC, alert_channels: { email: true, telegram: true, sms: false, premium_sms: false },
		alert_rules: [], display_config: { metrics: [{ metric_id: 'temperature', enabled: true }, { metric_id: 'wind', enabled: true }, { metric_id: 'geist', enabled: true }] },
		...extra
	};
}
export const tripPausiert = () => tripLaufend({ id: 'gd-pause', name: 'Haute Route', paused_at: '2026-06-20T08:00:00Z', stages: ETAPPEN.map((s, i) => ({ ...s, date: `2026-08-0${i + 1}` })) });
export const tripEntwurf = () => tripLaufend({ id: 'gd-entwurf', name: 'Entwurf Dolomiten', stages: [{ id: 'd1', name: 'E1', waypoints: [] }] });

/** Katalog wie GET /api/metrics (Labels sind API-Daten, F5): mit und ohne label_en. */
export const KATALOG = {
	temperature: [{ id: 'temperature', label: 'Temperatur', label_en: 'Temperature', unit: '°C', category: 'temperature', default_enabled: true, col_label: 'Temp' }],
	wind: [
		{ id: 'wind', label: 'Wind', label_en: 'Wind', unit: 'km/h', category: 'wind', default_enabled: true, col_label: 'Wind' },
		{ id: 'gust', label: 'Böen', label_en: 'Wind gusts', unit: 'km/h', category: 'wind', default_enabled: true, col_label: 'Gust' }
	],
	atmosphere: [{ id: 'cloud_total', label: 'Bewölkung', unit: '%', category: 'atmosphere', default_enabled: false, col_label: 'Cloud' }]
};
export const COL_LABELS = ['Temp', 'Wind', 'Gust', 'Cloud'];

// ── Komponenten ──────────────────────────────────────────────────────────────

const K = {
	TripHeader: await komp(td('TripHeader.svelte')),
	TripStatusBadge: await komp(td('TripStatusBadge.svelte')),
	HubOverview: await komp(td('HubOverview.svelte')),
	ReportLine: await komp(td('ReportLine.svelte')),
	StageList: await komp(td('StageList.svelte')),
	StageDetailRow: await komp(td('StageDetailRow.svelte')),
	TripStageRow: await komp(td('TripStageRow.svelte')),
	FullProfile: await komp(td('FullProfile.svelte')),
	BucketSection: await komp(td('BucketSection.svelte')),
	BucketSectionOff: await komp(td('BucketSectionOff.svelte')),
	BucketSectionOffOffen: await variante(td('BucketSectionOff.svelte'), [['let open = $state(false);', 'let open = $state(true);']]),
	ActiveMetricRow: await komp(td('ActiveMetricRow.svelte')),
	ChannelLimitMarkers: await komp(td('ChannelLimitMarkers.svelte')),
	PresetRow: await komp(td('PresetRow.svelte')),
	MetricCheckbox: await komp(td('MetricCheckbox.svelte')),
	TablePreview: await komp(td('TablePreview.svelte')),
	AlertsPreviewCard: await komp(td('AlertsPreviewCard.svelte')),
	WeatherV2Kanaele: await komp(td('WeatherV2Kanaele.svelte')),
	TripTabs: await komp(td('TripTabs.svelte')),
	BriefingScheduleStatus: await variante(td('BriefingScheduleTab.svelte'), [["let statusMsg = $state('');", "let statusMsg = $state('Gespeichert.');"]]),
	WaypointsPanelFehler: await variante(td('WaypointsPanel.svelte'), [['let saveError = $state<string | null>(null);', "let saveError = $state<string | null>('Speichern fehlgeschlagen');"]]),
	EtappenStripHover: await variante(wp('EtappenStrip.svelte'), [['let hoverGap = $state<number | null>(null);', 'let hoverGap = $state<number | null>(0);']]),
	StageCard: await komp(wp('StageCard.svelte')),
	WaypointCard: await komp(wp('WaypointCard.svelte')),
	PauseStageView: await komp(wp('PauseStageView.svelte')),
	ProfileEditor: await komp(wp('ProfileEditor.svelte')),
	WaypointPin: await komp(wp('WaypointPin.svelte')),
	StageDateField: await komp(ed('StageDateField.svelte')),
	StageTimeField: await komp(ed('StageTimeField.svelte')),
	WeatherSummaryCard: await komp(ed('WeatherSummaryCard.svelte')),
	EditRouteSectionOffen: await variante(ed('EditRouteSection.svelte'), [
		['let pendingFiles = $state<File[]>([]);', "let pendingFiles = $state<File[]>([{ name: 'a.gpx' }, { name: 'b.gpx' }]);"],
		['let bulkStartDate = $state(today());', "let bulkStartDate = $state('2026-07-01');"]
	]),
	EmailPreviewHeader: await komp(path.join(KOMP, 'email-preview', 'EmailPreviewHeader.svelte')),
	SubscriptionHeader: await komp(path.join(KOMP, 'shared', 'subscription-header', 'SubscriptionHeader.svelte')),
	SubscriptionHeaderOffen: await variante(path.join(KOMP, 'shared', 'subscription-header', 'SubscriptionHeader.svelte'), [
		['let open = $state({ name: false, region: false });', 'let open = $state({ name: true, region: true });']
	]),
	BriefingHistory: await komp(path.join(KOMP, 'shared', 'BriefingHistory.svelte'))
};

const PANEL = ed('EditStagesPanelNew.svelte');
const panelVariante = (extra: [string, string][]) => variante(PANEL, extra);
const KASKADE = (done: boolean): [string, string] => [
	'let cascade = $state<CascadeState | null>(null);',
	`let cascade = $state<CascadeState | null>({ done: ${done}, stageId: 'e1', baseFirstDate: '2026-07-01', anchorDate: '2026-07-05' });`
];
const P = {
	desktop: await komp(PANEL),
	kaskadeOffen: await panelVariante([KASKADE(false), ['let addModeHint = $state(false);', 'let addModeHint = $state(true);']]),
	kaskadeFertig: await panelVariante([KASKADE(true), ['let saveSuccess = $state(false);', 'let saveSuccess = $state(true);']]),
	mobil: await panelVariante([['let isMobileViewport = $state(false);', 'let isMobileViewport = $state(true);'], ['let addChoiceOpen = $state(false);', 'let addChoiceOpen = $state(true);']])
};

const TripNewEditor = await komp(path.join(KOMP, 'trip-new', 'TripNewEditor.svelte'));
const SEITE = path.join(FRONTEND, 'src', 'routes', 'trips', '[id]', '+page.svelte');
const seitenVariante = (extra: [string, string][] = []) => variante(SEITE, extra);
const S = {
	ruhe: await seitenVariante(),
	gesendet: await seitenVariante([["let sendStatus = $state<'idle' | 'ok' | 'error'>('idle');", "let sendStatus = $state<'idle' | 'ok' | 'error'>('ok');"]]),
	fehler: await seitenVariante([
		["let sendStatus = $state<'idle' | 'ok' | 'error'>('idle');", "let sendStatus = $state<'idle' | 'ok' | 'error'>('error');"],
		['let errorMsg = $state<string | null>(null);', "let errorMsg = $state<string | null>('Aktion fehlgeschlagen, bitte später erneut versuchen.');"]
	]),
	mobil: await seitenVariante([['let mobil = $state(false);', 'let mobil = $state(true);']])
};

// ── Faelle ───────────────────────────────────────────────────────────────────

export function kopfRendern(): string {
	const teile = [tripLaufend(), tripPausiert(), tripEntwurf(), tripLaufend({ id: 'gd-plan', stages: ETAPPEN.map((s, i) => ({ ...s, date: `2026-09-1${i}` })) })].map((trip) =>
		html(K.TripHeader, { trip, now: JETZT })
	);
	const status = [tripLaufend(), tripPausiert(), tripEntwurf(), tripLaufend({ archived_at: '2026-07-01T00:00:00Z' }), tripLaufend({ stages: ETAPPEN.map((s) => ({ ...s, date: '2026-05-01' })) }), tripLaufend({ stages: ETAPPEN.map((s) => ({ ...s, date: '2026-12-01' })) })].map((trip) =>
		html(K.TripStatusBadge, { trip, now: JETZT })
	);
	const kopf = html(K.SubscriptionHeaderOffen, { kind: 'trip', name: 'GR20 Nord 2026', region: 'Korsika', profile: 'trekking', profileOptions: [{ value: 'trekking', label: 'Trekking' }], testidPrefix: 'trip', onSaveField: async () => {} });
	return [...teile, ...status, kopf].join('\n');
}

/** Uebersicht: Katalog-Fehler, Altbestand, Leerauswahl, Auswahl mit 1 und 2 unbekannten Groessen. */
export function uebersichtRendern(): string {
	const t = (metrics: unknown) => tripLaufend({ display_config: { metrics } });
	const zweiUnbekannt = [{ metric_id: 'temperature', enabled: true }, { metric_id: 'geist', enabled: true }, { metric_id: 'spuk', enabled: true }];
	return [
		html(K.HubOverview, { trip: tripLaufend(), metricsCatalog: null, nextBriefing: null }),
		html(K.HubOverview, { trip: t(undefined), metricsCatalog: KATALOG, nextBriefing: null }),
		html(K.HubOverview, { trip: t([{ metric_id: 'temperature', enabled: false }]), metricsCatalog: KATALOG, nextBriefing: null }),
		html(K.HubOverview, { trip: tripLaufend(), metricsCatalog: KATALOG, nextBriefing: null }),
		html(K.HubOverview, { trip: t(zweiUnbekannt), metricsCatalog: KATALOG, nextBriefing: null })
	].join('\n');
}

export function etappenRendern(): string {
	const wetter = { risk: 'yellow', weather_summary: { wmo_code: 3, is_day: true, temp_min_c: 8.4, temp_max_c: 17.6, wind_max_kmh: 34.2, precip_mm: 1.6 } };
	return [
		html(K.StageList, { trip: tripLaufend(), selectedStageId: 'e2', onSelectStage: nix, now: JETZT }),
		html(K.StageList, { trip: tripLaufend({ stages: [] }), selectedStageId: null, onSelectStage: nix, now: JETZT }),
		...['green', 'red'].map((risk) => html(K.StageDetailRow, { stage: ETAPPEN[0], index: 0, code: 'T01', selected: false, active: true, onSelect: nix, now: JETZT, weatherData: { ...wetter, risk } })),
		html(K.StageDetailRow, { stage: ETAPPEN[1], index: 1, code: 'T02', selected: true, active: false, onSelect: nix, now: JETZT, weatherData: wetter }),
		html(K.TripStageRow, { stage: { ...ETAPPEN[0], distance_km: 12.4, ascent_m: 1350, descent_m: 60, elevation_m: 1570, summary: 'Steil' }, index: 0, active: true, risk: 'green' }),
		html(K.FullProfile, { trip: tripLaufend(), selectedStageId: 'e2', onSelectStage: nix, now: JETZT }),
		html(K.FullProfile, { trip: tripLaufend({ stages: [] }), selectedStageId: null, onSelectStage: nix, now: JETZT })
	].join('\n');
}

const metricById = Object.fromEntries(Object.values(KATALOG).flat().map((m) => [m.id, m]));
const ACHT = ['temperature', 'wind', 'gust', 'cloud_total', 'temperature', 'wind', 'gust', 'cloud_total', 'wind'].map((id, i) => (i < 4 ? id : `${id}`));

export function layoutRendern(): string {
	const viele = Array.from({ length: 9 }, (_, i) => `m${i}`);
	const vieleById = Object.fromEntries(viele.map((id, i) => [id, { ...metricById[ACHT[i]], id }]));
	const base = { metricById: vieleById, shortById: {}, friendlyMap: {}, indicatorCapable: (id: string) => id === 'm1', onMode: nix, onMove: nix, onDndReorder: nix };
	return [
		// Ueberschriften reicht der Aufrufer (OutputLayoutEditor, F8) aus seinem Katalog herein.
		html(K.BucketSection, { ...base, eyebrow: tr('layout.ausgabe.spalten_eyebrow'), title: tr('layout.ausgabe.spalten'), hint: 'h', bucket: 'primary', items: viele, showLimitMarkers: true }),
		html(K.BucketSection, { ...base, eyebrow: tr('layout.ausgabe.detail_eyebrow'), title: tr('layout.ausgabe.detail_werte'), hint: 'h', bucket: 'secondary', items: [] }),
		html(K.BucketSection, { ...base, eyebrow: tr('layout.ausgabe.detail_eyebrow'), title: tr('layout.ausgabe.detail_werte'), hint: 'h', bucket: 'secondary', items: ['m0', 'm1'] }),
		html(K.BucketSectionOffOffen, { items: ['temperature', 'gust', 'cloud_total'], metricById, shortById: { gust: 'G' }, categoryLabels: { temperature: 'Temperatur', wind: 'Wind', atmosphere: 'Atmosphäre' }, categoryOrder: ['temperature', 'wind', 'atmosphere'], onAdd: nix }),
		html(K.BucketSectionOffOffen, { items: ['gust'], metricById, shortById: {}, categoryLabels: {}, categoryOrder: [], onAdd: nix, hideDetailButton: true }),
		html(K.BucketSectionOff, { items: ['gust'], metricById, shortById: {}, categoryLabels: {}, categoryOrder: [], onAdd: nix }),
		html(K.ChannelLimitMarkers, { count: 9 }),
		html(K.PresetRow, { id: 'wandern', label: 'Wandern', metricCount: 6, isActive: true, onSelect: nix }),
		html(K.PresetRow, { id: 'eins', label: 'Eins', metricCount: 1, isActive: false, onSelect: nix }),
		html(K.MetricCheckbox, { metric: metricById.gust, enabled: true, useIndicator: false, indicatorCapable: true, horizons: { today: true, tomorrow: true, day_after: false }, onToggle: nix, onModeChange: nix, onHorizonChange: nix }),
		html(K.TablePreview, { catalog: KATALOG, enabledMap: { temperature: true, gust: true }, friendlyMap: { gust: true }, horizonsMap: { gust: { today: true, tomorrow: false, day_after: false }, temperature: { today: true, tomorrow: false, day_after: false } }, categoryOrder: ['temperature', 'wind'], indicatorCapable: (id: string) => id === 'gust' }),
		html(K.AlertsPreviewCard, { trip: tripLaufend() }),
		html(K.WeatherV2Kanaele, { channels: { email: true, telegram: true, sms: true }, primaryCount: 10, telegramKurzform: true, onChange: nix, onKurzformChange: nix, availability: { email: true, telegram: true, sms: false } }),
		...(['morning', 'evening', 'alert'] as const).map((kind) => html(K.ReportLine, { kind, time: '07:00', channels: ['email', 'telegram'], active: true, alert: kind === 'alert' })),
		html(K.BriefingScheduleStatus, { trip: tripLaufend() })
	].join('\n');
}

/** Alarmregeln (Bestand #409) — Namen und Stufen aus F7 (alertMetricLabel/severityLabel). */
export const ALARM_REGELN = [
	{ id: 'r1', metric: 'wind_gust', threshold: 60, severity: 'warning', enabled: true },
	{ id: 'r2', metric: 'precipitation_sum', threshold: 15, severity: 'critical', enabled: true },
	{ id: 'r3', metric: 'unbekannt_x', threshold: 1, severity: 'info', enabled: true }
];
export function alarmRegelnRendern(): string {
	return html(K.AlertsPreviewCard, { trip: tripLaufend({ alert_rules: ALARM_REGELN }) });
}
export const alarmLabels = await imp(path.join(FRONTEND, 'src/lib/utils/alertMetricLabels.ts'));

export function wegpunkteRendern(): string {
	const pause = { id: 'p1', name: 'Pausentag', date: '2026-07-02', waypoints: [], location: 'Carrozzu' };
	const strip = [ETAPPEN[0], pause, ETAPPEN[1]];
	return [
		html(K.EtappenStripHover, { stages: strip, activeStageId: 'e1', onStagesReorder: nix, onStageActivate: nix, onPauseInsert: nix, onRemoveStage: nix, onAddStage: nix }),
		html(K.StageCard, { stage: ETAPPEN[0], index: 0, active: true, onclick: nix, onRemove: nix }),
		html(K.StageCard, { stage: pause, index: 1, active: false }),
		html(K.WaypointCard, { waypoint: ETAPPEN[0].waypoints[1], index: 1, active: true, onActivate: nix, onRename: nix, onDelete: nix, arrival: '11:40' }),
		html(K.WaypointCard, { waypoint: { ...ETAPPEN[0].waypoints[0], type: 'unbekannt' }, index: 0, onActivate: nix, onRename: nix, onDelete: nix }),
		html(K.PauseStageView, { stage: pause, prevStage: ETAPPEN[0], nextStage: ETAPPEN[1] }),
		html(K.PauseStageView, { stage: pause, prevStage: null, nextStage: null }),
		html(K.ProfileEditor, { stage: ETAPPEN[0], activeWaypointId: 'w1', onWaypointActivate: nix }),
		html(K.ProfileEditor, { stage: { ...ETAPPEN[0], waypoints: [ETAPPEN[0].waypoints[0]] }, activeWaypointId: null, onWaypointActivate: nix }),
		html(K.WaypointPin, { index: 3, onclick: nix }),
		html(K.WaypointsPanelFehler, { trip: tripLaufend() })
	].join('\n');
}

export function editFelderRendern(): string {
	return [
		html(K.StageDateField, { value: '2026-07-05', isFirst: true }),
		html(K.StageDateField, { value: '2026-07-06' }),
		html(K.StageDateField, { value: '2026-07-07', isFirst: true, variant: 'inline' }),
		html(K.StageDateField, { value: '' }),
		html(K.StageTimeField, { value: '06:30' }),
		html(K.WeatherSummaryCard, { displayConfig: { metrics: [{ metric_id: 'a', enabled: true, bucket: 'primary' }, { metric_id: 'b', enabled: true, bucket: 'secondary' }] }, tripId: 'gd-gr20' }),
		html(K.WeatherSummaryCard, { displayConfig: { preset_name: 'Wandern', metrics: [] }, tripId: 'gd-gr20' }),
		html(K.EditRouteSectionOffen, { tripName: 'GR20', stages: ETAPPEN.slice(0, 2), mode: 'create' }),
		html(K.EmailPreviewHeader, { trip: tripLaufend(), stage: ETAPPEN[0], reportType: 'morning', reportDate: '01.07.2026' }),
		html(K.EmailPreviewHeader, { trip: tripLaufend({ shortcode: undefined }), stage: null, reportType: 'evening', reportDate: '01.07.2026' })
	].join('\n');
}

export function historieRendern(): string {
	const eintraege = [
		{ sent_at: '2026-07-01T05:00:00Z', kind: 'morning', channels: ['email', 'telegram'] },
		{ sent_at: '2026-07-01T16:00:00Z', kind: 'evening', channels: ['email'], on_demand: true },
		{ sent_at: '2026-07-02T09:15:00Z', kind: 'alert', channels: ['telegram'] }
	];
	const lader = (zustand: string) => ({ eintraege: [], zustand });
	return [
		html(K.BriefingHistory, { id: 'gd-gr20', kind: 'route', entries: eintraege }),
		html(K.BriefingHistory, { id: 'gd-gr20', kind: 'route', entries: [] }),
		html(K.BriefingHistory, { id: 'gd-gr20', kind: 'route', lader: lader('laedt') }),
		html(K.BriefingHistory, { id: 'gd-gr20', kind: 'route', lader: lader('fehler') })
	].join('\n');
}

export function etappenEditorRendern(fall: 'desktop' | 'kaskade_offen' | 'kaskade_fertig' | 'mobil'): string {
	const props = { stages: structuredClone(ETAPPEN), tripId: 'gd-gr20', showSave: true, activityType: 'trekking' };
	const k = { desktop: P.desktop, kaskade_offen: P.kaskadeOffen, kaskade_fertig: P.kaskadeFertig, mobil: P.mobil }[fall];
	if (fall === 'kaskade_offen') props.stages = props.stages.map((s, i) => ({ ...s, date: `2026-07-0${5 + i}` }));
	return html(k, props);
}

// Speicherfehler ohne Server-Text: der Editor haelt nur das Flag (leerer Text) und
// loest die Meldung beim Rendern auf — in beiden Sprachen derselbe Zustand.
const TripNewFehler = await variante(path.join(KOMP, 'trip-new', 'TripNewEditor.svelte'), [['let saveError: string | null = $state(null);', "let saveError: string | null = $state('');"]]);
// Gesperrter Schritt (mobil): der Toast haelt die Kennung, der Hinweis entsteht beim Rendern.
const TripNewToast = await variante(path.join(KOMP, 'trip-new', 'TripNewEditor.svelte'), [['let lockToastMsg = $state<TabId | null>(null);', "let lockToastMsg = $state<TabId | null>('etappen');"]]);
export function anlegenToastRendern(): string {
	return html(TripNewToast, { stateOverride: { activeTab: 'route', isMobileViewport: true } });
}
export function anlegenFehlerRendern(): string {
	return html(TripNewFehler, { stateOverride: { activeTab: 'route', isMobileViewport: false, name: 'GR20', startDate: '2026-07-01' } });
}

export type AnlegeFall = { tab: string; mobil: boolean; name?: string; startDate?: string; stageNames?: string[]; besucht?: boolean };
export function anlegenRendern(f: AnlegeFall): string {
	const stateOverride = { activeTab: f.tab, isMobileViewport: f.mobil, name: f.name, startDate: f.startDate, stageNames: f.stageNames, wtVisited: f.besucht, wbVisited: f.besucht, alVisited: f.besucht };
	return html(TripNewEditor, { stateOverride });
}
export const ANLEGE_FAELLE: Record<string, AnlegeFall[]> = {
	anlegen_route: [
		{ tab: 'route', mobil: false },
		{ tab: 'route', mobil: false, name: 'GR20 Nord 2026' },
		{ tab: 'route', mobil: false, name: 'GR20 Nord 2026', startDate: '2026-07-01' },
		{ tab: 'route', mobil: true },
		{ tab: 'route', mobil: true, name: 'GR20 Nord 2026', startDate: '2026-07-01' }
	],
	anlegen_etappen: [
		{ tab: 'etappen', mobil: false, name: 'GR20 Nord 2026', startDate: '2026-07-01', stageNames: ['Calenzana', ''] },
		{ tab: 'etappen', mobil: false, name: 'GR20 Nord 2026', startDate: '2026-07-01', stageNames: ['Calenzana'] },
		{ tab: 'etappen', mobil: true, name: 'GR20 Nord 2026', startDate: '2026-07-01', stageNames: ['Calenzana', '', ''] }
	],
	anlegen_weiter: [
		{ tab: 'wegpunkte', mobil: false, name: 'GR20 Nord 2026', startDate: '2026-07-01', stageNames: ['Calenzana'] },
		{ tab: 'wegpunkte', mobil: true, name: 'GR20 Nord 2026', startDate: '2026-07-01', stageNames: ['Calenzana'] },
		{ tab: 'alarme', mobil: false, name: 'GR20 Nord 2026', startDate: '2026-07-01', stageNames: ['Calenzana'], besucht: true },
		{ tab: 'alarme', mobil: true, name: 'GR20 Nord 2026', startDate: '2026-07-01', stageNames: ['Calenzana'] }
	]
};

// ── Fehler-Flags (nur neuer Quelltext): ohne Server-Text halten die Bausteine nur ein
// Flag bzw. einen Schluessel; die Meldung entsteht beim Rendern in der aktuellen Sprache.
const FLAG = {
	header: await variante(path.join(KOMP, 'shared', 'subscription-header', 'SubscriptionHeader.svelte'), [
		['let errors = $state<Record<Field, string | null>>({ name: null, region: null, profile: null });', "let errors = $state<Record<Field, string | null>>({ name: '', region: null, profile: null });"]
	]),
	wegpunkte: await variante(td('WaypointsPanel.svelte'), [['let saveError = $state<string | null>(null);', "let saveError = $state<string | null>('');"]]),
	panel: await panelVariante([['let saveError = $state<string | null>(null);', "let saveError = $state<string | null>('');"]]),
	zeitplan: await variante(td('BriefingScheduleTab.svelte'), [['let statusKey = $state<MessageKey | null>(null);', "let statusKey = $state<MessageKey | null>('trip.fehler_speichern');"]]),
	historie: await variante(path.join(KOMP, 'shared', 'BriefingHistory.svelte'), [['let eigenError = $state(false);', 'let eigenError = $state(true);']]),
	seite: await seitenVariante([
		['let errorKey = $state<MessageKey | null>(null);', "let errorKey = $state<MessageKey | null>('aktionen.fehler.allgemein');"],
		["let sendStatus = $state<'idle' | 'ok' | 'error'>('idle');", "let sendStatus = $state<'idle' | 'ok' | 'error'>('error');"]
	])
};
export function fehlerFlagsRendern(): string {
	return [
		html(FLAG.header, { kind: 'trip', name: 'GR20 Nord 2026', region: 'Korsika', profile: 'trekking', profileOptions: [], testidPrefix: 'trip', onSaveField: async () => {} }),
		html(FLAG.wegpunkte, { trip: tripLaufend() }),
		html(FLAG.panel, { stages: structuredClone(ETAPPEN), tripId: 'gd-gr20', showSave: true }),
		html(FLAG.zeitplan, { trip: tripLaufend() }),
		html(FLAG.historie, { id: '', kind: 'route' }),
		html(FLAG.seite, { data: { trip: tripLaufend(), metricsCatalog: KATALOG, profile: null } })
	].join('\n');
}

export function seiteRendern(fall: keyof typeof S, trip = tripLaufend()): string {
	return html(S[fall], { data: { trip, metricsCatalog: KATALOG, profile: null } });
}

/** Trip-Reiterleiste (TripTabs) mit Uebersicht-Reiter. */
export function reiterRendern(trip = tripLaufend()): string {
	return html(K.TripTabs, { initialTab: 'uebersicht', trip, metricsCatalog: KATALOG });
}

// ── Golden ───────────────────────────────────────────────────────────────────

export function htmlFaelle(): Record<string, () => string> {
	const f: Record<string, () => string> = {
		kopf_status: kopfRendern,
		uebersicht: uebersichtRendern,
		etappen: etappenRendern,
		layout_bausteine: layoutRendern,
		wegpunkte: wegpunkteRendern,
		edit_felder: editFelderRendern,
		historie: historieRendern,
		etappen_editor_desktop: () => etappenEditorRendern('desktop'),
		etappen_editor_kaskade: () => etappenEditorRendern('kaskade_offen') + '\n' + etappenEditorRendern('kaskade_fertig'),
		etappen_editor_mobil: () => etappenEditorRendern('mobil'),
		hub_seite: () => (['ruhe', 'gesendet', 'fehler', 'mobil'] as const).map((s) => seiteRendern(s)).join('\n') + '\n' + seiteRendern('ruhe', tripEntwurf()),
		hub_reiter: () => reiterRendern()
	};
	for (const [fall, liste] of Object.entries(ANLEGE_FAELLE)) f[fall] = () => liste.map(anlegenRendern).join('\n');
	return f;
}

/** Funktionsergebnisse als Tabelle `Eingabe → Ausgabe` (eine Zeile je Fall). */
export function funktionsTabelle(): string {
	const z: string[] = [];
	const j = (v: unknown) => JSON.stringify(v);
	for (const kind of ['trip', 'vergleich'] as const)
		for (const status of ['draft', 'active', 'paused', 'archived'] as const)
			for (const surface of ['list', 'hub', 'mobile'] as const) z.push(`subscriptionActions(${kind},${status},${surface}) → ${j(aktionen.subscriptionActions(kind, status, surface))}`);
	for (const kind of ['trip', 'vergleich'] as const) {
		z.push(`subscriptionTabs(${kind}) → ${j(reiter.subscriptionTabs(kind))}`);
		z.push(`anlegeKette(${kind}) → ${j(reiter.anlegeKette(kind))}`);
	}
	z.push(`stageDate(2026-07-01, 0..2) → ${j([0, 1, 2].map((i) => neuLogik.stageDate('2026-07-01', i)))}`);
	return z.join('\n');
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
