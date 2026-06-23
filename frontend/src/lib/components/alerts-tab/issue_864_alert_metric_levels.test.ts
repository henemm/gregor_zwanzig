// TDD RED — Issue #864/#859: Per-Metrik-Alert-Levels + Auto-Save AlertsTab.
//
// Spec: docs/specs/modules/feat_864_859_alert_presets.md
//
// Tests scheitern heute (RED), weil:
//   - `levelToThreshold()` in alertMetricTable.ts noch nicht existiert.
//   - `migrateAlertPreset()` in alertMetricTable.ts noch nicht existiert.
//   - `THRESHOLD_CROSSING_METRICS`-Set noch nicht exportiert wird.
//
// Geprüfte ACs (TypeScript-Helper):
//   AC-3: levelToThreshold() gibt "Δ ≥ X unit" für Delta-Metriken zurück;
//         "< X m" für visibility (THRESHOLD_CROSSING).
//   AC-9: migrateAlertPreset() wandelt globalen Preset-String in
//         Record<AlertMetric, SensLevel> um.
//
// Ausführen (nach npm ci):
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/alerts-tab/issue_864_alert_metric_levels.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
	levelToThreshold,
	migrateAlertPreset,
	THRESHOLD_CROSSING_METRICS,
} from './alertMetricTable.ts';

import type { AlertMetric } from '../../types.ts';

// ─── AC-3: levelToThreshold ────────────────────────────────────────────────

test('levelToThreshold > gibt null zurück wenn level = off', () => {
	const result = levelToThreshold('wind_gust' as AlertMetric, 'off');
	assert.equal(result, null, 'level=off muss null ergeben');
});

test('levelToThreshold > wind_gust standard → "Δ ≥ 20 km/h"', () => {
	const result = levelToThreshold('wind_gust' as AlertMetric, 'standard');
	assert.equal(result, 'Δ ≥ 20 km/h',
		`Erwartet "Δ ≥ 20 km/h", erhalten: ${result}`);
});

test('levelToThreshold > wind_gust entspannt → "Δ ≥ 35 km/h"', () => {
	const result = levelToThreshold('wind_gust' as AlertMetric, 'entspannt');
	assert.equal(result, 'Δ ≥ 35 km/h');
});

test('levelToThreshold > wind_gust sensibel → "Δ ≥ 12 km/h"', () => {
	const result = levelToThreshold('wind_gust' as AlertMetric, 'sensibel');
	assert.equal(result, 'Δ ≥ 12 km/h');
});

test('levelToThreshold > visibility standard → "< 1000 m" (THRESHOLD_CROSSING)', () => {
	const result = levelToThreshold('visibility' as AlertMetric, 'standard');
	assert.equal(result, '< 1000 m',
		`visibility standard muss "< 1000 m" sein, erhalten: ${result}`);
});

test('levelToThreshold > visibility entspannt → "< 500 m"', () => {
	const result = levelToThreshold('visibility' as AlertMetric, 'entspannt');
	assert.equal(result, '< 500 m');
});

test('levelToThreshold > visibility sensibel → "< 3000 m"', () => {
	const result = levelToThreshold('visibility' as AlertMetric, 'sensibel');
	assert.equal(result, '< 3000 m');
});

test('levelToThreshold > precipitation_sum standard → "Δ ≥ 10 mm"', () => {
	const result = levelToThreshold('precipitation_sum' as AlertMetric, 'standard');
	assert.equal(result, 'Δ ≥ 10 mm');
});

test('levelToThreshold > cape standard → "Δ ≥ 600 J/kg"', () => {
	const result = levelToThreshold('cape' as AlertMetric, 'standard');
	assert.equal(result, 'Δ ≥ 600 J/kg');
});

// ─── AC-3: THRESHOLD_CROSSING_METRICS ─────────────────────────────────────

test('THRESHOLD_CROSSING_METRICS > enthält visibility', () => {
	assert.ok(
		THRESHOLD_CROSSING_METRICS.has('visibility' as AlertMetric),
		'visibility muss in THRESHOLD_CROSSING_METRICS sein'
	);
});

test('THRESHOLD_CROSSING_METRICS > enthält NICHT wind_gust', () => {
	assert.ok(
		!THRESHOLD_CROSSING_METRICS.has('wind_gust' as AlertMetric),
		'wind_gust darf NICHT in THRESHOLD_CROSSING_METRICS sein'
	);
});

// ─── AC-9: migrateAlertPreset ──────────────────────────────────────────────

test('migrateAlertPreset > "standard" mit 2 Metriken → alle auf standard', () => {
	const activeMetrics = ['wind_gust', 'precipitation_sum'] as AlertMetric[];
	const result = migrateAlertPreset('standard', activeMetrics);
	assert.deepEqual(result, {
		wind_gust: 'standard',
		precipitation_sum: 'standard',
	});
});

test('migrateAlertPreset > "entspannt" → alle Metriken auf entspannt', () => {
	const activeMetrics = ['wind_gust', 'visibility'] as AlertMetric[];
	const result = migrateAlertPreset('entspannt', activeMetrics);
	assert.equal(result['wind_gust' as AlertMetric], 'entspannt');
	assert.equal(result['visibility' as AlertMetric], 'entspannt');
});

test('migrateAlertPreset > "deaktiviert" → alle Metriken auf off', () => {
	const activeMetrics = ['wind_gust'] as AlertMetric[];
	const result = migrateAlertPreset('deaktiviert', activeMetrics);
	assert.equal(result['wind_gust' as AlertMetric], 'off',
		'"deaktiviert" muss zu SensLevel "off" gemappt werden');
});

test('migrateAlertPreset > "sensibel" → alle Metriken auf sensibel', () => {
	const activeMetrics = ['wind_gust', 'cape'] as AlertMetric[];
	const result = migrateAlertPreset('sensibel', activeMetrics);
	assert.equal(result['wind_gust' as AlertMetric], 'sensibel');
	assert.equal(result['cape' as AlertMetric], 'sensibel');
});

test('migrateAlertPreset > leere Metrik-Liste → leeres Objekt', () => {
	const result = migrateAlertPreset('standard', []);
	assert.deepEqual(result, {});
});
