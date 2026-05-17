// TDD RED: Epic #137 — Wegpunkt-Editor Pure Functions (AC-14, AC-15)
//
// Spec: docs/specs/modules/epic_137_wegpunkt_editor.md
// Issues: #166–#172
// Workflow: Phase 5 (TDD RED) — Tests MÜSSEN FEHLSCHLAGEN bis Phase 6.
//
// `waypointEditor.ts` existiert noch NICHT → Import-Fehler = RED.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/utils/waypointEditor.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import { stripSuggested, buildMapPositions, boundingBox } from './waypointEditor.ts';

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
// AC-15: buildMapPositions
// =============================================================================

test('AC-15: buildMapPositions normiert Koordinaten auf SVG-Viewport [0,400]x[0,300]', () => {
	const s = stage('s1', '2026-06-01', [
		wp('w1', 'Start', 42.0, 9.0, 800),
		wp('w2', 'Mitte', 42.1, 9.1, 1000),
		wp('w3', 'Ende', 42.2, 9.2, 600)
	]);
	const positions = buildMapPositions(s, 400, 300);
	assert.equal(positions.length, 3);
	for (const pos of positions) {
		assert.ok(pos.x >= 0 && pos.x <= 400, `x=${pos.x} außerhalb [0, 400]`);
		assert.ok(pos.y >= 0 && pos.y <= 300, `y=${pos.y} außerhalb [0, 300]`);
		assert.equal(typeof pos.waypointId, 'string');
	}
});

test('AC-15: buildMapPositions mit leeren Waypoints → leeres Array', () => {
	const s = stage('s1', '2026-06-01', []);
	const positions = buildMapPositions(s, 400, 300);
	assert.deepEqual(positions, []);
});

test('AC-15: buildMapPositions mit 1 Waypoint → auf Mittelpunkt (200, 150)', () => {
	const s = stage('s1', '2026-06-01', [wp('w1', 'Einzeln', 42.0, 9.0, 800)]);
	const positions = buildMapPositions(s, 400, 300);
	assert.equal(positions.length, 1);
	assert.ok(Math.abs(positions[0].x - 200) < 1, `x=${positions[0].x} nicht ~200`);
	assert.ok(Math.abs(positions[0].y - 150) < 1, `y=${positions[0].y} nicht ~150`);
});

test('AC-15: buildMapPositions wenn alle Waypoints gleiche Koordinaten → alle auf Mittelpunkt', () => {
	const s = stage('s1', '2026-06-01', [
		wp('w1', 'A', 42.0, 9.0, 800),
		wp('w2', 'B', 42.0, 9.0, 900),
		wp('w3', 'C', 42.0, 9.0, 700)
	]);
	const positions = buildMapPositions(s, 400, 300);
	assert.equal(positions.length, 3);
	for (const pos of positions) {
		assert.ok(Math.abs(pos.x - 200) < 1, `x=${pos.x} nicht ~200`);
		assert.ok(Math.abs(pos.y - 150) < 1, `y=${pos.y} nicht ~150`);
	}
});

test('AC-15: buildMapPositions waypointId entspricht Waypoint-ID', () => {
	const s = stage('s1', '2026-06-01', [
		wp('id-alpha', 'A', 42.0, 9.0, 800),
		wp('id-beta', 'B', 42.1, 9.1, 900)
	]);
	const positions = buildMapPositions(s, 400, 300);
	assert.equal(positions[0].waypointId, 'id-alpha');
	assert.equal(positions[1].waypointId, 'id-beta');
});

test('AC-15: buildMapPositions Reihenfolge entspricht Waypoint-Reihenfolge', () => {
	const waypoints = [
		wp('w1', 'A', 42.0, 9.0, 800),
		wp('w2', 'B', 42.1, 9.1, 900),
		wp('w3', 'C', 42.2, 9.2, 700)
	];
	const s = stage('s1', '2026-06-01', waypoints);
	const positions = buildMapPositions(s, 400, 300);
	assert.equal(positions.length, 3);
	assert.equal(positions[0].waypointId, 'w1');
	assert.equal(positions[1].waypointId, 'w2');
	assert.equal(positions[2].waypointId, 'w3');
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
