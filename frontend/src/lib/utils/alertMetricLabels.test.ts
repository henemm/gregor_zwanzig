// Unit-Tests fuer Issue #222 Workflow 2 Fix-Loop 2: alertMetricLabels.
//
// Deckt AC-6 (HOCH/critical/danger) und die uebrigen Severity/Metric-Mappings ab.
// Spec: docs/specs/modules/issue_222_w2_frontend_alert_konfigurator.md
//
// Ausfuehrung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/utils/alertMetricLabels.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
	ALERT_METRIC_LABELS,
	ALERT_SEVERITY_TONE,
	thunderLevelLabel
} from './alertMetricLabels.ts';

test('thunderLevelLabel: threshold 2.0 → HOCH (AC-6)', () => {
	assert.equal(thunderLevelLabel(2.0), 'HOCH');
});

test('thunderLevelLabel: threshold 1.0 → MITTEL', () => {
	assert.equal(thunderLevelLabel(1.0), 'MITTEL');
});

test('thunderLevelLabel: threshold 0.5 → KEINE (sub-MITTEL)', () => {
	assert.equal(thunderLevelLabel(0.5), 'KEINE');
});

test('ALERT_SEVERITY_TONE: critical → danger (AC-6)', () => {
	assert.equal(ALERT_SEVERITY_TONE['critical'], 'danger');
});

test('ALERT_SEVERITY_TONE: warning → warning', () => {
	assert.equal(ALERT_SEVERITY_TONE['warning'], 'warning');
});

test('ALERT_SEVERITY_TONE: info → info', () => {
	assert.equal(ALERT_SEVERITY_TONE['info'], 'info');
});

test('ALERT_METRIC_LABELS: thunder_level hat comparison ≥', () => {
	assert.equal(ALERT_METRIC_LABELS['thunder_level'].comparison, '≥');
});

test('ALERT_METRIC_LABELS: wind_gust hat unit km/h und comparison >', () => {
	assert.equal(ALERT_METRIC_LABELS['wind_gust'].unit, 'km/h');
	assert.equal(ALERT_METRIC_LABELS['wind_gust'].comparison, '>');
});
