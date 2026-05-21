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
	// F002: pair_id + delta_window duerfen bei mode=absolute nicht gesetzt sein.
	assert.equal(result[0].pair_id, undefined, 'Absolute-Rule darf kein pair_id haben');
	assert.equal(result[0].delta_window, undefined, 'Absolute-Rule darf kein delta_window haben');
});

test('expandRules > mode=delta → eine Rule, kind=delta (AC-4)', () => {
	const base = newDefaultRule();
	const result = expandRules(base, 'delta');
	assert.ok(Array.isArray(result));
	assert.equal(result.length, 1);
	assert.equal(result[0].kind, 'delta');
	assert.equal(result[0].metric, base.metric);
	assert.equal(result[0].threshold, base.threshold);
	// F002: pair_id darf bei mode=delta (aus single-mode) nicht gesetzt sein.
	// delta_window kommt aus Default-Param ('6h'), wenn nicht uebergeben.
	assert.equal(result[0].pair_id, undefined, 'Delta-Rule aus mode=delta darf kein pair_id haben');
	assert.equal(result[0].delta_window, '6h', 'Delta-Rule muss delta_window aus Default-Param haben');
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

// =============================================================================
// Issue #297 — ZWEI Threshold-Felder bei mode='both'
// =============================================================================
// Diese Tests sind TDD RED — sie schlagen fehl bis expandRules() die neue
// Signatur (base, mode, absThreshold, deltaThreshold, deltaWindow) erhält.

test('expandRules #297 > mode=both → zwei Rules mit gleicher pair_id (AC-5)', () => {
	const base = newDefaultRule(); // wind_gust — nicht delta-only
	// Neue Signatur: expandRules(base, mode, absThreshold, deltaThreshold, deltaWindow)
	const result = expandRules(base, 'both', 80, 30, '3h');
	assert.equal(result.length, 2, 'mode=both muss 2 Rules erzeugen');
	// Beide Rules müssen dasselbe pair_id tragen
	assert.ok(result[0].pair_id, 'Erste Rule muss pair_id haben');
	assert.ok(result[1].pair_id, 'Zweite Rule muss pair_id haben');
	assert.equal(result[0].pair_id, result[1].pair_id, 'Beide pair_ids müssen identisch sein');
});

test('expandRules #297 > mode=both → korrekte absThreshold / deltaThreshold (AC-6)', () => {
	const base = newDefaultRule();
	const result = expandRules(base, 'both', 80, 30, '6h');
	assert.equal(result.length, 2);
	assert.equal(result[0].kind, 'absolute');
	assert.equal(result[0].threshold, 80, 'Erste Rule muss absThreshold=80 haben');
	assert.equal(result[1].kind, 'delta');
	assert.equal(result[1].threshold, 30, 'Zweite Rule muss deltaThreshold=30 haben');
});

test('expandRules #297 > mode=both → delta-Rule trägt delta_window (AC-7)', () => {
	const base = newDefaultRule();
	const result = expandRules(base, 'both', 80, 30, '3h');
	const deltaRule = result.find((r) => r.kind === 'delta');
	assert.ok(deltaRule, 'Delta-Rule muss existieren');
	assert.equal(deltaRule!.delta_window, '3h', 'delta_window muss aus Parameter kommen');
	const absRule = result.find((r) => r.kind === 'absolute');
	assert.ok(absRule, 'Absolute-Rule muss existieren');
	assert.equal(absRule!.delta_window, undefined, 'Absolute-Rule darf kein delta_window haben');
});

test('expandRules #297 > mode=both + delta-only Metrik → nur delta, kein pair_id (AC-8)', () => {
	const base: AlertRule = { ...newDefaultRule(), metric: 'temperature_change' };
	const result = expandRules(base, 'both', 80, 5, '6h');
	assert.equal(result.length, 1, 'delta-only Metrik muss nur 1 Rule erzeugen');
	assert.equal(result[0].kind, 'delta');
	// Bei delta-only kein pair_id (nur ein Objekt im Paar)
	assert.ok(!result[0].pair_id, 'delta-only Rule bei mode=both darf kein pair_id haben');
});
