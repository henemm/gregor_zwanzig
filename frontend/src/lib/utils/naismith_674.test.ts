// TDD RED — Issue #674 Fahrradtour-Aktivitätstyp (TypeScript)
//
// Spec: docs/specs/modules/issue_674_aktivitaetstyp_fahrrad.md
// Workflow: phase5_tdd_red — Tests MÜSSEN FEHLSCHLAGEN bis Phase 6.
//
// RED-Ursache: activityToSpeed() existiert nicht in naismith.ts → Import-Fehler.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/utils/naismith_674.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

// activityToSpeed existiert NOCH NICHT → Import-Fehler = RED
import { activityToSpeed, computeArrivalTimes } from './naismith.ts';
import type { Stage, Waypoint, ActivityType } from '../types.ts';

// =============================================================================
// Helpers
// =============================================================================

function wp(id: string, lat: number, lon: number, elevation_m: number): Waypoint {
	return { id, name: id, lat, lon, elevation_m };
}

function stage(id: string, waypoints: Waypoint[], start_time?: string): Stage {
	const s: Stage = { id, name: id, date: '2026-06-09', waypoints };
	if (start_time !== undefined) s.start_time = start_time;
	return s;
}

// 0.17987° Lat ≈ 20 km bei ~42° N
const DELTA_20KM_LAT = 0.17987;

// =============================================================================
// AC-7: activityToSpeed — Geschwindigkeit aus ActivityType
// =============================================================================

test('AC-7: activityToSpeed("fahrrad_25") === 25', () => {
	assert.equal(activityToSpeed('fahrrad_25'), 25.0);
});

test('AC-7: activityToSpeed("fahrrad_20") === 20', () => {
	assert.equal(activityToSpeed('fahrrad_20'), 20.0);
});

test('AC-7: activityToSpeed("fahrrad_15") === 15', () => {
	assert.equal(activityToSpeed('fahrrad_15'), 15.0);
});

test('AC-7: activityToSpeed(undefined) === 4 (Wanderer-Default bleibt erhalten)', () => {
	assert.equal(activityToSpeed(undefined), 4.0);
});

test('AC-7: activityToSpeed("trekking") === 4 (Wander-Aktivitäten → 4 km/h)', () => {
	assert.equal(activityToSpeed('trekking' as ActivityType), 4.0);
});

test('AC-7: activityToSpeed("skitour") === 4 (Ski → ebenfalls Wandergeschwindigkeit)', () => {
	assert.equal(activityToSpeed('skitour' as ActivityType), 4.0);
});

// =============================================================================
// AC-1 (TS-Seite): computeArrivalTimes mit Fahrrad-Speed
// =============================================================================

test('AC-1 TS: Fahrrad 20 km/h, 20 km flach → 08:00→09:00', () => {
	const s = stage(
		's674',
		[
			wp('w1', 42.0, 9.0, 200),
			wp('w2', 42.0 + DELTA_20KM_LAT, 9.0, 200),
		],
		'08:00'
	);
	// computeArrivalTimes wird mit Speed 20 km/h aufgerufen
	const arrivals = computeArrivalTimes(s, '08:00', activityToSpeed('fahrrad_20'));
	assert.equal(arrivals.length, 2);
	assert.equal(arrivals[0], '08:00');
	assert.equal(arrivals[1], '09:00', '20 km ÷ 20 km/h = 1 h → +1 h');
});

test('AC-2 TS: Wanderer-Default (kein Speed) → 20 km braucht 5 h → 13:00', () => {
	const s = stage(
		's674-wander',
		[
			wp('w1', 42.0, 9.0, 200),
			wp('w2', 42.0 + DELTA_20KM_LAT, 9.0, 200),
		],
		'08:00'
	);
	const arrivals = computeArrivalTimes(s, '08:00'); // kein Speed → Default 4 km/h
	assert.equal(arrivals.length, 2);
	assert.equal(arrivals[1], '13:00', '20 km ÷ 4 km/h = 5 h → 13:00');
});

test('AC-5 TS: Fahrrad 25 km/h kommt früher an als Wanderer', () => {
	const waypoints = [
		wp('w1', 42.0, 9.0, 200),
		wp('w2', 42.0 + DELTA_20KM_LAT, 9.0, 200),
	];
	const s = stage('s', waypoints, '08:00');

	const wanderer = computeArrivalTimes(s, '08:00');
	const fahrrad = computeArrivalTimes(s, '08:00', activityToSpeed('fahrrad_25'));

	// Fahrrad muss früher ankommen als zu Fuss
	const parse = (t: string) => parseInt(t.slice(0, 2)) * 60 + parseInt(t.slice(3));
	assert.ok(
		parse(fahrrad[1]) < parse(wanderer[1]),
		`Fahrrad (${fahrrad[1]}) soll früher als Wanderer (${wanderer[1]}) ankommen`
	);
});
