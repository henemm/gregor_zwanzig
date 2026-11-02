// Zentrale Label-, Unit- und Comparison-Map fuer AlertMetric.
// Spec: docs/specs/modules/issue_222_w2_frontend_alert_konfigurator.md §1.
//
// Single Source of Truth fuer:
//  - menschenlesbare Labels (de/en ueber den Katalog alarme.metrik.*, #2656)
//  - Einheiten-Strings
//  - Vergleichs-Symbole je Metric
//  - Severity → Pill-Tone Mapping

import type { AlertMetric, AlertSeverity } from '$lib/types';
import { trFor, type Lang, type MessageKey } from '../i18n/index.ts';

// Issue #2656 (i18n F7): die Namen stehen im Katalog (`alarme.metrik.<id>`, de
// wortgleich zum bisherigen `label_de`); `label_de`/`label_en` sind Lesezugriffe
// je Aufruf. Einheit und Vergleichssymbol sind Daten und bleiben hier.
type AlertMetricInfo = { readonly label_de: string; readonly label_en: string; unit: string; comparison: '>' | '≥' | '<' };

function info(metric: AlertMetric, unit: string, comparison: '>' | '≥' | '<'): AlertMetricInfo {
	const k = `alarme.metrik.${metric}` as MessageKey; // i18n-dynamic: alarme.metrik.
	return {
		get label_de() {
			return trFor('de', k);
		},
		get label_en() {
			return trFor('en', k);
		},
		unit,
		comparison
	};
}

export const ALERT_METRIC_LABELS: Record<AlertMetric, AlertMetricInfo> = {
	wind_gust: info('wind_gust', 'km/h', '>'),
	precipitation_sum: info('precipitation_sum', 'mm', '>'),
	thunder_level: info('thunder_level', '', '≥'),
	snow_line: info('snow_line', 'm', '>'),
	// #1401 Scheibe B: Wortlaut aus dem Register (metric_catalog.py, label_de).
	// Beide Eintraege sind Auswertungen derselben Register-Groesse
	// "Temperatur" (:78) und tragen sie fest im Text — kein Kollisions-Suffix
	// zur Laufzeit noetig, da es zwei getrennte AlertMetric-Schluessel sind.
	temperature_min: info('temperature_min', '°C', '<'),
	temperature_max: info('temperature_max', '°C', '>'),
	// #1435 E1a-2 AC-9 (PO-Entscheidung 2026-07-31): einheitlicher Stil wie
	// "Temperatur (Minimum)" — diese Zeilen warnen bei starker AENDERUNG,
	// nicht bei hohem Absolutwert. Nur der Wortlaut aendert sich.
	temperature_change: info('temperature_change', '°C', '>'),
	wind_change: info('wind_change', 'km/h', '>'),
	precipitation_change: info('precipitation_change', 'mm', '>'),
	// Issue #846: 4 neue Metriken (Epic #813 Slice 3)
	fresh_snow: info('fresh_snow', 'cm', '>'),
	// #1401 Scheibe B: Register-Wortlaut (metric_catalog.py:273) statt Kuerzel.
	cape: info('cape', 'J/kg', '>'),
	visibility: info('visibility', 'm', '<'),
	humidity: info('humidity', '%', '>'),
	// Issue #946: Nullgradgrenze
	freezing_level: info('freezing_level', 'm', '<'),
	// Issue #1468: die Schwelle ist eine Verschiebung in Stunden, nicht ein
	// Absolutwert — Vergleichssymbol darum '≥' wie bei Gewitter.
	thunder_onset: info('thunder_onset', 'h', '≥'),
	precipitation_heavy_onset: info('precipitation_heavy_onset', 'h', '≥')
};

/** Anzeigename einer Alarm-Metrik in `lang`; unbekannte Kennung: die Kennung selbst (nie leer). */
export function alertMetricLabel(metric: string, lang: Lang): string {
	const e = (ALERT_METRIC_LABELS as Record<string, AlertMetricInfo | undefined>)[metric];
	if (!e) return metric;
	return lang === 'en' ? e.label_en : e.label_de;
}

export const ALERT_SEVERITY_TONE: Record<AlertSeverity, 'info' | 'warning' | 'danger'> = {
	info: 'info',
	warning: 'warning',
	critical: 'danger'
};

const SEVERITY_KEY: Record<AlertSeverity, MessageKey> = {
	info: 'alarme.stufe.info',
	warning: 'alarme.stufe.warning',
	critical: 'alarme.stufe.critical'
};

/** Schweregrad-Name in `lang` (Katalog `alarme.stufe.*`); unbekannt: die Kennung. */
export function severityLabel(severity: string, lang: Lang): string {
	const k = SEVERITY_KEY[severity as AlertSeverity];
	return k ? trFor(lang, k) : severity;
}

/** Deutscher Schweregrad-Name (Bestand, z. B. trip-detail/AlertsPreviewCard bis F9). */
export const SEVERITY_LABEL_DE: Record<AlertSeverity, string> = {
	get info() {
		return severityLabel('info', 'de');
	},
	get warning() {
		return severityLabel('warning', 'de');
	},
	get critical() {
		return severityLabel('critical', 'de');
	}
};

// #1488 Scheibe A: `thunderLevelLabel()` ersatzlos entfernt. Die Stufenwoerter
// MITTEL/HOCH alarmierten eine Stufe frueher als beschriftet und gehoerten zu
// einer Absolut-Schwelle, die der Alarm-Dienst fuer Gewitter nie auswertet.

// Bug #317 — Legacy-AlertMetric-IDs auf aktuelle AlertMetric-Enum-Werte abbilden.
// Spec: docs/specs/modules/bug_317_alert_rules_editor_metrics.md
const LEGACY_ALERT_METRIC_MAP: Record<string, AlertMetric> = {
	precipitation: 'precipitation_sum',
	thunder: 'thunder_level',
	// Issue #959: Nullgradgrenze konsolidiert — snow_line/snowfall_limit lösen auf
	// freezing_level auf, damit alt-persistierte Werte weiterhin normalisieren.
	snowfall_limit: 'freezing_level',
	snow_line: 'freezing_level',
};

export function normalizeAlertMetric(raw: string): AlertMetric | undefined {
	if (raw in ALERT_METRIC_LABELS) return raw as AlertMetric;
	return LEGACY_ALERT_METRIC_MAP[raw] as AlertMetric | undefined;
}
