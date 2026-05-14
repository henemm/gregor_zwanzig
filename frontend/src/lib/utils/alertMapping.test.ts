// Unit-Tests fuer Issue #222 Workflow 2: mapBriefingsToAlertRules.
//
// Pure function: Wizard.briefings.thresholds → AlertRule[].
// Spec: docs/specs/modules/issue_222_w2_frontend_alert_konfigurator.md
//
// Ausfuehrung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/utils/alertMapping.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import { mapBriefingsToAlertRules } from './alertMapping.ts';

const empty = {
	gust_kmh: null,
	precip_mm: null,
	thunder_level: null,
	snow_line_m: null
};

test('mapBriefingsToAlertRules: alle null → leeres Array (AC-3)', () => {
	const rules = mapBriefingsToAlertRules(empty);
	assert.deepEqual(rules, []);
});

test('mapBriefingsToAlertRules: thunder_level=NONE → keine Rule', () => {
	const rules = mapBriefingsToAlertRules({ ...empty, thunder_level: 'NONE' });
	assert.deepEqual(rules, []);
});

test('mapBriefingsToAlertRules: nur gust_kmh=50 → eine wind_gust-Rule (AC-1)', () => {
	const rules = mapBriefingsToAlertRules({ ...empty, gust_kmh: 50 });
	assert.equal(rules.length, 1);
	const r = rules[0];
	assert.equal(r.kind, 'absolute');
	assert.equal(r.metric, 'wind_gust');
	assert.equal(r.threshold, 50);
	assert.equal(r.unit, 'km/h');
	assert.equal(r.severity, 'warning');
	assert.equal(r.enabled, true);
	assert.ok(typeof r.id === 'string' && r.id.length > 0);
});

test('mapBriefingsToAlertRules: nur precip_mm=20 → precipitation_sum-Rule', () => {
	const rules = mapBriefingsToAlertRules({ ...empty, precip_mm: 20 });
	assert.equal(rules.length, 1);
	assert.equal(rules[0].metric, 'precipitation_sum');
	assert.equal(rules[0].threshold, 20);
	assert.equal(rules[0].unit, 'mm');
});

test('mapBriefingsToAlertRules: thunder_level=MED → threshold=1.0', () => {
	const rules = mapBriefingsToAlertRules({ ...empty, thunder_level: 'MED' });
	assert.equal(rules.length, 1);
	assert.equal(rules[0].metric, 'thunder_level');
	assert.equal(rules[0].threshold, 1.0);
	assert.equal(rules[0].unit, '');
});

test('mapBriefingsToAlertRules: thunder_level=HIGH → threshold=2.0', () => {
	const rules = mapBriefingsToAlertRules({ ...empty, thunder_level: 'HIGH' });
	assert.equal(rules.length, 1);
	assert.equal(rules[0].metric, 'thunder_level');
	assert.equal(rules[0].threshold, 2.0);
});

test('mapBriefingsToAlertRules: nur snow_line_m=2500 → snow_line-Rule', () => {
	const rules = mapBriefingsToAlertRules({ ...empty, snow_line_m: 2500 });
	assert.equal(rules.length, 1);
	assert.equal(rules[0].metric, 'snow_line');
	assert.equal(rules[0].threshold, 2500);
	assert.equal(rules[0].unit, 'm');
});

test('mapBriefingsToAlertRules: alle vier gesetzt → vier Rules in der Reihenfolge wind/precip/thunder/snow (AC-2)', () => {
	const rules = mapBriefingsToAlertRules({
		gust_kmh: 50,
		precip_mm: 20,
		thunder_level: 'MED',
		snow_line_m: 2500
	});
	assert.equal(rules.length, 4);
	assert.equal(rules[0].metric, 'wind_gust');
	assert.equal(rules[1].metric, 'precipitation_sum');
	assert.equal(rules[2].metric, 'thunder_level');
	assert.equal(rules[2].threshold, 1.0);
	assert.equal(rules[3].metric, 'snow_line');
	// Alle haben severity=warning und enabled=true (Wizard-Default)
	for (const r of rules) {
		assert.equal(r.severity, 'warning');
		assert.equal(r.enabled, true);
		assert.equal(r.kind, 'absolute');
	}
});

test('mapBriefingsToAlertRules: gust_kmh=0 → keine Rule (Edge Case F003)', () => {
	const rules = mapBriefingsToAlertRules({ ...empty, gust_kmh: 0 });
	assert.deepEqual(rules, []);
});

test('mapBriefingsToAlertRules: IDs sind eindeutig pro Aufruf', () => {
	const rules = mapBriefingsToAlertRules({
		gust_kmh: 50,
		precip_mm: 20,
		thunder_level: 'HIGH',
		snow_line_m: 2500
	});
	const ids = new Set(rules.map((r) => r.id));
	assert.equal(ids.size, 4);
});
