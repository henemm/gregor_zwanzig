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
	deriveMetricAlertLevel,
	buildCorridorSavePayload,
	valueAtPointer,
	clampDragValue,
	clampBoundInput,
	saveGateDecision,
	COMPARE_METRIC_DEFS,
	VERGLEICH_CTX_DEFAULTS,
	buildComparePool,
	addCompareRow,
	buildCompareCorridorSavePayload,
	buildComparePrefillRows,
} from './corridorEditorState.ts';
// Fix-Loop 1 (F005): Erwartungswerte aus der Quelle ableiten statt Hardcode —
// ALL_METRICS waechst (zuletzt #1285: pop_max_pct), ein hartkodiertes "14"
// veraltet dann sofort. Vakuum-Schutz (nie 0 akzeptieren) bleibt erhalten.
import { ALL_METRICS } from '../../compare/compareMetricDefs.ts';

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

// --- Sync-Bruecke notify <-> metric_alert_levels (AC-10) ---
describe('deriveMetricAlertLevel', () => {
	test('notify=false -> immer "off"', () => {
		assert.equal(deriveMetricAlertLevel(false, 'wind_gust', { wind_gust: 'sensibel' }), 'off');
	});

	test('notify=true + zuvor bekannte Stufe -> Stufe wird restauriert', () => {
		assert.equal(deriveMetricAlertLevel(true, 'wind_gust', { wind_gust: 'sensibel' }), 'sensibel');
	});

	test('notify=true + nie gesetzt -> Default "standard"', () => {
		assert.equal(deriveMetricAlertLevel(true, 'wind_gust', {}), 'standard');
	});

	test('notify=true + zuvor "off" -> Default "standard" (kein Off-Zombie)', () => {
		assert.equal(deriveMetricAlertLevel(true, 'wind_gust', { wind_gust: 'off' }), 'standard');
	});
});

// --- Save-Payload: RMW, nur route-Metriken werden ueberschrieben ---
describe('buildCorridorSavePayload', () => {
	test('baut corridors[] + merged metric_alert_levels (RMW, fremde Metriken bleiben)', () => {
		const { rows } = buildRoutePool([
			{ metric: 'wind_gust', range: [null, 55], notify: false, mark: false },
		]);
		const payload = buildCorridorSavePayload(rows, {
			wind_gust: 'sensibel',
			temperature_change: 'standard', // nicht route-Pool -> muss erhalten bleiben
		});
		assert.deepEqual(payload.corridors, [
			{ metric: 'wind_gust', range: [null, 55], notify: false, mark: false },
		]);
		assert.equal(payload.metric_alert_levels.wind_gust, 'off');
		assert.equal(payload.metric_alert_levels.temperature_change, 'standard');
	});

	// F002 (Adversary, HIGH): "✕ entfernen" darf keinen Geister-Alert hinterlassen —
	// eine entfernte Zeile muss im Payload explizit auf "off" gesetzt werden,
	// sonst warnt der Δ-Wächter unsichtbar weiter mit der alten Stufe.
	test('entfernte Zeile -> Level wird explizit auf "off" gesetzt (F002)', () => {
		const { rows } = buildRoutePool([
			{ metric: 'wind_gust', range: [null, 55], notify: true, mark: false },
		]);
		const afterRemove = removeRow(rows, 'wind_gust');
		const payload = buildCorridorSavePayload(afterRemove, { wind_gust: 'sensibel' }, ['wind_gust']);
		assert.equal(payload.metric_alert_levels.wind_gust, 'off');
		assert.equal(payload.corridors.length, 0);
	});

	test('removedMetrics, die weiterhin in rows sind (erneut hinzugefuegt), werden NICHT ueberschrieben', () => {
		const { rows } = buildRoutePool([
			{ metric: 'wind_gust', range: [null, 55], notify: true, mark: false },
		]);
		const payload = buildCorridorSavePayload(rows, { wind_gust: 'sensibel' }, ['wind_gust']);
		assert.equal(payload.metric_alert_levels.wind_gust, 'sensibel');
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
describe('COMPARE_METRIC_DEFS — AC-3 confidence_pct-Ausschluss + alle ALL_METRICS', () => {
	test('enthaelt exakt alle ALL_METRICS-Keys, kein confidence_pct, nie leer (Vakuum-Schutz)', () => {
		const ids = COMPARE_METRIC_DEFS.map((m) => m.metric).sort();
		const expected = ALL_METRICS.map((m) => m.key).sort();
		assert.ok(expected.length > 0, 'Vorbedingung verletzt: ALL_METRICS ist leer');
		assert.deepEqual(ids, expected);
		assert.equal(ids.includes('confidence_pct'), false);
	});

	test('thunder_level_max ist kind "ordinal" mit 3 Stufen (kein/mittel/hoch)', () => {
		const thunder = COMPARE_METRIC_DEFS.find((m) => m.metric === 'thunder_level_max');
		assert.equal(thunder?.kind, 'ordinal');
		assert.deepEqual(thunder?.ordinalLabels, ['kein', 'mittel', 'hoch']);
		assert.deepEqual(thunder?.scale, [0, 2]);
	});

	// notify-Bruecke (compare_alert.py::_SUMMARY_KEY_TO_CATALOG_ID) kennt nur
	// 10 Metriken — die 4 uebrigen sind reine "mark"-Metriken (kein Alarm-Abgleich).
	test('alarmCapable=true fuer die 10 Alarm-Keys, false fuer die 4 reinen Vergleichs-Metriken', () => {
		const byId = new Map(COMPARE_METRIC_DEFS.map((m) => [m.metric, m.alarmCapable]));
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
		]);
		assert.equal(rows.length, 1);
		assert.equal(rows[0].label, 'Temperatur max');
		assert.equal(rows[0].unit, '°C');
		assert.equal(rows[0].max, 30);
		assert.equal(rows[0].mark, true);
		// Fix-Loop 1 (F005): Erwartung aus COMPARE_METRIC_DEFS.length ableiten
		// statt Hardcode (ALL_METRICS waechst, s. Import-Kommentar oben).
		assert.equal(poolLeft.length, COMPARE_METRIC_DEFS.length - 1);
		assert.equal(poolLeft.some((m) => m.metric === 'temp_max_c'), false);
	});

	test('leere corridors -> alle Metriken im poolLeft, keine rows', () => {
		const { rows, poolLeft } = buildComparePool([]);
		assert.equal(rows.length, 0);
		assert.equal(poolLeft.length, COMPARE_METRIC_DEFS.length);
	});

	// BUG-DATALOSS-Regressionstest (Team-Lead-Fund): echter Nutzer henning hat
	// einen sunny_hours_h-Corridor aus der Slice-2-Migration. Der 10er-Pool
	// (vor der Korrektur) kannte diese Metrik nicht -> Zeile verschwand aus
	// rows UND poolLeft -> beim Speichern verloren. Muss jetzt geladen werden.
	test('Corridor mit nicht-alarmfaehiger Metrik (sunny_hours_h) geht NICHT verloren', () => {
		const { rows, poolLeft } = buildComparePool([
			{ metric: 'sunny_hours_h', range: [7, 12], notify: false, mark: true },
		]);
		assert.equal(rows.length, 1);
		assert.equal(rows[0].metric, 'sunny_hours_h');
		assert.equal(rows[0].min, 7);
		assert.equal(rows[0].max, 12);
		assert.equal(rows[0].alarmCapable, false);
		assert.equal(poolLeft.length, COMPARE_METRIC_DEFS.length - 1);
	});
});

// --- addCompareRow: Kontext-Defaults notify=false/mark=true (PO-Vorgabe) ---
describe('addCompareRow — VERGLEICH_CTX_DEFAULTS', () => {
	test('Defaults sind notify=false, mark=true (umgekehrt zu route)', () => {
		assert.deepEqual(VERGLEICH_CTX_DEFAULTS, { notify: false, mark: true });
	});

	test('addCompareRow uebernimmt Default-Range + Kontext-Defaults der Metrik', () => {
		const { rows, poolLeft } = buildComparePool([]);
		const next = addCompareRow(rows, poolLeft, 'wind_max_kmh', VERGLEICH_CTX_DEFAULTS);
		assert.equal(next.rows.length, 1);
		assert.equal(next.rows[0].metric, 'wind_max_kmh');
		assert.equal(next.rows[0].notify, false);
		assert.equal(next.rows[0].mark, true);
		assert.equal(next.poolLeft.some((m) => m.metric === 'wind_max_kmh'), false);
	});

	test('addCompareRow fuer thunder_level_max setzt Ordinal-Default (kind + Bounds)', () => {
		const { rows, poolLeft } = buildComparePool([]);
		const next = addCompareRow(rows, poolLeft, 'thunder_level_max', VERGLEICH_CTX_DEFAULTS);
		assert.equal(next.rows[0].kind, 'ordinal');
		assert.equal(next.rows[0].max, 0); // NONE, aus SUMMER_TREKKING-Default gespiegelt
	});
});

// --- Dual-Write: mark -> ideal_ranges, notify -> active_metrics/metric_alert_levels ---
describe('buildCompareCorridorSavePayload — Dual-Write (mark -> ideal_ranges)', () => {
	test('mark=true numerische Zeile -> ideal_ranges[metric] = {min?,max?}, offene Seite weggelassen', () => {
		const { rows } = buildComparePool([
			{ metric: 'temp_max_c', range: [null, 30], notify: false, mark: true },
		]);
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
		]);
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
		]);
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
		]);
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
		]);
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
		]);
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
		]);
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
// Details Abschnitt 3). notify behaelt seine Alarm-Funktion (metric_alert_levels).
// Ersetzt die vor C1 gueltigen "Dual-Write (notify -> active_metrics/#1191)"-
// Erwartungen (aktueller Verhaltensnachweis: weatherMetricsTabCorridorCoupling.test.ts AC-3).
describe('buildCompareCorridorSavePayload — C1 Entkopplung notify <-> active_metrics', () => {
	test('notify=true veraendert activeMetricKeys NICHT MEHR, metric_alert_levels != off', () => {
		const { rows } = buildComparePool([
			{ metric: 'wind_max_kmh', range: [0, 50], notify: true, mark: false },
		]);
		const payload = buildCompareCorridorSavePayload(rows, [], {
			idealRanges: {},
			activeMetricKeys: [],
			metricAlertLevels: {},
		});
		assert.deepEqual(payload.activeMetricKeys, []);
		assert.equal(payload.metricAlertLevels.wind_max_kmh, 'standard');
	});

	test('notify=false entfernt die Metrik NICHT MEHR aus activeMetricKeys, metric_alert_levels="off"', () => {
		const { rows } = buildComparePool([
			{ metric: 'wind_max_kmh', range: [0, 50], notify: false, mark: true },
		]);
		const payload = buildCompareCorridorSavePayload(rows, [], {
			idealRanges: {},
			activeMetricKeys: ['wind_max_kmh'],
			metricAlertLevels: { wind_max_kmh: 'sensibel' },
		});
		assert.deepEqual(payload.activeMetricKeys, ['wind_max_kmh']);
		assert.equal(payload.metricAlertLevels.wind_max_kmh, 'off');
	});

	// #1191-Erhalt: alle Zeilen notify=false -> bewusst leeres [] bleibt leer,
	// wird NICHT durch das Fehlen der Zeilen "reaktiviert".
	test('#1191: alle Zeilen notify=false -> active_metrics bleibt [] (kein Reaktivieren)', () => {
		const { rows } = buildComparePool([
			{ metric: 'wind_max_kmh', range: [0, 50], notify: false, mark: true },
			{ metric: 'temp_max_c', range: [null, 30], notify: false, mark: true },
		]);
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
		]);
		const payload = buildCompareCorridorSavePayload(rows, [], {
			idealRanges: {},
			activeMetricKeys: ['temp_min_c'],
			metricAlertLevels: {},
		});
		assert.ok(payload.activeMetricKeys.includes('temp_min_c'));
		assert.equal(payload.activeMetricKeys.includes('wind_max_kmh'), false);
	});

	// F002-Analogon (Slice 3): entfernte Zeile hinterlaesst keinen Geister-Alert
	// UND keinen verwaisten ideal_ranges-Eintrag.
	test('removedMetrics -> Level explizit "off", aus active_metrics UND ideal_ranges entfernt', () => {
		const { rows } = buildComparePool([
			{ metric: 'wind_max_kmh', range: [0, 50], notify: true, mark: true },
		]);
		const afterRemove = removeRow(rows, 'wind_max_kmh');
		const payload = buildCompareCorridorSavePayload(afterRemove, ['wind_max_kmh'], {
			idealRanges: { wind_max_kmh: { min: 0, max: 50 } },
			activeMetricKeys: ['wind_max_kmh'],
			metricAlertLevels: { wind_max_kmh: 'sensibel' },
		});
		assert.equal(payload.metricAlertLevels.wind_max_kmh, 'off');
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
		const rows = buildComparePrefillRows('ALLGEMEIN');
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
		const rows = buildComparePrefillRows('WINTERSPORT');
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
		const rows = buildComparePrefillRows('SUMMER_TREKKING');
		const thunder = rows.find((r) => r.metric === 'thunder_level_max')!;
		assert.equal(thunder.kind, 'ordinal');
		assert.equal(thunder.max, 0); // NONE
		assert.equal(thunder.notify, true); // thunder_level_max ist alarmfaehig
		assert.equal(thunder.mark, true);
	});

	test('unbekannter/keiner Profil-Key -> Fallback ALLGEMEIN (analog Step3Idealwerte)', () => {
		const rows = buildComparePrefillRows('ALLGEMEIN');
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
		const { rows, poolLeft } = buildComparePool([]);
		const next = addCompareRow(rows, poolLeft, 'temp_max_c', VERGLEICH_CTX_DEFAULTS, true);
		assert.equal(next.rows[0].notify, true);
	});

	test('wasActive=false (Standardfall) -> notify=Kontext-Default (unveraendertes Verhalten)', () => {
		const { rows, poolLeft } = buildComparePool([]);
		const next = addCompareRow(rows, poolLeft, 'temp_max_c', VERGLEICH_CTX_DEFAULTS, false);
		assert.equal(next.rows[0].notify, false);
	});

	test('wasActive=true auf nicht-alarmfaehiger Metrik -> notify bleibt false (defensiv)', () => {
		const { rows, poolLeft } = buildComparePool([]);
		const next = addCompareRow(rows, poolLeft, 'sunny_hours_h', VERGLEICH_CTX_DEFAULTS, true);
		assert.equal(next.rows[0].notify, false);
	});

	// Exakter mallorca-Fall (Team-Lead): active_metrics voll (10 Keys),
	// corridors fehlend. add(temp_max_c) darf active_metrics NICHT verkleinern.
	test('Mallorca-Szenario: active_metrics bleibt vollstaendig inkl. temp_max_c nach add()', () => {
		const activeMetricKeys = [
			'temp_max_c', 'temp_min_c', 'wind_max_kmh', 'gust_max_kmh', 'precip_sum_mm',
			'thunder_level_max', 'visibility_min_m', 'snow_new_sum_cm', 'cape_max_jkg', 'freezing_level_m',
		];
		const { rows, poolLeft } = buildComparePool([]); // corridors fehlt (Legacy, nicht migriert)
		const wasActive = activeMetricKeys.includes('temp_max_c');
		const next = addCompareRow(rows, poolLeft, 'temp_max_c', VERGLEICH_CTX_DEFAULTS, wasActive);
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
		]);
		assert.equal(rows.some((r) => r.metric === 'foo_bar'), false);
		assert.equal(unknownCorridors.length, 1);
		assert.deepEqual(unknownCorridors[0], { metric: 'foo_bar', range: [1, 2], notify: false, mark: true });
	});

	test('bekannte + unbekannte Corridors gemischt -> beide korrekt getrennt', () => {
		const { rows, unknownCorridors } = buildComparePool([
			{ metric: 'temp_max_c', range: [null, 30], notify: false, mark: true },
			{ metric: 'foo_bar', range: [1, 2], notify: false, mark: true },
		]);
		assert.equal(rows.length, 1);
		assert.equal(unknownCorridors.length, 1);
	});
});

describe('buildCompareCorridorSavePayload — F003 unknownCorridors bleiben beim Speichern erhalten', () => {
	test('unknownCorridors werden unveraendert an corridors[] angehaengt', () => {
		const { rows } = buildComparePool([
			{ metric: 'temp_max_c', range: [null, 30], notify: false, mark: true },
		]);
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
		]);
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
