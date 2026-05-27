// Epic #135 Step 5 — Pure-Function-Helper fuer die rechte Spalte im Trip-Detail
// Overview-Tab (Issues #158 + #159).
//
// Spec: docs/specs/modules/epic_135_step5_right_column.md §1.
//
// Issue #207: Nutzt jetzt die strukturierten Interfaces `Aggregation`,
// `WeatherConfig`, `ReportConfig` aus `$lib/types` — keine Casts auf
// `Record<string, unknown>` mehr. Defensive Runtime-Checks bleiben drin, weil
// das Backend `map[string]interface{}` schickt und Tests bewusst Off-Spec-Werte
// (Non-String, Non-Boolean) reinkippen, um Fallback-Pfade zu beweisen.

import type { Trip } from '$lib/types';

const TEMPLATE_LABELS: Record<string, string> = {
	wandern: 'Wandern',
	wintersport: 'Wintersport',
	skitouren: 'Skitouren',
	'alpen-trekking': 'Alpen-Trekking',
	radtour: 'Radtour',
	wassersport: 'Wassersport',
	allgemein: 'Allgemein',
	summer_trekking: 'Sommer-Trekking',
};

const DEFAULT_LABEL = 'Standard-Metriken';

export function getPresetLabel(trip: Trip): string {
	const savedKey = trip.display_config?.preset_name;
	if (savedKey && savedKey in TEMPLATE_LABELS) {
		return TEMPLATE_LABELS[savedKey];
	}
	const profile = trip.aggregation?.profile;
	if (profile === 'wintersport') return 'Wintersport-Standard';
	if (profile === 'wandern') return 'Wandern-Standard';
	if (profile === 'summer_trekking') return 'Sommer-Trekking-Standard';
	if (profile === 'allgemein') return DEFAULT_LABEL;
	return DEFAULT_LABEL;
}

/**
 * Issue #173 — Liefert den aktiv ausgewaehlten Preset-Template-Key fuer die
 * PresetRow-Liste in `WeatherMetricsTab`. Single Source of Truth: das
 * persistierte `display_config.preset_name` (Issue #206).
 *
 * - String mit Inhalt -> Template-Key (z.B. "skitouren")
 * - Leer / undefined / Non-String -> null (keine PresetRow ist aktiv)
 */
export function getActivePreset(trip: Trip): string | null {
	const key: unknown = trip.display_config?.preset_name;
	return typeof key === 'string' && key.length > 0 ? key : null;
}

export function getDefaultMetricsForProfile(profile: unknown): string[] {
	if (profile === 'wintersport')
		return ['temp_min', 'temp_max', 'wind_max', 'snow_new', 'snow_depth', 'thunder_level'];
	if (profile === 'wandern')
		return ['temp_min', 'temp_max', 'wind_max', 'precip_sum', 'thunder_level', 'cloud_avg'];
	if (profile === 'summer_trekking')
		return ['temp_min', 'temp_max', 'wind_max', 'gust_max', 'precip_sum', 'thunder_level', 'cloud_avg', 'uv_index'];
	if (profile === 'allgemein') return ['temp_min', 'temp_max', 'wind_max', 'precip_sum'];
	return [];
}

export function getActiveMetrics(trip: Trip): string[] {
	// Backend liefert `metrics` als unstrukturiertes JSON-Array — Off-Spec-Werte
	// (Non-Array, Non-String-Elemente) sind moeglich. Wir greifen ueber `unknown`
	// zu, damit die defensiven Branches kompilieren, ohne dass wir das Interface
	// aufweichen muessen.
	const metrics: unknown = trip.display_config?.metrics;
	if (Array.isArray(metrics)) {
		// WeatherConfigMetric-Objekte: { metric_id, enabled, use_friendly_format }
		// Real production data from WeatherMetricsTab
		if (metrics.length > 0 && typeof (metrics[0] as { metric_id?: unknown })?.metric_id === 'string') {
			return (metrics as Array<{ metric_id: string; enabled: boolean }>)
				.filter(m => m.enabled)
				.map(m => m.metric_id);
		}
		// String array (test compatibility)
		if (metrics.every((m): m is string => typeof m === 'string')) {
			return metrics;
		}
		// Non-string, non-object → fallback auf Profile-Default
		const profile = trip.aggregation?.profile;
		return getDefaultMetricsForProfile(profile);
	}
	const profile = trip.aggregation?.profile;
	return getDefaultMetricsForProfile(profile);
}

export interface ReportSchedule {
	morning?: string;
	evening?: string;
	morning_enabled: boolean;
	evening_enabled: boolean;
	alertOnChanges: boolean;
	enabled: boolean;
}

export function getReportSchedule(trip: Trip): ReportSchedule {
	const rc = trip.report_config;
	if (!rc) return { enabled: false, morning_enabled: false, evening_enabled: false, alertOnChanges: false };
	// Defensive Runtime-Checks: Backend kann Off-Spec-Werte liefern.
	const morningTime: unknown = rc.morning_time;
	const eveningTime: unknown = rc.evening_time;
	return {
		enabled: rc.enabled === true,
		morning_enabled: rc.morning_enabled === true,
		evening_enabled: rc.evening_enabled === true,
		morning: typeof morningTime === 'string' ? morningTime : undefined,
		evening: typeof eveningTime === 'string' ? eveningTime : undefined,
		alertOnChanges: rc.alert_on_changes === true
	};
}

const METRIC_LABELS: Record<string, string> = {
	temp_min: 'Min-Temp',
	temp_max: 'Max-Temp',
	wind_max: 'Wind',
	gust_max: 'Böen',
	precip_sum: 'Niederschlag',
	thunder_level: 'Gewitter',
	cloud_avg: 'Bewölkung',
	humidity_avg: 'Feuchte',
	snow_new: 'Neuschnee',
	snow_depth: 'Schneehöhe',
	uv_index: 'UV-Index'
};

export function prettyLabel(metricKey: string): string {
	return METRIC_LABELS[metricKey] ?? metricKey;
}
