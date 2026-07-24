// RED (Issue #1359, Scheibe 1) — der Reihenfolge-Abschnitt muss auch im
// Vergleich-Kontext sichtbar sein (Spec: compare_metric_order.md, AC-1/AC-9).
import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { weatherMetricsTabSections } from '../weather-metrics-tab/weatherMetricsTabSections.ts';
import { toggleCompareMetricKey } from '../weather-metrics-tab/compareMetricOrder.ts';
import { flushPendingWeatherMetricsSave } from '../weather-metrics-tab/weatherMetricsCompareSave.ts';
import type { ComparePreset } from '../../../types.ts';

describe('Issue #1359 Scheibe 1: Reihenfolge-Abschnitt im Vergleich', () => {
	test('AC-1: vergleich zeigt den geteilten Reihenfolge-Abschnitt', () => {
		const sections = weatherMetricsTabSections('vergleich');
		assert.ok(
			sections.includes('reihenfolge'),
			`AC-1 FAIL: "reihenfolge" fehlt im vergleich-Kontext — Ist: ${JSON.stringify(sections)}`
		);
	});

	test('AC-1: sms_schwellen/report_config bleiben route-exklusiv', () => {
		const sections = weatherMetricsTabSections('vergleich');
		for (const s of ['sms_schwellen', 'report_config']) {
			assert.ok(
				!sections.includes(s),
				`AC-1 FAIL: "${s}" hat im Vergleich keine Mail-Wirkung (Attrappen-Verbot) — Ist: ${JSON.stringify(sections)}`
			);
		}
	});

	test('AC-9: route-Kontext bleibt unveraendert (Regressionsschutz Trip)', () => {
		const sections = weatherMetricsTabSections('route');
		assert.deepEqual(sections, [
			'grundauswahl',
			'reihenfolge',
			'sms_schwellen',
			'report_config',
			'official_alerts'
		]);
	});
});

// AC-2: abwaehlen + wieder anwaehlen darf die Reihenfolge der UEBRIGEN
// Metriken nicht anruehren. Vorher baute `toggleCompareMetric` die Liste ueber
// ein `Set` neu auf — genau der Grund, warum die Reihenfolge im Vergleich
// bisher als Nebenwirkung der Klick-Historie entstand.
describe('Issue #1359 Scheibe 1: An-/Abwaehlen erhaelt die Reihenfolge (AC-2)', () => {
	const ORDER = ['cloud_avg_pct', 'temp_max_c', 'sunny_hours_h', 'wind_max_kmh'];

	test('AC-2: Abwaehlen entfernt NUR die eine Metrik, Rest behaelt seine Folge', () => {
		const after = toggleCompareMetricKey(ORDER, 'sunny_hours_h');
		assert.deepEqual(after, ['cloud_avg_pct', 'temp_max_c', 'wind_max_kmh']);
	});

	test('AC-2: Wiederanwaehlen haengt ans Ende an — uebrige Reihenfolge unveraendert', () => {
		const removed = toggleCompareMetricKey(ORDER, 'temp_max_c');
		const readded = toggleCompareMetricKey(removed, 'temp_max_c');
		assert.deepEqual(
			readded.filter((m) => m !== 'temp_max_c'),
			['cloud_avg_pct', 'sunny_hours_h', 'wind_max_kmh'],
			'AC-2 FAIL: die uebrigen Metriken haben ihre relative Reihenfolge verloren'
		);
		assert.equal(readded[readded.length - 1], 'temp_max_c');
	});

	test('AC-2: reine Funktion — die Eingabeliste wird nie mutiert', () => {
		const input = [...ORDER];
		toggleCompareMetricKey(input, 'temp_max_c');
		assert.deepEqual(input, ORDER);
	});
});

// AC-3 (Kern-Anteil): der Diff-Guard vor dem PUT muss eine REINE Umsortierung
// als Aenderung erkennen. Vorher normalisierte er mit `.sort()` — gleiche
// Menge in anderer Reihenfolge galt als identisch, `flushPendingWeatherMetrics
// Save` lieferte `null`, es wurde nie gespeichert. Das ist der versteckte
// Blocker, an dem der ganze Fix sonst unsichtbar scheitert.
describe('Issue #1359 Scheibe 1: Diff-Guard erkennt reine Umsortierung (AC-3)', () => {
	const preset = { id: 'p-1359', display_config: {} } as unknown as ComparePreset;

	test('AC-3: nur umsortiert -> Speicher-Payload mit der NEUEN Reihenfolge', () => {
		const payload = flushPendingWeatherMetricsSave(
			preset,
			{ activeMetricKeys: ['wind_max_kmh', 'temp_max_c'], officialAlertsEnabled: true },
			{ activeMetricKeys: ['temp_max_c', 'wind_max_kmh'], officialAlertsEnabled: true }
		);
		assert.ok(payload, 'AC-3 FAIL: reine Umsortierung wurde als "keine Aenderung" verworfen');
		assert.deepEqual(payload!.body.display_config?.active_metrics, [
			'wind_max_kmh',
			'temp_max_c'
		]);
	});

	test('AC-3: unveraenderte Reihenfolge schreibt weiterhin NICHT', () => {
		const snapshot = {
			activeMetricKeys: ['temp_max_c', 'wind_max_kmh'],
			officialAlertsEnabled: true
		};
		assert.equal(
			flushPendingWeatherMetricsSave(preset, { ...snapshot }, { ...snapshot }),
			null,
			'AC-3 FAIL: ohne Unterschied darf kein Schreibvorgang entstehen'
		);
	});
});
