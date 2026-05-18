// Unit-Tests fuer Issue #223 — newDefaultRule() Helper.
//
// Spec: docs/specs/modules/issue_223_alert_rules_editor.md (Section 2)
//
// Ausfuehrung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/alert-rules-editor/alertRuleDefaults.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import { newDefaultRule, expandRules } from './alertRuleDefaults.ts';
import type { AlertMetric, AlertRule } from '$lib/types';

test('newDefaultRule: liefert AlertRule mit Wizard-Default-Werten (AC-3)', () => {
	const rule = newDefaultRule();
	assert.equal(rule.kind, 'absolute');
	assert.equal(rule.metric, 'wind_gust');
	assert.equal(rule.threshold, 50);
	assert.equal(rule.unit, 'km/h');
	assert.equal(rule.severity, 'warning');
	assert.equal(rule.enabled, true);
});

test('newDefaultRule: liefert eindeutige ID pro Aufruf', () => {
	const a = newDefaultRule();
	const b = newDefaultRule();
	const c = newDefaultRule();
	assert.notEqual(a.id, b.id);
	assert.notEqual(b.id, c.id);
	assert.notEqual(a.id, c.id);
	for (const r of [a, b, c]) {
		assert.equal(typeof r.id, 'string');
		assert.ok(r.id.length > 0);
	}
});

test('newDefaultRule: erzeugt keine geteilten Referenzen (frische Objekte)', () => {
	const a = newDefaultRule();
	const b = newDefaultRule();
	a.threshold = 999;
	assert.equal(b.threshold, 50, 'Mutation an a darf b nicht beeinflussen');
});

// =============================================================================
// Issue #179 — Modus-Toggle: expandRules() Logik
// =============================================================================
// Spec: docs/specs/modules/issue_179_alert_konfigurator_modus_toggle.md
//
// expandRules(rule, mode) ist die Pure-Function-Extraktion der saveEdit()-Logik
// aus AlertRuleRow.svelte. Sie nimmt eine Rule + den gewaehlten UI-Modus
// ('absolute' | 'delta' | 'both') und liefert das Array, das an
// AlertRulesEditor.updateRules(index, ...) weitergereicht wird.
//
//   mode='absolute'                  -> [rule mit kind='absolute']
//   mode='delta'                     -> [rule mit kind='delta']
//   mode='both' (Standard-Metrik)    -> [absolute, delta] (zwei Rules, gleiche
//                                       metric/threshold/severity, verschiedene IDs)
//   mode='both' (Delta-only Metrik)  -> [rule mit kind='delta'] (Guard greift)

const DELTA_ONLY_METRICS: AlertMetric[] = [
	'temperature_change',
	'wind_change',
	'precipitation_change'
];

test('expandRules > mode=absolute → eine Rule, kind=absolute (AC-4)', () => {
	const base = newDefaultRule(); // metric='wind_gust' (nicht delta-only)
	const result = expandRules(base, 'absolute');
	assert.ok(Array.isArray(result), 'Rueckgabe muss Array sein');
	assert.equal(result.length, 1, 'Genau eine Rule erwartet');
	assert.equal(result[0].kind, 'absolute');
	assert.equal(result[0].metric, base.metric);
	assert.equal(result[0].threshold, base.threshold);
	assert.equal(result[0].severity, base.severity);
});

test('expandRules > mode=delta → eine Rule, kind=delta (AC-4)', () => {
	const base = newDefaultRule();
	const result = expandRules(base, 'delta');
	assert.ok(Array.isArray(result));
	assert.equal(result.length, 1);
	assert.equal(result[0].kind, 'delta');
	assert.equal(result[0].metric, base.metric);
	assert.equal(result[0].threshold, base.threshold);
});

test('expandRules > mode=both → zwei Rules (AC-5)', () => {
	const base = newDefaultRule(); // wind_gust ist NICHT delta-only
	const result = expandRules(base, 'both');
	assert.ok(Array.isArray(result));
	assert.equal(result.length, 2, 'Modus "Beides" muss zwei Rules erzeugen');
});

test('expandRules > mode=both → erste Rule absolute, zweite delta (AC-5)', () => {
	const base: AlertRule = { ...newDefaultRule(), metric: 'wind_gust' };
	const result = expandRules(base, 'both');
	assert.equal(result.length, 2);

	// AC-5: erste hat kind='absolute' (original-ID), zweite hat kind='delta' (neue UUID)
	assert.equal(result[0].kind, 'absolute');
	assert.equal(result[1].kind, 'delta');

	// Original-ID bleibt an der absoluten Rule
	assert.equal(result[0].id, base.id, 'Erste Rule behaelt original-ID');

	// Zweite Rule hat neue, eindeutige ID
	assert.notEqual(result[1].id, base.id, 'Zweite Rule muss neue ID haben');
	assert.notEqual(result[0].id, result[1].id, 'IDs muessen verschieden sein');
	assert.equal(typeof result[1].id, 'string');
	assert.ok(result[1].id.length > 0);

	// metric, threshold, severity sind identisch zwischen beiden Rules
	assert.equal(result[0].metric, result[1].metric);
	assert.equal(result[0].threshold, result[1].threshold);
	assert.equal(result[0].severity, result[1].severity);
});

test('expandRules > mode=both, delta-only-Metrik → nur eine delta-Rule (AC-6)', () => {
	for (const metric of DELTA_ONLY_METRICS) {
		const base: AlertRule = { ...newDefaultRule(), metric };
		const result = expandRules(base, 'both');
		assert.equal(
			result.length,
			1,
			`Delta-only-Metrik "${metric}" darf bei mode=both nur EINE Rule liefern`
		);
		assert.equal(
			result[0].kind,
			'delta',
			`Einzige Rule muss kind='delta' haben (Metrik=${metric})`
		);
		assert.equal(result[0].metric, metric);
	}
});

test('expandRules > bestehende Rule mit kind=delta → [rule] unveraendert bei mode=delta (AC-8)', () => {
	// Legacy-Rule (z.B. aus report_config.change_threshold_*-Migration) hat bereits kind='delta'.
	// expandRules mit mode='delta' muss das Array mit genau einer delta-Rule liefern.
	const legacyDeltaRule: AlertRule = {
		id: 'legacy-uuid-123',
		kind: 'delta',
		metric: 'wind_gust',
		threshold: 20,
		unit: 'km/h',
		severity: 'warning',
		enabled: true
	};

	const result = expandRules(legacyDeltaRule, 'delta');
	assert.equal(result.length, 1);
	assert.equal(result[0].kind, 'delta');
	assert.equal(result[0].id, legacyDeltaRule.id, 'ID bleibt erhalten');
	assert.equal(result[0].metric, legacyDeltaRule.metric);
	assert.equal(result[0].threshold, legacyDeltaRule.threshold);
	assert.equal(result[0].severity, legacyDeltaRule.severity);
});
