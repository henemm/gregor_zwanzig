// Unit-Tests fuer Issue #223 — newDefaultRule() Helper.
//
// Spec: docs/specs/modules/issue_223_alert_rules_editor.md (Section 2)
//
// Ausfuehrung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/alert-rules-editor/alertRuleDefaults.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import { newDefaultRule } from './alertRuleDefaults.ts';

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
