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
	prettyLabel,
	type ReportSchedule
} from './rightColumn.ts';

import type { Aggregation, ReportConfig, Trip, WeatherConfigMetric } from '../types.ts';

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

test('getPresetLabel > AC-13a: profile = "wintersport" → "Wintersport-Standard"', () => {
	const trip = tripWith({ aggregation: { profile: 'wintersport' } });
	assert.equal(getPresetLabel(trip), 'Wintersport-Standard');
});

test('getPresetLabel > AC-13b: profile = "wandern" → "Wandern-Standard"', () => {
	const trip = tripWith({ aggregation: { profile: 'wandern' } });
	assert.equal(getPresetLabel(trip), 'Wandern-Standard');
});

test('getPresetLabel > AC-13c: profile = "allgemein" → "Standard-Metriken"', () => {
	const trip = tripWith({ aggregation: { profile: 'allgemein' } });
	assert.equal(getPresetLabel(trip), 'Standard-Metriken');
});

test('getPresetLabel > AC-13d: unbekanntes Profile → "Standard-Metriken"', () => {
	// Issue #207: Off-Spec-Wert — testet Defensiv-Pfad gegen Fremddaten.
	const trip = tripWith({
		aggregation: { profile: 'mountainbike' } as unknown as Aggregation
	});
	assert.equal(getPresetLabel(trip), 'Standard-Metriken');
});

test('getPresetLabel > AC-13e: profile = null → "Standard-Metriken"', () => {
	// Issue #207: Off-Spec-Wert — Backend kann null senden, Defensiv-Pfad.
	const trip = tripWith({
		aggregation: { profile: null } as unknown as Aggregation
	});
	assert.equal(getPresetLabel(trip), 'Standard-Metriken');
});

test('getPresetLabel > AC-13f: profile = undefined → "Standard-Metriken"', () => {
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

test('getActiveMetrics > AC-14a: display_config.metrics gesetzt → genau diese Werte', () => {
	const trip = tripWith({
		display_config: { metrics: ['temp_min', 'wind_max'] as unknown as WeatherConfigMetric[] }
	});
	assert.deepEqual(getActiveMetrics(trip), ['temp_min', 'wind_max']);
});

test('getActiveMetrics > AC-14b: kein weather_config.metrics, profile = "wandern" → Wandern-Default-Set', () => {
	const trip = tripWith({
		aggregation: { profile: 'wandern' }
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

test('getActiveMetrics > display_config.metrics leer ([]) → leeres Array', () => {
	const trip = tripWith({
		display_config: { metrics: [] },
		aggregation: { profile: 'wandern' }
	});
	assert.deepEqual(getActiveMetrics(trip), []);
});

test('getActiveMetrics > display_config.metrics ist kein Array → Fallback auf profile', () => {
	const trip = tripWith({
		display_config: { metrics: 'temp_min' } as unknown as import('../types.ts').DisplayConfig,
		aggregation: { profile: 'allgemein' }
	});
	assert.deepEqual(getActiveMetrics(trip), ['temp_min', 'temp_max', 'wind_max', 'precip_sum']);
});

test('getActiveMetrics > display_config.metrics mit Non-String → Fallback auf Profile-Default', () => {
	const trip = tripWith({
		display_config: { metrics: ['temp_min', 42] } as unknown as import('../types.ts').DisplayConfig,
		aggregation: { profile: 'allgemein' }
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
	// Issue #207: Off-Spec — alert_on_changes als String. Defensiver Strict-Compare.
	const trip = tripWith({
		report_config: { enabled: true, alert_on_changes: 'yes' } as unknown as ReportConfig
	});
	// Spec: rc.alert_on_changes === true → exakter Strict-Compare
	assert.equal(getReportSchedule(trip).alertOnChanges, false);
});

test('getReportSchedule > morning_time / evening_time als Non-String → undefined', () => {
	// Issue #207: Off-Spec — Backend liefert Non-String fuer Zeit-Felder.
	const trip = tripWith({
		report_config: {
			enabled: true,
			morning_time: 6,
			evening_time: null
		} as unknown as ReportConfig
	});
	const schedule = getReportSchedule(trip);
	assert.equal(schedule.morning, undefined);
	assert.equal(schedule.evening, undefined);
});

// =============================================================================
// Issue #232 — summer_trekking-Profil-Behandlung
// Spec: docs/specs/modules/epic_135_step5_right_column.md AC-13 (erweitert),
// AC-19, AC-20, AC-21 (Changelog 2026-05-16).
// =============================================================================

test('getPresetLabel > AC-13g: profile = "summer_trekking" → "Sommer-Trekking-Standard"', () => {
	const trip = tripWith({ aggregation: { profile: 'summer_trekking' } });
	assert.equal(getPresetLabel(trip), 'Sommer-Trekking-Standard');
});

test('getDefaultMetricsForProfile > AC-19: "summer_trekking" → wandern-Basis + gust_max + uv_index', () => {
	assert.deepEqual(getDefaultMetricsForProfile('summer_trekking'), [
		'temp_min',
		'temp_max',
		'wind_max',
		'gust_max',
		'precip_sum',
		'thunder_level',
		'cloud_avg',
		'uv_index'
	]);
});

test('getActiveMetrics > AC-20: kein weather_config.metrics, profile = "summer_trekking" → Default-Set', () => {
	const trip = tripWith({
		aggregation: { profile: 'summer_trekking' }
	});
	assert.deepEqual(getActiveMetrics(trip), [
		'temp_min',
		'temp_max',
		'wind_max',
		'gust_max',
		'precip_sum',
		'thunder_level',
		'cloud_avg',
		'uv_index'
	]);
});

test('prettyLabel > AC-21: "uv_index" → "UV-Index"', () => {
	assert.equal(prettyLabel('uv_index'), 'UV-Index');
});

test('getActiveMetrics > WeatherConfigMetric-Objekte → nur enabled=true als string[]', () => {
	const trip = tripWith({
		display_config: {
			metrics: [
				{ metric_id: 'temp_min', enabled: true },
				{ metric_id: 'wind_max', enabled: false },
				{ metric_id: 'precip_sum', enabled: true },
			] as unknown as WeatherConfigMetric[]
		}
	});
	assert.deepEqual(getActiveMetrics(trip), ['temp_min', 'precip_sum']);
});

// =============================================================================
// Issue #206 — preset_name in display_config
// Spec: docs/specs/modules/issue_206_weather_config_preset_name.md
// =============================================================================

test('getActiveMetrics > #206 AC-7: display_config.metrics gesetzt → diese Metriken zurück', () => {
	const trip = tripWith({
		display_config: { metrics: ['temp_max', 'wind_max'] as unknown as WeatherConfigMetric[] },
	});
	const result = getActiveMetrics(trip);
	assert.deepEqual(result, ['temp_max', 'wind_max']);
});

test('getPresetLabel > #206 AC-3: display_config.preset_name="wandern" → "Wandern" (nicht "Wandern-Standard")', () => {
	const trip = tripWith({
		display_config: { preset_name: 'wandern' },
		aggregation: { profile: 'wintersport' }
	});
	assert.equal(getPresetLabel(trip), 'Wandern');
});

test('getPresetLabel > #206 AC-3b: display_config.preset_name="wintersport" → "Wintersport"', () => {
	const trip = tripWith({
		display_config: { preset_name: 'wintersport' },
		aggregation: { profile: 'wandern' }
	});
	assert.equal(getPresetLabel(trip), 'Wintersport');
});

test('getPresetLabel > #206 AC-8: unbekannter preset_name → Fallback auf profile', () => {
	const trip = tripWith({
		display_config: { preset_name: 'geloeschtes-template-xyz' },
		aggregation: { profile: 'wandern' }
	});
	assert.equal(getPresetLabel(trip), 'Wandern-Standard');
});
