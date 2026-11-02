// Issue #2656 (i18n F7, Epic #2644) — gemeinsamer SSR-Pruefstand fuer den
// geteilten Alarme-Reiter (shared/AlarmeTab.svelte, Trip UND Ortsvergleich),
// den Alarm-Kanal-Picker und alle Bausteine unter alerts-tab/. Echte
// Svelte-Komponenten, gerendert mit svelte/server; Vergleichs-Props baut die
// ECHTE Funktion der drei Vergleichs-Mounts (compare/alarmePropsAus.ts).
// Zustaende, die erst ein Klick setzt (Popover offen, Vorschau geladen/
// laedt/Fehler), kommen ueber den Hook der F8 (f8VarianteHook.mjs: exakte
// Umlenkung benannter `$state`-Startwerte) — Markup und Helfer bleiben echt.
// Nutzer `golden-de`. Golden: tests/golden/f7_alarme_tab/<fall>.de.(html|txt)
// = Ist-Stand VOR der Umstellung (nie neu schreiben); <fall>.en.* = Review-Hilfe:
//   cd frontend && GZ_GOLDEN_SCHREIBEN=en npm test -- src/lib/components/alerts-tab/__tests__/alarme_tab_sprache.test.ts
// Spec: docs/specs/modules/i18n_f7_alarme_tab_2656.md
// Pfadregel #1409: alles relativ zu DIESER Datei.

import { register } from 'node:module';
import { mkdirSync, writeFileSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

export const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> alerts-tab -> components -> lib -> src -> frontend
export const FRONTEND = path.resolve(HERE, '../../../../..');
export const AT = path.resolve(HERE, '..');
export const SHARED = path.resolve(HERE, '../../shared');
export const GOLDEN_DIR = path.resolve(FRONTEND, '..', 'tests', 'golden', 'f7_alarme_tab');
const basis = pathToFileURL(FRONTEND + '/').href;
register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, basis);
register(pathToFileURL(path.join(SHARED, 'layout-tab', '__tests__', 'f8VarianteHook.mjs')).href, basis);

const { render } = await import('svelte/server');
const imp = async (datei: string) => await import(pathToFileURL(datei).href);
const komp = async (datei: string) => (await imp(datei)).default;
const variante = async (datei: string, ersetzungen: [string, string][]) =>
	(await import(`${pathToFileURL(datei).href}?f8variante=${Buffer.from(JSON.stringify(ersetzungen)).toString('base64url')}`)).default;

export const { locale, tr, trFor } = await imp(path.join(FRONTEND, 'src/lib/i18n/index.ts'));
/** Namensraum-Importe: ein fehlender Export ist ein roter Einzeltest, kein Ladefehler. */
export const labels = await imp(path.join(FRONTEND, 'src/lib/utils/alertMetricLabels.ts'));
export const amt = await imp(path.join(AT, 'alertMetricTable.ts'));
export const vorschau = await imp(path.join(AT, 'alertPreviewHelpers.ts'));
export const sektionen = await imp(path.join(SHARED, 'alarme-tab', 'alarmeTabSections.ts'));
export const kanal = await imp(path.join(SHARED, 'alarme-tab', 'alertChannelState.ts'));
export const gate = await imp(path.join(SHARED, 'alarme-tab', 'premiumSmsAlarmGate.ts'));
export const katalogAbl = await imp(path.join(SHARED, 'alarme-tab', 'activeAlertMetricsFromCatalog.ts'));
export const lieferung = await imp(path.join(SHARED, 'alarme-tab', 'alarmeDeliveryPayload.ts'));
export const premiumVersand = await imp(path.join(SHARED, 'versand-tab', 'premiumSmsChannelState.ts'));
export const { alarmePropsAus } = await imp(path.join(SHARED, '..', 'compare', 'alarmePropsAus.ts'));

const AlarmeTab = await komp(path.join(SHARED, 'AlarmeTab.svelte'));
const AlertChannelPicker = await komp(path.join(SHARED, 'AlertChannelPicker.svelte'));
const AlertsTab = await komp(path.join(AT, 'AlertsTab.svelte'));
const AlertCard = await komp(path.join(AT, 'AlertCard.svelte'));
const AlertMetricTable = await komp(path.join(AT, 'AlertMetricTable.svelte'));
const AlertMetricLevelTable = await komp(path.join(AT, 'AlertMetricLevelTable.svelte'));
const AlertQuietHoursCard = await komp(path.join(AT, 'AlertQuietHoursCard.svelte'));
const AlertPreviewCard = await komp(path.join(AT, 'AlertPreviewCard.svelte'));
const PresetOffen = await variante(path.join(AT, 'AlertPresetSelector.svelte'), [
	['let popoverOpen = $state(false);', 'let popoverOpen = $state(true);']
]);
const VORSCHAU_ZUSTAND: [string, string][] = [
	["let subject = $state('');", 'let subject = $state(globalThis.__F7_VORSCHAU.subject);'],
	["let emailHtml = $state('');", 'let emailHtml = $state(globalThis.__F7_VORSCHAU.emailHtml);'],
	["let telegram = $state('');", 'let telegram = $state(globalThis.__F7_VORSCHAU.telegram);'],
	["let sms = $state('');", 'let sms = $state(globalThis.__F7_VORSCHAU.sms);'],
	['let loading = $state(false);', 'let loading = $state(globalThis.__F7_VORSCHAU.loading);'],
	['let error = $state<string | null>(null);', 'let error = $state<string | null>(globalThis.__F7_VORSCHAU.error);']
];
const VorschauZustand = await variante(path.join(AT, 'AlertPreviewCard.svelte'), VORSCHAU_ZUSTAND);

export type Kontext = 'route' | 'vergleich';
const nix = () => {};
const g = globalThis as unknown as Record<string, unknown>;
const ohneKommentare = (h: string) => h.replace(/<!--[\s\S]*?-->/g, '');
const html = (k: unknown, props: Record<string, unknown> = {}) => ohneKommentare(render(k as never, { props } as never).body);

// ── Fixtures (Nutzer golden-de) ─────────────────────────────────────────────

/** Gespeicherte Alarm-Regeln des Trips (Schwellen, Einheiten = Daten). */
export const REGELN = [
	{ id: 'r-gust-d', kind: 'delta', metric: 'wind_gust', threshold: 20, unit: 'km/h', severity: 'warning', enabled: true },
	{ id: 'r-gust-a', kind: 'absolute', metric: 'wind_gust', threshold: 70, unit: 'km/h', severity: 'critical', enabled: true },
	{ id: 'r-tmin-a', kind: 'absolute', metric: 'temperature_min', threshold: -5, unit: '°C', severity: 'info', enabled: true },
	{ id: 'r-wchg-d', kind: 'delta', metric: 'wind_change', threshold: 25, unit: 'km/h', severity: 'warning', enabled: true }
];
export const TRIP_METRIKEN = ['wind_gust', 'temperature_min', 'cape', 'thunder_onset'];
export const TRIP_STUFEN = { wind_gust: 'standard', temperature_min: 'sensibel', cape: 'entspannt', thunder_onset: 'off' };

export function trip(id = 'golden-de-gr20') {
	return {
		id,
		name: 'GR20',
		stages: [],
		alert_rules: REGELN,
		display_config: {},
		report_config: { send_email: true, send_telegram: true, send_sms: false },
		official_warnings: { enabled: true },
		alert_cooldown_minutes: 45,
		alert_quiet_from: '22:00',
		alert_quiet_to: '07:00'
	};
}

/** Vergleichs-Katalog wie /api/compare/metrics: alarmfaehig, nicht alarmfaehig, Doppelname. */
export const VERGLEICH_KATALOG = [
	{ metric: 'gust_max_kmh', label: 'Böen', aggregation: 'max', aggregation_label: 'Maximum', alertMetric: 'wind_gust' },
	{ metric: 'temp_min_c', label: 'Temperatur', aggregation: 'min', aggregation_label: 'Minimum', alertMetric: 'temperature_min' },
	{ metric: 'cape_max_jkg', label: 'Gewitterenergie (CAPE)', aggregation: 'max', aggregation_label: 'Maximum', alertMetric: 'cape' },
	{ metric: 'humidity_avg_pct', label: 'Luftfeuchtigkeit', aggregation: 'avg', aggregation_label: 'Mittel', alertMetric: null },
	{ metric: 'feels_min_c', label: 'Gefühlte Temperatur', aggregation: 'min', aggregation_label: 'Minimum', alertMetric: null },
	{ metric: 'feels_max_c', label: 'Gefühlte Temperatur', aggregation: 'max', aggregation_label: 'Maximum', alertMetric: null }
];
export const VERGLEICH_AKTIV = ['gust_max_kmh', 'temp_min_c', 'cape_max_jkg', 'humidity_avg_pct', 'feels_min_c', 'feels_max_c'];

export function wizard(over: Record<string, unknown> = {}): Record<string, unknown> {
	return {
		officialWarningsEnabled: true,
		radarAlertEnabled: true,
		activeMetricKeys: VERGLEICH_AKTIV,
		metricAlertLevels: { wind_gust: 'sensibel', temperature_min: 'standard', cape: 'off' },
		channelThresholds: { telegram: 'MODERATE', sms: 'HIGH' },
		channels: { email: true, telegram: true, sms: false, premium_sms: false },
		telegramStyle: 'rich',
		alertCooldownMinutes: 30,
		alertQuietFrom: '23:00',
		alertQuietTo: '06:30',
		...over
	};
}

// ── Renderer ────────────────────────────────────────────────────────────────

export function alarmeRoute(over: Record<string, unknown> = {}): string {
	return html(AlarmeTab, {
		context: 'route',
		trip: trip(),
		activeMetrics: TRIP_METRIKEN,
		metricLevels: TRIP_STUFEN,
		existingChannels: { email: true, telegram: true, sms: false, premium_sms: false },
		existingChannelThresholds: { telegram: 'MODERATE', sms: 'HIGH' },
		profileOverride: { premium_sms_allowed: false },
		...over
	});
}

export function alarmeVergleich(wiz: Record<string, unknown> = wizard(), over: Record<string, unknown> = {}): string {
	return html(AlarmeTab, {
		context: 'vergleich',
		...alarmePropsAus(wiz),
		catalog: VERGLEICH_KATALOG,
		preset: { id: 'golden-de-vergleich', name: 'Korsika', location_ids: ['l1', 'l2', 'l3'] },
		profileOverride: null,
		...over
	});
}

/** Leer- und Sonderzustaende von Reiter, Kanal-Picker und Beispiel-Warnung. */
export function zustaendeRendern(): string {
	const regel = [{ ...REGELN[0] }];
	const aus = [{ ...REGELN[0], enabled: false }];
	return [
		alarmeRoute({ activeMetrics: [], metricLevels: {}, profileOverride: { premium_sms_allowed: true } }),
		alarmeVergleich(wizard({ activeMetricKeys: ['humidity_avg_pct', 'feels_min_c', 'feels_max_c'] }), { preset: { id: 'v2', location_ids: [] } }),
		html(AlertChannelPicker, { channels: { telegram: false, sms: false, email: false, premium_sms: false }, onToggle: nix }),
		html(AlertChannelPicker, { channels: { telegram: true, sms: true, email: false, premium_sms: false }, onToggle: nix, targets: { telegram: '987654321' }, dense: true }),
		html(AlertPreviewCard, { kind: 'route', id: '', alertRules: regel }),
		html(AlertPreviewCard, { kind: 'vergleich', id: 'v1', alertRules: regel, locationIds: [] }),
		html(AlertPreviewCard, { kind: 'route', id: 't1', alertRules: aus }),
		html(AlertPreviewCard, { kind: 'route', id: 't1', alertRules: [] }),
		html(AlertQuietHoursCard, {})
	].join('\n');
}

function vorschauRendern(zustand: Record<string, unknown>): string {
	g.__F7_VORSCHAU = { subject: '', emailHtml: '', telegram: '', sms: '', loading: false, error: null, ...zustand };
	try {
		return html(VorschauZustand, { kind: 'route', id: 't1', alertRules: REGELN });
	} finally {
		delete g.__F7_VORSCHAU;
	}
}

/** Bausteine unter alerts-tab/ ausserhalb des geteilten Reiters. */
export function bausteineRendern(): string {
	const metriken = (ids: string[]) => ids.map((metric_id) => ({ metric_id, enabled: true }));
	const leveled = { wind_gust: 'standard', temperature_min: 'standard', cape: 'standard' };
	return [
		html(AlertsTab, { trip: { ...trip(), display_config: {} } }),
		html(AlertsTab, { trip: { ...trip(), display_config: { metric_alert_levels: {}, metrics: [] } } }),
		html(AlertsTab, { trip: { ...trip(), display_config: { alert_preset: 'entspannt', metrics: metriken(['gust', 'temperature', 'cape']) } } }),
		html(AlertMetricLevelTable, { activeMetrics: ['wind_gust', 'temperature_min', 'cape'], levels: leveled, onLevelChange: nix }),
		html(AlertMetricLevelTable, { activeMetrics: ['wind_gust', 'temperature_min'], levels: { wind_gust: 'off', temperature_min: 'sensibel' }, onLevelChange: nix }),
		html(AlertMetricLevelTable, { activeMetrics: [], levels: {}, onLevelChange: nix }),
		html(AlertCard, { rule: REGELN[0], activeChannels: ['email', 'telegram'] }),
		html(AlertMetricTable, { alert_rules: REGELN }),
		html(PresetOffen, { value: 'entspannt' }),
		vorschauRendern({ loading: true }),
		vorschauRendern({ subject: '[GR20] Böen 75 km/h', emailHtml: '<p>Mail</p>', telegram: 'GR20 Böen 75', sms: 'GR20 G75' }),
		vorschauRendern({ error: 'HTTP 503' })
	].join('\n');
}

// ── Golden ───────────────────────────────────────────────────────────────────

/** Golden-Faelle HTML (Spec Implementation Details 7). */
export function htmlFaelle(): Record<string, () => string> {
	return {
		alarme_tab_route: () => alarmeRoute(),
		alarme_tab_vergleich: () => alarmeVergleich(),
		zustaende: zustaendeRendern,
		bausteine: bausteineRendern
	};
}

export const ALLE_ALARM_METRIKEN = [
	'wind_gust', 'precipitation_sum', 'thunder_level', 'snow_line', 'temperature_min', 'temperature_max',
	'temperature_change', 'wind_change', 'precipitation_change', 'fresh_snow', 'cape', 'visibility',
	'humidity', 'freezing_level', 'thunder_onset', 'precipitation_heavy_onset'
];

/** Funktionsergebnisse als Tabelle `Eingabe → Ausgabe` (eine Zeile je Fall). */
export function funktionsTabelle(): string {
	const z: string[] = [];
	const j = (v: unknown) => JSON.stringify(v);
	for (const m of ALLE_ALARM_METRIKEN) {
		const e = labels.ALERT_METRIC_LABELS[m];
		z.push(`ALERT_METRIC_LABELS(${m}) → ${j({ label_de: e.label_de, unit: e.unit, comparison: e.comparison })}`);
	}
	for (const s of ['info', 'warning', 'critical']) z.push(`SEVERITY_LABEL_DE(${s}) → ${j(labels.SEVERITY_LABEL_DE[s])}`);
	for (const s of ['LOW', 'MODERATE', 'HIGH']) z.push(`CHANNEL_THRESHOLD_LABELS(${s}) → ${j(kanal.CHANNEL_THRESHOLD_LABELS[s])}`);
	for (const c of ['route', 'vergleich']) z.push(`triggerGroupHeading(${c}) → ${j(sektionen.triggerGroupHeading(c))}`);
	for (const p of [null, { premium_sms_allowed: false }, { premium_sms_allowed: true }])
		z.push(`derivePremiumSmsAlarmGate(${j(p)}) → ${j(gate.derivePremiumSmsAlarmGate(p))}`);
	for (const m of ['cape', 'wind_gust']) z.push(`thresholdTitle(${m}) → ${j(amt.thresholdTitle(m) ?? null)}`);
	for (const m of ['cape', 'wind_gust', 'thunder_onset']) z.push(`levelToThreshold(${m}, standard) → ${j(amt.levelToThreshold(m, 'standard'))}`);
	z.push(`deriveUnalertableSelectedMetricNames(alle) → ${j(katalogAbl.deriveUnalertableSelectedMetricNames(VERGLEICH_AKTIV, VERGLEICH_KATALOG))}`);
	z.push(`deriveActiveAlertMetricsFromCatalog(alle) → ${j(katalogAbl.deriveActiveAlertMetricsFromCatalog(VERGLEICH_AKTIV, VERGLEICH_KATALOG))}`);
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
