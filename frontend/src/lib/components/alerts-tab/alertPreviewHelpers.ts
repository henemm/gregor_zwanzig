// Issue #182 — Alert-Konfigurator: Alert-Vorschau (Email).
// Spec: docs/specs/modules/issue_182_alert_preview.md
//
// Helper: METRIC_MAP + SEVERITY_MAP + buildAlertPreviewPayload(rules, stages).
// Wird von AlertPreviewCard.svelte und alertPreviewHelpers.test.ts genutzt.

import type { AlertRule, AlertMetric, Stage } from '../../types.ts';
import { METRIC_DEFAULTS } from './alertMetricTable.ts';
import { tr } from '../../i18n/index.ts';

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
	// Issue #1468: Beginn-Verschiebung. `direction` ist hier nur der
	// Vorschau-Vorgabewert; die echte Richtung entscheidet der Wert-Vergleich
	// im Backend (frueher = decrease, spaeter = increase).
	thunder_onset:             { metric: 'thunder_onset_utc',      direction: 'decrease' },
	precipitation_heavy_onset: { metric: 'precip_heavy_onset_utc', direction: 'decrease' },
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
	_stages: Stage[],
): AlertPreviewPayload {
	// Issue #1737: `segment_id` ist eine SEGMENT-Kennung des Tages (1..N,
	// `trip_segments.py`), keine Etappen-Kennung. Frueher stand hier
	// `stages[0].id` ("T01") -- das lehnte der Kern fuer jeden heute laufenden
	// Trip mit 422 ab. Die Vorschau zeigt das erste Segment des Tages.
	// (Issue #1244 F002: `stages` wird nicht mehr gelesen, ein Legacy-`null`
	// kann hier also nicht mehr crashen.)
	const segmentId = '1';
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

// Issue #2283 S5 (AC-20): Body-Bau je kind fuer die kind-neutrale
// Alarm-Vorschau (POST /api/briefings/{id}/alert-preview?kind=…).
// route: unveraendert der Trip-Koerper (Segmente). vergleich: dieselben
// Aenderungswerte je aktiver Regel, aber je Ort (`location_id`) statt Segment
// und ohne `segment_times` — Koerperform wie die S4-Python-Tests.
export type CompareChangePayload = Omit<ChangePayload, 'segment_id'> & { location_id: string };

export function buildAlertPreviewBody(
	kind: 'route' | 'vergleich',
	input: { rules: AlertRule[]; stages?: Stage[]; locationIds?: string[] },
): AlertPreviewPayload | { changes: CompareChangePayload[] } {
	const trip = buildAlertPreviewPayload(input.rules, input.stages ?? []);
	if (kind === 'route') return trip;
	const orte = input.locationIds ?? [];
	return {
		changes: trip.changes.flatMap(({ segment_id: _s, ...rest }) =>
			orte.map((location_id) => ({ ...rest, location_id })),
		),
	};
}

// Issue #2283 S5: der Vergleich speichert keine `alert_rules` — die Vorschau
// bildet je aktiver Alarm-Metrik (Empfindlichkeit nicht „off") eine Regel mit
// dem Standard-Schwellwert des Alarm-Editors.
export function vergleichAlarmRegeln(
	metrics: AlertMetric[],
	levels: Record<string, string> = {},
): AlertRule[] {
	return metrics
		.filter((m) => levels[m] !== 'off' && METRIC_MAP[m])
		.map((m) => ({
			id: `vergleich-${m}`,
			kind: 'absolute',
			metric: m,
			threshold: METRIC_DEFAULTS[m],
			severity: 'warning',
			enabled: true,
		}));
}

/**
 * Issue #2656 (i18n F7): Fehlertext der Beispiel-Warnung. Ein Servertext
 * (`{ error }`) bzw. die Fehlermeldung bleibt unveraendert (Server-Sprache);
 * nur der eigene Rueckfall kommt aus dem Katalog (aktuelle Sprache).
 */
export function vorschauFehlerText(e: unknown): string {
	if (e && typeof e === 'object' && 'error' in e) return String((e as { error: unknown }).error);
	if (e instanceof Error && e.message) return e.message;
	return tr('alarme.vorschau.fehler');
}
