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
	normalizeAlertMetric,
} from './alertMetricLabels.ts';
import type { AlertMetric } from '$lib/types';

// #1488 Scheibe A: die drei `thunderLevelLabel`-Faelle sind entfallen — sie
// zementierten die falschen Stufenwoerter MITTEL/HOCH; die Funktion selbst ist
// mit dem Absolut-Modus fuer Gewitter geloescht worden.

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
// #1401 Scheibe B, Teil 2 — AC-3/AC-4: die Alarm-Beschriftungen folgen dem
// zentralen Metrik-Register (src/app/metric_catalog.py, label_de).
// Spec: docs/specs/modules/fix_1401b_register_stundenverlauf_alarme.md
// =============================================================================

// AC-3: sichtbare Aenderung — bisher "CAPE" (blosses Kuerzel), jetzt der
// Register-Wortlaut (metric_catalog.py:273).
test('#1401b AC-3: cape heisst "Gewitterenergie (CAPE)" wie im Register', () => {
	assert.equal(ALERT_METRIC_LABELS['cape'].label_de, 'Gewitterenergie (CAPE)');
});

// AC-3 Regressionsschutz: die uebrigen 8 Metriken mit 1:1-Register-Entsprechung
// stimmten schon vorher ueberein und duerfen sich NICHT mitverschieben.
test('#1401b AC-3: die 8 uebrigen 1:1-Metriken bleiben unveraendert', () => {
	const unchanged: Partial<Record<AlertMetric, string>> = {
		wind_gust: 'Böen',                  // metric_catalog.py:175 (gust)
		precipitation_sum: 'Niederschlag',  // :210 (precipitation)
		thunder_level: 'Gewitter',          // :256 (thunder)
		snow_line: 'Schneefallgrenze',      // :297 (snowfall_limit)
		visibility: 'Sichtweite',           // :384
		humidity: 'Luftfeuchtigkeit',       // :132
		freezing_level: 'Nullgradgrenze',   // :457
		fresh_snow: 'Neuschnee',            // :480
	};
	for (const [metric, label] of Object.entries(unchanged)) {
		assert.equal(
			ALERT_METRIC_LABELS[metric as AlertMetric].label_de,
			label,
			`${metric} unerwartet geaendert`
		);
	}
});

// AC-4: sichtbare Aenderung — beide Temperatur-Auswertungen tragen jetzt den
// Register-Namen der Groesse ("Temperatur", :78) plus die Auswertung als
// festen Zusatz. Vorher: "Tiefsttemperatur" / "Höchsttemperatur".
test('#1401b AC-4: temperature_min/max heissen "Temperatur (Minimum)"/"(Maximum)"', () => {
	assert.equal(ALERT_METRIC_LABELS['temperature_min'].label_de, 'Temperatur (Minimum)');
	assert.equal(ALERT_METRIC_LABELS['temperature_max'].label_de, 'Temperatur (Maximum)');
});

test('#1401b AC-4: beide Temperatur-Zeilen bleiben unterscheidbar (kein Doppeltext)', () => {
	assert.notEqual(
		ALERT_METRIC_LABELS['temperature_min'].label_de,
		ALERT_METRIC_LABELS['temperature_max'].label_de
	);
});

// Einheit/Vergleichsoperator sind KEINE Register-Felder und bleiben lokal.
test('#1401b: Einheit und Vergleichsoperator der geaenderten Eintraege bleiben', () => {
	assert.equal(ALERT_METRIC_LABELS['cape'].unit, 'J/kg');
	assert.equal(ALERT_METRIC_LABELS['temperature_min'].comparison, '<');
	assert.equal(ALERT_METRIC_LABELS['temperature_max'].comparison, '>');
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
