// Issue #674 Fahrradtour (TypeScript), seit #3196 über das Tempo-Objekt:
// das Altfeld `activity` wird per deriveTempo abgeleitet (fahrrad_* → Rad mit
// Zahl, alles andere → zu Fuß 4 km/h), die Gehzeit rechnet computeArrivalTimes
// mit dem Tempo nach DAV. Volle Falltabelle: naismith_dav_3196.test.ts.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/utils/naismith_674.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import { deriveTempo, computeArrivalTimes } from './naismith.ts';
import type { Stage, Waypoint } from '../types.ts';

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

test('deriveTempo("fahrrad_25") → Rad 25 km/h', () => {
	assert.deepEqual(deriveTempo('fahrrad_25'), { fortbewegung: 'rad', grundtempo_kmh: 25 });
});

test('deriveTempo("fahrrad_15") → Rad 15 km/h', () => {
	assert.deepEqual(deriveTempo('fahrrad_15'), { fortbewegung: 'rad', grundtempo_kmh: 15 });
});

test('deriveTempo(undefined) und "skitour" → zu Fuß 4 km/h (nie Ski)', () => {
	assert.deepEqual(deriveTempo(undefined), { fortbewegung: 'fuss', grundtempo_kmh: 4 });
	assert.deepEqual(deriveTempo('skitour'), { fortbewegung: 'fuss', grundtempo_kmh: 4 });
});

test('Rad 20 km/h, 20 km flach → 08:00→09:00', () => {
	const s = stage('s674', [wp('w1', 42.0, 9.0, 200), wp('w2', 42.0 + DELTA_20KM_LAT, 9.0, 200)], '08:00');
	const arrivals = computeArrivalTimes(s, '08:00', deriveTempo('fahrrad_20'));
	assert.deepEqual(arrivals, ['08:00', '09:00']);
});

test('ohne Tempo → zu Fuß 4 km/h: 20 km flach braucht 5 h → 13:00', () => {
	const s = stage('s674-wander', [wp('w1', 42.0, 9.0, 200), wp('w2', 42.0 + DELTA_20KM_LAT, 9.0, 200)], '08:00');
	assert.deepEqual(computeArrivalTimes(s, '08:00'), ['08:00', '13:00']);
});

test('Rad 25 km/h kommt früher an als zu Fuß', () => {
	const s = stage('s', [wp('w1', 42.0, 9.0, 200), wp('w2', 42.0 + DELTA_20KM_LAT, 9.0, 200)], '08:00');
	const wanderer = computeArrivalTimes(s, '08:00');
	const fahrrad = computeArrivalTimes(s, '08:00', deriveTempo('fahrrad_25'));
	const parse = (t: string) => parseInt(t.slice(0, 2)) * 60 + parseInt(t.slice(3));
	assert.ok(parse(fahrrad[1]) < parse(wanderer[1]), `Rad (${fahrrad[1]}) soll früher als zu Fuß (${wanderer[1]}) ankommen`);
});
