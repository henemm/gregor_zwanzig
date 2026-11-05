// TDD RED: Issue #180 — Alert-Konfigurator: Schwellwert-Tabelle
//
// Spec: docs/specs/modules/issue_180_alert_metric_table.md
//
// Tests scheitern absichtlich (RED): alertMetricTable.ts existiert noch nicht.
//
// Ausfuehrung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/alerts-tab/alertMetricTable.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

// Issue #1895 S4: die Tests der entfernten Regel-Editor-Umrechner
// (ALL_ALERT_METRICS, Row-State, Modus, DELTA_ONLY_METRICS) sind mit ihrem
// Pruefling entfallen; hier bleiben die Tests des produktiven METRIC_DEFAULTS.
import { METRIC_DEFAULTS } from './alertMetricTable.ts';

// =============================================================================
// METRIC_DEFAULTS — 16 Eintraege mit korrekten Standardwerten (Spec §Implementation)
// (Issue #946: freezing_level ergänzt → 14 statt 13.
//  Issue #1468: thunder_onset + precipitation_heavy_onset → 16 statt 14.)
// =============================================================================

test('METRIC_DEFAULTS > hat genau 16 Eintraege', () => {
	assert.equal(Object.keys(METRIC_DEFAULTS).length, 16);
});

test('METRIC_DEFAULTS > wind_gust default ist 50', () => {
	assert.equal(METRIC_DEFAULTS['wind_gust'], 50);
});

test('METRIC_DEFAULTS > precipitation_sum default ist 10', () => {
	assert.equal(METRIC_DEFAULTS['precipitation_sum'], 10);
});

test('METRIC_DEFAULTS > thunder_level default ist 1', () => {
	assert.equal(METRIC_DEFAULTS['thunder_level'], 1);
});

test('METRIC_DEFAULTS > snow_line default ist 2000', () => {
	assert.equal(METRIC_DEFAULTS['snow_line'], 2000);
});

test('METRIC_DEFAULTS > temperature_min default ist -5', () => {
	assert.equal(METRIC_DEFAULTS['temperature_min'], -5);
});

test('METRIC_DEFAULTS > temperature_max default ist 35', () => {
	assert.equal(METRIC_DEFAULTS['temperature_max'], 35);
});

test('METRIC_DEFAULTS > temperature_change default ist 10', () => {
	assert.equal(METRIC_DEFAULTS['temperature_change'], 10);
});

test('METRIC_DEFAULTS > wind_change default ist 20', () => {
	assert.equal(METRIC_DEFAULTS['wind_change'], 20);
});

test('METRIC_DEFAULTS > precipitation_change default ist 5', () => {
	assert.equal(METRIC_DEFAULTS['precipitation_change'], 5);
});
