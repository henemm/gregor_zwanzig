// Epic #135 Step 5 — Pure-Function-Helper fuer die rechte Spalte im Trip-Detail
// Overview-Tab (Issues #158 + #159).
//
// Spec: docs/specs/modules/epic_135_step5_right_column.md §1.
//
// Kapselt den generischen `Record<string, unknown>`-Zugriff auf
// `trip.report_config`, `trip.weather_config` und `trip.aggregation` an einer
// Stelle. Alle Funktionen sind pure (kein Side-Effect, kein I/O) und
// vollstaendig unit-testbar.

import type { Trip } from '$lib/types';

const DEFAULT_LABEL = 'Standard-Metriken';

export function getPresetLabel(trip: Trip): string {
	const profile = (trip.aggregation as Record<string, unknown> | undefined)?.activity_profile;
	if (profile === 'wintersport') return 'Wintersport-Standard';
	if (profile === 'wandern') return 'Wandern-Standard';
	if (profile === 'allgemein') return DEFAULT_LABEL;
	return DEFAULT_LABEL;
}

export function getDefaultMetricsForProfile(profile: unknown): string[] {
	if (profile === 'wintersport')
		return ['temp_min', 'temp_max', 'wind_max', 'snow_new', 'snow_depth', 'thunder_level'];
	if (profile === 'wandern')
		return ['temp_min', 'temp_max', 'wind_max', 'precip_sum', 'thunder_level', 'cloud_avg'];
	if (profile === 'allgemein') return ['temp_min', 'temp_max', 'wind_max', 'precip_sum'];
	return [];
}

export function getActiveMetrics(trip: Trip): string[] {
	const wc = trip.weather_config as Record<string, unknown> | undefined;
	const metrics = wc?.metrics;
	if (Array.isArray(metrics)) {
		if (metrics.every((m) => typeof m === 'string')) {
			return metrics as string[];
		}
		// Array vorhanden aber enthaelt Non-Strings -> Fallback auf Profile-Default
		const profile = (trip.aggregation as Record<string, unknown> | undefined)?.activity_profile;
		return getDefaultMetricsForProfile(profile);
	}
	const profile = (trip.aggregation as Record<string, unknown> | undefined)?.activity_profile;
	return getDefaultMetricsForProfile(profile);
}

export interface ReportSchedule {
	morning?: string;
	evening?: string;
	alertOnChanges: boolean;
	enabled: boolean;
}

export function getReportSchedule(trip: Trip): ReportSchedule {
	const rc = trip.report_config as Record<string, unknown> | undefined;
	if (!rc) return { enabled: false, alertOnChanges: false };
	return {
		enabled: rc.enabled === true,
		morning: typeof rc.morning_time === 'string' ? (rc.morning_time as string) : undefined,
		evening: typeof rc.evening_time === 'string' ? (rc.evening_time as string) : undefined,
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
	snow_depth: 'Schneehöhe'
};

export function prettyLabel(metricKey: string): string {
	return METRIC_LABELS[metricKey] ?? metricKey;
}
