// TDD: Issue #183 — Email-Preview Header: pure-function Stats-Berechnung.
//
// Spec: docs/specs/modules/issue_183_email_preview_header.md
//
// Ausführen:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/email-preview/__tests__/headerStats.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import { computeHeaderStats } from '../headerStats.ts';
import type { Stage } from '../../../types.ts';

function wp(name: string, lat: number, lon: number, elev: number) {
	return { id: name, name, lat, lon, elevation_m: elev };
}

test('AC-3/AC-4: stage=null returns zero stats', () => {
	const stats = computeHeaderStats(null);
	assert.deepEqual(stats, {
		distanceKm: 0,
		ascentM: 0,
		descentM: 0,
		maxElevationM: 0,
		segmentCount: 0
	});
});

test('AC-3: stage with empty waypoints returns zero stats', () => {
	const stage: Stage = { id: 's1', name: 'x', date: '2026-05-11', waypoints: [] };
	const stats = computeHeaderStats(stage);
	assert.equal(stats.distanceKm, 0);
	assert.equal(stats.segmentCount, 0);
});

test('AC-2: ascent/descent/max-elevation from elevation profile', () => {
	const stage: Stage = {
		id: 's1', name: 'demo', date: '2026-05-11',
		waypoints: [
			wp('A', 47.0, 11.0, 800),
			wp('B', 47.001, 11.0, 1200),
			wp('C', 47.002, 11.0, 1100),
			wp('D', 47.003, 11.0, 1500),
			wp('E', 47.004, 11.0, 1400)
		]
	};
	const stats = computeHeaderStats(stage);
	// Auf: 400 (800→1200) + 400 (1100→1500) = 800
	assert.equal(stats.ascentM, 800);
	// Ab: 100 (1200→1100) + 100 (1500→1400) = 200
	assert.equal(stats.descentM, 200);
	assert.equal(stats.maxElevationM, 1500);
	assert.equal(stats.segmentCount, 4);
});

test('AC-1 (revised): distance computed via Haversine between consecutive waypoints', () => {
	// 2 Punkte ~1 km voneinander entfernt (47.0, 11.0) und (47.009, 11.0).
	// Lat-Diff 0.009 * 111.32 km ≈ 1.0 km
	const stage: Stage = {
		id: 's1', name: 'demo', date: '2026-05-11',
		waypoints: [
			wp('A', 47.0, 11.0, 800),
			wp('B', 47.009, 11.0, 800)
		]
	};
	const stats = computeHeaderStats(stage);
	// ~1.0 km, Toleranz 0.05 km
	assert.ok(
		Math.abs(stats.distanceKm - 1.0) < 0.05,
		`expected ~1.0 km, got ${stats.distanceKm}`
	);
	assert.equal(stats.segmentCount, 1);
});

test('Single waypoint: no segments, no distance, but elevation visible', () => {
	const stage: Stage = {
		id: 's1', name: 'x', date: '2026-05-11',
		waypoints: [wp('A', 47.0, 11.0, 1234)]
	};
	const stats = computeHeaderStats(stage);
	assert.equal(stats.segmentCount, 0);
	assert.equal(stats.distanceKm, 0);
	assert.equal(stats.maxElevationM, 1234);
	assert.equal(stats.ascentM, 0);
	assert.equal(stats.descentM, 0);
});

// =============================================================================
// TDD RED: Issue #2110 — Track-Distanz statt Haversine, wenn Etappe vollständig
// vermessen ist (distance_from_start_km je Wegpunkt).
// Spec: docs/specs/modules/fix_2110_gui_gpx_km.md (AC-1, AC-2, AC-3)
// `distance_from_start_km` existiert im `Waypoint`-Type noch NICHT (kommt in
// Phase 6) — hier bewusst als lockeres Objekt-Literal gesetzt, `wp()` deckt
// den Rest ab. `--experimental-strip-types` prüft zur Laufzeit keine Typen.
// =============================================================================

test('AC-1: vollstaendig vermessene Etappe nutzt Track-Distanz statt Haversine-Summe', () => {
	// Haversine (47.0,11.0)→(47.009,11.0) ≈ 1.0 km (s.o.), Track-Distanz wird
	// hier bewusst auf 5.0 km gesetzt — deutlich verschieden, damit die
	// Assertion nur bei echter Track-Nutzung erfüllt ist.
	const stage: Stage = {
		id: 's1', name: 'demo', date: '2026-05-11',
		waypoints: [
			{ ...wp('A', 47.0, 11.0, 800), distance_from_start_km: 0 },
			{ ...wp('B', 47.009, 11.0, 800), distance_from_start_km: 5.0 }
		]
	};
	const stats = computeHeaderStats(stage);
	assert.equal(
		stats.distanceKm,
		5.0,
		`erwartet Track-Distanz 5.0 km (Haversine wäre ~1.0 km), erhalten ${stats.distanceKm}`
	);
});

test('AC-3: teilweise vermessene Etappe (ein Wegpunkt ohne distance_from_start_km) faellt komplett auf Haversine zurueck — kein Mischen', () => {
	const coordsOnly: Stage = {
		id: 's1', name: 'demo', date: '2026-05-11',
		waypoints: [
			wp('A', 47.0, 11.0, 800),
			wp('B', 47.003, 11.0, 900),
			wp('C', 47.009, 11.0, 800)
		]
	};
	const expectedHaversine = computeHeaderStats(coordsOnly).distanceKm;

	const partiallyMeasured: Stage = {
		id: 's1', name: 'demo', date: '2026-05-11',
		waypoints: [
			{ ...wp('A', 47.0, 11.0, 800), distance_from_start_km: 0 },
			wp('B', 47.003, 11.0, 900), // fehlt: distance_from_start_km
			{ ...wp('C', 47.009, 11.0, 800), distance_from_start_km: 5.0 }
		]
	};
	const stats = computeHeaderStats(partiallyMeasured);
	assert.equal(
		stats.distanceKm,
		expectedHaversine,
		`teilweise vermessene Etappe muss exakt dem reinen Haversine-Fall entsprechen (kein Segment-Mischen), erwartet ${expectedHaversine}, erhalten ${stats.distanceKm}`
	);
});

test('Multiple stages with various profiles', () => {
	// Flacher Trail
	const flat: Stage = {
		id: 's', name: 'flat', date: '2026-05-11',
		waypoints: [
			wp('A', 47.0, 11.0, 500),
			wp('B', 47.001, 11.0, 500),
			wp('C', 47.002, 11.0, 500)
		]
	};
	const flatStats = computeHeaderStats(flat);
	assert.equal(flatStats.ascentM, 0);
	assert.equal(flatStats.descentM, 0);
	assert.equal(flatStats.maxElevationM, 500);
	assert.equal(flatStats.segmentCount, 2);
});
