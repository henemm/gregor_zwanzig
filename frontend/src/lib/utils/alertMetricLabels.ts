// Zentrale Label-, Unit- und Comparison-Map fuer AlertMetric.
// Spec: docs/specs/modules/issue_222_w2_frontend_alert_konfigurator.md §1.
//
// Single Source of Truth fuer:
//  - menschenlesbare Labels (DE)
//  - Einheiten-Strings
//  - Vergleichs-Symbole je Metric
//  - Severity → Pill-Tone Mapping

import type { AlertMetric, AlertSeverity } from '$lib/types';

export const ALERT_METRIC_LABELS: Record<
	AlertMetric,
	{ label_de: string; unit: string; comparison: '>' | '≥' | '<' }
> = {
	wind_gust: { label_de: 'Böen', unit: 'km/h', comparison: '>' },
	precipitation_sum: { label_de: 'Niederschlag', unit: 'mm', comparison: '>' },
	thunder_level: { label_de: 'Gewitter', unit: '', comparison: '≥' },
	snow_line: { label_de: 'Schneefallgrenze', unit: 'm', comparison: '>' },
	// #1401 Scheibe B: Wortlaut aus dem Register (metric_catalog.py, label_de).
	// Beide Eintraege sind Auswertungen derselben Register-Groesse
	// "Temperatur" (:78) und tragen sie fest im Text — kein Kollisions-Suffix
	// zur Laufzeit noetig, da es zwei getrennte AlertMetric-Schluessel sind.
	temperature_min: { label_de: 'Temperatur (Minimum)', unit: '°C', comparison: '<' },
	temperature_max: { label_de: 'Temperatur (Maximum)', unit: '°C', comparison: '>' },
	// #1435 E1a-2 AC-9 (PO-Entscheidung 2026-07-31): einheitlicher Stil wie
	// "Temperatur (Minimum)" — diese Zeilen warnen bei starker AENDERUNG,
	// nicht bei hohem Absolutwert. Nur der Wortlaut aendert sich.
	temperature_change: { label_de: 'Temperatur (Änderung)', unit: '°C', comparison: '>' },
	wind_change: { label_de: 'Wind (Änderung)', unit: 'km/h', comparison: '>' },
	precipitation_change: { label_de: 'Niederschlag (Änderung)', unit: 'mm', comparison: '>' },
	// Issue #846: 4 neue Metriken (Epic #813 Slice 3)
	fresh_snow: { label_de: 'Neuschnee', unit: 'cm', comparison: '>' },
	// #1401 Scheibe B: Register-Wortlaut (metric_catalog.py:273) statt Kuerzel.
	cape: { label_de: 'Gewitterenergie (CAPE)', unit: 'J/kg', comparison: '>' },
	visibility: { label_de: 'Sichtweite', unit: 'm', comparison: '<' },
	humidity: { label_de: 'Luftfeuchtigkeit', unit: '%', comparison: '>' },
	// Issue #946: Nullgradgrenze
	freezing_level: { label_de: 'Nullgradgrenze', unit: 'm', comparison: '<' },
	// Issue #1468: die Schwelle ist eine Verschiebung in Stunden, nicht ein
	// Absolutwert — Vergleichssymbol darum '≥' wie bei Gewitter.
	thunder_onset: { label_de: 'Gewitter (Beginn)', unit: 'h', comparison: '≥' },
	precipitation_heavy_onset: {
		label_de: 'Starkregen (Beginn)',
		unit: 'h',
		comparison: '≥'
	},
};

export const ALERT_SEVERITY_TONE: Record<AlertSeverity, 'info' | 'warning' | 'danger'> = {
	info: 'info',
	warning: 'warning',
	critical: 'danger'
};

export const SEVERITY_LABEL_DE: Record<AlertSeverity, string> = {
	info: 'Info',
	warning: 'Warnung',
	critical: 'Kritisch'
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
