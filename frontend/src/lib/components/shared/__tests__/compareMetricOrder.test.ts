// RED (Issue #1359, Scheibe 1) — der Reihenfolge-Abschnitt muss auch im
// Vergleich-Kontext sichtbar sein (Spec: compare_metric_order.md, AC-1/AC-9).
import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { weatherMetricsTabSections } from '../weather-metrics-tab/weatherMetricsTabSections.ts';
import {
	toggleCompareMetricKey,
	materializeActiveMetricKeys,
	toggleCompareMetricKeyFromState
} from '../weather-metrics-tab/compareMetricOrder.ts';
import { flushPendingWeatherMetricsSave } from '../weather-metrics-tab/weatherMetricsCompareSave.ts';
import { COMPARE_METRIC_KEYS } from '../corridor-editor/corridorEditorState.ts';
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

	test('AC-9: route-Kontext (Regressionsschutz Trip, seit #1361/#1372 S1b mit tagesfenster)', () => {
		const sections = weatherMetricsTabSections('route');
		assert.deepEqual(sections, [
			'grundauswahl',
			'reihenfolge',
			'tagesfenster',
			'sms_schwellen',
			// Issue #1357: Auswertungswahl fuer die Mail-Kachelzeile — route-only,
			// der Ortsvergleich zieht mit #1411 nach (Spec AC-9).
			'auswertungen',
			'report_config',
			// Issue #1720 S1: 'ausblick' kommt DAZU — der Trip bekommt die
			// Spaltenauswahl der 3-Tages-Vorschau (dasselbe geteilte Bauteil wie
			// der Ortsvergleich). Diese Erwartung fror das Fehlen des Abschnitts
			// fest; sie dreht sich um, weil `display_config.outlook_metrics` jetzt
			// auch im Trip echte Mail-Wirkung hat (HTML- und Klartext-Ausblick).
			// Spec: docs/specs/modules/feat_1720_s1_trip_ausblick_metriken.md
			'ausblick',
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

// Issue #1366 F002 (symmetrisch zu F001/CompareHourlyLayoutControls): echter
// Bedienpfad ueber toggleCompareMetricKeyFromState -- genau die Funktion, die
// WeatherMetricsTab.svelte fuer den Checkbox-Handler aufruft. Ein isolierter
// toggleCompareMetricKey([], ...)-Aufruf haette den F002-Regress nicht
// gefangen (Adversary-Dialog Runde 2).
describe('toggleCompareMetricKeyFromState — echter Bedienpfad (Issue #1366 F002)', () => {
	test('Bestandsvergleich ohne gespeicherte Auswahl (null), eine Groesse abwaehlen -> Vorgabemenge minus eine', () => {
		const [first] = COMPARE_METRIC_KEYS;
		const result = toggleCompareMetricKeyFromState(null, first);
		assert.deepEqual(
			result,
			COMPARE_METRIC_KEYS.filter((k) => k !== first),
			'F002-Regression: eine einzelne Abwahl aus "nie eingestellt" darf nicht in eine leere Liste kippen'
		);
		assert.equal(result.length, COMPARE_METRIC_KEYS.length - 1);
	});

	test('bewusste Leerauswahl ([]), eine Groesse anhaken -> genau diese eine', () => {
		const result = toggleCompareMetricKeyFromState([], 'temp_max_c');
		assert.deepEqual(result, ['temp_max_c']);
	});

	test('materializeActiveMetricKeys: null -> Vorgabemenge, [] bleibt leer', () => {
		assert.deepEqual(materializeActiveMetricKeys(null), COMPARE_METRIC_KEYS);
		assert.deepEqual(materializeActiveMetricKeys([]), []);
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
			{
				activeMetricKeys: ['wind_max_kmh', 'temp_max_c'],
				// Issue #1703 S8: kein Kanal je editiert (dieser Test prueft die
				// GRUNDauswahl-Reihenfolge) — alle drei folgen ihr.
				channelActiveMetricKeys: { email: null, telegram: null, sms: null },
				officialAlertsEnabled: true,
				dayWindowStartHour: 4,
				dayWindowEndHour: 19
			},
			{
				activeMetricKeys: ['temp_max_c', 'wind_max_kmh'],
				channelActiveMetricKeys: { email: null, telegram: null, sms: null },
				officialAlertsEnabled: true,
				dayWindowStartHour: 4,
				dayWindowEndHour: 19
			}
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
			channelActiveMetricKeys: { email: null, telegram: null, sms: null },
			officialAlertsEnabled: true,
			dayWindowStartHour: 4,
			dayWindowEndHour: 19
		};
		assert.equal(
			flushPendingWeatherMetricsSave(preset, { ...snapshot }, { ...snapshot }),
			null,
			'AC-3 FAIL: ohne Unterschied darf kein Schreibvorgang entstehen'
		);
	});
});
