// TDD RED — Issue #1350 Teil 2: Compare-Metrik-Auswahlliste bezieht ihre
// Einträge künftig aus GET /api/compare/metrics (Teil 1, live seit a824a6cc)
// statt aus dem statischen Frontend-Import COMPARE_METRIC_DEFS.
//
// Spec: docs/specs/modules/compare_metric_selection_source.md § AC-1, AC-2
// Kontext: docs/context/fix-1350-compare-metric-select.md
//
// Die Naht `compareMetricSelection.ts::toCompareSelectionEntries()` existiert
// in RED noch nicht. Analog dem existsSync/dynamischen-Import-Muster in
// shared/__tests__/weatherMetricsTabSharing.test.ts wird der Modul-Existenz-
// Test bewusst sprechend rot gemacht, statt den Runner mit einem rohen
// ENOENT abzubrechen.
//
// Ausführung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/weather-metrics-tab/__tests__/compareMetricSelection.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join, dirname } from 'node:path';

const MODULE_FILE = join(
	dirname(fileURLToPath(import.meta.url)),
	'..',
	'compareMetricSelection.ts'
);
const MODULE_SPECIFIER = '../compareMetricSelection.ts';

// Fixture 1:1 aus src/output/renderers/compare_metric_catalog.py::COMPARE_METRIC_CATALOG
// gezogen (25 Einträge, identische Reihenfolge/Keys/Labels — die echte Antwort
// von GET /api/compare/metrics, Teil 1).
const REAL_CATALOG_FIXTURE = {
	metrics: [
		{ key: 'snow_depth_cm', label: 'Schneehöhe', unit: 'cm', decimals: 0, higherIsBetter: true, kind: 'range', rangeMin: 0, rangeMax: 200, step: 5 },
		{ key: 'snow_new_sum_cm', label: 'Neuschnee', unit: 'cm', decimals: 0, higherIsBetter: true, kind: 'range', rangeMin: 0, rangeMax: 50, step: 1 },
		{ key: 'sunny_hours_h', label: 'Sonnenstunden', unit: 'h', decimals: 1, higherIsBetter: true, kind: 'range', rangeMin: 0, rangeMax: 12, step: 0.5 },
		{ key: 'wind_max_kmh', label: 'Windspitzen', unit: 'km/h', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 100, step: 5 },
		{ key: 'cloud_avg_pct', label: 'Bewölkung Ø', unit: '%', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 100, step: 5 },
		{ key: 'visibility_min_m', label: 'Sichtweite min', unit: 'm', decimals: 0, higherIsBetter: true, kind: 'range', rangeMin: 0, rangeMax: 10000, step: 500 },
		{ key: 'precip_sum_mm', label: 'Niederschlag', unit: 'mm', decimals: 1, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 30, step: 0.5 },
		{ key: 'uv_index_max', label: 'UV-Index max', unit: '', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 12, step: 1 },
		{ key: 'temp_max_c', label: 'Temperatur max', unit: '°C', decimals: 0, higherIsBetter: true, kind: 'range', rangeMin: -20, rangeMax: 45, step: 1 },
		{ key: 'thunder_level_max', label: 'Gewitter', unit: '', decimals: 0, higherIsBetter: false, kind: 'ordinal', ordinalLabels: ['kein', 'mittel', 'hoch'] },
		{ key: 'temp_min_c', label: 'Temperatur min', unit: '°C', decimals: 0, higherIsBetter: true, kind: 'range', rangeMin: -30, rangeMax: 30, step: 1 },
		{ key: 'gust_max_kmh', label: 'Böen', unit: 'km/h', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 150, step: 5 },
		{ key: 'cape_max_jkg', label: 'Gewitter-Energie (CAPE)', unit: 'J/kg', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 3000, step: 100 },
		{ key: 'freezing_level_m', label: 'Nullgradgrenze', unit: 'm', decimals: 0, higherIsBetter: true, kind: 'range', rangeMin: 0, rangeMax: 5000, step: 100 },
		{ key: 'pop_max_pct', label: 'Regenwahrscheinlichkeit', unit: '%', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 100, step: 5 },
		{ key: 'wind_direction_deg', label: 'Windrichtung', unit: '°', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 360, step: 10 },
		{ key: 'wind_chill_min_c', label: 'Gefühlte Temp. min', unit: '°C', decimals: 0, higherIsBetter: true, kind: 'range', rangeMin: -30, rangeMax: 30, step: 1 },
		{ key: 'humidity_avg_pct', label: 'Luftfeuchtigkeit Ø', unit: '%', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 100, step: 5 },
		{ key: 'dewpoint_avg_c', label: 'Taupunkt Ø', unit: '°C', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: -20, rangeMax: 30, step: 1 },
		{ key: 'snowfall_limit_m', label: 'Schneefallgrenze', unit: 'm', decimals: 0, higherIsBetter: true, kind: 'range', rangeMin: 0, rangeMax: 5000, step: 100 },
		{ key: 'precip_type_dominant', label: 'Niederschlagsart', unit: '', decimals: 0, higherIsBetter: false, kind: 'enum', enumValues: ['RAIN', 'SNOW', 'MIXED', 'FREEZING_RAIN'] },
		{ key: 'cloud_low_avg_pct', label: 'Wolken tief', unit: '%', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 100, step: 5 },
		{ key: 'cloud_mid_avg_pct', label: 'Wolken mittel', unit: '%', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 100, step: 5 },
		{ key: 'cloud_high_avg_pct', label: 'Wolken hoch', unit: '%', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 100, step: 5 },
		{ key: 'pressure_avg_hpa', label: 'Luftdruck Ø', unit: 'hPa', decimals: 0, higherIsBetter: true, kind: 'range', rangeMin: 950, rangeMax: 1050, step: 5 }
	]
};

const moduleExists = () => existsSync(MODULE_FILE);

describe('AC-1/AC-2: compareMetricSelection.ts existiert und exportiert toCompareSelectionEntries', () => {
	test('frontend/.../weather-metrics-tab/compareMetricSelection.ts existiert', () => {
		assert.ok(
			moduleExists(),
			'AC-1 FAIL: compareMetricSelection.ts existiert noch nicht — die Compare-Auswahlliste ' +
				'kann nicht aus GET /api/compare/metrics gemappt werden (Teil 2 von #1350 noch nicht implementiert).'
		);
	});

	test('exportiert toCompareSelectionEntries als Funktion', async () => {
		let mod: typeof import('../compareMetricSelection.ts');
		try {
			mod = await import(MODULE_SPECIFIER);
		} catch (e) {
			assert.fail(
				`AC-1 FAIL: compareMetricSelection.ts kann nicht importiert werden (existiert noch nicht): ${(e as Error).message}`
			);
			return;
		}
		assert.equal(
			typeof mod.toCompareSelectionEntries,
			'function',
			'AC-1 FAIL: kein Export toCompareSelectionEntries gefunden'
		);
	});
});

describe('AC-1: toCompareSelectionEntries — echte 25er-Katalog-Fixture, Reihenfolge + Labels bit-identisch', () => {
	test('liefert 25 Einträge in Endpoint-Reihenfolge mit key->metric, label->label', async () => {
		let mod: typeof import('../compareMetricSelection.ts');
		try {
			mod = await import(MODULE_SPECIFIER);
		} catch (e) {
			assert.fail(
				`AC-1 FAIL: compareMetricSelection.ts kann nicht importiert werden (existiert noch nicht): ${(e as Error).message}`
			);
			return;
		}

		const result = mod.toCompareSelectionEntries(REAL_CATALOG_FIXTURE);

		assert.equal(
			result.length,
			25,
			`AC-1 FAIL: erwartet 25 Einträge (echter Katalog), erhalten ${result.length}`
		);
		REAL_CATALOG_FIXTURE.metrics.forEach((expected, i) => {
			assert.equal(
				result[i]?.metric,
				expected.key,
				`AC-1 FAIL: Reihenfolge/Key-Mapping an Index ${i} weicht ab — erwartet metric='${expected.key}', erhalten '${result[i]?.metric}'`
			);
			assert.equal(
				result[i]?.label,
				expected.label,
				`AC-1 FAIL: Label an Index ${i} weicht ab — erwartet '${expected.label}', erhalten '${result[i]?.label}'`
			);
		});
	});
});

describe('AC-2: SSoT-Kern — neuer Backend-Eintrag erscheint ohne Frontend-Konstanten-Änderung', () => {
	test('synthetischer neuer Katalog-Eintrag (nicht in COMPARE_METRIC_DEFS) wird gemappt', async () => {
		let mod: typeof import('../compareMetricSelection.ts');
		try {
			mod = await import(MODULE_SPECIFIER);
		} catch (e) {
			assert.fail(
				`AC-2 FAIL: compareMetricSelection.ts kann nicht importiert werden (existiert noch nicht): ${(e as Error).message}`
			);
			return;
		}

		const extendedFixture = {
			metrics: [
				...REAL_CATALOG_FIXTURE.metrics,
				{ key: 'foo_new_metric', label: 'Testmetrik Neu' }
			]
		};

		const result = mod.toCompareSelectionEntries(extendedFixture);

		assert.equal(
			result.length,
			26,
			'AC-2 FAIL: der synthetische neue Eintrag muss zusätzlich zu den 25 bekannten erscheinen'
		);
		assert.deepEqual(
			result[25],
			{ metric: 'foo_new_metric', label: 'Testmetrik Neu' },
			'AC-2 FAIL: neuer Backend-Eintrag wurde nicht 1:1 (key->metric, label->label) gemappt — ' +
				'SSoT-Eigenschaft verletzt, Auswahlliste haengt noch an einer Frontend-Konstante'
		);
	});
});

describe('Robustheit: leere/fehlende metrics -> leeres Array, kein Crash', () => {
	test('metrics: [] -> []', async () => {
		let mod: typeof import('../compareMetricSelection.ts');
		try {
			mod = await import(MODULE_SPECIFIER);
		} catch (e) {
			assert.fail(
				`FAIL: compareMetricSelection.ts kann nicht importiert werden (existiert noch nicht): ${(e as Error).message}`
			);
			return;
		}
		assert.deepEqual(mod.toCompareSelectionEntries({ metrics: [] }), []);
	});

	test('fehlendes metrics-Feld -> [] (kein Crash)', async () => {
		let mod: typeof import('../compareMetricSelection.ts');
		try {
			mod = await import(MODULE_SPECIFIER);
		} catch (e) {
			assert.fail(
				`FAIL: compareMetricSelection.ts kann nicht importiert werden (existiert noch nicht): ${(e as Error).message}`
			);
			return;
		}
		// @ts-expect-error absichtlich unvollstaendiger Response-Body (Fehlerpfad-Robustheit)
		assert.deepEqual(mod.toCompareSelectionEntries({}), []);
	});
});
