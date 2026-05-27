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

import {
	METRIC_DEFAULTS,
	ALL_ALERT_METRICS,
	alertRulesToRowState,
	rowStateToAlertRules,
	deriveAlertMode,
	applyModeToRowState,
} from './alertMetricTable.ts';

import type { AlertRule, AlertMetric } from '../../types.ts';

// =============================================================================
// METRIC_DEFAULTS — 9 Eintraege mit korrekten Standardwerten (Spec §Implementation)
// =============================================================================

test('METRIC_DEFAULTS > hat genau 9 Eintraege', () => {
	assert.equal(Object.keys(METRIC_DEFAULTS).length, 9);
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

// =============================================================================
// ALL_ALERT_METRICS — geordnete Liste aller 9 Metriken (Spec §Reihenfolge)
// =============================================================================

test('ALL_ALERT_METRICS > hat genau 9 Eintraege', () => {
	assert.equal(ALL_ALERT_METRICS.length, 9);
});

test('ALL_ALERT_METRICS > wind_gust kommt zuerst', () => {
	assert.equal(ALL_ALERT_METRICS[0], 'wind_gust');
});

test('ALL_ALERT_METRICS > precipitation_change kommt zuletzt', () => {
	assert.equal(ALL_ALERT_METRICS[8], 'precipitation_change');
});

test('ALL_ALERT_METRICS > enthaelt alle Delta-only-Metriken', () => {
	assert.ok(ALL_ALERT_METRICS.includes('temperature_change'), 'temperature_change fehlt');
	assert.ok(ALL_ALERT_METRICS.includes('wind_change'), 'wind_change fehlt');
	assert.ok(ALL_ALERT_METRICS.includes('precipitation_change'), 'precipitation_change fehlt');
});

// =============================================================================
// alertRulesToRowState — Mapping alert_rules → Row State (AC-3)
// =============================================================================

test('alertRulesToRowState > leere Liste ergibt alle Zeilen mit defaults', () => {
	const state = alertRulesToRowState([]);
	const metrics: AlertMetric[] = ['wind_gust', 'precipitation_sum', 'thunder_level', 'snow_line',
		'temperature_min', 'temperature_max', 'temperature_change', 'wind_change', 'precipitation_change'];
	for (const m of metrics) {
		assert.ok(m in state, `${m} fehlt im State`);
		assert.equal(state[m].absEnabled, false, `${m}.absEnabled sollte false sein`);
		assert.equal(state[m].deltaEnabled, false, `${m}.deltaEnabled sollte false sein`);
		assert.equal(state[m].severity, 'warning', `${m}.severity sollte 'warning' sein`);
	}
});

test('alertRulesToRowState > absolute Regel fuer wind_gust wird korrekt gemappt (AC-3)', () => {
	const rules: AlertRule[] = [{
		id: 'r1',
		kind: 'absolute',
		metric: 'wind_gust',
		threshold: 70,
		severity: 'critical',
		enabled: true,
	}];
	const state = alertRulesToRowState(rules);
	assert.equal(state['wind_gust'].absEnabled, true);
	assert.equal(state['wind_gust'].absThreshold, 70);
	assert.equal(state['wind_gust'].severity, 'critical');
	assert.equal(state['wind_gust'].deltaEnabled, false);
});

test('alertRulesToRowState > delta Regel fuer precipitation_sum wird korrekt gemappt', () => {
	const rules: AlertRule[] = [{
		id: 'r2',
		kind: 'delta',
		metric: 'precipitation_sum',
		threshold: 5,
		severity: 'info',
		enabled: true,
	}];
	const state = alertRulesToRowState(rules);
	assert.equal(state['precipitation_sum'].deltaEnabled, true);
	assert.equal(state['precipitation_sum'].deltaThreshold, 5);
	assert.equal(state['precipitation_sum'].severity, 'info');
	assert.equal(state['precipitation_sum'].absEnabled, false);
});

test('alertRulesToRowState > beide Regeln (abs + delta) fuer eine Metrik', () => {
	const rules: AlertRule[] = [
		{ id: 'r1', kind: 'absolute', metric: 'wind_gust', threshold: 80, severity: 'critical', enabled: true },
		{ id: 'r2', kind: 'delta', metric: 'wind_gust', threshold: 30, severity: 'warning', enabled: true },
	];
	const state = alertRulesToRowState(rules);
	assert.equal(state['wind_gust'].absEnabled, true);
	assert.equal(state['wind_gust'].absThreshold, 80);
	assert.equal(state['wind_gust'].deltaEnabled, true);
	assert.equal(state['wind_gust'].deltaThreshold, 30);
});

test('alertRulesToRowState > Threshold-Default wenn keine Regel vorhanden', () => {
	const state = alertRulesToRowState([]);
	assert.equal(state['wind_gust'].absThreshold, 50);
	assert.equal(state['snow_line'].absThreshold, 2000);
	assert.equal(state['temperature_min'].absThreshold, -5);
});

// =============================================================================
// rowStateToAlertRules — Mapping Row State → alert_rules (AC-4, AC-5)
// =============================================================================

test('rowStateToAlertRules > leerer State (alle disabled) ergibt leeres Array (AC-5)', () => {
	const state = alertRulesToRowState([]);
	const rules = rowStateToAlertRules(state);
	assert.equal(rules.length, 0);
});

test('rowStateToAlertRules > aktivierter abs-Toggle fuer wind_gust erzeugt absolute Regel (AC-4)', () => {
	const state = alertRulesToRowState([]);
	state['wind_gust'].absEnabled = true;
	state['wind_gust'].absThreshold = 60;
	state['wind_gust'].severity = 'warning';
	const rules = rowStateToAlertRules(state);
	const windRule = rules.find(r => r.metric === 'wind_gust' && r.kind === 'absolute');
	assert.ok(windRule, 'Keine absolute wind_gust-Regel gefunden');
	assert.equal(windRule!.threshold, 60);
	assert.equal(windRule!.severity, 'warning');
	assert.equal(windRule!.enabled, true);
});

test('rowStateToAlertRules > aktivierter delta-Toggle fuer precipitation_sum erzeugt delta Regel (AC-4)', () => {
	const state = alertRulesToRowState([]);
	state['precipitation_sum'].deltaEnabled = true;
	state['precipitation_sum'].deltaThreshold = 5;
	const rules = rowStateToAlertRules(state);
	const deltaRule = rules.find(r => r.metric === 'precipitation_sum' && r.kind === 'delta');
	assert.ok(deltaRule, 'Keine delta precipitation_sum-Regel gefunden');
	assert.equal(deltaRule!.threshold, 5);
});

test('rowStateToAlertRules > deaktivierter Toggle erzeugt keine Regel fuer diese Metrik (AC-5)', () => {
	const rules: AlertRule[] = [{
		id: 'r1', kind: 'absolute', metric: 'wind_gust', threshold: 50, severity: 'warning', enabled: true,
	}];
	const state = alertRulesToRowState(rules);
	state['wind_gust'].absEnabled = false; // Toggle deaktivieren
	const result = rowStateToAlertRules(state);
	const windRule = result.find(r => r.metric === 'wind_gust');
	assert.equal(windRule, undefined, 'wind_gust-Regel sollte nicht mehr enthalten sein');
});

test('rowStateToAlertRules > Delta-only-Metrik ohne abs-Regel im Output (AC-2)', () => {
	const state = alertRulesToRowState([]);
	state['temperature_change'].deltaEnabled = true;
	state['temperature_change'].deltaThreshold = 8;
	state['temperature_change'].absEnabled = true; // wird ignoriert (delta-only)
	const rules = rowStateToAlertRules(state);
	const absRule = rules.find(r => r.metric === 'temperature_change' && r.kind === 'absolute');
	const deltaRule = rules.find(r => r.metric === 'temperature_change' && r.kind === 'delta');
	assert.equal(absRule, undefined, 'temperature_change darf keine absolute Regel haben');
	assert.ok(deltaRule, 'temperature_change muss eine delta Regel haben');
});

test('rowStateToAlertRules > vorhandene IDs werden beibehalten', () => {
	const rules: AlertRule[] = [{
		id: 'existing-id-123', kind: 'absolute', metric: 'wind_gust', threshold: 50, severity: 'warning', enabled: true,
	}];
	const state = alertRulesToRowState(rules, rules); // existierende IDs uebergeben
	state['wind_gust'].absEnabled = true;
	const result = rowStateToAlertRules(state, rules);
	const windRule = result.find(r => r.metric === 'wind_gust' && r.kind === 'absolute');
	assert.equal(windRule?.id, 'existing-id-123', 'Bestehende ID muss erhalten bleiben');
});

test('rowStateToAlertRules > neue Regel bekommt eine UUID', () => {
	const state = alertRulesToRowState([]);
	state['snow_line'].absEnabled = true;
	const result = rowStateToAlertRules(state);
	const rule = result.find(r => r.metric === 'snow_line');
	assert.ok(rule?.id, 'Neue Regel muss eine ID haben');
	assert.ok(rule!.id.length > 0, 'ID darf nicht leer sein');
});

// =============================================================================
// deriveAlertMode — Issue #414
// =============================================================================

test('deriveAlertMode > leeres Array ergibt "both" (Default)', () => {
	const mode = deriveAlertMode([]);
	assert.equal(mode, 'both');
});

test('deriveAlertMode > nur absolute Rules ergibt "both" (Default bevorzugt)', () => {
	const rules: AlertRule[] = [{ id: 'r1', kind: 'absolute', metric: 'wind_gust', threshold: 50, severity: 'warning', enabled: true }];
	assert.equal(deriveAlertMode(rules), 'both');
});

test('deriveAlertMode > nur delta Rules ergibt "delta"', () => {
	const rules: AlertRule[] = [{ id: 'r1', kind: 'delta', metric: 'wind_gust', threshold: 20, severity: 'warning', enabled: true }];
	assert.equal(deriveAlertMode(rules), 'delta');
});

test('deriveAlertMode > abs + delta Rules ergibt "both"', () => {
	const rules: AlertRule[] = [
		{ id: 'r1', kind: 'absolute', metric: 'wind_gust', threshold: 50, severity: 'warning', enabled: true },
		{ id: 'r2', kind: 'delta',    metric: 'wind_gust', threshold: 20, severity: 'warning', enabled: true },
	];
	assert.equal(deriveAlertMode(rules), 'both');
});

// =============================================================================
// applyModeToRowState — Issue #414
// =============================================================================

test('applyModeToRowState "absolute" setzt absEnabled=true, deltaEnabled=false für Standard-Metriken (AC-4)', () => {
	const state = alertRulesToRowState([]);
	applyModeToRowState(state, 'absolute');
	assert.equal(state['wind_gust'].absEnabled, true);
	assert.equal(state['wind_gust'].deltaEnabled, false);
	assert.equal(state['precipitation_sum'].absEnabled, true);
	assert.equal(state['precipitation_sum'].deltaEnabled, false);
});

test('applyModeToRowState "delta" setzt absEnabled=false, deltaEnabled=true für alle Metriken (AC-5)', () => {
	const state = alertRulesToRowState([]);
	applyModeToRowState(state, 'delta');
	assert.equal(state['wind_gust'].absEnabled, false);
	assert.equal(state['wind_gust'].deltaEnabled, true);
	assert.equal(state['snow_line'].absEnabled, false);
	assert.equal(state['snow_line'].deltaEnabled, true);
});

test('applyModeToRowState "both" setzt absEnabled=true und deltaEnabled=true für Standard-Metriken', () => {
	const state = alertRulesToRowState([]);
	applyModeToRowState(state, 'both');
	assert.equal(state['wind_gust'].absEnabled, true);
	assert.equal(state['wind_gust'].deltaEnabled, true);
});

test('applyModeToRowState "absolute" lässt DELTA_ONLY_METRICS absEnabled=false (AC-11)', () => {
	const state = alertRulesToRowState([]);
	applyModeToRowState(state, 'absolute');
	assert.equal(state['temperature_change'].absEnabled, false);
	assert.equal(state['wind_change'].absEnabled, false);
	assert.equal(state['precipitation_change'].absEnabled, false);
	assert.equal(state['thunder_level'].absEnabled, false);
});

test('applyModeToRowState bewahrt Threshold-Werte beim Modus-Wechsel (AC-6)', () => {
	const state = alertRulesToRowState([]);
	state['wind_gust'].absThreshold = 70;
	state['wind_gust'].deltaThreshold = 25;
	applyModeToRowState(state, 'delta');
	assert.equal(state['wind_gust'].absThreshold, 70);
	assert.equal(state['wind_gust'].deltaThreshold, 25);
});
