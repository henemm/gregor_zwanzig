// TDD — Issue #1231, Slice 3: CorridorEditor Desktop route — reine Logik.
//
// Ausführung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/corridor-editor/corridorEditorState.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import {
	ROUTE_METRIC_DEFS,
	ROUTE_CTX_DEFAULTS,
	buildRoutePool,
	addRow,
	removeRow,
	patchRow,
	validateCorridorRows,
	buildCorridorSavePayload,
	valueAtPointer,
	clampDragValue,
	clampBoundInput,
	saveGateDecision,
	VERGLEICH_CTX_DEFAULTS,
	buildComparePool,
	addCompareRow,
	buildCompareCorridorSavePayload,
	buildComparePrefillRows,
	type CompareMetricDef,
} from './corridorEditorState.ts';
// Issue #1350 Teil 3: COMPARE_METRIC_DEFS (Modul-Konstante) entfaellt — die
// Tests unten bauen ihre eigene, frozen Defs-Liste ueber den echten Mapper
// (buildCompareMetricDefs) aus einer Endpoint-Antwort-Fixture (1:1 aus
// src/output/renderers/compare_metric_catalog.py, identisch zur Fixture in
// __tests__/compareMetricCatalogParity.test.ts). Testet damit gegen den
// echten Produktionscode statt eine zweite Erwartung zu erfinden.
import { buildCompareMetricDefs, buildRouteMetricDefsFromCatalog } from './compareMetricCatalogLoader.ts';

// Endpoint-Antwort-Fixture: 25 Eintraege 1:1 aus
// src/output/renderers/compare_metric_catalog.py::COMPARE_METRIC_CATALOG,
// alarmCapable = die 10 Keys aus compare_alert.py::_SUMMARY_KEY_TO_CATALOG_ID.
const CATALOG_FIXTURE = {
	metrics: [
		{ key: 'snow_depth_cm', label: 'Schneehöhe', aggregation_label: 'Maximum', unit: 'cm', decimals: 0, higherIsBetter: true, kind: 'range', rangeMin: 0, rangeMax: 200, step: 5, alarmCapable: false },
		{ key: 'snow_new_sum_cm', label: 'Neuschnee', aggregation_label: 'Summe', unit: 'cm', decimals: 0, higherIsBetter: true, kind: 'range', rangeMin: 0, rangeMax: 50, step: 1, alarmCapable: true },
		{ key: 'sunny_hours_h', label: 'Sonnenstunden', aggregation_label: 'Summe', unit: 'h', decimals: 1, higherIsBetter: true, kind: 'range', rangeMin: 0, rangeMax: 12, step: 0.5, alarmCapable: false },
		{ key: 'wind_max_kmh', label: 'Wind', aggregation_label: 'Maximum', unit: 'km/h', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 100, step: 5, alarmCapable: true },
		{ key: 'cloud_avg_pct', label: 'Bewölkung', aggregation_label: 'Mittel', unit: '%', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 100, step: 5, alarmCapable: false },
		{ key: 'visibility_min_m', label: 'Sichtweite', aggregation_label: 'Minimum', unit: 'm', decimals: 0, higherIsBetter: true, kind: 'range', rangeMin: 0, rangeMax: 10000, step: 500, alarmCapable: true },
		{ key: 'precip_sum_mm', label: 'Niederschlag', aggregation_label: 'Summe', unit: 'mm', decimals: 1, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 30, step: 0.5, alarmCapable: true },
		{ key: 'uv_index_max', label: 'UV-Index', aggregation_label: 'Maximum', unit: '', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 12, step: 1, alarmCapable: false },
		{ key: 'temp_max_c', label: 'Temperatur', aggregation_label: 'Maximum', unit: '°C', decimals: 0, higherIsBetter: true, kind: 'range', rangeMin: -20, rangeMax: 45, step: 1, alarmCapable: true },
		{ key: 'thunder_level_max', label: 'Gewitter', aggregation_label: 'Maximum', unit: '', decimals: 0, higherIsBetter: false, kind: 'ordinal', ordinalLabels: ['kein', 'mittel', 'hoch'], alarmCapable: true },
		{ key: 'temp_min_c', label: 'Temperatur', aggregation_label: 'Minimum', unit: '°C', decimals: 0, higherIsBetter: true, kind: 'range', rangeMin: -30, rangeMax: 30, step: 1, alarmCapable: true },
		{ key: 'gust_max_kmh', label: 'Böen', aggregation_label: 'Maximum', unit: 'km/h', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 150, step: 5, alarmCapable: true },
		{ key: 'cape_max_jkg', label: 'Gewitterenergie (CAPE)', aggregation_label: 'Maximum', unit: 'J/kg', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 3000, step: 100, alarmCapable: true },
		{ key: 'freezing_level_m', label: 'Nullgradgrenze', aggregation_label: 'Minimum', unit: 'm', decimals: 0, higherIsBetter: true, kind: 'range', rangeMin: 0, rangeMax: 5000, step: 100, alarmCapable: true },
		{ key: 'pop_max_pct', label: 'Regenwahrscheinlichkeit', aggregation_label: 'Maximum', unit: '%', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 100, step: 5, alarmCapable: false },
		{ key: 'wind_direction_deg', label: 'Windrichtung', aggregation_label: 'Mittel', unit: '°', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 360, step: 10, alarmCapable: false },
		{ key: 'wind_chill_min_c', label: 'Gefühlte Temperatur', aggregation_label: 'Minimum', unit: '°C', decimals: 0, higherIsBetter: true, kind: 'range', rangeMin: -30, rangeMax: 30, step: 1, alarmCapable: false },
		// Issue #1424: fehlte hier bislang (Fixture war 25 statt 26 Eintraege).
		{ key: 'wind_chill_max_c', label: 'Gefühlte Temperatur', aggregation_label: 'Maximum', unit: '°C', decimals: 0, higherIsBetter: true, kind: 'range', rangeMin: -20, rangeMax: 45, step: 1, alarmCapable: false },
		{ key: 'humidity_avg_pct', label: 'Luftfeuchtigkeit', aggregation_label: 'Mittel', unit: '%', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 100, step: 5, alarmCapable: false },
		{ key: 'dewpoint_avg_c', label: 'Taupunkt', aggregation_label: 'Mittel', unit: '°C', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: -20, rangeMax: 30, step: 1, alarmCapable: false },
		{ key: 'snowfall_limit_m', label: 'Schneefallgrenze', aggregation_label: 'Minimum', unit: 'm', decimals: 0, higherIsBetter: true, kind: 'range', rangeMin: 0, rangeMax: 5000, step: 100, alarmCapable: false },
		{ key: 'precip_type_dominant', label: 'Niederschlagsart', aggregation_label: 'Maximum', unit: '', decimals: 0, higherIsBetter: false, kind: 'enum', enumValues: ['RAIN', 'SNOW', 'MIXED', 'FREEZING_RAIN'], alarmCapable: false },
		{ key: 'cloud_low_avg_pct', label: 'Tiefe Wolken', aggregation_label: 'Mittel', unit: '%', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 100, step: 5, alarmCapable: false },
		{ key: 'cloud_mid_avg_pct', label: 'Mittelhohe Wolken', aggregation_label: 'Mittel', unit: '%', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 100, step: 5, alarmCapable: false },
		{ key: 'cloud_high_avg_pct', label: 'Hohe Wolken', aggregation_label: 'Mittel', unit: '%', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 100, step: 5, alarmCapable: false },
		{ key: 'pressure_avg_hpa', label: 'Luftdruck', aggregation_label: 'Mittel', unit: 'hPa', decimals: 0, higherIsBetter: true, kind: 'range', rangeMin: 950, rangeMax: 1050, step: 5, alarmCapable: false },
	],
};

const TEST_DEFS: CompareMetricDef[] = buildCompareMetricDefs(CATALOG_FIXTURE);

// --- AC-3: confidence_pct darf im route-Metrikpool nie auftauchen ---
describe('ROUTE_METRIC_DEFS — AC-3 confidence_pct-Ausschluss', () => {
	test('enthaelt genau die 6 AlertableMetrics, kein confidence_pct', () => {
		const ids = ROUTE_METRIC_DEFS.map((m) => m.metric).sort();
		assert.deepEqual(ids, [
			'precipitation_sum',
			'snow_line',
			'temperature_max',
			'temperature_min',
			'thunder_level',
			'wind_gust',
		]);
		assert.equal(ids.includes('confidence_pct'), false);
	});
});

// --- buildRoutePool: Zeilen aus trip.corridors[], Rest als poolLeft ---
describe('buildRoutePool', () => {
	test('baut Zeile aus vorhandenem Corridor + Metrik-Definition', () => {
		const { rows, poolLeft } = buildRoutePool([
			{ metric: 'wind_gust', range: [null, 55], notify: true, mark: false },
		]);
		assert.equal(rows.length, 1);
		assert.equal(rows[0].label, 'Böen');
		assert.equal(rows[0].unit, 'km/h');
		assert.equal(rows[0].min, null);
		assert.equal(rows[0].max, 55);
		assert.equal(rows[0].notify, true);
		assert.equal(poolLeft.length, 5);
		assert.equal(poolLeft.some((m) => m.metric === 'wind_gust'), false);
	});

	test('leere corridors -> alle 6 Metriken im poolLeft, keine rows', () => {
		const { rows, poolLeft } = buildRoutePool([]);
		assert.equal(rows.length, 0);
		assert.equal(poolLeft.length, 6);
	});
});

// --- Issue #1387: Namensraum-Bruecke Katalog-ID -> Korridor-Metrik ---
// Nutzersicht: im Reiter "Wetter-Metriken" ist NUR "Nullgradgrenze"
// (freezing_level) angehakt; im Reiter "Wertebereiche" bot "+ Metrik" die
// Schneefallgrenze (snow_line) trotzdem nicht an. Go
// (internal/model/trip.go::catalogIDToAlertMetrics) und Python
// (weather_change_detection.py::catalog_id_to_alert_metrics) bilden BEIDE
// Katalog-IDs auf snow_line ab — nur diese dritte Schicht war gedriftet.
describe('buildRoutePool — Katalog-Filter (Issue #1387)', () => {
	test('nur "Nullgradgrenze" (freezing_level) aktiv -> snow_line steht im poolLeft', () => {
		const { poolLeft } = buildRoutePool([], [
			{ metric_id: 'freezing_level', enabled: true },
		]);
		assert.equal(
			poolLeft.some((m) => m.metric === 'snow_line'),
			true,
			'Schneefallgrenze fehlt im "+ Metrik"-Pool, obwohl Nullgradgrenze aktiv ist'
		);
	});

	// Regressionsschutz: der bereits vorhandene Pfad darf nicht kaputtgehen.
	test('nur "Schneefallgrenze" (snowfall_limit) aktiv -> snow_line steht weiterhin im poolLeft', () => {
		const { poolLeft } = buildRoutePool([], [
			{ metric_id: 'snowfall_limit', enabled: true },
		]);
		assert.equal(poolLeft.some((m) => m.metric === 'snow_line'), true);
	});

	test('beide aktiv -> snow_line erscheint genau EINMAL (keine Dublette)', () => {
		const { poolLeft } = buildRoutePool([], [
			{ metric_id: 'freezing_level', enabled: true },
			{ metric_id: 'snowfall_limit', enabled: true },
		]);
		assert.equal(poolLeft.filter((m) => m.metric === 'snow_line').length, 1);
	});

	test('freezing_level deaktiviert -> snow_line bleibt draussen', () => {
		const { poolLeft } = buildRoutePool([], [
			{ metric_id: 'freezing_level', enabled: false },
		]);
		assert.equal(poolLeft.some((m) => m.metric === 'snow_line'), false);
	});
});

// --- Issue #1429: Min/Max-Unterscheidung bei geteiltem Katalog-Label ---
// (AC-1/AC-2) buildRouteMetricDefsFromCatalog mappt entry.aggregation_label
// nach RouteMetricDef.aggregationLabel — exakt wie buildCompareMetricDefs es
// bereits fuer CompareMetricDef tut.
describe('buildRouteMetricDefsFromCatalog — Issue #1429 aggregationLabel', () => {
	test('AC-1: Katalog-Eintrag mit aggregation_label liefert aggregationLabel im RouteMetricDef', () => {
		const defs = buildRouteMetricDefsFromCatalog(CATALOG_FIXTURE.metrics);
		const windChillMin = defs.find((d) => d.metric === 'wind_chill_min_c');
		const windChillMax = defs.find((d) => d.metric === 'wind_chill_max_c');
		assert.equal(windChillMin?.aggregationLabel, 'Minimum');
		assert.equal(windChillMax?.aggregationLabel, 'Maximum');
	});

	test('AC-2: Katalog-Eintrag ohne aggregation_label liefert aggregationLabel===undefined, kein erfundener Key', () => {
		const defs = buildRouteMetricDefsFromCatalog([
			{ key: 'wind_max_kmh', label: 'Wind', unit: 'km/h', rangeMin: 0, rangeMax: 100, step: 5 },
		]);
		const def = defs.find((d) => d.metric === 'wind_max_kmh');
		assert.ok(def);
		assert.equal(def?.aggregationLabel, undefined);
		assert.equal('aggregationLabel' in (def as object), false);
	});
});

// --- addRow / removeRow / patchRow — Reducer ---
describe('addRow / removeRow / patchRow', () => {
	test('addRow uebernimmt Default-Range + Kontext-Defaults der Metrik', () => {
		const { rows, poolLeft } = buildRoutePool([]);
		const next = addRow(rows, poolLeft, 'thunder_level', ROUTE_CTX_DEFAULTS);
		assert.equal(next.rows.length, 1);
		assert.equal(next.rows[0].metric, 'thunder_level');
		assert.equal(next.rows[0].notify, true); // route default
		assert.equal(next.rows[0].mark, false);
		assert.equal(next.poolLeft.some((m) => m.metric === 'thunder_level'), false);
	});

	test('removeRow entfernt die Zeile', () => {
		const { rows } = buildRoutePool([
			{ metric: 'wind_gust', range: [null, 55], notify: true, mark: false },
		]);
		const next = removeRow(rows, 'wind_gust');
		assert.equal(next.length, 0);
	});

	test('patchRow aktualisiert nur die betroffene Zeile', () => {
		const { rows } = buildRoutePool([
			{ metric: 'wind_gust', range: [null, 55], notify: true, mark: false },
			{ metric: 'snow_line', range: [1500, null], notify: true, mark: false },
		]);
		const next = patchRow(rows, 'wind_gust', { max: 70, mark: true });
		assert.equal(next.find((r) => r.metric === 'wind_gust')?.max, 70);
		assert.equal(next.find((r) => r.metric === 'wind_gust')?.mark, true);
		assert.equal(next.find((r) => r.metric === 'snow_line')?.max, null);
	});
});

// --- Issue #1429 (AC-3/AC-4): aggregationLabel-Durchreichung fuer bereits
// gespeicherte UND neu hinzugefuegte route-Zeilen (extraDefs aus dem
// zentralen Katalog, #1425 S2 Teil 1). ---
describe('buildRoutePool — Issue #1429 aggregationLabel bei gespeicherter Zeile', () => {
	test('AC-3: gespeicherte wind_chill_min_c-Zeile traegt aggregationLabel aus extraDefs', () => {
		const extraDefs = buildRouteMetricDefsFromCatalog(CATALOG_FIXTURE.metrics);
		const { rows } = buildRoutePool(
			[{ metric: 'wind_chill_min_c', range: [-5, null], notify: false, mark: true }],
			undefined,
			extraDefs
		);
		const row = rows.find((r) => r.metric === 'wind_chill_min_c');
		assert.equal(row?.aggregationLabel, 'Minimum');
	});

	// Nicht-Regression: eine der fest verdrahteten 6 route-Metriken (kein
	// Katalog-Kollisions-Label) bleibt ohne aggregationLabel.
	test('Nicht-Regression: wind_gust (fest verdrahtete Route-Metrik) bleibt ohne aggregationLabel', () => {
		const { rows } = buildRoutePool([
			{ metric: 'wind_gust', range: [null, 55], notify: true, mark: false },
		]);
		assert.equal(rows[0].aggregationLabel, undefined);
	});
});

describe('addRow — Issue #1429 aggregationLabel bei neu hinzugefuegter Zeile', () => {
	test('AC-4: addRow uebernimmt aggregationLabel der aus poolLeft gefundenen Def', () => {
		const extraDefs = buildRouteMetricDefsFromCatalog(CATALOG_FIXTURE.metrics);
		const { poolLeft } = buildRoutePool([], undefined, extraDefs);
		const next = addRow([], poolLeft, 'wind_chill_max_c', ROUTE_CTX_DEFAULTS);
		const row = next.rows.find((r) => r.metric === 'wind_chill_max_c');
		assert.equal(row?.aggregationLabel, 'Maximum');
	});
});

// --- AC-12: mind. eine Grenze ist Pflicht ---
describe('validateCorridorRows — AC-12', () => {
	test('blockt, wenn eine Zeile beidseitig offen ist', () => {
		const { rows } = buildRoutePool([
			{ metric: 'wind_gust', range: [null, null], notify: true, mark: false },
		]);
		const result = validateCorridorRows(rows);
		assert.equal(result.valid, false);
		assert.equal(result.errors.length, 1);
	});

	// Fresh-Eyes-Fund (Lokalisierung): Fehlermeldung muss das deutsche
	// Metrik-Label zeigen ("Böen"), nicht den internen Bezeichner ("wind_gust").
	test('Fehlermeldung nennt das deutsche Label, nicht den internen Bezeichner', () => {
		const { rows } = buildRoutePool([
			{ metric: 'wind_gust', range: [null, null], notify: true, mark: false },
		]);
		const result = validateCorridorRows(rows);
		assert.deepEqual(result.errors, ['Böen']);
		assert.equal(result.errors.includes('wind_gust'), false);
	});

	test('gueltig, wenn jede Zeile mind. eine Grenze hat', () => {
		const { rows } = buildRoutePool([
			{ metric: 'wind_gust', range: [null, 55], notify: true, mark: false },
		]);
		assert.equal(validateCorridorRows(rows).valid, true);
	});
});

// --- AC-11: notify + mark gleichzeitig blockt NICHT ---
describe('validateCorridorRows — AC-11 keine Blockade bei notify+mark', () => {
	test('beide Wirkungen aktiv + Grenze gesetzt -> gueltig', () => {
		const { rows } = buildRoutePool([
			{ metric: 'wind_gust', range: [null, 55], notify: true, mark: true },
		]);
		assert.equal(validateCorridorRows(rows).valid, true);
	});
});

// --- Save-Payload: RMW, metric_alert_levels bleibt seit #1371 ein reiner
// Pass-Through — der Reiter Wertebereiche setzt keine Alarm-Stufen mehr. ---
describe('buildCorridorSavePayload — #1371: metric_alert_levels ist reiner Pass-Through', () => {
	test('baut corridors[] + gibt metric_alert_levels unveraendert zurueck (RMW, kein notify-Einfluss)', () => {
		const { rows } = buildRoutePool([
			{ metric: 'wind_gust', range: [null, 55], notify: false, mark: false },
		]);
		const original = {
			wind_gust: 'sensibel' as const,
			temperature_change: 'standard' as const, // nicht route-Pool -> muss erhalten bleiben
		};
		const payload = buildCorridorSavePayload(rows, original);
		assert.deepEqual(payload.corridors, [
			{ metric: 'wind_gust', range: [null, 55], notify: false, mark: false },
		]);
		assert.deepEqual(payload.metric_alert_levels, original, '#1371 FAIL: metric_alert_levels wurde veraendert');
	});

	// AC-3 (ex-F002): "✕ entfernen" darf metric_alert_levels seit #1371 nicht
	// mehr auf "off" setzen — die Empfindlichkeit bleibt exklusiv beim Reiter Alarme.
	test('AC-3: entfernte Zeile veraendert metric_alert_levels NICHT (kein stilles "off")', () => {
		const { rows } = buildRoutePool([
			{ metric: 'wind_gust', range: [null, 55], notify: true, mark: false },
		]);
		const afterRemove = removeRow(rows, 'wind_gust');
		const payload = buildCorridorSavePayload(afterRemove, { wind_gust: 'sensibel' });
		assert.equal(payload.metric_alert_levels.wind_gust, 'sensibel', '#1371 AC-3 FAIL: auf "off" gesetzt');
		assert.equal(payload.corridors.length, 0);
	});

	// AC-2: nur die Grenze (min/max) aendern darf die Alarm-Stufe nicht anfassen.
	test('AC-2: Grenze aendern laesst metric_alert_levels unveraendert (notify=true wirkungslos)', () => {
		const { rows } = buildRoutePool([
			{ metric: 'wind_gust', range: [null, 55], notify: true, mark: false },
		]);
		const changed = patchRow(rows, 'wind_gust', { max: 80 });
		const payload = buildCorridorSavePayload(changed, { wind_gust: 'sensibel' });
		assert.equal(payload.metric_alert_levels.wind_gust, 'sensibel');
		assert.equal(payload.corridors[0].range[1], 80);
	});
});

// F003 (Adversary, LOW): manuelle Zahleneingabe darf min/max nicht kreuzen
// lassen — dieselbe Clamp-Logik wie beim Drag, nur null-sicher (offene
// Grenze bleibt offen). Bewusste Abweichung vom JSX (das dieselbe Lücke
// hat): funktionale Korrektheit schlägt Bug-Treue.
describe('clampBoundInput — F003', () => {
	test('numerischer Wert wird geclamped wie beim Drag', () => {
		assert.equal(clampBoundInput(80, 'min', { min: null, max: 50 }), 50);
		assert.equal(clampBoundInput(10, 'max', { min: 30, max: null }), 30);
	});

	test('null (offene Grenze) bleibt unveraendert', () => {
		assert.equal(clampBoundInput(null, 'min', { min: null, max: 50 }), null);
	});

	test('Gegenseite offen -> kein Clamping', () => {
		assert.equal(clampBoundInput(999, 'min', { min: null, max: null }), 999);
	});
});

// --- Band-Drag: Pointer-Position -> Wert (PO-Vorgabe: Geste muss funktionieren) ---
describe('valueAtPointer', () => {
	test('am linken Track-Rand -> scale-Minimum', () => {
		assert.equal(valueAtPointer(100, 100, 200, [0, 100], 5), 0);
	});

	test('am rechten Track-Rand -> scale-Maximum', () => {
		assert.equal(valueAtPointer(300, 100, 200, [0, 100], 5), 100);
	});

	test('mittig -> gerundeter Wert, snap auf step', () => {
		assert.equal(valueAtPointer(200, 100, 200, [0, 100], 5), 50);
	});

	test('clientX vor dem Track -> geclamped auf scale-Minimum', () => {
		assert.equal(valueAtPointer(0, 100, 200, [0, 100], 5), 0);
	});

	test('clientX hinter dem Track -> geclamped auf scale-Maximum', () => {
		assert.equal(valueAtPointer(9999, 100, 200, [0, 100], 5), 100);
	});

	test('snap auf ungeraden step (step=7 bei scale[0,120])', () => {
		// t=0.5 -> raw=60 -> gerundet auf naechstes Vielfaches von 7 = 63
		assert.equal(valueAtPointer(200, 100, 200, [0, 120], 7), 63);
	});
});

describe('clampDragValue — min darf max nicht kreuzen und umgekehrt', () => {
	test('min-Drag ueber aktuellem max -> auf max geclamped', () => {
		assert.equal(clampDragValue('min', 80, null, 50), 50);
	});

	test('max-Drag unter aktuellem min -> auf min geclamped', () => {
		assert.equal(clampDragValue('max', 10, 30, null), 30);
	});

	test('Gegenseite offen (null) -> kein Clamping', () => {
		assert.equal(clampDragValue('min', 999, null, null), 999);
		assert.equal(clampDragValue('max', -999, null, null), -999);
	});
});

// F005 (Staging-Adversary, HIGH, AC-12-Rest): bei Invaliditaet darf der
// Save-Indikator nicht das "Gespeichert ✓" des letzten erfolgreichen Saves
// stehen lassen — widerspruechliches Feedback neben dem Fehlerbanner.
// saveGateDecision() ist die reine Entscheidung, welche Aktion die duenne
// DOM-Verdrahtung auf dem BESTEHENDEN saveController ausloest
// (schedule() vs. setDirty() — Store selbst bleibt unveraendert).
describe('saveGateDecision — F005', () => {
	test('gueltige Zeilen -> "schedule"', () => {
		const { rows } = buildRoutePool([
			{ metric: 'wind_gust', range: [null, 55], notify: true, mark: false },
		]);
		assert.equal(saveGateDecision(rows), 'schedule');
	});

	test('beidseitig offene Zeile (AC-12) -> "dirty" statt Save', () => {
		const { rows } = buildRoutePool([
			{ metric: 'wind_gust', range: [null, null], notify: true, mark: false },
		]);
		assert.equal(saveGateDecision(rows), 'dirty');
	});
});

// ════════════════════════════════════════════════════════════════════════
// Issue #1231, Slice 4: CorridorEditor context="vergleich"
// ════════════════════════════════════════════════════════════════════════

// --- AC-3: confidence_pct darf im vergleich-Metrikpool nie auftauchen ---
// Fakten-Korrektur (Team-Lead, nach Slice-4-Erstlieferung): Katalog MUSS alle
// 14 ALL_METRICS abdecken, nicht nur die 10 alarmfaehigen — sonst verliert der
// Editor beim Speichern Corridor-Eintraege realer Nutzer (Slice-2-Migration
// hat ALLE ideal_ranges-Metriken migriert, nicht nur die 10 Alarm-Keys).
describe('TEST_DEFS (buildCompareMetricDefs) — AC-3 confidence_pct-Ausschluss + alle Katalog-Keys', () => {
	// Issue #1424 (AC-3): precip_type_dominant + wind_direction_deg taugen nicht
	// als Von/Bis-Bereich und sind seither aus dem Angebot gefiltert — sie
	// bleiben normale Wettergroessen (COMPARE_METRIC_KEYS), nur hier nicht mehr.
	test('enthaelt alle Endpoint-Katalog-Keys ausser den zwei AC-3-Ausnahmen, kein confidence_pct, nie leer (Vakuum-Schutz)', () => {
		const ids = TEST_DEFS.map((m) => m.metric).sort();
		const expected = CATALOG_FIXTURE.metrics
			.map((m) => m.key)
			.filter((k) => k !== 'precip_type_dominant' && k !== 'wind_direction_deg')
			.sort();
		assert.ok(expected.length > 0, 'Vorbedingung verletzt: CATALOG_FIXTURE ist leer');
		assert.deepEqual(ids, expected);
		assert.equal(ids.includes('confidence_pct'), false);
		assert.equal(ids.includes('precip_type_dominant'), false, 'AC-3 FAIL: precip_type_dominant noch im Angebot');
		assert.equal(ids.includes('wind_direction_deg'), false, 'AC-3 FAIL: wind_direction_deg noch im Angebot');
	});

	test('thunder_level_max ist kind "ordinal" mit 3 Stufen (kein/mittel/hoch)', () => {
		const thunder = TEST_DEFS.find((m) => m.metric === 'thunder_level_max');
		assert.equal(thunder?.kind, 'ordinal');
		assert.deepEqual(thunder?.ordinalLabels, ['kein', 'mittel', 'hoch']);
		assert.deepEqual(thunder?.scale, [0, 2]);
	});

	// notify-Bruecke (compare_alert.py::_SUMMARY_KEY_TO_CATALOG_ID) kennt nur
	// 10 Metriken — die 4 uebrigen sind reine "mark"-Metriken (kein Alarm-Abgleich).
	test('alarmCapable=true fuer die 10 Alarm-Keys, false fuer die 4 reinen Vergleichs-Metriken', () => {
		const byId = new Map(TEST_DEFS.map((m) => [m.metric, m.alarmCapable]));
		for (const k of ['temp_max_c', 'temp_min_c', 'wind_max_kmh', 'gust_max_kmh', 'precip_sum_mm',
			'thunder_level_max', 'visibility_min_m', 'snow_new_sum_cm', 'cape_max_jkg', 'freezing_level_m']) {
			assert.equal(byId.get(k), true, `${k} sollte alarmCapable sein`);
		}
		for (const k of ['snow_depth_cm', 'sunny_hours_h', 'cloud_avg_pct', 'uv_index_max']) {
			assert.equal(byId.get(k), false, `${k} sollte NICHT alarmCapable sein`);
		}
	});
});

// --- buildComparePool: Zeilen aus preset.corridors[] (vergleich-Namensraum) ---
describe('buildComparePool', () => {
	test('baut Zeile aus vorhandenem Corridor + Metrik-Definition', () => {
		const { rows, poolLeft } = buildComparePool([
			{ metric: 'temp_max_c', range: [null, 30], notify: false, mark: true },
		], TEST_DEFS);
		assert.equal(rows.length, 1);
		// #1401 A1: der Name kommt aus dem zentralen Register, die Auswertung
		// steht als eigenes Feld daneben (nicht mehr im Namen).
		assert.equal(rows[0].label, 'Temperatur');
		assert.equal(rows[0].aggregationLabel, 'Maximum');
		assert.equal(rows[0].unit, '°C');
		assert.equal(rows[0].max, 30);
		assert.equal(rows[0].mark, true);
		// Fix-Loop 1 (F005): Erwartung aus TEST_DEFS.length ableiten
		// statt Hardcode (ALL_METRICS waechst, s. Import-Kommentar oben).
		assert.equal(poolLeft.length, TEST_DEFS.length - 1);
		assert.equal(poolLeft.some((m) => m.metric === 'temp_max_c'), false);
	});

	test('leere corridors -> alle Metriken im poolLeft, keine rows', () => {
		const { rows, poolLeft } = buildComparePool([], TEST_DEFS);
		assert.equal(rows.length, 0);
		assert.equal(poolLeft.length, TEST_DEFS.length);
	});

	// BUG-DATALOSS-Regressionstest (Team-Lead-Fund): echter Nutzer henning hat
	// einen sunny_hours_h-Corridor aus der Slice-2-Migration. Der 10er-Pool
	// (vor der Korrektur) kannte diese Metrik nicht -> Zeile verschwand aus
	// rows UND poolLeft -> beim Speichern verloren. Muss jetzt geladen werden.
	test('Corridor mit nicht-alarmfaehiger Metrik (sunny_hours_h) geht NICHT verloren', () => {
		const { rows, poolLeft } = buildComparePool([
			{ metric: 'sunny_hours_h', range: [7, 12], notify: false, mark: true },
		], TEST_DEFS);
		assert.equal(rows.length, 1);
		assert.equal(rows[0].metric, 'sunny_hours_h');
		assert.equal(rows[0].min, 7);
		assert.equal(rows[0].max, 12);
		assert.equal(rows[0].alarmCapable, false);
		assert.equal(poolLeft.length, TEST_DEFS.length - 1);
	});
});

// --- addCompareRow: Kontext-Defaults notify=false/mark=true (PO-Vorgabe) ---
describe('addCompareRow — VERGLEICH_CTX_DEFAULTS', () => {
	test('Defaults sind notify=false, mark=true (umgekehrt zu route)', () => {
		assert.deepEqual(VERGLEICH_CTX_DEFAULTS, { notify: false, mark: true });
	});

	test('addCompareRow uebernimmt Default-Range + Kontext-Defaults der Metrik', () => {
		const { rows, poolLeft } = buildComparePool([], TEST_DEFS);
		const next = addCompareRow(rows, poolLeft, 'wind_max_kmh', TEST_DEFS, VERGLEICH_CTX_DEFAULTS);
		assert.equal(next.rows.length, 1);
		assert.equal(next.rows[0].metric, 'wind_max_kmh');
		assert.equal(next.rows[0].notify, false);
		assert.equal(next.rows[0].mark, true);
		assert.equal(next.poolLeft.some((m) => m.metric === 'wind_max_kmh'), false);
	});

	test('addCompareRow fuer thunder_level_max setzt Ordinal-Default (kind + Bounds)', () => {
		const { rows, poolLeft } = buildComparePool([], TEST_DEFS);
		const next = addCompareRow(rows, poolLeft, 'thunder_level_max', TEST_DEFS, VERGLEICH_CTX_DEFAULTS);
		assert.equal(next.rows[0].kind, 'ordinal');
		assert.equal(next.rows[0].max, 0); // NONE, aus SUMMER_TREKKING-Default gespiegelt
	});
});

// --- Dual-Write: mark -> ideal_ranges, notify -> active_metrics/metric_alert_levels ---
describe('buildCompareCorridorSavePayload — Dual-Write (mark -> ideal_ranges)', () => {
	test('mark=true numerische Zeile -> ideal_ranges[metric] = {min?,max?}, offene Seite weggelassen', () => {
		const { rows } = buildComparePool([
			{ metric: 'temp_max_c', range: [null, 30], notify: false, mark: true },
		], TEST_DEFS);
		const payload = buildCompareCorridorSavePayload(rows, [], {
			idealRanges: {},
			activeMetricKeys: [],
			metricAlertLevels: {},
		});
		assert.deepEqual(payload.idealRanges.temp_max_c, { max: 30 });
		assert.equal('min' in payload.idealRanges.temp_max_c, false);
	});

	test('mark=false -> Key wird aus ideal_ranges entfernt', () => {
		const { rows } = buildComparePool([
			{ metric: 'temp_max_c', range: [null, 30], notify: false, mark: false },
		], TEST_DEFS);
		const payload = buildCompareCorridorSavePayload(rows, [], {
			idealRanges: { temp_max_c: { max: 30 } },
			activeMetricKeys: [],
			metricAlertLevels: {},
		});
		assert.equal('temp_max_c' in payload.idealRanges, false);
	});

	test('ideal_ranges-Keys ohne Zeile in DIESER Session (z.B. noch nicht geladen) bleiben erhalten (RMW)', () => {
		const { rows } = buildComparePool([
			{ metric: 'temp_max_c', range: [null, 30], notify: false, mark: true },
		], TEST_DEFS);
		const payload = buildCompareCorridorSavePayload(rows, [], {
			idealRanges: { snow_depth_cm: { min: 30, max: 200 } },
			activeMetricKeys: [],
			metricAlertLevels: {},
		});
		assert.deepEqual(payload.idealRanges.snow_depth_cm, { min: 30, max: 200 });
		assert.deepEqual(payload.idealRanges.temp_max_c, { max: 30 });
	});

	// BUG-DATALOSS-Regressionstest (Team-Lead-Fund): sunny_hours_h ist NICHT
	// alarmfaehig, muss aber trotzdem vollstaendig im corridors[]-Output
	// landen (kein stiller Drop) UND editierbar bleiben (mark spiegelt normal).
	test('nicht-alarmfaehige Metrik (sunny_hours_h) geht beim Speichern NICHT verloren', () => {
		const { rows } = buildComparePool([
			{ metric: 'sunny_hours_h', range: [7, 12], notify: false, mark: true },
		], TEST_DEFS);
		const payload = buildCompareCorridorSavePayload(rows, [], {
			idealRanges: {},
			activeMetricKeys: [],
			metricAlertLevels: {},
		});
		assert.deepEqual(
			payload.corridors,
			[{ metric: 'sunny_hours_h', range: [7, 12], notify: false, mark: true }]
		);
		assert.deepEqual(payload.idealRanges.sunny_hours_h, { min: 7, max: 12 });
	});

	// Defensiv: notify auf einer nicht-alarmfaehigen Zeile darf NIE
	// active_metrics/metric_alert_levels beeinflussen — die Alarm-Bruecke
	// (compare_alert.py::_SUMMARY_KEY_TO_CATALOG_ID) kennt diese Metriken nicht.
	test('notify=true auf nicht-alarmfaehiger Zeile wird ignoriert (kein Alarm-Abgleich)', () => {
		const { rows } = buildComparePool([
			{ metric: 'sunny_hours_h', range: [7, 12], notify: true, mark: true },
		], TEST_DEFS);
		const payload = buildCompareCorridorSavePayload(rows, [], {
			idealRanges: {},
			activeMetricKeys: [],
			metricAlertLevels: {},
		});
		assert.equal(payload.activeMetricKeys.includes('sunny_hours_h'), false);
		assert.equal(payload.metricAlertLevels.sunny_hours_h, undefined);
	});

	test('Gewitter-Ordinal mark=true -> ideal_ranges.thunder_level_max spiegelt Enum-String (heutiges Format)', () => {
		const { rows } = buildComparePool([
			{ metric: 'thunder_level_max', range: [null, 0], notify: false, mark: true },
		], TEST_DEFS);
		const payload = buildCompareCorridorSavePayload(rows, [], {
			idealRanges: {},
			activeMetricKeys: [],
			metricAlertLevels: {},
		});
		assert.deepEqual(payload.idealRanges.thunder_level_max, { max: 'NONE' });
	});

	test('Gewitter-Ordinal ohne max (nur min gesetzt) -> keine Legacy-Repraesentation, Key entfernt', () => {
		const { rows } = buildComparePool([
			{ metric: 'thunder_level_max', range: [1, null], notify: false, mark: true },
		], TEST_DEFS);
		const payload = buildCompareCorridorSavePayload(rows, [], {
			idealRanges: { thunder_level_max: { max: 'HIGH' } },
			activeMetricKeys: [],
			metricAlertLevels: {},
		});
		assert.equal('thunder_level_max' in payload.idealRanges, false);
	});
});

// Issue #1311 (C1 von Epic #1301): notify steuert NICHT MEHR active_metrics —
// das gehoert seit C1 exklusiv dem Wetter-Metriken-Tab (Spec Implementation
// Details Abschnitt 3).
// Issue #1371: notify steuert seither AUCH NICHT MEHR metric_alert_levels —
// der Reiter Wertebereiche markiert nur noch, die Alarm-Empfindlichkeit setzt
// exklusiv der Reiter Alarme. Ersetzt die vor #1371 gueltigen
// "notify -> metric_alert_levels"-Erwartungen.
describe('buildCompareCorridorSavePayload — #1371: notify <-> active_metrics UND metric_alert_levels entkoppelt', () => {
	test('AC-2: notify=true veraendert weder activeMetricKeys noch metricAlertLevels (reiner Pass-Through)', () => {
		const { rows } = buildComparePool([
			{ metric: 'wind_max_kmh', range: [0, 50], notify: true, mark: false },
		], TEST_DEFS);
		const payload = buildCompareCorridorSavePayload(rows, [], {
			idealRanges: {},
			activeMetricKeys: [],
			metricAlertLevels: { wind_max_kmh: 'sensibel' },
		});
		assert.deepEqual(payload.activeMetricKeys, []);
		assert.equal(payload.metricAlertLevels.wind_max_kmh, 'sensibel');
	});

	test('AC-2: notify=false veraendert weder activeMetricKeys noch metricAlertLevels (kein stilles "off")', () => {
		const { rows } = buildComparePool([
			{ metric: 'wind_max_kmh', range: [0, 50], notify: false, mark: true },
		], TEST_DEFS);
		const payload = buildCompareCorridorSavePayload(rows, [], {
			idealRanges: {},
			activeMetricKeys: ['wind_max_kmh'],
			metricAlertLevels: { wind_max_kmh: 'sensibel' },
		});
		assert.deepEqual(payload.activeMetricKeys, ['wind_max_kmh']);
		assert.equal(payload.metricAlertLevels.wind_max_kmh, 'sensibel');
	});

	// #1191-Erhalt: alle Zeilen notify=false -> bewusst leeres [] bleibt leer,
	// wird NICHT durch das Fehlen der Zeilen "reaktiviert".
	test('#1191: alle Zeilen notify=false -> active_metrics bleibt [] (kein Reaktivieren)', () => {
		const { rows } = buildComparePool([
			{ metric: 'wind_max_kmh', range: [0, 50], notify: false, mark: true },
			{ metric: 'temp_max_c', range: [null, 30], notify: false, mark: true },
		], TEST_DEFS);
		const payload = buildCompareCorridorSavePayload(rows, [], {
			idealRanges: {},
			activeMetricKeys: [],
			metricAlertLevels: {},
		});
		assert.deepEqual(payload.activeMetricKeys, []);
	});

	test('activeMetricKeys ist reiner Pass-Through von original — notify fuegt nichts mehr hinzu (RMW)', () => {
		const { rows } = buildComparePool([
			{ metric: 'wind_max_kmh', range: [0, 50], notify: true, mark: false },
		], TEST_DEFS);
		const payload = buildCompareCorridorSavePayload(rows, [], {
			idealRanges: {},
			activeMetricKeys: ['temp_min_c'],
			metricAlertLevels: {},
		});
		assert.ok(payload.activeMetricKeys.includes('temp_min_c'));
		assert.equal(payload.activeMetricKeys.includes('wind_max_kmh'), false);
	});

	// AC-3 (ex-F002): entfernte Zeile hinterlaesst weder einen verwaisten
	// active_metrics-/ideal_ranges-Eintrag NOCH eine veraenderte Alarm-Stufe.
	test('AC-3: removedMetrics entfernen aus active_metrics UND ideal_ranges, metricAlertLevels bleibt unveraendert', () => {
		const { rows } = buildComparePool([
			{ metric: 'wind_max_kmh', range: [0, 50], notify: true, mark: true },
		], TEST_DEFS);
		const afterRemove = removeRow(rows, 'wind_max_kmh');
		const payload = buildCompareCorridorSavePayload(afterRemove, ['wind_max_kmh'], {
			idealRanges: { wind_max_kmh: { min: 0, max: 50 } },
			activeMetricKeys: ['wind_max_kmh'],
			metricAlertLevels: { wind_max_kmh: 'sensibel' },
		});
		assert.equal(payload.metricAlertLevels.wind_max_kmh, 'sensibel', '#1371 AC-3 FAIL: metricAlertLevels veraendert');
		assert.equal(payload.activeMetricKeys.includes('wind_max_kmh'), false);
		assert.equal('wind_max_kmh' in payload.idealRanges, false);
		assert.equal(payload.corridors.length, 0);
	});
});

// --- Ordinal-Snap: valueAtPointer/clampDragValue funktionieren generisch auch
// fuer die 3-Stufen-Gewitter-Skala [0,2] (Wiederverwendung, keine Sonderlogik). ---
describe('Ordinal-Snap fuer Gewitter (scale [0,2], step 1)', () => {
	test('mittig auf der 3-Stufen-Skala snapt auf Stufe 1 (mittel)', () => {
		assert.equal(valueAtPointer(200, 100, 200, [0, 2], 1), 1);
	});

	test('am rechten Rand -> Stufe 2 (hoch)', () => {
		assert.equal(valueAtPointer(300, 100, 200, [0, 2], 1), 2);
	});
});

// ════════════════════════════════════════════════════════════════════════
// Wizard-Create-Prefill (Team-Lead-Korrektur, PO-Linie „nichts Neues erfinden
// — wie heute"): Step3Idealwerte befuellte den Create-Wizard automatisch aus
// dem Aktivitaetsprofil. buildComparePrefillRows() spiegelt das exakt.
// ════════════════════════════════════════════════════════════════════════
describe('buildComparePrefillRows — Wizard-Create-Default (wie Step3Idealwerte heute)', () => {
	test('ALLGEMEIN: 4 Profil-Metriken, alle mark=true+notify=true (alle 4 sind alarmfaehig)', () => {
		const rows = buildComparePrefillRows('ALLGEMEIN', TEST_DEFS);
		const ids = rows.map((r) => r.metric).sort();
		assert.deepEqual(ids, ['precip_sum_mm', 'temp_max_c', 'visibility_min_m', 'wind_max_kmh']);
		for (const r of rows) {
			assert.equal(r.mark, true, `${r.metric} sollte mark=true sein`);
			assert.equal(r.notify, true, `${r.metric} sollte notify=true sein (alarmfaehig)`);
		}
		// IDEAL_DEFAULTS.ALLGEMEIN.temp_max_c = {min:15,max:35}
		const tempMax = rows.find((r) => r.metric === 'temp_max_c')!;
		assert.equal(tempMax.min, 15);
		assert.equal(tempMax.max, 35);
		// visibility_min_m hat KEIN ALLGEMEIN-Default -> Fallback aus COMPARE_METRIC_DEFS
		const vis = rows.find((r) => r.metric === 'visibility_min_m')!;
		assert.equal(vis.min, 2000);
		assert.equal(vis.max, 10000);
	});

	test('WINTERSPORT: 5 Profil-Metriken, notify nur bei den alarmfaehigen (snow_new_sum_cm/wind_max_kmh)', () => {
		const rows = buildComparePrefillRows('WINTERSPORT', TEST_DEFS);
		const byId = new Map(rows.map((r) => [r.metric, r]));
		assert.equal(byId.size, 5);
		// alarmfaehig
		assert.equal(byId.get('snow_new_sum_cm')?.notify, true);
		assert.equal(byId.get('wind_max_kmh')?.notify, true);
		// nicht alarmfaehig -> notify bleibt false, aber mark=true (Zeile existiert, editierbar)
		assert.equal(byId.get('snow_depth_cm')?.notify, false);
		assert.equal(byId.get('sunny_hours_h')?.notify, false);
		assert.equal(byId.get('cloud_avg_pct')?.notify, false);
		for (const m of ['snow_depth_cm', 'sunny_hours_h', 'cloud_avg_pct', 'snow_new_sum_cm', 'wind_max_kmh']) {
			assert.equal(byId.get(m)?.mark, true);
		}
		// sunny_hours_h hat in KEINEM Profil einen IDEAL_DEFAULTS-Eintrag -> Sinnwert-Fallback
		assert.equal(byId.get('sunny_hours_h')?.min, 4);
		assert.equal(byId.get('sunny_hours_h')?.max, null);
	});

	test('SUMMER_TREKKING: Gewitter-Ordinal-Default aus Enum-String "NONE" gespiegelt', () => {
		const rows = buildComparePrefillRows('SUMMER_TREKKING', TEST_DEFS);
		const thunder = rows.find((r) => r.metric === 'thunder_level_max')!;
		assert.equal(thunder.kind, 'ordinal');
		assert.equal(thunder.max, 0); // NONE
		assert.equal(thunder.notify, true); // thunder_level_max ist alarmfaehig
		assert.equal(thunder.mark, true);
	});

	test('unbekannter/keiner Profil-Key -> Fallback ALLGEMEIN (analog Step3Idealwerte)', () => {
		const rows = buildComparePrefillRows('ALLGEMEIN', TEST_DEFS);
		assert.equal(rows.length, 4);
	});
});

// ════════════════════════════════════════════════════════════════════════
// Adversary-Fix-Loop (CRITICAL, Team-Lead nach Verdict BROKEN):
// F002 — "+ Metrik hinzufügen" darf laufende Alarme nicht stillschweigend
//        deaktivieren.
// F003 — Corridor-Eintraege ausserhalb des 14er-Katalogs duerfen beim
//        Speichern nicht verschwinden.
// ════════════════════════════════════════════════════════════════════════

describe('addCompareRow — F002 Bestandserhalt (wasActive)', () => {
	test('wasActive=true -> notify=true, unabhaengig vom Kontext-Default (kein stilles Alarm-Aus)', () => {
		const { rows, poolLeft } = buildComparePool([], TEST_DEFS);
		const next = addCompareRow(rows, poolLeft, 'temp_max_c', TEST_DEFS, VERGLEICH_CTX_DEFAULTS, true);
		assert.equal(next.rows[0].notify, true);
	});

	test('wasActive=false (Standardfall) -> notify=Kontext-Default (unveraendertes Verhalten)', () => {
		const { rows, poolLeft } = buildComparePool([], TEST_DEFS);
		const next = addCompareRow(rows, poolLeft, 'temp_max_c', TEST_DEFS, VERGLEICH_CTX_DEFAULTS, false);
		assert.equal(next.rows[0].notify, false);
	});

	test('wasActive=true auf nicht-alarmfaehiger Metrik -> notify bleibt false (defensiv)', () => {
		const { rows, poolLeft } = buildComparePool([], TEST_DEFS);
		const next = addCompareRow(rows, poolLeft, 'sunny_hours_h', TEST_DEFS, VERGLEICH_CTX_DEFAULTS, true);
		assert.equal(next.rows[0].notify, false);
	});

	// Exakter mallorca-Fall (Team-Lead): active_metrics voll (10 Keys),
	// corridors fehlend. add(temp_max_c) darf active_metrics NICHT verkleinern.
	test('Mallorca-Szenario: active_metrics bleibt vollstaendig inkl. temp_max_c nach add()', () => {
		const activeMetricKeys = [
			'temp_max_c', 'temp_min_c', 'wind_max_kmh', 'gust_max_kmh', 'precip_sum_mm',
			'thunder_level_max', 'visibility_min_m', 'snow_new_sum_cm', 'cape_max_jkg', 'freezing_level_m',
		];
		const { rows, poolLeft } = buildComparePool([], TEST_DEFS); // corridors fehlt (Legacy, nicht migriert)
		const wasActive = activeMetricKeys.includes('temp_max_c');
		const next = addCompareRow(rows, poolLeft, 'temp_max_c', TEST_DEFS, VERGLEICH_CTX_DEFAULTS, wasActive);
		const payload = buildCompareCorridorSavePayload(next.rows, [], {
			idealRanges: {},
			activeMetricKeys,
			metricAlertLevels: {},
		});
		assert.deepEqual([...payload.activeMetricKeys].sort(), [...activeMetricKeys].sort());
		assert.ok(payload.activeMetricKeys.includes('temp_max_c'));
	});
});

describe('buildComparePool — F003 unknownCorridors (Pass-Through)', () => {
	test('Corridor mit Metrik-ID ausserhalb des 14er-Katalogs landet in unknownCorridors, nicht in rows/poolLeft', () => {
		const { rows, unknownCorridors } = buildComparePool([
			{ metric: 'foo_bar', range: [1, 2], notify: false, mark: true },
		], TEST_DEFS);
		assert.equal(rows.some((r) => r.metric === 'foo_bar'), false);
		assert.equal(unknownCorridors.length, 1);
		assert.deepEqual(unknownCorridors[0], { metric: 'foo_bar', range: [1, 2], notify: false, mark: true });
	});

	test('bekannte + unbekannte Corridors gemischt -> beide korrekt getrennt', () => {
		const { rows, unknownCorridors } = buildComparePool([
			{ metric: 'temp_max_c', range: [null, 30], notify: false, mark: true },
			{ metric: 'foo_bar', range: [1, 2], notify: false, mark: true },
		], TEST_DEFS);
		assert.equal(rows.length, 1);
		assert.equal(unknownCorridors.length, 1);
	});
});

describe('buildCompareCorridorSavePayload — F003 unknownCorridors bleiben beim Speichern erhalten', () => {
	test('unknownCorridors werden unveraendert an corridors[] angehaengt', () => {
		const { rows } = buildComparePool([
			{ metric: 'temp_max_c', range: [null, 30], notify: false, mark: true },
		], TEST_DEFS);
		const unknown = [{ metric: 'foo_bar', range: [1, 2] as [number, number], notify: false, mark: true }];
		const payload = buildCompareCorridorSavePayload(rows, [], {
			idealRanges: {},
			activeMetricKeys: [],
			metricAlertLevels: {},
		}, unknown);
		assert.deepEqual(payload.corridors, [
			{ metric: 'temp_max_c', range: [null, 30], notify: false, mark: true },
			{ metric: 'foo_bar', range: [1, 2], notify: false, mark: true },
		]);
	});

	// Team-Lead-Vorgabe: Laden -> fremde (bekannte) Zeile aendern -> Save
	// byte-gleich fuer den unbekannten Eintrag.
	test('End-to-End: foo_bar-Corridor ueberlebt Laden->Aendern-einer-bekannten-Zeile->Save byte-gleich', () => {
		const { rows, unknownCorridors } = buildComparePool([
			{ metric: 'foo_bar', range: [1, 2], notify: false, mark: true },
			{ metric: 'wind_max_kmh', range: [0, 50], notify: false, mark: true },
		], TEST_DEFS);
		// User aendert NUR wind_max_kmh (bekannte Zeile) — foo_bar bleibt unangetastet.
		const changedRows = patchRow(rows, 'wind_max_kmh', { max: 60 });
		const payload = buildCompareCorridorSavePayload(changedRows, [], {
			idealRanges: {},
			activeMetricKeys: [],
			metricAlertLevels: {},
		}, unknownCorridors);
		const fooBar = payload.corridors.find((c) => c.metric === 'foo_bar');
		assert.deepEqual(fooBar, { metric: 'foo_bar', range: [1, 2], notify: false, mark: true });
		const windMax = payload.corridors.find((c) => c.metric === 'wind_max_kmh');
		assert.equal(windMax?.range[1], 60);
	});
});

// ════════════════════════════════════════════════════════════════════════
// Issue #1401 Scheibe A1 (AC-6): der Wertebereiche-Editor fuehrt Name und
// Auswertung GETRENNT — Zeilen wie Pool-Eintraege. Ohne das eigene Feld
// stuende in der Liste zweimal "Temperatur" ohne Unterscheidung.
// Spec: docs/specs/modules/fix_1401_a1_namensregister.md § AC-6
// ════════════════════════════════════════════════════════════════════════
describe('#1401 AC-6: Wertebereiche fuehren Name und Auswertung getrennt', () => {
	test('Pool-Eintraege tragen den Registernamen und die Auswertung als eigenes Feld', () => {
		const byMetric = new Map(TEST_DEFS.map((d) => [d.metric, d]));
		for (const [metric, name, auswertung] of [
			['temp_max_c', 'Temperatur', 'Maximum'],
			['temp_min_c', 'Temperatur', 'Minimum'],
			['cloud_avg_pct', 'Bewölkung', 'Mittel'],
			['sunny_hours_h', 'Sonnenstunden', 'Summe']
		] as const) {
			const def = byMetric.get(metric);
			assert.equal(def?.label, name, `${metric}: Name weicht vom Register ab`);
			assert.equal(def?.aggregationLabel, auswertung, `${metric}: Auswertung fehlt`);
			assert.ok(
				!def!.label.includes(auswertung),
				`${metric}: die Auswertung steckt im Namen statt daneben (${def?.label})`
			);
		}
	});

	test('hinzugefuegte Zeile und geladene Zeile fuehren beide Felder getrennt', () => {
		const { rows, poolLeft } = buildComparePool([
			{ metric: 'temp_min_c', range: [-5, null], notify: false, mark: true }
		], TEST_DEFS);
		assert.equal(rows[0].label, 'Temperatur');
		assert.equal(rows[0].aggregationLabel, 'Minimum');

		const next = addCompareRow(rows, poolLeft, 'temp_max_c', TEST_DEFS);
		const hinzugefuegt = next.rows.find((r) => r.metric === 'temp_max_c');
		assert.equal(hinzugefuegt?.label, 'Temperatur');
		assert.equal(hinzugefuegt?.aggregationLabel, 'Maximum');
		// Beide Zeilen bleiben unterscheidbar, obwohl der Name derselbe ist.
		assert.equal(next.rows.length, 2);
		assert.notEqual(next.rows[0].aggregationLabel, next.rows[1].aggregationLabel);
	});

	test('Prefill-Zeilen (Anlegen) fuehren die Auswertung ebenfalls mit', () => {
		const rows = buildComparePrefillRows('WINTERSPORT', TEST_DEFS);
		const sonne = rows.find((r) => r.metric === 'sunny_hours_h');
		assert.equal(sonne?.label, 'Sonnenstunden');
		assert.equal(sonne?.aggregationLabel, 'Summe');
	});
});

// Issue #1424 (S6 von #1372/#1374, Spec: fix_1424_wertebereiche_startwerte.md)
// AC-1 + AC-6: die zehn zuvor luecken-behafteten Groessen bekommen eine
// PO-freigegebene Vorgabe; saveGateDecision() muss "schedule" liefern (statt
// "dirty" wie vorher bei defaultMin/defaultMax=null,null).
describe('Issue #1424 AC-1/AC-6: die zehn neuen Startwerte', () => {
	const EXPECTED: Record<string, { min: number | null; max: number | null }> = {
		pop_max_pct: { min: null, max: 30 },
		humidity_avg_pct: { min: 30, max: 70 },
		dewpoint_avg_c: { min: null, max: 16 },
		pressure_avg_hpa: { min: 1010, max: null },
		cloud_low_avg_pct: { min: null, max: 50 },
		cloud_mid_avg_pct: { min: null, max: 50 },
		cloud_high_avg_pct: { min: null, max: 70 },
		wind_chill_min_c: { min: -5, max: null },
		wind_chill_max_c: { min: null, max: 30 },
		snowfall_limit_m: { min: 1500, max: null },
	};

	for (const [metric, expected] of Object.entries(EXPECTED)) {
		test(`${metric}: addCompareRow uebernimmt die Vorgabe, saveGateDecision -> "schedule" (nicht "dirty")`, () => {
			const { rows, poolLeft } = buildComparePool([], TEST_DEFS);
			const next = addCompareRow(rows, poolLeft, metric, TEST_DEFS);
			const row = next.rows.find((r) => r.metric === metric);
			assert.ok(row, `${metric}: keine Zeile erzeugt (fehlt in TEST_DEFS?)`);
			assert.equal(row!.min, expected.min, `AC-1 FAIL ${metric}.min weicht ab`);
			assert.equal(row!.max, expected.max, `AC-1 FAIL ${metric}.max weicht ab`);
			assert.equal(
				saveGateDecision(next.rows),
				'schedule',
				`AC-1 FAIL ${metric}: saveGateDecision liefert "dirty" — beidseitig offen, Speichern bleibt aus`
			);
			// AC-6: jeder gesetzte Wert liegt innerhalb der Skala und auf der Schrittweite.
			for (const bound of [row!.min, row!.max]) {
				if (bound == null) continue;
				assert.ok(
					bound >= row!.scale[0] && bound <= row!.scale[1],
					`AC-6 FAIL ${metric}: ${bound} ausserhalb der Skala [${row!.scale}]`
				);
				assert.equal(
					(bound - row!.scale[0]) % row!.step,
					0,
					`AC-6 FAIL ${metric}: ${bound} liegt nicht auf der Schrittweite ${row!.step}`
				);
			}
		});
	}
});

// AC-4 (Datenerhalt, BUG-DATALOSS-GR221/#102): ein frueher gespeicherter
// precip_type_dominant-Korridor (seit AC-3 nicht mehr im Angebot) muss ueber
// unknownCorridors erhalten bleiben, nicht verworfen werden.
describe('Issue #1424 AC-4: alter precip_type_dominant-Korridor bleibt beim Speichern erhalten', () => {
	test('buildComparePool sammelt ihn in unknownCorridors, buildCompareCorridorSavePayload haengt ihn unveraendert an', () => {
		const savedCorridor = { metric: 'precip_type_dominant', range: [1, 2] as [number, number], notify: false, mark: true };
		const { rows, poolLeft, unknownCorridors } = buildComparePool(
			[
				savedCorridor,
				{ metric: 'wind_max_kmh', range: [0, 50], notify: false, mark: true },
			],
			TEST_DEFS
		);
		assert.equal(
			rows.some((r) => r.metric === 'precip_type_dominant'),
			false,
			'AC-4 FAIL: precip_type_dominant taucht als Zeile auf, obwohl es nicht mehr im Angebot ist'
		);
		assert.equal(
			poolLeft.some((m) => m.metric === 'precip_type_dominant'),
			false,
			'AC-4 FAIL: precip_type_dominant taucht im "+ Metrik"-Pool auf'
		);
		assert.deepEqual(unknownCorridors, [savedCorridor], 'AC-4 FAIL: unknownCorridors-Weg greift nicht');

		// Nutzer aendert nur die bekannte Zeile (wind_max_kmh) und speichert.
		const changedRows = patchRow(rows, 'wind_max_kmh', { max: 60 });
		const payload = buildCompareCorridorSavePayload(
			changedRows,
			[],
			{ idealRanges: {}, activeMetricKeys: [], metricAlertLevels: {} },
			unknownCorridors
		);
		const preserved = payload.corridors.find((c) => c.metric === 'precip_type_dominant');
		assert.deepEqual(
			preserved,
			savedCorridor,
			'AC-4 FAIL: der alte precip_type_dominant-Korridor wurde beim Speichern veraendert/verworfen'
		);
	});
});
