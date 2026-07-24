// TDD RED — Issue #1350 Teil 3 (compare_metric_ssot_final): der Schwellen-
// Editor des Ortsvergleichs bezieht seine CompareMetricDef-Objekte künftig
// aus GET /api/compare/metrics (via buildCompareMetricDefs()) statt aus dem
// statischen Modul-Import COMPARE_METRIC_DEFS (corridorEditorState.ts:273-289,
// ALL_METRICS aus compareMetricDefs.ts).
//
// Spec: docs/specs/modules/compare_metric_ssot_final.md § AC-1, AC-2
// Kontext: docs/context/fix-1350-compare-metric-ssot-final.md
//
// Die Naht `compareMetricCatalogLoader.ts::buildCompareMetricDefs()` existiert
// in RED noch nicht. Analog dem existsSync/dynamischen-Import-Muster in
// shared/weather-metrics-tab/__tests__/compareMetricSelection.test.ts (Teil 2)
// wird der Modul-Existenz-Test bewusst sprechend rot gemacht statt den Runner
// mit einem rohen ENOENT abzubrechen.
//
// Ausführung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/corridor-editor/__tests__/compareMetricCatalogParity.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join, dirname } from 'node:path';

const MODULE_FILE = join(
	dirname(fileURLToPath(import.meta.url)),
	'..',
	'compareMetricCatalogLoader.ts'
);
const MODULE_SPECIFIER = '../compareMetricCatalogLoader.ts';

// Endpoint-Antwort-Fixture: 25 Einträge 1:1 aus
// src/output/renderers/compare_metric_catalog.py::COMPARE_METRIC_CATALOG,
// ergänzt um das künftige Feld `alarmCapable` (AC-3, D1 Hybrid) — `true` für
// genau die 10 Keys aus compare_alert.py::_SUMMARY_KEY_TO_CATALOG_ID
// (temp_max_c, temp_min_c, wind_max_kmh, gust_max_kmh, precip_sum_mm,
// thunder_level_max, visibility_min_m, snow_new_sum_cm, cape_max_jkg,
// freezing_level_m), sonst `false`. Reihenfolge = ALL_METRICS-Reihenfolge.
const ENDPOINT_FIXTURE = {
	metrics: [
		{ key: 'snow_depth_cm', label: 'Schneehöhe', unit: 'cm', decimals: 0, higherIsBetter: true, kind: 'range', rangeMin: 0, rangeMax: 200, step: 5, alarmCapable: false },
		{ key: 'snow_new_sum_cm', label: 'Neuschnee', unit: 'cm', decimals: 0, higherIsBetter: true, kind: 'range', rangeMin: 0, rangeMax: 50, step: 1, alarmCapable: true },
		{ key: 'sunny_hours_h', label: 'Sonnenstunden', unit: 'h', decimals: 1, higherIsBetter: true, kind: 'range', rangeMin: 0, rangeMax: 12, step: 0.5, alarmCapable: false },
		{ key: 'wind_max_kmh', label: 'Windspitzen', unit: 'km/h', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 100, step: 5, alarmCapable: true },
		{ key: 'cloud_avg_pct', label: 'Bewölkung Ø', unit: '%', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 100, step: 5, alarmCapable: false },
		{ key: 'visibility_min_m', label: 'Sichtweite min', unit: 'm', decimals: 0, higherIsBetter: true, kind: 'range', rangeMin: 0, rangeMax: 10000, step: 500, alarmCapable: true },
		{ key: 'precip_sum_mm', label: 'Niederschlag', unit: 'mm', decimals: 1, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 30, step: 0.5, alarmCapable: true },
		{ key: 'uv_index_max', label: 'UV-Index max', unit: '', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 12, step: 1, alarmCapable: false },
		{ key: 'temp_max_c', label: 'Temperatur max', unit: '°C', decimals: 0, higherIsBetter: true, kind: 'range', rangeMin: -20, rangeMax: 45, step: 1, alarmCapable: true },
		{ key: 'thunder_level_max', label: 'Gewitter', unit: '', decimals: 0, higherIsBetter: false, kind: 'ordinal', ordinalLabels: ['kein', 'mittel', 'hoch'], alarmCapable: true },
		{ key: 'temp_min_c', label: 'Temperatur min', unit: '°C', decimals: 0, higherIsBetter: true, kind: 'range', rangeMin: -30, rangeMax: 30, step: 1, alarmCapable: true },
		{ key: 'gust_max_kmh', label: 'Böen', unit: 'km/h', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 150, step: 5, alarmCapable: true },
		{ key: 'cape_max_jkg', label: 'Gewitter-Energie (CAPE)', unit: 'J/kg', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 3000, step: 100, alarmCapable: true },
		{ key: 'freezing_level_m', label: 'Nullgradgrenze', unit: 'm', decimals: 0, higherIsBetter: true, kind: 'range', rangeMin: 0, rangeMax: 5000, step: 100, alarmCapable: true },
		{ key: 'pop_max_pct', label: 'Regenwahrscheinlichkeit', unit: '%', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 100, step: 5, alarmCapable: false },
		{ key: 'wind_direction_deg', label: 'Windrichtung', unit: '°', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 360, step: 10, alarmCapable: false },
		{ key: 'wind_chill_min_c', label: 'Gefühlte Temp. min', unit: '°C', decimals: 0, higherIsBetter: true, kind: 'range', rangeMin: -30, rangeMax: 30, step: 1, alarmCapable: false },
		{ key: 'humidity_avg_pct', label: 'Luftfeuchtigkeit Ø', unit: '%', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 100, step: 5, alarmCapable: false },
		{ key: 'dewpoint_avg_c', label: 'Taupunkt Ø', unit: '°C', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: -20, rangeMax: 30, step: 1, alarmCapable: false },
		{ key: 'snowfall_limit_m', label: 'Schneefallgrenze', unit: 'm', decimals: 0, higherIsBetter: true, kind: 'range', rangeMin: 0, rangeMax: 5000, step: 100, alarmCapable: false },
		{ key: 'precip_type_dominant', label: 'Niederschlagsart', unit: '', decimals: 0, higherIsBetter: false, kind: 'enum', enumValues: ['RAIN', 'SNOW', 'MIXED', 'FREEZING_RAIN'], alarmCapable: false },
		{ key: 'cloud_low_avg_pct', label: 'Wolken tief', unit: '%', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 100, step: 5, alarmCapable: false },
		{ key: 'cloud_mid_avg_pct', label: 'Wolken mittel', unit: '%', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 100, step: 5, alarmCapable: false },
		{ key: 'cloud_high_avg_pct', label: 'Wolken hoch', unit: '%', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 100, step: 5, alarmCapable: false },
		{ key: 'pressure_avg_hpa', label: 'Luftdruck Ø', unit: 'hPa', decimals: 0, higherIsBetter: true, kind: 'range', rangeMin: 950, rangeMax: 1050, step: 5, alarmCapable: false }
	]
};

// Golden-Fixture: eingefroren aus dem HEUTIGEN COMPARE_METRIC_DEFS-Stand
// (corridorEditorState.ts:273-289, gebaut aus ALL_METRICS + _COMPARE_DEFAULTS
// (Z.256-271) + _COMPARE_ALARM_KEYS (Z.235-238)). Reihenfolge =
// ALL_METRICS-Reihenfolge (compareMetricDefs.ts). Kein `ordinalLabels`-Feld
// bei Range-Einträgen — COMPARE_METRIC_DEFS setzt den Key heute nur im
// Thunder-Sonderfall (Objektliteral-Zweig), s. Feld-für-Feld-Vergleich unten
// (bewusst kein deepEqual auf ganze Objekte, um Key-Praesenz-Semantik nicht
// ungewollt Teil der Assertion zu machen).
const GOLDEN_DEFS: Array<{
	metric: string;
	label: string;
	unit: string;
	scale: [number, number];
	step: number;
	kind: 'range' | 'ordinal';
	ordinalLabels?: string[];
	defaultMin: number | null;
	defaultMax: number | null;
	alarmCapable: boolean;
}> = [
	{ metric: 'snow_depth_cm', label: 'Schneehöhe', unit: 'cm', scale: [0, 200], step: 5, kind: 'range', defaultMin: 30, defaultMax: 200, alarmCapable: false },
	{ metric: 'snow_new_sum_cm', label: 'Neuschnee', unit: 'cm', scale: [0, 50], step: 1, kind: 'range', defaultMin: 5, defaultMax: 50, alarmCapable: true },
	{ metric: 'sunny_hours_h', label: 'Sonnenstunden', unit: 'h', scale: [0, 12], step: 0.5, kind: 'range', defaultMin: 4, defaultMax: null, alarmCapable: false },
	{ metric: 'wind_max_kmh', label: 'Windspitzen', unit: 'km/h', scale: [0, 100], step: 5, kind: 'range', defaultMin: 0, defaultMax: 50, alarmCapable: true },
	{ metric: 'cloud_avg_pct', label: 'Bewölkung Ø', unit: '%', scale: [0, 100], step: 5, kind: 'range', defaultMin: 0, defaultMax: 60, alarmCapable: false },
	{ metric: 'visibility_min_m', label: 'Sichtweite min', unit: 'm', scale: [0, 10000], step: 500, kind: 'range', defaultMin: 2000, defaultMax: 10000, alarmCapable: true },
	{ metric: 'precip_sum_mm', label: 'Niederschlag', unit: 'mm', scale: [0, 30], step: 0.5, kind: 'range', defaultMin: 0, defaultMax: 5, alarmCapable: true },
	{ metric: 'uv_index_max', label: 'UV-Index max', unit: '', scale: [0, 12], step: 1, kind: 'range', defaultMin: 0, defaultMax: 8, alarmCapable: false },
	{ metric: 'temp_max_c', label: 'Temperatur max', unit: '°C', scale: [-20, 45], step: 1, kind: 'range', defaultMin: 15, defaultMax: 35, alarmCapable: true },
	{ metric: 'thunder_level_max', label: 'Gewitter', unit: '', scale: [0, 2], step: 1, kind: 'ordinal', ordinalLabels: ['kein', 'mittel', 'hoch'], defaultMin: null, defaultMax: 0, alarmCapable: true },
	{ metric: 'temp_min_c', label: 'Temperatur min', unit: '°C', scale: [-30, 30], step: 1, kind: 'range', defaultMin: -5, defaultMax: null, alarmCapable: true },
	{ metric: 'gust_max_kmh', label: 'Böen', unit: 'km/h', scale: [0, 150], step: 5, kind: 'range', defaultMin: null, defaultMax: 70, alarmCapable: true },
	{ metric: 'cape_max_jkg', label: 'Gewitter-Energie (CAPE)', unit: 'J/kg', scale: [0, 3000], step: 100, kind: 'range', defaultMin: null, defaultMax: 500, alarmCapable: true },
	{ metric: 'freezing_level_m', label: 'Nullgradgrenze', unit: 'm', scale: [0, 5000], step: 100, kind: 'range', defaultMin: 1500, defaultMax: null, alarmCapable: true },
	{ metric: 'pop_max_pct', label: 'Regenwahrscheinlichkeit', unit: '%', scale: [0, 100], step: 5, kind: 'range', defaultMin: null, defaultMax: null, alarmCapable: false },
	{ metric: 'wind_direction_deg', label: 'Windrichtung', unit: '°', scale: [0, 360], step: 10, kind: 'range', defaultMin: null, defaultMax: null, alarmCapable: false },
	{ metric: 'wind_chill_min_c', label: 'Gefühlte Temp. min', unit: '°C', scale: [-30, 30], step: 1, kind: 'range', defaultMin: null, defaultMax: null, alarmCapable: false },
	{ metric: 'humidity_avg_pct', label: 'Luftfeuchtigkeit Ø', unit: '%', scale: [0, 100], step: 5, kind: 'range', defaultMin: null, defaultMax: null, alarmCapable: false },
	{ metric: 'dewpoint_avg_c', label: 'Taupunkt Ø', unit: '°C', scale: [-20, 30], step: 1, kind: 'range', defaultMin: null, defaultMax: null, alarmCapable: false },
	{ metric: 'snowfall_limit_m', label: 'Schneefallgrenze', unit: 'm', scale: [0, 5000], step: 100, kind: 'range', defaultMin: null, defaultMax: null, alarmCapable: false },
	// precip_type_dominant: MetricDef.kind='enum' wird im Editor wie heute auf
	// 'range' plattgedrückt (kein numerisches Backing in ALL_METRICS -> Default-
	// Fallback scale=[0,100], step=1).
	{ metric: 'precip_type_dominant', label: 'Niederschlagsart', unit: '', scale: [0, 100], step: 1, kind: 'range', defaultMin: null, defaultMax: null, alarmCapable: false },
	{ metric: 'cloud_low_avg_pct', label: 'Wolken tief', unit: '%', scale: [0, 100], step: 5, kind: 'range', defaultMin: null, defaultMax: null, alarmCapable: false },
	{ metric: 'cloud_mid_avg_pct', label: 'Wolken mittel', unit: '%', scale: [0, 100], step: 5, kind: 'range', defaultMin: null, defaultMax: null, alarmCapable: false },
	{ metric: 'cloud_high_avg_pct', label: 'Wolken hoch', unit: '%', scale: [0, 100], step: 5, kind: 'range', defaultMin: null, defaultMax: null, alarmCapable: false },
	{ metric: 'pressure_avg_hpa', label: 'Luftdruck Ø', unit: 'hPa', scale: [950, 1050], step: 5, kind: 'range', defaultMin: null, defaultMax: null, alarmCapable: false }
];

const moduleExists = () => existsSync(MODULE_FILE);

/** Feld-für-Feld-Vergleich (AC-2: "Wertevergleich, kein Datei-Grep") — bewusst
 *  kein deepEqual auf ganze Objekte (s. Kommentar an GOLDEN_DEFS). */
function assertDefMatches(actual: Record<string, unknown> | undefined, expected: (typeof GOLDEN_DEFS)[number], where: string) {
	assert.ok(actual, `${where}: kein Ergebnis-Eintrag vorhanden`);
	assert.equal(actual!.metric, expected.metric, `${where}.metric weicht ab`);
	assert.equal(actual!.label, expected.label, `${where}.label weicht ab`);
	assert.equal(actual!.unit, expected.unit, `${where}.unit weicht ab`);
	assert.deepEqual(actual!.scale, expected.scale, `${where}.scale weicht ab`);
	assert.equal(actual!.step, expected.step, `${where}.step weicht ab`);
	assert.equal(actual!.kind, expected.kind, `${where}.kind weicht ab`);
	assert.deepEqual(actual!.ordinalLabels, expected.ordinalLabels, `${where}.ordinalLabels weicht ab`);
	assert.equal(actual!.defaultMin, expected.defaultMin, `${where}.defaultMin weicht ab`);
	assert.equal(actual!.defaultMax, expected.defaultMax, `${where}.defaultMax weicht ab`);
	assert.equal(actual!.alarmCapable, expected.alarmCapable, `${where}.alarmCapable weicht ab`);
}

describe('AC-2: compareMetricCatalogLoader.ts existiert und exportiert buildCompareMetricDefs', () => {
	test('frontend/.../corridor-editor/compareMetricCatalogLoader.ts existiert', () => {
		assert.ok(
			moduleExists(),
			'AC-2 FAIL: compareMetricCatalogLoader.ts existiert noch nicht — der Schwellen-Editor ' +
				'kann CompareMetricDef nicht aus GET /api/compare/metrics bauen (Teil 3 von #1350 noch nicht implementiert).'
		);
	});

	test('exportiert buildCompareMetricDefs als Funktion', async () => {
		let mod: typeof import('../compareMetricCatalogLoader.ts');
		try {
			mod = await import(MODULE_SPECIFIER);
		} catch (e) {
			assert.fail(
				`AC-2 FAIL: compareMetricCatalogLoader.ts kann nicht importiert werden (existiert noch nicht): ${(e as Error).message}`
			);
			return;
		}
		assert.equal(
			typeof mod.buildCompareMetricDefs,
			'function',
			'AC-2 FAIL: kein Export buildCompareMetricDefs gefunden'
		);
	});
});

// Absicherung (RED-Phase-Sicherheitsnetz, GEGENSTANDSLOS nach GREEN): die
// Golden-Fixture wurde in RED zusaetzlich gegen den damaligen
// COMPARE_METRIC_DEFS-Stand geprueft (schuetzte vor einer falsch abgetippten
// Erwartung, bevor buildCompareMetricDefs() existierte). Issue #1350 Teil 3
// entfernt COMPARE_METRIC_DEFS als Modul-Konstante ersatzlos (Spec Punkt 4) —
// der Vergleich unten (buildCompareMetricDefs(ENDPOINT_FIXTURE) vs.
// GOLDEN_DEFS) deckt die Paritaet jetzt vollstaendig ab, dieser Block entfaellt.

describe('AC-2 (Charakterisierung, Parität): buildCompareMetricDefs(endpointFixture) === GOLDEN_DEFS', () => {
	test('liefert 25 CompareMetricDef-Objekte, feldweise bitgleich zur Golden-Fixture', async () => {
		let mod: typeof import('../compareMetricCatalogLoader.ts');
		try {
			mod = await import(MODULE_SPECIFIER);
		} catch (e) {
			assert.fail(
				`AC-2 FAIL: compareMetricCatalogLoader.ts kann nicht importiert werden (existiert noch nicht): ${(e as Error).message}`
			);
			return;
		}

		const result = mod.buildCompareMetricDefs(ENDPOINT_FIXTURE);

		assert.equal(
			result.length,
			25,
			`AC-2 FAIL: erwartet 25 CompareMetricDef-Objekte, erhalten ${result.length}`
		);
		GOLDEN_DEFS.forEach((expected, i) => {
			assertDefMatches(
				result[i] as unknown as Record<string, unknown>,
				expected,
				`AC-2[${i}] (${expected.metric})`
			);
		});
	});
});

describe('AC-1 (SSoT-Kern): ein synthetischer neuer Katalog-Eintrag erscheint im Pool ohne Frontend-Code-Änderung', () => {
	test('erweiterte Endpoint-Fixture -> Zusatz-Def erscheint zusätzlich zu den 25 bekannten', async () => {
		let mod: typeof import('../compareMetricCatalogLoader.ts');
		try {
			mod = await import(MODULE_SPECIFIER);
		} catch (e) {
			assert.fail(
				`AC-1 FAIL: compareMetricCatalogLoader.ts kann nicht importiert werden (existiert noch nicht): ${(e as Error).message}`
			);
			return;
		}

		const extendedFixture = {
			metrics: [
				...ENDPOINT_FIXTURE.metrics,
				{
					key: 'foo_new_metric',
					label: 'Testmetrik Neu',
					unit: 'x',
					kind: 'range',
					rangeMin: 0,
					rangeMax: 10,
					step: 1,
					alarmCapable: false
				}
			]
		};

		const result = mod.buildCompareMetricDefs(extendedFixture);

		assert.equal(
			result.length,
			26,
			'AC-1 FAIL: der synthetische neue Eintrag muss zusätzlich zu den 25 bekannten erscheinen — ' +
				'ohne jede Frontend-Code-Änderung (SSoT-Eigenschaft)'
		);
		assertDefMatches(
			result[25] as unknown as Record<string, unknown>,
			{
				metric: 'foo_new_metric',
				label: 'Testmetrik Neu',
				unit: 'x',
				scale: [0, 10],
				step: 1,
				kind: 'range',
				defaultMin: null,
				defaultMax: null,
				alarmCapable: false
			},
			'AC-1[25] (foo_new_metric)'
		);
	});
});
