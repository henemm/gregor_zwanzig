// TDD RED: Issue #182 — Alert-Konfigurator: Alert-Vorschau (Email)
//
// Spec: docs/specs/modules/issue_182_alert_preview.md
//
// Tests scheitern absichtlich (RED): alertPreviewHelpers.ts existiert noch nicht.
//
// Ausfuehrung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/alerts-tab/alertPreviewHelpers.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
	METRIC_MAP,
	SEVERITY_MAP,
	buildAlertPreviewPayload,
} from './alertPreviewHelpers.ts';

import type { AlertRule, Stage } from '../../types.ts';

// =============================================================================
// METRIC_MAP — 9 Eintraege, TypeScript AlertMetric → Python-Feldname + direction
// =============================================================================

test('METRIC_MAP > hat genau 9 Eintraege', () => {
	assert.equal(Object.keys(METRIC_MAP).length, 9);
});

test('METRIC_MAP > wind_gust mappt auf gust_max_kmh / above (Spec §Data Model)', () => {
	assert.equal(METRIC_MAP['wind_gust'].metric, 'gust_max_kmh');
	assert.equal(METRIC_MAP['wind_gust'].direction, 'above');
});

test('METRIC_MAP > precipitation_sum mappt auf precip_sum_mm / above', () => {
	assert.equal(METRIC_MAP['precipitation_sum'].metric, 'precip_sum_mm');
	assert.equal(METRIC_MAP['precipitation_sum'].direction, 'above');
});

test('METRIC_MAP > temperature_min mappt auf temp_min_c / below (Kaeltealarm)', () => {
	assert.equal(METRIC_MAP['temperature_min'].metric, 'temp_min_c');
	assert.equal(METRIC_MAP['temperature_min'].direction, 'below');
});

test('METRIC_MAP > temperature_max mappt auf temp_max_c / above', () => {
	assert.equal(METRIC_MAP['temperature_max'].metric, 'temp_max_c');
	assert.equal(METRIC_MAP['temperature_max'].direction, 'above');
});

test('METRIC_MAP > thunder_level mappt auf thunder_level_max / above', () => {
	assert.equal(METRIC_MAP['thunder_level'].metric, 'thunder_level_max');
	assert.equal(METRIC_MAP['thunder_level'].direction, 'above');
});

test('METRIC_MAP > snow_line mappt auf freezing_level_m / above', () => {
	assert.equal(METRIC_MAP['snow_line'].metric, 'freezing_level_m');
	assert.equal(METRIC_MAP['snow_line'].direction, 'above');
});

test('METRIC_MAP > temperature_change mappt auf temp_min_c / increase (Delta)', () => {
	assert.equal(METRIC_MAP['temperature_change'].metric, 'temp_min_c');
	assert.equal(METRIC_MAP['temperature_change'].direction, 'increase');
});

test('METRIC_MAP > wind_change mappt auf wind_max_kmh / increase (Delta)', () => {
	assert.equal(METRIC_MAP['wind_change'].metric, 'wind_max_kmh');
	assert.equal(METRIC_MAP['wind_change'].direction, 'increase');
});

test('METRIC_MAP > precipitation_change mappt auf precip_sum_mm / increase (Delta)', () => {
	assert.equal(METRIC_MAP['precipitation_change'].metric, 'precip_sum_mm');
	assert.equal(METRIC_MAP['precipitation_change'].direction, 'increase');
});

// =============================================================================
// SEVERITY_MAP — AlertSeverity → ChangeSeverity
// =============================================================================

test('SEVERITY_MAP > info → minor', () => {
	assert.equal(SEVERITY_MAP['info'], 'minor');
});

test('SEVERITY_MAP > warning → moderate (AC-2)', () => {
	assert.equal(SEVERITY_MAP['warning'], 'moderate');
});

test('SEVERITY_MAP > critical → major', () => {
	assert.equal(SEVERITY_MAP['critical'], 'major');
});

// =============================================================================
// buildAlertPreviewPayload — Payload-Generierung aus AlertRules + Stages
// =============================================================================

function makeStage(id: string): Stage {
	return {
		id,
		name: 'Testabschnitt',
		date: '2026-05-19',
		waypoints: [],
	};
}

function makeRule(overrides: Partial<AlertRule> = {}): AlertRule {
	return {
		id: 'r1',
		kind: 'absolute',
		metric: 'wind_gust',
		threshold: 60,
		severity: 'warning',
		enabled: true,
		...overrides,
	};
}

// --- AC-1: Keine aktivierten Regeln → leeres changes-Array ---

test('buildAlertPreviewPayload > keine enabled-Regeln → changes ist leer (AC-1)', () => {
	const rules: AlertRule[] = [makeRule({ enabled: false })];
	const stages: Stage[] = [makeStage('s1')];
	const payload = buildAlertPreviewPayload(rules, stages);
	assert.equal(payload.changes.length, 0);
});

test('buildAlertPreviewPayload > leere rules-Liste → changes ist leer (AC-1)', () => {
	const payload = buildAlertPreviewPayload([], [makeStage('s1')]);
	assert.equal(payload.changes.length, 0);
});

// --- AC-2: Absolute Regel korrekt transformiert ---

test('buildAlertPreviewPayload > absolute wind_gust-Regel: metric + direction korrekt (AC-2)', () => {
	const rules = [makeRule({ metric: 'wind_gust', kind: 'absolute', threshold: 60, severity: 'warning' })];
	const payload = buildAlertPreviewPayload(rules, [makeStage('s1')]);
	assert.equal(payload.changes.length, 1);
	assert.equal(payload.changes[0].metric, 'gust_max_kmh');
	assert.equal(payload.changes[0].direction, 'above');
});

test('buildAlertPreviewPayload > absolute wind_gust threshold=60: new_value=72, old_value=48 (AC-2)', () => {
	const rules = [makeRule({ metric: 'wind_gust', threshold: 60 })];
	const payload = buildAlertPreviewPayload(rules, [makeStage('s1')]);
	assert.ok(Math.abs(payload.changes[0].new_value - 72.0) < 0.001, `new_value sollte 72.0 sein, ist ${payload.changes[0].new_value}`);
	assert.ok(Math.abs(payload.changes[0].old_value - 48.0) < 0.001, `old_value sollte 48.0 sein, ist ${payload.changes[0].old_value}`);
});

test('buildAlertPreviewPayload > absolute Regel: delta = new_value - old_value (AC-2)', () => {
	const rules = [makeRule({ threshold: 60 })];
	const payload = buildAlertPreviewPayload(rules, [makeStage('s1')]);
	const c = payload.changes[0];
	assert.ok(Math.abs(c.delta - (c.new_value - c.old_value)) < 0.001);
});

test('buildAlertPreviewPayload > severity warning → moderate im Payload (AC-2)', () => {
	const rules = [makeRule({ severity: 'warning' })];
	const payload = buildAlertPreviewPayload(rules, [makeStage('s1')]);
	assert.equal(payload.changes[0].severity, 'moderate');
});

test('buildAlertPreviewPayload > severity critical → major im Payload', () => {
	const rules = [makeRule({ severity: 'critical' })];
	const payload = buildAlertPreviewPayload(rules, [makeStage('s1')]);
	assert.equal(payload.changes[0].severity, 'major');
});

test('buildAlertPreviewPayload > severity info → minor im Payload', () => {
	const rules = [makeRule({ severity: 'info' })];
	const payload = buildAlertPreviewPayload(rules, [makeStage('s1')]);
	assert.equal(payload.changes[0].severity, 'minor');
});

// --- AC-4: Delta-Regel: old_value=0 ---

test('buildAlertPreviewPayload > delta-Regel: old_value ist 0 (AC-4)', () => {
	const rules = [makeRule({ kind: 'delta', metric: 'temperature_change', threshold: 10 })];
	const payload = buildAlertPreviewPayload(rules, [makeStage('s1')]);
	assert.equal(payload.changes[0].old_value, 0);
});

test('buildAlertPreviewPayload > delta-Regel temperature_change threshold=10: new_value=12, delta=12 (AC-4)', () => {
	const rules = [makeRule({ kind: 'delta', metric: 'temperature_change', threshold: 10 })];
	const payload = buildAlertPreviewPayload(rules, [makeStage('s1')]);
	assert.ok(Math.abs(payload.changes[0].new_value - 12.0) < 0.001);
	assert.ok(Math.abs(payload.changes[0].delta - 12.0) < 0.001);
});

test('buildAlertPreviewPayload > delta-Regel: direction ist increase (AC-4)', () => {
	const rules = [makeRule({ kind: 'delta', metric: 'wind_change', threshold: 20 })];
	const payload = buildAlertPreviewPayload(rules, [makeStage('s1')]);
	assert.equal(payload.changes[0].direction, 'increase');
});

// --- segment_id und segment_times ---

test('buildAlertPreviewPayload > segment_id kommt aus stages[0].id', () => {
	const rules = [makeRule()];
	const stages = [makeStage('etappe-42')];
	const payload = buildAlertPreviewPayload(rules, stages);
	assert.equal(payload.changes[0].segment_id, 'etappe-42');
});

test('buildAlertPreviewPayload > segment_id Fallback auf "1" wenn stages leer', () => {
	const rules = [makeRule()];
	const payload = buildAlertPreviewPayload(rules, []);
	assert.equal(payload.changes[0].segment_id, '1');
});

test('buildAlertPreviewPayload > segment_times enthaelt genau einen Eintrag', () => {
	const rules = [makeRule()];
	const payload = buildAlertPreviewPayload(rules, [makeStage('s1')]);
	assert.equal(payload.segment_times.length, 1);
});

test('buildAlertPreviewPayload > segment_times[0].start ist "08:00"', () => {
	const rules = [makeRule()];
	const payload = buildAlertPreviewPayload(rules, [makeStage('s1')]);
	assert.equal(payload.segment_times[0].start, '08:00');
});

test('buildAlertPreviewPayload > segment_times[0].end ist "17:00"', () => {
	const rules = [makeRule()];
	const payload = buildAlertPreviewPayload(rules, [makeStage('s1')]);
	assert.equal(payload.segment_times[0].end, '17:00');
});

test('buildAlertPreviewPayload > segment_times[0].segment_id stimmt mit changes[0].segment_id ueberein', () => {
	const rules = [makeRule()];
	const stages = [makeStage('meine-etappe')];
	const payload = buildAlertPreviewPayload(rules, stages);
	assert.equal(payload.segment_times[0].segment_id, payload.changes[0].segment_id);
});

// --- threshold wird korrekt weitergegeben ---

test('buildAlertPreviewPayload > threshold wird ungekuerzt in Payload uebernommen', () => {
	const rules = [makeRule({ threshold: 85 })];
	const payload = buildAlertPreviewPayload(rules, [makeStage('s1')]);
	assert.equal(payload.changes[0].threshold, 85);
});

// --- Mehrere Regeln ---

test('buildAlertPreviewPayload > zwei enabled-Regeln ergeben zwei changes-Eintraege', () => {
	const rules: AlertRule[] = [
		makeRule({ id: 'r1', metric: 'wind_gust', threshold: 60 }),
		makeRule({ id: 'r2', metric: 'precipitation_sum', threshold: 15 }),
	];
	const payload = buildAlertPreviewPayload(rules, [makeStage('s1')]);
	assert.equal(payload.changes.length, 2);
});

test('buildAlertPreviewPayload > disabled-Regeln werden uebersprungen', () => {
	const rules: AlertRule[] = [
		makeRule({ id: 'r1', metric: 'wind_gust', enabled: true }),
		makeRule({ id: 'r2', metric: 'precipitation_sum', enabled: false }),
	];
	const payload = buildAlertPreviewPayload(rules, [makeStage('s1')]);
	assert.equal(payload.changes.length, 1);
	assert.equal(payload.changes[0].metric, 'gust_max_kmh');
});
