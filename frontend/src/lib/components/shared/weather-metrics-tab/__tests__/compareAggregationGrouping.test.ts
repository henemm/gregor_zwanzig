// TDD RED — Issue #1411 (Epic #1372 S4b Scheibe 1) — Ortsvergleich-
// Grundauswahl: eine Zeile je Wettergroesse statt einer Zeile je
// (Groesse, Auswertung)-Paar.
//
// Spec: docs/specs/modules/feat_1411_s4b_grundauswahl.md § AC-1, AC-4, AC-8
// Kontext: docs/context/feat-1411-s4b-grundauswahl.md
//
// `compareAggregationGrouping.ts` existiert in RED noch nicht — analog dem
// existsSync-Muster in compareMetricSelection.test.ts wird der Modul-
// Existenz-Test bewusst sprechend rot gemacht statt den Runner mit einem
// rohen ENOENT abzubrechen.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/weather-metrics-tab/__tests__/compareAggregationGrouping.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join, dirname } from 'node:path';

const MODULE_FILE = join(
	dirname(fileURLToPath(import.meta.url)),
	'..',
	'compareAggregationGrouping.ts'
);
const MODULE_SPECIFIER = '../compareAggregationGrouping.ts';

// Echter 26-Zeilen-Katalog, 1:1 aus
// `src/output/renderers/compare_metric_catalog.py::get_compare_metric_catalog()`
// gezogen (Aufruf 2026-07-29, keine erfundene Fixture) und auf die Form
// abgebildet, die `toCompareSelectionEntries()` daraus macht
// (key -> metric, Rest unveraendert durchgereicht).
const REAL_26_ROW_CATALOG = [
	{ metric: 'snow_depth_cm', label: 'Schneehöhe', metric_id: 'snow_depth', aggregation: 'max', aggregation_label: 'Maximum' },
	{ metric: 'snow_new_sum_cm', label: 'Neuschnee', metric_id: 'fresh_snow', aggregation: 'sum', aggregation_label: 'Summe' },
	{ metric: 'sunny_hours_h', label: 'Sonnenstunden', metric_id: 'sunshine', aggregation: 'sum', aggregation_label: 'Summe' },
	{ metric: 'wind_max_kmh', label: 'Wind', metric_id: 'wind', aggregation: 'max', aggregation_label: 'Maximum' },
	{ metric: 'cloud_avg_pct', label: 'Bewölkung', metric_id: 'cloud_total', aggregation: 'avg', aggregation_label: 'Mittel' },
	{ metric: 'visibility_min_m', label: 'Sichtweite', metric_id: 'visibility', aggregation: 'min', aggregation_label: 'Minimum' },
	{ metric: 'precip_sum_mm', label: 'Niederschlag', metric_id: 'precipitation', aggregation: 'sum', aggregation_label: 'Summe' },
	{ metric: 'uv_index_max', label: 'UV-Index', metric_id: 'uv_index', aggregation: 'max', aggregation_label: 'Maximum' },
	{ metric: 'temp_max_c', label: 'Temperatur', metric_id: 'temperature', aggregation: 'max', aggregation_label: 'Maximum' },
	{ metric: 'thunder_level_max', label: 'Gewitter', metric_id: 'thunder', aggregation: 'max', aggregation_label: 'Maximum' },
	{ metric: 'temp_min_c', label: 'Temperatur', metric_id: 'temperature', aggregation: 'min', aggregation_label: 'Minimum' },
	{ metric: 'gust_max_kmh', label: 'Böen', metric_id: 'gust', aggregation: 'max', aggregation_label: 'Maximum' },
	{ metric: 'cape_max_jkg', label: 'Gewitterenergie (CAPE)', metric_id: 'cape', aggregation: 'max', aggregation_label: 'Maximum' },
	{ metric: 'freezing_level_m', label: 'Nullgradgrenze', metric_id: 'freezing_level', aggregation: 'min', aggregation_label: 'Minimum' },
	{ metric: 'pop_max_pct', label: 'Regenwahrscheinlichkeit', metric_id: 'rain_probability', aggregation: 'max', aggregation_label: 'Maximum' },
	{ metric: 'wind_direction_deg', label: 'Windrichtung', metric_id: 'wind_direction', aggregation: 'avg', aggregation_label: 'Mittel' },
	{ metric: 'wind_chill_min_c', label: 'Gefühlte Temperatur', metric_id: 'wind_chill', aggregation: 'min', aggregation_label: 'Minimum' },
	{ metric: 'wind_chill_max_c', label: 'Gefühlte Temperatur', metric_id: 'wind_chill', aggregation: 'max', aggregation_label: 'Maximum' },
	{ metric: 'humidity_avg_pct', label: 'Luftfeuchtigkeit', metric_id: 'humidity', aggregation: 'avg', aggregation_label: 'Mittel' },
	{ metric: 'dewpoint_avg_c', label: 'Taupunkt', metric_id: 'dewpoint', aggregation: 'avg', aggregation_label: 'Mittel' },
	{ metric: 'snowfall_limit_m', label: 'Schneefallgrenze', metric_id: 'snowfall_limit', aggregation: 'min', aggregation_label: 'Minimum' },
	{ metric: 'precip_type_dominant', label: 'Niederschlagsart', metric_id: 'precip_type', aggregation: 'max', aggregation_label: 'Maximum' },
	{ metric: 'cloud_low_avg_pct', label: 'Tiefe Wolken', metric_id: 'cloud_low', aggregation: 'avg', aggregation_label: 'Mittel' },
	{ metric: 'cloud_mid_avg_pct', label: 'Mittelhohe Wolken', metric_id: 'cloud_mid', aggregation: 'avg', aggregation_label: 'Mittel' },
	{ metric: 'cloud_high_avg_pct', label: 'Hohe Wolken', metric_id: 'cloud_high', aggregation: 'avg', aggregation_label: 'Mittel' },
	{ metric: 'pressure_avg_hpa', label: 'Luftdruck', metric_id: 'pressure', aggregation: 'avg', aggregation_label: 'Mittel' },
];

const moduleExists = () => existsSync(MODULE_FILE);

describe('Modul compareAggregationGrouping.ts existiert und exportiert groupCompareCatalog', () => {
	test('frontend/.../weather-metrics-tab/compareAggregationGrouping.ts existiert', () => {
		assert.ok(
			moduleExists(),
			'RED: compareAggregationGrouping.ts existiert noch nicht — die Compare-Grundauswahl kann ' +
				'die 26 Katalogzeilen noch nicht nach metric_id gruppieren (Issue #1411 noch nicht implementiert).'
		);
	});

	test('exportiert groupCompareCatalog als Funktion', async () => {
		let mod: typeof import('../compareAggregationGrouping.ts');
		try {
			mod = await import(MODULE_SPECIFIER);
		} catch (e) {
			assert.fail(`RED: compareAggregationGrouping.ts kann nicht importiert werden: ${(e as Error).message}`);
			return;
		}
		assert.equal(typeof mod.groupCompareCatalog, 'function', 'kein Export groupCompareCatalog gefunden');
	});
});

describe('AC-1: 26 Katalogzeilen -> 24 Gruppen (eine Zeile je Wettergroesse)', () => {
	test('liefert genau 24 Gruppen aus dem echten 26-Zeilen-Katalog', async () => {
		let mod: typeof import('../compareAggregationGrouping.ts');
		try {
			mod = await import(MODULE_SPECIFIER);
		} catch (e) {
			assert.fail(`AC-1 FAIL: Modul fehlt: ${(e as Error).message}`);
			return;
		}
		const groups = mod.groupCompareCatalog(REAL_26_ROW_CATALOG);
		assert.equal(
			groups.length,
			24,
			`AC-1 FAIL: erwartet 24 Gruppen (26 Zeilen, temperature+wind_chill je 2x zusammengefasst), erhalten ${groups.length}`
		);
	});

	test('Fundreihenfolge bestimmt die Zeilenposition — erstes Auftreten der metric_id zaehlt', async () => {
		let mod: typeof import('../compareAggregationGrouping.ts');
		try {
			mod = await import(MODULE_SPECIFIER);
		} catch (e) {
			assert.fail(`AC-1 FAIL: Modul fehlt: ${(e as Error).message}`);
			return;
		}
		const groups = mod.groupCompareCatalog(REAL_26_ROW_CATALOG);
		const expectedOrder = [
			'snow_depth', 'fresh_snow', 'sunshine', 'wind', 'cloud_total', 'visibility',
			'precipitation', 'uv_index', 'temperature', 'thunder', 'gust', 'cape',
			'freezing_level', 'rain_probability', 'wind_direction', 'wind_chill',
			'humidity', 'dewpoint', 'snowfall_limit', 'precip_type', 'cloud_low',
			'cloud_mid', 'cloud_high', 'pressure',
		];
		assert.deepEqual(
			groups.map((g) => g.metric_id),
			expectedOrder,
			'AC-1 FAIL: Gruppenreihenfolge weicht vom ersten Auftreten im Katalog ab — ' +
				'"Temperatur" muesste an Position 9 stehen (erste Fundstelle temp_max_c), nicht an der ' +
				'Position von temp_min_c'
		);
	});

	test('Label der Gruppe kommt unveraendert vom Katalog-Eintrag', async () => {
		let mod: typeof import('../compareAggregationGrouping.ts');
		try {
			mod = await import(MODULE_SPECIFIER);
		} catch (e) {
			assert.fail(`AC-1 FAIL: Modul fehlt: ${(e as Error).message}`);
			return;
		}
		const groups = mod.groupCompareCatalog(REAL_26_ROW_CATALOG);
		const temp = groups.find((g) => g.metric_id === 'temperature');
		const chill = groups.find((g) => g.metric_id === 'wind_chill');
		assert.equal(temp?.label, 'Temperatur');
		assert.equal(chill?.label, 'Gefühlte Temperatur');
	});
});

describe('AC-4: Groessen mit nur einer Auswertung bekommen eine Options-Liste der Laenge 1', () => {
	test('22 von 24 Gruppen haben genau eine Option', async () => {
		let mod: typeof import('../compareAggregationGrouping.ts');
		try {
			mod = await import(MODULE_SPECIFIER);
		} catch (e) {
			assert.fail(`AC-4 FAIL: Modul fehlt: ${(e as Error).message}`);
			return;
		}
		const groups = mod.groupCompareCatalog(REAL_26_ROW_CATALOG);
		const singleOption = groups.filter((g) => g.options.length === 1);
		const multiOption = groups.filter((g) => g.options.length > 1);
		assert.equal(singleOption.length, 22, `AC-4 FAIL: erwartet 22 Einzel-Options-Gruppen, erhalten ${singleOption.length}`);
		assert.equal(multiOption.length, 2, `AC-4 FAIL: erwartet 2 Mehrfach-Options-Gruppen, erhalten ${multiOption.length}`);
		assert.deepEqual(
			multiOption.map((g) => g.metric_id).sort(),
			['temperature', 'wind_chill'],
			'AC-4 FAIL: nur temperature und wind_chill duerfen mehr als eine Option haben'
		);
	});

	test('Beispiel Wind (eine Auswertung): Options-Liste enthaelt genau den einen Katalog-Eintrag', async () => {
		let mod: typeof import('../compareAggregationGrouping.ts');
		try {
			mod = await import(MODULE_SPECIFIER);
		} catch (e) {
			assert.fail(`AC-4 FAIL: Modul fehlt: ${(e as Error).message}`);
			return;
		}
		const groups = mod.groupCompareCatalog(REAL_26_ROW_CATALOG);
		const wind = groups.find((g) => g.metric_id === 'wind');
		assert.deepEqual(wind?.options, [{ key: 'wind_max_kmh', aggregation: 'max', aggregation_label: 'Maximum' }]);
	});

	test('temperature: zwei Optionen in Katalog-Reihenfolge (max vor min, wie im Katalog gefunden)', async () => {
		let mod: typeof import('../compareAggregationGrouping.ts');
		try {
			mod = await import(MODULE_SPECIFIER);
		} catch (e) {
			assert.fail(`AC-4 FAIL: Modul fehlt: ${(e as Error).message}`);
			return;
		}
		const groups = mod.groupCompareCatalog(REAL_26_ROW_CATALOG);
		const temp = groups.find((g) => g.metric_id === 'temperature');
		assert.deepEqual(
			temp?.options,
			[
				{ key: 'temp_max_c', aggregation: 'max', aggregation_label: 'Maximum' },
				{ key: 'temp_min_c', aggregation: 'min', aggregation_label: 'Minimum' },
			],
			'AC-4 FAIL: Optionsliste ist nicht nach Katalog-Fundreihenfolge sortiert oder enthaelt ein ' +
				'fest verdrahtetes Hoechst-/Tiefstwert-Paar statt der echten Katalog-Optionen'
		);
	});

	test('wind_chill: Katalog fuehrt min vor max — die Optionsliste spiegelt genau das, kein erfundenes avg', async () => {
		let mod: typeof import('../compareAggregationGrouping.ts');
		try {
			mod = await import(MODULE_SPECIFIER);
		} catch (e) {
			assert.fail(`AC-4 FAIL: Modul fehlt: ${(e as Error).message}`);
			return;
		}
		const groups = mod.groupCompareCatalog(REAL_26_ROW_CATALOG);
		const chill = groups.find((g) => g.metric_id === 'wind_chill');
		assert.deepEqual(
			chill?.options,
			[
				{ key: 'wind_chill_min_c', aggregation: 'min', aggregation_label: 'Minimum' },
				{ key: 'wind_chill_max_c', aggregation: 'max', aggregation_label: 'Maximum' },
			]
		);
		assert.ok(!chill?.options.some((o) => o.aggregation === 'avg'), 'kein erfundenes avg fuer wind_chill');
	});
});

describe('AC-8 (Kern-Proxy): Gruppierung verliert und erfindet keinen einzelnen Auswahl-Schluessel', () => {
	// Der vollstaendige AC-8-Nachweis (Reihenfolge-Liste zeigt weiterhin zwei
	// separate, sortierbare Zeilen im DOM) ist ein Rendering-/E2E-Test
	// (compare-editor-slice4.spec.ts, s. Test-Plan) und bewusst NICHT Teil
	// dieser RED-Phase (kein Rendering-Harness in node:test). Diese Kern-Probe
	// beweist das Fundament dafuer: die Gruppierung ist eine reine
	// Umsortierung/Zusammenfassung der DARSTELLUNG, kein einzelner
	// Auswahl-Schluessel (`key`, das WeatherV2Reihenfolge.svelte weiterhin
	// einzeln fuehrt) geht dabei verloren oder wird verdoppelt.
	test('alle 26 einzelnen Auswahl-Schluessel tauchen nach der Gruppierung genau einmal in den Optionen auf', async () => {
		let mod: typeof import('../compareAggregationGrouping.ts');
		try {
			mod = await import(MODULE_SPECIFIER);
		} catch (e) {
			assert.fail(`AC-8 FAIL: Modul fehlt: ${(e as Error).message}`);
			return;
		}
		const groups = mod.groupCompareCatalog(REAL_26_ROW_CATALOG);
		const flattenedKeys = groups.flatMap((g) => g.options.map((o) => o.key));
		const originalKeys = REAL_26_ROW_CATALOG.map((e) => e.metric);
		assert.deepEqual(
			[...flattenedKeys].sort(),
			[...originalKeys].sort(),
			'AC-8 FAIL: die Menge der einzelnen Auswahl-Schluessel veraendert sich durch die Gruppierung — ' +
				'die Reihenfolge-Liste (die weiterhin einzelne Schluessel fuehrt) wuerde einen Eintrag ' +
				'verlieren oder verdoppeln'
		);
	});
});

describe('Robustheit: leerer Katalog -> leere Gruppenliste, kein Crash', () => {
	test('[] -> []', async () => {
		let mod: typeof import('../compareAggregationGrouping.ts');
		try {
			mod = await import(MODULE_SPECIFIER);
		} catch (e) {
			assert.fail(`FAIL: Modul fehlt: ${(e as Error).message}`);
			return;
		}
		assert.deepEqual(mod.groupCompareCatalog([]), []);
	});
});
