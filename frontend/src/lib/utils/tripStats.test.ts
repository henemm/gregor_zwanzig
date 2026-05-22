// TDD RED: Issue #302 — Trip-Detail-Seite Redesign.
//
// Deckt AC-9: computeTripStats() summiert km und Höhenmeter über alle Etappen.
// Spec: docs/specs/modules/issue_302_trip_detail_page.md
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/utils/tripStats.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import { computeTripStats } from './tripStats.ts';

import type { Trip, Stage } from '../types.ts';

// Hilfsfunktion: minimaler Trip für Tests
function makeTrip(stages: Stage[]): Trip {
	return {
		id: 'test-trip',
		name: 'Test Trip',
		stages,
	} as Trip;
}

// Stage mit zwei Wegpunkten in Korsika (ca. 15 km Abstand, 400 m Aufstieg)
const stageKorsika: Stage = {
	id: 'stage-1',
	name: 'Étappe 1',
	date: '2026-06-01',
	waypoints: [
		{ id: 'wp-1', name: 'Start', lat: 42.1, lon: 9.0, elevation_m: 800 },
		{ id: 'wp-2', name: 'Mitte', lat: 42.2, lon: 9.1, elevation_m: 1200 },
		{ id: 'wp-3', name: 'Ziel', lat: 42.3, lon: 9.2, elevation_m: 600 },
	],
};

// Stage mit einem Waypoint (kein Segment → km = 0)
const stageSingle: Stage = {
	id: 'stage-solo',
	name: 'Solo',
	date: '2026-06-02',
	waypoints: [
		{ id: 'wp-solo', name: 'Allein', lat: 42.5, lon: 9.3, elevation_m: 1000 },
	],
};

// Stage ohne Waypoints
const stageEmpty: Stage = {
	id: 'stage-empty',
	name: 'Leer',
	date: '2026-06-03',
	waypoints: [],
};

// =============================================================================
// AC-9: computeTripStats() — Kern-Einheit

test('AC-9a: Leerer Trip liefert stages=0, kmTotal=0, ascentM=0', () => {
	const result = computeTripStats(makeTrip([]));
	assert.equal(result.stages, 0, 'stages muss 0 sein');
	assert.equal(result.kmTotal, 0, 'kmTotal muss 0 sein');
	assert.equal(result.ascentM, 0, 'ascentM muss 0 sein');
});

test('AC-9b: Trip mit einer Stage und 3 Wegpunkten liefert stages=1, kmTotal>0, ascentM>0', () => {
	const result = computeTripStats(makeTrip([stageKorsika]));
	assert.equal(result.stages, 1, 'stages muss 1 sein');
	assert.ok(result.kmTotal > 0, `kmTotal muss > 0 sein, ist: ${result.kmTotal}`);
	assert.ok(result.ascentM > 0, `ascentM muss > 0 sein, ist: ${result.ascentM}`);
});

test('AC-9c: Stage mit nur 1 Waypoint trägt 0 km bei', () => {
	const result = computeTripStats(makeTrip([stageSingle]));
	assert.equal(result.stages, 1, 'stages muss 1 sein');
	assert.equal(result.kmTotal, 0, 'kmTotal muss 0 für 1 Waypoint sein');
});

test('AC-9d: Stage ohne Waypoints trägt 0 km bei', () => {
	const result = computeTripStats(makeTrip([stageEmpty]));
	assert.equal(result.stages, 1, 'stages muss 1 sein');
	assert.equal(result.kmTotal, 0, 'kmTotal muss 0 für leere Waypoints sein');
});

test('AC-9e: Zwei Stages — kmTotal ist Summe beider Stages', () => {
	const single = computeTripStats(makeTrip([stageKorsika]));
	const combined = computeTripStats(makeTrip([stageKorsika, stageKorsika]));
	assert.equal(combined.stages, 2, 'stages muss 2 sein');
	assert.ok(
		Math.abs(combined.kmTotal - single.kmTotal * 2) < 0.001,
		`kmTotal muss doppelt sein: erwartet ${single.kmTotal * 2}, erhalten ${combined.kmTotal}`
	);
	assert.ok(
		Math.abs(combined.ascentM - single.ascentM * 2) < 1,
		`ascentM muss doppelt sein: erwartet ${single.ascentM * 2}, erhalten ${combined.ascentM}`
	);
});

test('AC-9f: Rückgabe hat korrekte Interface-Struktur { stages, kmTotal, ascentM }', () => {
	const result = computeTripStats(makeTrip([stageKorsika]));
	assert.ok('stages' in result, 'Feld stages fehlt');
	assert.ok('kmTotal' in result, 'Feld kmTotal fehlt');
	assert.ok('ascentM' in result, 'Feld ascentM fehlt');
	assert.equal(typeof result.stages, 'number', 'stages muss number sein');
	assert.equal(typeof result.kmTotal, 'number', 'kmTotal muss number sein');
	assert.equal(typeof result.ascentM, 'number', 'ascentM muss number sein');
});
