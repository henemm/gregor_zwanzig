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

const DEFAULT_LABEL = 'Standard-Metriken';

export function getPresetLabel(trip: Trip): string {
	const profile = trip.aggregation?.profile;
	if (profile === 'wintersport') return 'Wintersport-Standard';
	if (profile === 'wandern') return 'Wandern-Standard';
	if (profile === 'summer_trekking') return 'Sommer-Trekking-Standard';
	if (profile === 'allgemein') return DEFAULT_LABEL;
	return DEFAULT_LABEL;
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
	const metrics: unknown = trip.weather_config?.metrics;
	if (Array.isArray(metrics)) {
		if (metrics.every((m): m is string => typeof m === 'string')) {
			return metrics;
		}
		// Array vorhanden aber enthaelt Non-Strings -> Fallback auf Profile-Default
		const profile = trip.aggregation?.profile;
		return getDefaultMetricsForProfile(profile);
	}
	const profile = trip.aggregation?.profile;
	return getDefaultMetricsForProfile(profile);
}

export interface ReportSchedule {
	morning?: string;
	evening?: string;
	alertOnChanges: boolean;
	enabled: boolean;
}

export function getReportSchedule(trip: Trip): ReportSchedule {
	const rc = trip.report_config;
	if (!rc) return { enabled: false, alertOnChanges: false };
	// Defensive Runtime-Checks: Backend kann Off-Spec-Werte liefern.
	const morningTime: unknown = rc.morning_time;
	const eveningTime: unknown = rc.evening_time;
	return {
		enabled: rc.enabled === true,
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
