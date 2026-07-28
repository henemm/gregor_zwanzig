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
		{ key: 'snow_depth_cm', label: 'Schneehöhe', aggregation_label: 'Maximum', unit: 'cm', decimals: 0, higherIsBetter: true, kind: 'range', rangeMin: 0, rangeMax: 200, step: 5 },
		{ key: 'snow_new_sum_cm', label: 'Neuschnee', aggregation_label: 'Summe', unit: 'cm', decimals: 0, higherIsBetter: true, kind: 'range', rangeMin: 0, rangeMax: 50, step: 1 },
		{ key: 'sunny_hours_h', label: 'Sonnenstunden', aggregation_label: 'Summe', unit: 'h', decimals: 1, higherIsBetter: true, kind: 'range', rangeMin: 0, rangeMax: 12, step: 0.5 },
		{ key: 'wind_max_kmh', label: 'Wind', aggregation_label: 'Maximum', unit: 'km/h', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 100, step: 5 },
		{ key: 'cloud_avg_pct', label: 'Bewölkung', aggregation_label: 'Mittel', unit: '%', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 100, step: 5 },
		{ key: 'visibility_min_m', label: 'Sichtweite', aggregation_label: 'Minimum', unit: 'm', decimals: 0, higherIsBetter: true, kind: 'range', rangeMin: 0, rangeMax: 10000, step: 500 },
		{ key: 'precip_sum_mm', label: 'Niederschlag', aggregation_label: 'Summe', unit: 'mm', decimals: 1, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 30, step: 0.5 },
		{ key: 'uv_index_max', label: 'UV-Index', aggregation_label: 'Maximum', unit: '', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 12, step: 1 },
		{ key: 'temp_max_c', label: 'Temperatur', aggregation_label: 'Maximum', unit: '°C', decimals: 0, higherIsBetter: true, kind: 'range', rangeMin: -20, rangeMax: 45, step: 1 },
		{ key: 'thunder_level_max', label: 'Gewitter', aggregation_label: 'Maximum', unit: '', decimals: 0, higherIsBetter: false, kind: 'ordinal', ordinalLabels: ['kein', 'mittel', 'hoch'] },
		{ key: 'temp_min_c', label: 'Temperatur', aggregation_label: 'Minimum', unit: '°C', decimals: 0, higherIsBetter: true, kind: 'range', rangeMin: -30, rangeMax: 30, step: 1 },
		{ key: 'gust_max_kmh', label: 'Böen', aggregation_label: 'Maximum', unit: 'km/h', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 150, step: 5 },
		{ key: 'cape_max_jkg', label: 'Gewitterenergie (CAPE)', aggregation_label: 'Maximum', unit: 'J/kg', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 3000, step: 100 },
		{ key: 'freezing_level_m', label: 'Nullgradgrenze', aggregation_label: 'Minimum', unit: 'm', decimals: 0, higherIsBetter: true, kind: 'range', rangeMin: 0, rangeMax: 5000, step: 100 },
		{ key: 'pop_max_pct', label: 'Regenwahrscheinlichkeit', aggregation_label: 'Maximum', unit: '%', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 100, step: 5 },
		{ key: 'wind_direction_deg', label: 'Windrichtung', aggregation_label: 'Mittel', unit: '°', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 360, step: 10 },
		{ key: 'wind_chill_min_c', label: 'Gefühlte Temperatur', aggregation_label: 'Minimum', unit: '°C', decimals: 0, higherIsBetter: true, kind: 'range', rangeMin: -30, rangeMax: 30, step: 1 },
		{ key: 'humidity_avg_pct', label: 'Luftfeuchtigkeit', aggregation_label: 'Mittel', unit: '%', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 100, step: 5 },
		{ key: 'dewpoint_avg_c', label: 'Taupunkt', aggregation_label: 'Mittel', unit: '°C', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: -20, rangeMax: 30, step: 1 },
		{ key: 'snowfall_limit_m', label: 'Schneefallgrenze', aggregation_label: 'Minimum', unit: 'm', decimals: 0, higherIsBetter: true, kind: 'range', rangeMin: 0, rangeMax: 5000, step: 100 },
		{ key: 'precip_type_dominant', label: 'Niederschlagsart', aggregation_label: 'Maximum', unit: '', decimals: 0, higherIsBetter: false, kind: 'enum', enumValues: ['RAIN', 'SNOW', 'MIXED', 'FREEZING_RAIN'] },
		{ key: 'cloud_low_avg_pct', label: 'Tiefe Wolken', aggregation_label: 'Mittel', unit: '%', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 100, step: 5 },
		{ key: 'cloud_mid_avg_pct', label: 'Mittelhohe Wolken', aggregation_label: 'Mittel', unit: '%', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 100, step: 5 },
		{ key: 'cloud_high_avg_pct', label: 'Hohe Wolken', aggregation_label: 'Mittel', unit: '%', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 100, step: 5 },
		{ key: 'pressure_avg_hpa', label: 'Luftdruck', aggregation_label: 'Mittel', unit: 'hPa', decimals: 0, higherIsBetter: true, kind: 'range', rangeMin: 950, rangeMax: 1050, step: 5 }
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

// ---------------------------------------------------------------------------
// TDD RED — #1373 (S2 Scheibe A), AC-6: der Katalog-Endpoint liefert je Eintrag
// zusätzlich `metric_id` (zentrale Wettergröße) und `aggregation` (Auswertung).
// `toCompareSelectionEntries()` reicht beide unverändert durch — reines
// Durchreichen, keine neue Auswahl-Logik, keine UI-Änderung. Scheibe B baut
// darauf auf.
//
// Spec: docs/specs/modules/feat_1373_s2_ein_katalog.md § AC-6, Punkt 4
// ---------------------------------------------------------------------------

// Auszug aus der Endpoint-Antwort NACH #1373 (Herkunftsfelder ergänzt, Rest
// unverändert) — inklusive der beiden Aufspaltungen, die dieselbe zentrale
// Größe mit unterschiedlicher Auswertung tragen.
const CATALOG_WITH_ORIGIN_FIXTURE = {
	metrics: [
		{ key: 'temp_max_c', label: 'Temperatur', aggregation_label: 'Maximum', unit: '°C', decimals: 0, higherIsBetter: true, kind: 'range', rangeMin: -20, rangeMax: 45, step: 1, metric_id: 'temperature', aggregation: 'max' },
		{ key: 'temp_min_c', label: 'Temperatur', aggregation_label: 'Minimum', unit: '°C', decimals: 0, higherIsBetter: true, kind: 'range', rangeMin: -30, rangeMax: 30, step: 1, metric_id: 'temperature', aggregation: 'min' },
		{ key: 'wind_max_kmh', label: 'Wind', aggregation_label: 'Maximum', unit: 'km/h', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 100, step: 5, metric_id: 'wind', aggregation: 'max' },
		{ key: 'precip_sum_mm', label: 'Niederschlag', aggregation_label: 'Summe', unit: 'mm', decimals: 1, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 30, step: 0.5, metric_id: 'precipitation', aggregation: 'sum' }
	]
};

type SelectionEntryWithOrigin = {
	metric: string;
	label: string;
	metric_id?: string;
	aggregation?: string;
};

describe('#1373 AC-6: metric_id/aggregation werden unveraendert durchgereicht', () => {
	test('jeder Auswahl-Eintrag traegt metric_id und aggregation aus der Endpoint-Antwort', async () => {
		let mod: typeof import('../compareMetricSelection.ts');
		try {
			mod = await import(MODULE_SPECIFIER);
		} catch (e) {
			assert.fail(
				`AC-6 FAIL: compareMetricSelection.ts kann nicht importiert werden: ${(e as Error).message}`
			);
			return;
		}

		const result = mod.toCompareSelectionEntries(
			CATALOG_WITH_ORIGIN_FIXTURE as unknown as Parameters<typeof mod.toCompareSelectionEntries>[0]
		) as unknown as SelectionEntryWithOrigin[];

		assert.equal(result.length, 4, `AC-6 FAIL: erwartet 4 Eintraege, erhalten ${result.length}`);

		CATALOG_WITH_ORIGIN_FIXTURE.metrics.forEach((expected, i) => {
			const actual = result[i];
			assert.equal(actual?.metric, expected.key, `AC-6 FAIL: key->metric an Index ${i}`);
			assert.equal(actual?.label, expected.label, `AC-6 FAIL: label an Index ${i}`);
			assert.equal(
				actual?.metric_id,
				expected.metric_id,
				`AC-6 FAIL: metric_id an Index ${i} nicht durchgereicht — erwartet '${expected.metric_id}', erhalten '${actual?.metric_id}'`
			);
			assert.equal(
				actual?.aggregation,
				expected.aggregation,
				`AC-6 FAIL: aggregation an Index ${i} nicht durchgereicht — erwartet '${expected.aggregation}', erhalten '${actual?.aggregation}'`
			);
		});
	});

	test('die beiden Aufspaltungen bleiben getrennte Eintraege derselben Groesse', async () => {
		let mod: typeof import('../compareMetricSelection.ts');
		try {
			mod = await import(MODULE_SPECIFIER);
		} catch (e) {
			assert.fail(
				`AC-6 FAIL: compareMetricSelection.ts kann nicht importiert werden: ${(e as Error).message}`
			);
			return;
		}

		const result = mod.toCompareSelectionEntries(
			CATALOG_WITH_ORIGIN_FIXTURE as unknown as Parameters<typeof mod.toCompareSelectionEntries>[0]
		) as unknown as SelectionEntryWithOrigin[];

		const hi = result.find((e) => e.metric === 'temp_max_c');
		const lo = result.find((e) => e.metric === 'temp_min_c');
		assert.ok(hi && lo, 'AC-6 FAIL: temp_max_c/temp_min_c sind nicht beide vorhanden');
		assert.equal(hi?.metric_id, 'temperature');
		assert.equal(lo?.metric_id, 'temperature');
		assert.equal(hi?.aggregation, 'max');
		assert.equal(lo?.aggregation, 'min');
	});

	test('Eintrag ohne Herkunftsfelder wird weiterhin gemappt, ohne leere Schluessel zu erfinden', async () => {
		// Vertrag (haelt den bestehenden #1350-AC-2-Test gruen): fehlen die
		// Felder in der Antwort, darf das Mapping sie NICHT als `undefined`
		// ergaenzen — sonst bricht der strikte deepEqual-Vergleich oben.
		let mod: typeof import('../compareMetricSelection.ts');
		try {
			mod = await import(MODULE_SPECIFIER);
		} catch (e) {
			assert.fail(
				`AC-6 FAIL: compareMetricSelection.ts kann nicht importiert werden: ${(e as Error).message}`
			);
			return;
		}

		const result = mod.toCompareSelectionEntries({
			metrics: [{ key: 'ohne_herkunft', label: 'Ohne Herkunft' }]
		} as unknown as Parameters<typeof mod.toCompareSelectionEntries>[0]);

		assert.deepEqual(result, [{ metric: 'ohne_herkunft', label: 'Ohne Herkunft' }]);
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
