// TDD RED: Epic #135 Step 5 — Right-Column Pure-Functions (Issues #158 + #159).
//
// Spec: docs/specs/modules/epic_135_step5_right_column.md
//
// Diese Tests scheitern absichtlich (RED-Phase):
//   - `$lib/utils/rightColumn` existiert noch nicht
//   - Erwartete Funktionen: getPresetLabel, getDefaultMetricsForProfile,
//     getActiveMetrics, getReportSchedule (+ prettyLabel)
//
// Ausfuehrung (Vitest):
//   cd frontend && npx vitest run src/lib/utils/rightColumn.test.ts

import { describe, test, expect } from 'vitest';

import {
	getPresetLabel,
	getDefaultMetricsForProfile,
	getActiveMetrics,
	getReportSchedule,
	type ReportSchedule
} from './rightColumn';

import type { Trip } from '$lib/types';

// =============================================================================
// Helpers
// =============================================================================

function tripWith(overrides: Partial<Trip>): Trip {
	return {
		id: 't1',
		name: 'Test Trip',
		stages: [],
		...overrides
	} as Trip;
}

// =============================================================================
// getPresetLabel
// =============================================================================

describe('getPresetLabel', () => {
	test('AC-13a: activity_profile = "wintersport" → "Wintersport-Standard"', () => {
		const trip = tripWith({ aggregation: { activity_profile: 'wintersport' } });
		expect(getPresetLabel(trip)).toBe('Wintersport-Standard');
	});

	test('AC-13b: activity_profile = "wandern" → "Wandern-Standard"', () => {
		const trip = tripWith({ aggregation: { activity_profile: 'wandern' } });
		expect(getPresetLabel(trip)).toBe('Wandern-Standard');
	});

	test('AC-13c: activity_profile = "allgemein" → "Standard-Metriken"', () => {
		const trip = tripWith({ aggregation: { activity_profile: 'allgemein' } });
		expect(getPresetLabel(trip)).toBe('Standard-Metriken');
	});

	test('AC-13d: unbekanntes Profile → "Standard-Metriken"', () => {
		const trip = tripWith({ aggregation: { activity_profile: 'mountainbike' } });
		expect(getPresetLabel(trip)).toBe('Standard-Metriken');
	});

	test('AC-13e: activity_profile = null → "Standard-Metriken"', () => {
		const trip = tripWith({ aggregation: { activity_profile: null } });
		expect(getPresetLabel(trip)).toBe('Standard-Metriken');
	});

	test('AC-13f: activity_profile = undefined → "Standard-Metriken"', () => {
		const trip = tripWith({ aggregation: {} });
		expect(getPresetLabel(trip)).toBe('Standard-Metriken');
	});

	test('Trip ohne aggregation → "Standard-Metriken"', () => {
		const trip = tripWith({});
		expect(getPresetLabel(trip)).toBe('Standard-Metriken');
	});
});

// =============================================================================
// getDefaultMetricsForProfile
// =============================================================================

describe('getDefaultMetricsForProfile', () => {
	test('"wintersport" enthält snow_new, snow_depth, thunder_level', () => {
		const metrics = getDefaultMetricsForProfile('wintersport');
		expect(metrics).toContain('snow_new');
		expect(metrics).toContain('snow_depth');
		expect(metrics).toContain('thunder_level');
	});

	test('"wandern" enthält precip_sum + cloud_avg und keine snow_*-Metrik', () => {
		const metrics = getDefaultMetricsForProfile('wandern');
		expect(metrics).toContain('precip_sum');
		expect(metrics).toContain('cloud_avg');
		expect(metrics.some((m) => m.startsWith('snow_'))).toBe(false);
	});

	test('"allgemein" → genau ["temp_min","temp_max","wind_max","precip_sum"]', () => {
		expect(getDefaultMetricsForProfile('allgemein')).toEqual([
			'temp_min',
			'temp_max',
			'wind_max',
			'precip_sum'
		]);
	});

	test('unbekanntes Profile → []', () => {
		expect(getDefaultMetricsForProfile('mountainbike')).toEqual([]);
	});

	test('null → []', () => {
		expect(getDefaultMetricsForProfile(null)).toEqual([]);
	});

	test('undefined → []', () => {
		expect(getDefaultMetricsForProfile(undefined)).toEqual([]);
	});
});

// =============================================================================
// getActiveMetrics
// =============================================================================

describe('getActiveMetrics', () => {
	test('AC-14a: weather_config.metrics gesetzt → genau diese Werte', () => {
		const trip = tripWith({
			weather_config: { metrics: ['temp_min', 'wind_max'] }
		});
		expect(getActiveMetrics(trip)).toEqual(['temp_min', 'wind_max']);
	});

	test('AC-14b: kein weather_config.metrics, activity_profile = "wandern" → Wandern-Default-Set', () => {
		const trip = tripWith({
			aggregation: { activity_profile: 'wandern' }
		});
		expect(getActiveMetrics(trip)).toEqual([
			'temp_min',
			'temp_max',
			'wind_max',
			'precip_sum',
			'thunder_level',
			'cloud_avg'
		]);
	});

	test('Trip ohne weather_config und ohne aggregation → []', () => {
		const trip = tripWith({});
		expect(getActiveMetrics(trip)).toEqual([]);
	});

	test('weather_config.metrics leer ([]) → leeres Array', () => {
		const trip = tripWith({
			weather_config: { metrics: [] },
			aggregation: { activity_profile: 'wandern' }
		});
		// Array.isArray([]) === true → explizit konfigurierte (leere) Liste zaehlt.
		expect(getActiveMetrics(trip)).toEqual([]);
	});

	test('weather_config.metrics ist kein Array → Fallback auf activity_profile', () => {
		const trip = tripWith({
			weather_config: { metrics: 'temp_min' },
			aggregation: { activity_profile: 'allgemein' }
		});
		expect(getActiveMetrics(trip)).toEqual(['temp_min', 'temp_max', 'wind_max', 'precip_sum']);
	});

	test('weather_config.metrics mit Non-String → Fallback auf Profile-Default', () => {
		const trip = tripWith({
			weather_config: { metrics: ['temp_min', 42] },
			aggregation: { activity_profile: 'allgemein' }
		});
		expect(getActiveMetrics(trip)).toEqual(['temp_min', 'temp_max', 'wind_max', 'precip_sum']);
	});
});

// =============================================================================
// getReportSchedule
// =============================================================================

describe('getReportSchedule', () => {
	test('AC-15a: voll konfiguriert → strukturiertes Schedule-Objekt', () => {
		const trip = tripWith({
			report_config: {
				enabled: true,
				morning_time: '06:00:00',
				evening_time: '18:00:00',
				alert_on_changes: true
			}
		});
		const schedule: ReportSchedule = getReportSchedule(trip);
		expect(schedule).toEqual({
			enabled: true,
			morning: '06:00:00',
			evening: '18:00:00',
			alertOnChanges: true
		});
	});

	test('enabled: false → enabled=false, alertOnChanges=false (Defaults)', () => {
		const trip = tripWith({
			report_config: { enabled: false }
		});
		const schedule = getReportSchedule(trip);
		expect(schedule.enabled).toBe(false);
		expect(schedule.alertOnChanges).toBe(false);
		expect(schedule.morning).toBeUndefined();
		expect(schedule.evening).toBeUndefined();
	});

	test('AC-15b: kein report_config → enabled=false, alertOnChanges=false, morning/evening undefined', () => {
		const trip = tripWith({});
		const schedule = getReportSchedule(trip);
		expect(schedule.enabled).toBe(false);
		expect(schedule.alertOnChanges).toBe(false);
		expect(schedule.morning).toBeUndefined();
		expect(schedule.evening).toBeUndefined();
	});

	test('Nur morning_time, kein evening_time → evening: undefined', () => {
		const trip = tripWith({
			report_config: {
				enabled: true,
				morning_time: '07:30:00',
				alert_on_changes: false
			}
		});
		const schedule = getReportSchedule(trip);
		expect(schedule.morning).toBe('07:30:00');
		expect(schedule.evening).toBeUndefined();
		expect(schedule.alertOnChanges).toBe(false);
		expect(schedule.enabled).toBe(true);
	});

	test('alert_on_changes nicht boolean → alertOnChanges=false', () => {
		const trip = tripWith({
			report_config: { enabled: true, alert_on_changes: 'yes' }
		});
		// Spec: rc.alert_on_changes === true → exakter Strict-Compare
		expect(getReportSchedule(trip).alertOnChanges).toBe(false);
	});

	test('morning_time / evening_time als Non-String → undefined', () => {
		const trip = tripWith({
			report_config: {
				enabled: true,
				morning_time: 6,
				evening_time: null
			}
		});
		const schedule = getReportSchedule(trip);
		expect(schedule.morning).toBeUndefined();
		expect(schedule.evening).toBeUndefined();
	});
});
