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
	thunderLevelLabel,
	normalizeAlertMetric,
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

// =============================================================================
// Bug #317 — normalizeAlertMetric(): Legacy-Metrik-IDs normalisieren
// Spec: docs/specs/modules/bug_317_alert_rules_editor_metrics.md
// =============================================================================

test('normalizeAlertMetric: aktuelle ID "precipitation_sum" → gibt sich selbst zurück (AC-5)', () => {
	assert.equal(normalizeAlertMetric('precipitation_sum'), 'precipitation_sum');
});

test('normalizeAlertMetric: Legacy-ID "precipitation" → "precipitation_sum" (AC-1)', () => {
	assert.equal(normalizeAlertMetric('precipitation'), 'precipitation_sum');
});

test('normalizeAlertMetric: Legacy-ID "thunder" → "thunder_level" (AC-2)', () => {
	assert.equal(normalizeAlertMetric('thunder'), 'thunder_level');
});

// Issue #959: Nullgradgrenze konsolidiert — snowfall_limit löst seit b65f22a0
// auf freezing_level auf (nicht mehr snow_line).
test('normalizeAlertMetric: Legacy-ID "snowfall_limit" → "freezing_level" (AC-3)', () => {
	assert.equal(normalizeAlertMetric('snowfall_limit'), 'freezing_level');
});

test('normalizeAlertMetric: vollständig unbekannte ID "foobar" → undefined (AC-4)', () => {
	assert.equal(normalizeAlertMetric('foobar'), undefined);
});

test('normalizeAlertMetric: alle 9 aktuellen AlertMetric-IDs werden unverändert zurückgegeben (AC-5 Vollabdeckung)', () => {
	const current = [
		'wind_gust', 'precipitation_sum', 'temperature_min', 'temperature_max',
		'thunder_level', 'snow_line', 'temperature_change', 'wind_change', 'precipitation_change',
	];
	for (const id of current) {
		assert.equal(normalizeAlertMetric(id), id, `${id} wurde unerwartet verändert`);
	}
});

test('normalizeAlertMetric: Normalisierung aller 3 Legacy-IDs aus dem Validator-Trip (AC-6)', () => {
	const legacyRules = [
		{ metric: 'precipitation' },
		{ metric: 'thunder' },
		{ metric: 'snowfall_limit' },
	];
	const normalized = legacyRules.map(r => ({
		...r,
		metric: normalizeAlertMetric(r.metric) ?? r.metric,
	}));
	assert.equal(normalized[0].metric, 'precipitation_sum');
	assert.equal(normalized[1].metric, 'thunder_level');
	assert.equal(normalized[2].metric, 'freezing_level');
});
