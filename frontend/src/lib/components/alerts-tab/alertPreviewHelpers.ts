// Issue #182 — Alert-Konfigurator: Alert-Vorschau (Email).
// Spec: docs/specs/modules/issue_182_alert_preview.md
//
// Helper: METRIC_MAP + SEVERITY_MAP + buildAlertPreviewPayload(rules, stages).
// Wird von AlertPreviewCard.svelte und alertPreviewHelpers.test.ts genutzt.

import type { AlertRule, AlertMetric, Stage } from '../../types.ts';

export const METRIC_MAP: Record<AlertMetric, { metric: string; direction: string }> = {
	wind_gust:            { metric: 'gust_max_kmh',      direction: 'above' },
	precipitation_sum:    { metric: 'precip_sum_mm',     direction: 'above' },
	temperature_min:      { metric: 'temp_min_c',        direction: 'below' },
	temperature_max:      { metric: 'temp_max_c',        direction: 'above' },
	thunder_level:        { metric: 'thunder_level_max', direction: 'above' },
	snow_line:            { metric: 'freezing_level_m',  direction: 'above' },
	temperature_change:   { metric: 'temp_min_c',        direction: 'increase' },
	wind_change:          { metric: 'wind_max_kmh',      direction: 'increase' },
	precipitation_change: { metric: 'precip_sum_mm',     direction: 'increase' },
	// Issue #846: 4 neue Metriken
	fresh_snow:           { metric: 'snow_new_sum_cm',   direction: 'above' },
	cape:                 { metric: 'cape_max_jkg',      direction: 'above' },
	visibility:           { metric: 'visibility_min_m',  direction: 'below_threshold' },
	humidity:             { metric: 'humidity_avg_pct',  direction: 'above' },
	// Issue #946: Nullgradgrenze (freezing_level).
	freezing_level:       { metric: 'freezing_level_m',  direction: 'below' },
};

export const SEVERITY_MAP: Record<string, string> = {
	info: 'minor',
	warning: 'moderate',
	critical: 'major',
};

export interface ChangePayload {
	metric: string;
	old_value: number;
	new_value: number;
	delta: number;
	threshold: number;
	severity: string;
	direction: string;
	segment_id: string;
}

export interface SegmentTime {
	segment_id: string;
	start: string;
	end: string;
}

export interface AlertPreviewPayload {
	changes: ChangePayload[];
	segment_times: SegmentTime[];
}

export function buildAlertPreviewPayload(
	rules: AlertRule[],
	stages: Stage[],
): AlertPreviewPayload {
	const segmentId = stages[0]?.id ?? '1';
	const enabled = rules.filter((r) => r.enabled);
	const changes: ChangePayload[] = enabled.map((rule) => {
		const mapped = METRIC_MAP[rule.metric];
		const newValue = rule.threshold * 1.2;
		const oldValue = rule.kind === 'delta' ? 0 : rule.threshold * 0.8;
		return {
			metric: mapped.metric,
			old_value: oldValue,
			new_value: newValue,
			delta: newValue - oldValue,
			threshold: rule.threshold,
			severity: SEVERITY_MAP[rule.severity],
			direction: mapped.direction,
			segment_id: segmentId,
		};
	});
	return {
		changes,
		segment_times: [{ segment_id: segmentId, start: '08:00', end: '17:00' }],
	};
}
