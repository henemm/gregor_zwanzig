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
} from './corridorEditorState.ts';

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
