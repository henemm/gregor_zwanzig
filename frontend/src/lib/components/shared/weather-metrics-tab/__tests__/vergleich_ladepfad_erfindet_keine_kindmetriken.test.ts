// TDD — Bug #2454 AC-5: der ECHTE Ortsvergleich-Ladepfad erfindet keine
// Trip-Kind-Metriken (wind_chill_day_low/_day_high/_night,
// temperature_day_low/_day_high/_night), wenn er mit einer Auswahl
// gefuettert wird, die "wind_chill" enthaelt.
//
// Spec: docs/specs/bugfix/bug_2454_kurzform_gefuehlte_temperatur.md AC-5.
//
// Kein Quelltext-Grep: dieser Test ruft die ECHTEN Bausteine auf, die
// WeatherMetricsTab.svelte im context="vergleich"-Zweig tatsaechlich nutzt --
// `rehydrateActiveMetrics()` (Laden, compareEditorLoad.ts, ruft intern
// `normalizeStoredActiveMetrics()` aus compareMetricSelection.ts),
// `materializeActiveMetricKeys()`/`toggleCompareMetricKeyFromState()`
// (Anzeige/Umschalten, compareMetricOrder.ts, s. WeatherMetricsTab.svelte
// Zeilen ~1180-1209) und `toStoredActiveMetrics()` (Speichern,
// compareMetricSelection.ts). `deriveMissingChildMetrics()`/
// `moveWithDerivedChildren()` (metricsEditor.ts) werden aus KEINEM dieser
// Bausteine aufgerufen -- Spec Abschnitt 3.
//
// Fixture 1:1 aus src/output/renderers/compare_metric_catalog.py (Zeilen
// 129-168): die wind_chill/temperature-Eintraege des Ortsvergleichs tragen
// `metric_id: "wind_chill"`/`"temperature"` UND (fuer wind_chill)
// `kuerzel_metric_id` in Form von ZWEI der sechs Trip-Kind-IDs
// (`wind_chill_day_low`/`wind_chill_day_high`) -- eine realistische
// Kollisionsgefahr, kein Strohmann: ein Aufruf von `deriveMissingChildMetrics()`
// gegen die gespeicherte Compare-Auswahl (Objekte mit `metric_id: "wind_chill"`)
// wuerde die sechs Trip-Kind-IDs tatsaechlich erfinden, wenn er stattfaende.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/shared/weather-metrics-tab/__tests__/vergleich_ladepfad_erfindet_keine_kindmetriken.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { rehydrateActiveMetrics } from '../../../compare/compareEditorLoad.ts';
import {
	materializeActiveMetricKeys,
	toggleCompareMetricKeyFromState,
} from '../compareMetricOrder.ts';
import { toStoredActiveMetrics, type CompareSelectionEntry } from '../compareMetricSelection.ts';

// 1:1 aus src/output/renderers/compare_metric_catalog.py (Zeilen 129-168):
// Temperatur + Gefuehlte-Temperatur, je zwei Eintraege (min/max), beide mit
// derselben metric_id wie im Trip-Katalog ("temperature"/"wind_chill").
const CATALOG: CompareSelectionEntry[] = [
	{ metric: 'temp_max_c', label: 'Temperatur', metric_id: 'temperature', aggregation: 'max' },
	{ metric: 'temp_min_c', label: 'Temperatur', metric_id: 'temperature', aggregation: 'min' },
	{
		metric: 'wind_chill_min_c', label: 'Gefühlte Temperatur',
		metric_id: 'wind_chill', aggregation: 'min', kuerzel_metric_id: 'wind_chill_day_low',
	},
	{
		metric: 'wind_chill_max_c', label: 'Gefühlte Temperatur',
		metric_id: 'wind_chill', aggregation: 'max', kuerzel_metric_id: 'wind_chill_day_high',
	},
];

const TRIP_KIND_IDS = [
	'wind_chill_day_low', 'wind_chill_day_high', 'wind_chill_night',
	'temperature_day_low', 'temperature_day_high', 'temperature_night',
];

function assertKeineTripKindIds(werte: ReadonlyArray<unknown>, ort: string) {
	for (const id of TRIP_KIND_IDS) {
		assert.ok(
			!werte.includes(id),
			`AC-5: ${ort} enthaelt ${id} -- der echte Ortsvergleichs-Ladepfad darf keine ` +
			`Trip-Kind-Metrik erfinden.\n${ort}: ${JSON.stringify(werte)}`,
		);
	}
}

describe('AC-5: der echte Ortsvergleich-Ladepfad erfindet keine Trip-Kind-Metriken', () => {
	test('rehydrateActiveMetrics (Laden) einer gespeicherten wind_chill-Auswahl liefert keine Trip-Kind-IDs', () => {
		// Neuformat, wie #1373 es speichert (S2 Scheibe B).
		const stored = [
			{ metric_id: 'wind_chill', aggregation: 'min' },
			{ metric_id: 'wind_chill', aggregation: 'max' },
		];
		const rehydriert = rehydrateActiveMetrics(stored, CATALOG);
		assert.ok(rehydriert, 'Vorbedingung: ein vorhandenes Array wird rehydriert (#1191)');
		assert.deepEqual(rehydriert!.activeMetricKeys, ['wind_chill_min_c', 'wind_chill_max_c']);
		assertKeineTripKindIds(rehydriert!.activeMetricKeys, 'activeMetricKeys nach dem Laden');
	});

	test('materializeActiveMetricKeys (Anzeige) + toggleCompareMetricKeyFromState (Umschalten) erfinden keine Trip-Kind-IDs', () => {
		const geladen = ['wind_chill_min_c'];
		const angezeigt = materializeActiveMetricKeys(geladen);
		assertKeineTripKindIds(angezeigt, 'materialisierte Anzeige');

		// Nutzer waehlt zusaetzlich wind_chill_max_c an -- derselbe Umschalt-Pfad
		// wie toggleCompareMetric() in WeatherMetricsTab.svelte.
		const nachToggle = toggleCompareMetricKeyFromState(geladen, 'wind_chill_max_c');
		assert.deepEqual(nachToggle, ['wind_chill_min_c', 'wind_chill_max_c']);
		assertKeineTripKindIds(nachToggle, 'Auswahl nach Umschalten');
	});

	test('toStoredActiveMetrics (Speichern) einer wind_chill-Auswahl erfindet keine Trip-Kind-IDs', () => {
		const auswahl = ['wind_chill_min_c', 'wind_chill_max_c', 'temp_max_c'];
		const payload = toStoredActiveMetrics(auswahl, CATALOG);

		assert.deepEqual(payload, [
			{ metric_id: 'wind_chill', aggregation: 'min' },
			{ metric_id: 'wind_chill', aggregation: 'max' },
			{ metric_id: 'temperature', aggregation: 'max' },
		]);
		const metricIds = payload.map((p) => (typeof p === 'string' ? p : p.metric_id));
		assertKeineTripKindIds(metricIds, 'gespeicherte Payload (metric_id-Werte)');
	});
});
