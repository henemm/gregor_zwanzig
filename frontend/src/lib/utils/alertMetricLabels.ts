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
	temperature_min: { label_de: 'Tiefsttemperatur', unit: '°C', comparison: '<' },
	temperature_max: { label_de: 'Höchsttemperatur', unit: '°C', comparison: '>' },
	temperature_change: { label_de: 'Temperaturänderung', unit: '°C', comparison: '>' },
	wind_change: { label_de: 'Windänderung', unit: 'km/h', comparison: '>' },
	precipitation_change: { label_de: 'Niederschlagsänderung', unit: 'mm', comparison: '>' }
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

/**
 * Wandelt einen THUNDER_LEVEL-Threshold (1.0 / 2.0) in einen menschenlesbaren
 * Label fuer die AlertRow-Anzeige. >=2.0 → "HOCH", >=1.0 → "MITTEL", sonst "KEINE".
 */
export function thunderLevelLabel(threshold: number): string {
	if (threshold >= 2.0) return 'HOCH';
	if (threshold >= 1.0) return 'MITTEL';
	return 'KEINE';
}
