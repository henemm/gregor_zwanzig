// Issue #2654 (i18n F5, Epic #2644) — EINE Stelle fuer den Anzeigenamen einer
// Wettergroesse (F5, F7, F8, F9, F10). Quelle ist das Metrik-Register
// (GET /api/metrics: `label` = label_de, seit P1 #2662 `label_en`/`alert_label_en`).
// Nur die volle Form wird sprachabhaengig (ADR-0104 Klasse 2); Kurzform (`col_label`)
// und Kuerzel (`sms_code`) laufen NIE hier durch (ADR-0042).
// Spec: docs/specs/modules/i18n_f5_wertebereiche_tab_2654.md
import { trFor, type Lang, type MessageKey } from './index.ts';

export type MetricLabelFields = {
	label: string;
	label_de?: string;
	label_en?: string;
	alert_label?: string;
	alert_label_en?: string;
};

const gesetzt = (s: string | undefined): s is string => typeof s === 'string' && s.trim().length > 0;

/** Voller Name in `lang`; fehlt/leer `label_en`, steht der deutsche Name (nie ""). */
export function metricLabel(def: MetricLabelFields, lang: Lang): string {
	const deutsch = gesetzt(def.label_de) ? def.label_de : def.label;
	return lang === 'en' && gesetzt(def.label_en) ? def.label_en : deutsch;
}

/** Alarm-Kurzform in `lang`; en: alert_label_en, sonst alert_label; leer, wenn beides fehlt. */
export function metricAlertLabel(def: MetricLabelFields, lang: Lang): string {
	if (lang === 'en' && gesetzt(def.alert_label_en)) return def.alert_label_en;
	return def.alert_label ?? '';
}

// Annahme A1 der Spec: `aggregation_label` liefert das Backend nur deutsch; die
// Auswertung wird ueber ihre Kennung auf den Katalog abgebildet.
const AUSWERTUNG: Record<string, MessageKey> = {
	min: 'wertebereiche.auswertung.min',
	max: 'wertebereiche.auswertung.max',
	avg: 'wertebereiche.auswertung.avg',
	sum: 'wertebereiche.auswertung.sum'
};

/** Beschriftung einer Auswertung (min/max/avg/sum) in `lang`; unbekannt: `fallback`. */
export function metricAggregationLabel(aggregation: string | undefined, fallback: string | undefined, lang: Lang): string {
	const k = aggregation ? AUSWERTUNG[aggregation] : undefined;
	return k ? trFor(lang, k) : (fallback ?? '');
}
