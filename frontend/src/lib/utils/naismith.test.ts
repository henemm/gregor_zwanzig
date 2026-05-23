// TDD RED: Issue #296-FE — Naismith-Util (clientseitige Live-Berechnung)
//
// Spec: docs/specs/modules/issue_296_fe_profile_editor.md (AC-5, AC-6)
// Test-Manifest: docs/specs/tests/issue_296_fe_profile_editor_tests.md
// Workflow: Phase 5 (TDD RED) — Tests MÜSSEN FEHLSCHLAGEN bis Phase 6.
//
// `naismith.ts` existiert noch NICHT → Import-Fehler = RED.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/utils/naismith.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import { naismithHours, computeArrivalTimes } from './naismith.ts';

import type { Stage, Waypoint } from '../types.ts';

// =============================================================================
// Helpers
// =============================================================================

function wp(
	id: string,
	name: string,
	lat: number,
	lon: number,
	elevation_m: number
): Waypoint {
	return { id, name, lat, lon, elevation_m };
}

function stage(id: string, waypoints: Waypoint[], start_time?: string): Stage {
	const s: Stage = { id, name: id, date: '2026-06-01', waypoints };
	if (start_time !== undefined) {
		s.start_time = start_time;
	}
	return s;
}

// 0.035973° Lat ≈ exakt 4 km Haversine-Distanz (auf ~42° N). 4 km / 4 km/h = 1 h.
const DELTA_4KM_LAT = 0.035973;

// =============================================================================
// AC-6: naismithHours — SUMME (dist/4 + ascent/300 + descent/500)
// =============================================================================

test('AC-6: naismithHours(4,0,0) === 1 (4 km flach / 4 km/h)', () => {
	assert.equal(naismithHours(4, 0, 0), 1);
});

test('AC-6: naismithHours(0,300,0) === 1 (300 Höhenmeter Aufstieg / 300 m/h)', () => {
	assert.equal(naismithHours(0, 300, 0), 1);
});

test('AC-6: naismithHours(0,0,500) === 1 (500 Höhenmeter Abstieg / 500 m/h)', () => {
	assert.equal(naismithHours(0, 0, 500), 1);
});

test('AC-6: naismithHours summiert alle drei Terme (nicht max)', () => {
	// 4 km flach (1 h) + 300 m auf (1 h) + 500 m ab (1 h) = 3 h
	assert.equal(naismithHours(4, 300, 500), 3);
});

// =============================================================================
// AC-5: computeArrivalTimes — kumulative Ankunftszeiten "HH:MM"
// =============================================================================

test('AC-5: Stage 08:00 mit 2 Wegpunkten 4 km flach → ["08:00","09:00"]', () => {
	const s = stage(
		's1',
		[
			wp('w1', 'Start', 42.0, 9.0, 1000),
			wp('w2', 'Ziel', 42.0 + DELTA_4KM_LAT, 9.0, 1000) // 4 km nördlich, gleiche Höhe → flach
		],
		'08:00'
	);
	const arrivals = computeArrivalTimes(s, s.start_time);
	assert.equal(arrivals.length, 2);
	assert.equal(arrivals[0], '08:00', 'erster Wegpunkt = Startzeit');
	assert.equal(arrivals[1], '09:00', '4 km flach = +1 h');
});

test('AC-5: Pausentag (0 Wegpunkte) → []', () => {
	const s = stage('pause', [], '08:00');
	assert.deepEqual(computeArrivalTimes(s, s.start_time), []);
});

test('AC-5: Default-Startzeit 08:00 wenn startTime fehlt', () => {
	const s = stage('s1', [wp('w1', 'Start', 42.0, 9.0, 1000)]);
	const arrivals = computeArrivalTimes(s);
	assert.equal(arrivals.length, 1);
	assert.equal(arrivals[0], '08:00');
});
