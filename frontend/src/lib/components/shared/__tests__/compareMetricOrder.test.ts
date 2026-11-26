// RED (Issue #1359, Scheibe 1) — der Reihenfolge-Abschnitt muss auch im
// Vergleich-Kontext sichtbar sein (Spec: compare_metric_order.md, AC-1/AC-9).
import { test, describe, before } from 'node:test';
import assert from 'node:assert/strict';
import {
	toggleCompareMetricKey,
	materializeActiveMetricKeys,
	toggleCompareMetricKeyFromState
} from '../weather-metrics-tab/compareMetricOrder.ts';
import { getCompareDefaultOrder, loadCompareMetricCatalog } from '../wetter-tab/compareMetricCatalogLoader.ts';
import { endpointFetch } from '../wetter-tab/__tests__/compareDefaultOrder2989Daten.ts';

// #2989: die Vorgabemenge ist die Standardfolge `default_order` der Katalog-Antwort,
// befuellt ueber den echten Lader (fetch-Stub an der Netzgrenze, echte Endpoint-Antwort).
let STANDARD: string[] = [];
before(async () => {
	const zurueck = endpointFetch();
	try {
		await loadCompareMetricCatalog();
	} finally {
		zurueck();
	}
	STANDARD = getCompareDefaultOrder() ?? [];
	assert.ok(STANDARD.length > 0, 'Standardfolge nicht geladen');
});

// #3297/#3020: Abschnittsfaelle von weatherMetricsTabSections entfallen — Datei geloescht.

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
		const [first] = STANDARD;
		const result = toggleCompareMetricKeyFromState(null, first);
		assert.deepEqual(
			result,
			STANDARD.filter((k) => k !== first),
			'F002-Regression: eine einzelne Abwahl aus "nie eingestellt" darf nicht in eine leere Liste kippen'
		);
		assert.equal(result.length, STANDARD.length - 1);
	});

	test('bewusste Leerauswahl ([]), eine Groesse anhaken -> genau diese eine', () => {
		const result = toggleCompareMetricKeyFromState([], 'temp_max_c');
		assert.deepEqual(result, ['temp_max_c']);
	});

	test('materializeActiveMetricKeys: null -> Vorgabemenge, [] bleibt leer', () => {
		assert.deepEqual(materializeActiveMetricKeys(null), STANDARD);
		assert.deepEqual(materializeActiveMetricKeys([]), []);
	});
});

// AC-3 (Kern-Anteil, Diff-Guard `flushPendingWeatherMetricsSave`) entfaellt mit #3276 (F005):
// die Funktion hatte keinen Produktions-Aufrufer mehr.
