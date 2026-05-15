// TDD RED: Epic #135 Step 5 — Right-Column Pure-Functions (Issues #158 + #159).
//
// Spec: docs/specs/modules/epic_135_step5_right_column.md
//
// Diese Tests scheitern absichtlich (RED-Phase):
//   - `$lib/utils/rightColumn` existiert noch nicht
//   - Erwartete Funktionen: getPresetLabel, getDefaultMetricsForProfile,
//     getActiveMetrics, getReportSchedule (+ prettyLabel)
//
// Ausfuehrung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/utils/rightColumn.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
	getPresetLabel,
	getDefaultMetricsForProfile,
	getActiveMetrics,
	getReportSchedule,
	type ReportSchedule
} from './rightColumn.ts';

import type { Trip } from '../types.ts';

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

// getPresetLabel

test('getPresetLabel > AC-13a: activity_profile = "wintersport" → "Wintersport-Standard"', () => {
	const trip = tripWith({ aggregation: { activity_profile: 'wintersport' } });
	assert.equal(getPresetLabel(trip), 'Wintersport-Standard');
});

test('getPresetLabel > AC-13b: activity_profile = "wandern" → "Wandern-Standard"', () => {
	const trip = tripWith({ aggregation: { activity_profile: 'wandern' } });
	assert.equal(getPresetLabel(trip), 'Wandern-Standard');
});

test('getPresetLabel > AC-13c: activity_profile = "allgemein" → "Standard-Metriken"', () => {
	const trip = tripWith({ aggregation: { activity_profile: 'allgemein' } });
	assert.equal(getPresetLabel(trip), 'Standard-Metriken');
});

test('getPresetLabel > AC-13d: unbekanntes Profile → "Standard-Metriken"', () => {
	const trip = tripWith({ aggregation: { activity_profile: 'mountainbike' } });
	assert.equal(getPresetLabel(trip), 'Standard-Metriken');
});

test('getPresetLabel > AC-13e: activity_profile = null → "Standard-Metriken"', () => {
	const trip = tripWith({ aggregation: { activity_profile: null } });
	assert.equal(getPresetLabel(trip), 'Standard-Metriken');
});

test('getPresetLabel > AC-13f: activity_profile = undefined → "Standard-Metriken"', () => {
	const trip = tripWith({ aggregation: {} });
	assert.equal(getPresetLabel(trip), 'Standard-Metriken');
});

test('getPresetLabel > Trip ohne aggregation → "Standard-Metriken"', () => {
	const trip = tripWith({});
	assert.equal(getPresetLabel(trip), 'Standard-Metriken');
});

// =============================================================================
// getDefaultMetricsForProfile
// =============================================================================

// getDefaultMetricsForProfile

test('getDefaultMetricsForProfile > "wintersport" enthält snow_new, snow_depth, thunder_level', () => {
	const metrics = getDefaultMetricsForProfile('wintersport');
	assert.ok(metrics.includes('snow_new'));
	assert.ok(metrics.includes('snow_depth'));
	assert.ok(metrics.includes('thunder_level'));
});

test('getDefaultMetricsForProfile > "wandern" enthält precip_sum + cloud_avg und keine snow_*-Metrik', () => {
	const metrics = getDefaultMetricsForProfile('wandern');
	assert.ok(metrics.includes('precip_sum'));
	assert.ok(metrics.includes('cloud_avg'));
	assert.equal(metrics.some((m) => m.startsWith('snow_')), false);
});

test('getDefaultMetricsForProfile > "allgemein" → genau ["temp_min","temp_max","wind_max","precip_sum"]', () => {
	assert.deepEqual(getDefaultMetricsForProfile('allgemein'), [
		'temp_min',
		'temp_max',
		'wind_max',
		'precip_sum'
	]);
});

test('getDefaultMetricsForProfile > unbekanntes Profile → []', () => {
	assert.deepEqual(getDefaultMetricsForProfile('mountainbike'), []);
});

test('getDefaultMetricsForProfile > null → []', () => {
	assert.deepEqual(getDefaultMetricsForProfile(null), []);
});

test('getDefaultMetricsForProfile > undefined → []', () => {
	assert.deepEqual(getDefaultMetricsForProfile(undefined), []);
});

// =============================================================================
// getActiveMetrics
// =============================================================================

// getActiveMetrics

test('getActiveMetrics > AC-14a: weather_config.metrics gesetzt → genau diese Werte', () => {
	const trip = tripWith({
		weather_config: { metrics: ['temp_min', 'wind_max'] }
	});
	assert.deepEqual(getActiveMetrics(trip), ['temp_min', 'wind_max']);
});

test('getActiveMetrics > AC-14b: kein weather_config.metrics, activity_profile = "wandern" → Wandern-Default-Set', () => {
	const trip = tripWith({
		aggregation: { activity_profile: 'wandern' }
	});
	assert.deepEqual(getActiveMetrics(trip), [
		'temp_min',
		'temp_max',
		'wind_max',
		'precip_sum',
		'thunder_level',
		'cloud_avg'
	]);
});

test('getActiveMetrics > Trip ohne weather_config und ohne aggregation → []', () => {
	const trip = tripWith({});
	assert.deepEqual(getActiveMetrics(trip), []);
});

test('getActiveMetrics > weather_config.metrics leer ([]) → leeres Array', () => {
	const trip = tripWith({
		weather_config: { metrics: [] },
		aggregation: { activity_profile: 'wandern' }
	});
	// Array.isArray([]) === true → explizit konfigurierte (leere) Liste zaehlt.
	assert.deepEqual(getActiveMetrics(trip), []);
});

test('getActiveMetrics > weather_config.metrics ist kein Array → Fallback auf activity_profile', () => {
	const trip = tripWith({
		weather_config: { metrics: 'temp_min' },
		aggregation: { activity_profile: 'allgemein' }
	});
	assert.deepEqual(getActiveMetrics(trip), ['temp_min', 'temp_max', 'wind_max', 'precip_sum']);
});

test('getActiveMetrics > weather_config.metrics mit Non-String → Fallback auf Profile-Default', () => {
	const trip = tripWith({
		weather_config: { metrics: ['temp_min', 42] },
		aggregation: { activity_profile: 'allgemein' }
	});
	assert.deepEqual(getActiveMetrics(trip), ['temp_min', 'temp_max', 'wind_max', 'precip_sum']);
});

// =============================================================================
// getReportSchedule
// =============================================================================

// getReportSchedule

test('getReportSchedule > AC-15a: voll konfiguriert → strukturiertes Schedule-Objekt', () => {
	const trip = tripWith({
		report_config: {
			enabled: true,
			morning_time: '06:00:00',
			evening_time: '18:00:00',
			alert_on_changes: true
		}
	});
	const schedule: ReportSchedule = getReportSchedule(trip);
	assert.deepEqual(schedule, {
		enabled: true,
		morning: '06:00:00',
		evening: '18:00:00',
		alertOnChanges: true
	});
});

test('getReportSchedule > enabled: false → enabled=false, alertOnChanges=false (Defaults)', () => {
	const trip = tripWith({
		report_config: { enabled: false }
	});
	const schedule = getReportSchedule(trip);
	assert.equal(schedule.enabled, false);
	assert.equal(schedule.alertOnChanges, false);
	assert.equal(schedule.morning, undefined);
	assert.equal(schedule.evening, undefined);
});

test('getReportSchedule > AC-15b: kein report_config → enabled=false, alertOnChanges=false, morning/evening undefined', () => {
	const trip = tripWith({});
	const schedule = getReportSchedule(trip);
	assert.equal(schedule.enabled, false);
	assert.equal(schedule.alertOnChanges, false);
	assert.equal(schedule.morning, undefined);
	assert.equal(schedule.evening, undefined);
});

test('getReportSchedule > Nur morning_time, kein evening_time → evening: undefined', () => {
	const trip = tripWith({
		report_config: {
			enabled: true,
			morning_time: '07:30:00',
			alert_on_changes: false
		}
	});
	const schedule = getReportSchedule(trip);
	assert.equal(schedule.morning, '07:30:00');
	assert.equal(schedule.evening, undefined);
	assert.equal(schedule.alertOnChanges, false);
	assert.equal(schedule.enabled, true);
});

test('getReportSchedule > alert_on_changes nicht boolean → alertOnChanges=false', () => {
	const trip = tripWith({
		report_config: { enabled: true, alert_on_changes: 'yes' }
	});
	// Spec: rc.alert_on_changes === true → exakter Strict-Compare
	assert.equal(getReportSchedule(trip).alertOnChanges, false);
});

test('getReportSchedule > morning_time / evening_time als Non-String → undefined', () => {
	const trip = tripWith({
		report_config: {
			enabled: true,
			morning_time: 6,
			evening_time: null
		}
	});
	const schedule = getReportSchedule(trip);
	assert.equal(schedule.morning, undefined);
	assert.equal(schedule.evening, undefined);
});
