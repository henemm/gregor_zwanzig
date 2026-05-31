// Tests: Epic #137 — Wegpunkt-Editor Pure Functions (AC-14)
//
// Spec: docs/specs/modules/epic_137_wegpunkt_editor.md
// Issue #495: SVG-Projektions-Tests entfernt — Leaflet ersetzt sie.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/utils/waypointEditor.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import { stripSuggested, boundingBox } from './waypointEditor.ts';

import type { Stage, Waypoint } from '../types.ts';

// =============================================================================
// Helpers
// =============================================================================

function wp(
	id: string,
	name: string,
	lat: number,
	lon: number,
	elevation_m: number,
	suggested?: boolean
): Waypoint {
	const w: Waypoint = { id, name, lat, lon, elevation_m };
	if (suggested !== undefined) {
		w.suggested = suggested;
	}
	return w;
}

function stage(id: string, date: string, waypoints: Waypoint[], name?: string): Stage {
	return { id, name: name ?? id, date, waypoints };
}

// =============================================================================
// AC-14: stripSuggested
// =============================================================================

test('AC-14: stripSuggested entfernt suggested-Flag aus allen Waypoints', () => {
	const stages: Stage[] = [
		stage('s1', '2026-06-01', [
			wp('w1', 'A', 42.1, 9.0, 800, true),
			wp('w2', 'B', 42.2, 9.1, 900, false),
			wp('w3', 'C', 42.3, 9.2, 700)
		])
	];
	const result = stripSuggested(stages);
	for (const s of result) {
		for (const w of s.waypoints) {
			assert.notEqual(w.suggested, true, `Waypoint ${w.id} hat noch suggested: true`);
		}
	}
});

test('AC-14: stripSuggested mit leeren stages → leeres Array', () => {
	const result = stripSuggested([]);
	assert.deepEqual(result, []);
});

test('AC-14: stripSuggested ohne suggested-Waypoints → Stages unverändert (deep equal)', () => {
	const stages: Stage[] = [
		stage('s1', '2026-06-01', [
			wp('w1', 'A', 42.0, 9.0, 500),
			wp('w2', 'B', 42.1, 9.1, 800)
		])
	];
	const result = stripSuggested(stages);
	assert.equal(result.length, 1);
	assert.equal(result[0].waypoints.length, 2);
	assert.equal(result[0].waypoints[0].suggested, undefined);
	assert.equal(result[0].waypoints[1].suggested, undefined);
});

test('AC-14: stripSuggested mit mehreren Stages mit suggested → alle bereinigt', () => {
	const stages: Stage[] = [
		stage('s1', '2026-06-01', [
			wp('w1', 'A', 42.0, 9.0, 500, true),
			wp('w2', 'B', 42.1, 9.1, 800, true)
		]),
		stage('s2', '2026-06-02', [
			wp('w3', 'C', 42.2, 9.2, 700, true),
			wp('w4', 'D', 42.3, 9.3, 600, false)
		])
	];
	const result = stripSuggested(stages);
	assert.equal(result.length, 2);
	for (const s of result) {
		for (const w of s.waypoints) {
			assert.notEqual(w.suggested, true, `Waypoint ${w.id} hat noch suggested: true`);
		}
	}
});

test('AC-14: stripSuggested mutiert das Original-Array nicht (gibt neue Stages zurück)', () => {
	const originalWp = wp('w1', 'A', 42.0, 9.0, 500, true);
	const stages: Stage[] = [stage('s1', '2026-06-01', [originalWp])];
	stripSuggested(stages);
	// Original bleibt unberührt
	assert.equal(originalWp.suggested, true, 'Original-Waypoint sollte nicht mutiert werden');
});

// =============================================================================
// boundingBox
// =============================================================================

test('boundingBox: normale Waypoints → minLat < maxLat, minLon < maxLon, cosLat im (0,1]', () => {
	const waypoints: Waypoint[] = [
		wp('w1', 'A', 42.0, 9.0, 500),
		wp('w2', 'B', 42.5, 9.5, 800),
		wp('w3', 'C', 42.2, 9.1, 600)
	];
	const bb = boundingBox(waypoints);
	assert.ok(bb.minLat < bb.maxLat, `minLat=${bb.minLat} >= maxLat=${bb.maxLat}`);
	assert.ok(bb.minLon < bb.maxLon, `minLon=${bb.minLon} >= maxLon=${bb.maxLon}`);
	assert.ok(bb.cosLat > 0 && bb.cosLat <= 1, `cosLat=${bb.cosLat} außerhalb (0, 1]`);
});

test('boundingBox: cosLat korrekt für Korsika (lat ~42°) — ca. 0.74', () => {
	const waypoints: Waypoint[] = [
		wp('w1', 'A', 42.0, 9.0, 500),
		wp('w2', 'B', 42.4, 9.4, 800)
	];
	const bb = boundingBox(waypoints);
	// cos(42.2°) ≈ 0.741 — Toleranz ±0.02
	assert.ok(bb.cosLat > 0.72 && bb.cosLat < 0.76, `cosLat=${bb.cosLat} nicht ~0.74`);
});

test('boundingBox: leere Waypoints → Nullwerte (alle 0)', () => {
	const bb = boundingBox([]);
	assert.equal(bb.minLat, 0);
	assert.equal(bb.maxLat, 0);
	assert.equal(bb.minLon, 0);
	assert.equal(bb.maxLon, 0);
	assert.equal(bb.cosLat, 0);
});

test('boundingBox: alle Rückgabewerte sind Zahlen', () => {
	const waypoints: Waypoint[] = [
		wp('w1', 'A', 42.0, 9.0, 500),
		wp('w2', 'B', 42.1, 9.1, 600)
	];
	const bb = boundingBox(waypoints);
	assert.equal(typeof bb.minLat, 'number');
	assert.equal(typeof bb.maxLat, 'number');
	assert.equal(typeof bb.minLon, 'number');
	assert.equal(typeof bb.maxLon, 'number');
	assert.equal(typeof bb.cosLat, 'number');
});
