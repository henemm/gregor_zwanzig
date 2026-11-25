// Issue #3020 S1 — vom F8-Pruefstand abgetrennter Teil: Renders der Alt-Bausteine, die kein Nutzer mehr sieht
// (OutputLayoutEditor: Scheibe S2; LayoutTab, LTCutLine, OutlookLayoutControls: S3; MailInhaltCard: S4).
// Einziger Nutzer: layout_korridor_sprache.test.ts, dort nur in den Faellen dieser Bausteine (dynamischer
// Import). Faellt mit ihnen. Pfadregel #1409: alles relativ zu DIESER Datei.

import path from 'node:path';
import { html, komp, lt, LT, SHARED, type Kontext } from './f8Pruefstand.ts';

const LayoutTab = await komp(path.join(LT, 'LayoutTab.svelte'));
const OutputLayoutEditor = await komp(path.join(SHARED, 'OutputLayoutEditor.svelte'));
const LTCutLine = await komp(path.join(LT, 'LTCutLine.svelte'));
const OutlookLayoutControls = await komp(path.join(SHARED, 'OutlookLayoutControls.svelte'));
const MailInhaltCard = await komp(path.join(SHARED, 'MailInhaltCard.svelte'));

const nix = () => {};

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

type LayoutProps = Record<string, unknown> & { buckets: typeof BUCKETS; templates?: unknown[]; hideDetailBucket?: boolean };

/** LayoutTab mit dem geteilten Ausgabe-Layout-Editor im `editor`-Snippet (frueher die Test-Huelle
 *  LayoutTabPruefstand.svelte): so traegt ein Render Eyebrow, Kanal-Umschalter, Reihenfolge/Spalten und
 *  Kappungs-Hinweis in EINEM Durchgang. Ein Snippet ist serverseitig eine Funktion (Renderer, Argument). */
function layoutMitEditor({ buckets, templates = [], hideDetailBucket = false, ...props }: LayoutProps): string {
	const editor = (renderer: unknown, { channel }: { channel: string }) =>
		OutputLayoutEditor(renderer, { catalog: KATALOG, buckets, friendlyMap: {}, channel, templates, hideDetailBucket });
	return html(LayoutTab, { ...props, editor });
}

/** Layout-Reiter eines Kontexts fuer einen Kanal. #3047 R8: Vergleich mit den Props des echten Aufrufers (WeatherMetricsTab: Metriken als Zeilen, ohne Label-Spalte). */
export function layoutTabRendern(context: Kontext, channel: 'email' | 'telegram' | 'sms', colCount = 3): string {
	const props =
		context === 'route'
			? { context, channel, colCount, subjectLabel: 'Metriken', hasLabelColumn: false }
			: { context, channel, colCount, subjectLabel: 'Metriken', hasLabelColumn: false, smsCharLimit: lt.SMS_COMPARE_CHAR_LIMIT };
	return layoutMitEditor({ ...props, buckets: BUCKETS, templates: [{ id: 'wandern', label: 'Wandern', metrics: ['temperature', 'wind'] }] });
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
		html(LTCutLine, { label: 'Telegram', platz: 8, context: 'route' }), // #3047 R8 F3
		ausblick({ enabled: true, onEnabledChange: nix }),
		ausblick({ title: '3-Tages-Vorschau', showEmailOnlyHint: false }),
		html(MailInhaltCard, { reportConfig: { email_format: 'full', show_stability: true } }), // #3237 F002: Haken = show_stability
		html(MailInhaltCard, { reportConfig: { email_format: 'compact' } }),
		layoutMitEditor({ context: 'route', channel: 'sms', colCount: 0, subjectLabel: 'Metriken', hasLabelColumn: false, buckets: leer }),
		layoutMitEditor({ context: 'route', channel: 'email', colCount: 9, subjectLabel: 'Metriken', hasLabelColumn: false, buckets: BUCKETS, hideDetailBucket: true })
	].join('\n');
}

/** Golden-Faelle der Alt-Bausteine (zusaetzlich zu `htmlFaelle()` des Pruefstands). */
export const altFaelle = (): Record<string, () => string> => ({
	layout_tab_route: () => (['email', 'telegram', 'sms'] as const).map((k) => layoutTabRendern('route', k)).join('\n'),
	layout_tab_vergleich: () => (['email', 'telegram', 'sms'] as const).map((k) => layoutTabRendern('vergleich', k, 9)).join('\n'),
	bausteine: bausteineRendern
});
