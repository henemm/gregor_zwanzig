// TDD RED: Epic #135 Step 4 — Full-Profile Pure-Functions.
//
// Spec: docs/specs/modules/epic_135_step4_left_column.md
// Issues: #156 + #157
//
// Diese Tests scheitern absichtlich (RED-Phase):
//   - `$lib/utils/fullProfile` existiert noch nicht
//   - Erwartete Funktionen: buildProfilePoints, computeStageBoundaries,
//     formatStageCode, getActiveStageId
//
// Ausfuehrung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/utils/fullProfile.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
	buildProfilePoints,
	computeStageBoundaries,
	formatStageCode,
	getActiveStageId,
	type ProfilePoint,
	type StageBoundary
} from './fullProfile.ts';

import type { Trip, Stage, Waypoint } from '../types.ts';

// =============================================================================
// Helpers
// =============================================================================

function wp(
	id: string,
	lat: number,
	lon: number,
	elevation_m: number | null | undefined
): Waypoint {
	// elevation_m wird in den negativ-Tests bewusst null/undefined gesetzt,
	// obwohl der Type-Contract `number` verlangt. buildProfilePoints muss
	// diese Faelle defensiv handhaben (AC-12).
	return {
		id,
		name: id,
		lat,
		lon,
		elevation_m: elevation_m as number
	};
}

function stage(id: string, date: string, waypoints: Waypoint[], name?: string): Stage {
	return {
		id,
		name: name ?? id,
		date,
		waypoints
	};
}

function tripWith(overrides: Partial<Trip>): Trip {
	return {
		id: 't1',
		name: 'Test Trip',
		stages: [],
		...overrides
	} as Trip;
}

const TODAY = new Date('2026-05-12T12:00:00Z');

// =============================================================================
// buildProfilePoints
// =============================================================================

test('buildProfilePoints > leerer Trip (stages = []) → leeres Array', () => {
	const trip = tripWith({ stages: [] });
	const points = buildProfilePoints(trip);
	assert.deepEqual(points, []);
});

test('buildProfilePoints > Trip ohne stages-Property → leeres Array (defensive)', () => {
	const trip = tripWith({});
	const points = buildProfilePoints(trip);
	assert.equal(Array.isArray(points), true);
	assert.equal(points.length, 0);
});

test('buildProfilePoints > Trip mit 1 Stage / 2 Waypoints → 2 Punkte mit x=0 und x=Haversine, korrekte y', () => {
	const trip = tripWith({
		stages: [
			stage('s1', '2026-05-12', [
				wp('w1', 42.1, 9.0, 800),
				wp('w2', 42.2, 9.1, 1200)
			])
		]
	});
	const points = buildProfilePoints(trip);
	assert.equal(points.length, 2);

	// Erster Waypoint immer x=0 (toBeCloseTo(x, 5) → Threshold 5e-6)
	assert.ok(Math.abs(points[0].x - 0) < 5e-6);
	assert.equal(points[0].y, 800);
	assert.equal(points[0].stageId, 's1');

	// Zweiter Waypoint: Haversine zwischen (42.1, 9.0) und (42.2, 9.1) ≈ 13.6 km
	assert.ok(points[1].x > 0);
	assert.equal(points[1].y, 1200);
	assert.equal(points[1].stageId, 's1');
});

test('buildProfilePoints > Multi-Stage 3 Stages → kumulative Distanz monoton steigend, korrekte stageId-Zuordnung', () => {
	const trip = tripWith({
		stages: [
			stage('s1', '2026-05-11', [
				wp('w1', 42.0, 9.0, 500),
				wp('w2', 42.1, 9.0, 800)
			]),
			stage('s2', '2026-05-12', [
				wp('w3', 42.2, 9.1, 1000),
				wp('w4', 42.3, 9.2, 1200)
			]),
			stage('s3', '2026-05-13', [
				wp('w5', 42.4, 9.3, 700),
				wp('w6', 42.5, 9.4, 400)
			])
		]
	});
	const points = buildProfilePoints(trip);
	assert.equal(points.length, 6);

	// Monoton steigend
	for (let i = 1; i < points.length; i++) {
		assert.ok(points[i].x >= points[i - 1].x);
	}

	// stageId-Zuordnung
	assert.equal(points[0].stageId, 's1');
	assert.equal(points[1].stageId, 's1');
	assert.equal(points[2].stageId, 's2');
	assert.equal(points[3].stageId, 's2');
	assert.equal(points[4].stageId, 's3');
	assert.equal(points[5].stageId, 's3');

	// Erster Punkt bei x=0 (toBeCloseTo(x, 5) → Threshold 5e-6)
	assert.ok(Math.abs(points[0].x - 0) < 5e-6);
	// Letzter Punkt deutlich groesser
	assert.ok(points[5].x > 0);
});

test('buildProfilePoints > Stage ohne Waypoints → wird übersprungen (keine Punkte mit dieser stageId)', () => {
	const trip = tripWith({
		stages: [
			stage('s1', '2026-05-11', [wp('w1', 42.0, 9.0, 500)]),
			stage('s2', '2026-05-12', []),
			stage('s3', '2026-05-13', [wp('w3', 42.1, 9.1, 700)])
		]
	});
	const points = buildProfilePoints(trip);
	const stageIds = points.map((p) => p.stageId);
	assert.ok(!stageIds.includes('s2'));
	assert.ok(stageIds.includes('s1'));
	assert.ok(stageIds.includes('s3'));
});

test('buildProfilePoints > AC-12: Waypoint mit elevation_m=null → übersprungen, x-Cursor läuft trotzdem weiter', () => {
	const trip = tripWith({
		stages: [
			stage('s1', '2026-05-12', [
				wp('w1', 42.0, 9.0, 500),
				wp('w2', 42.1, 9.0, null),
				wp('w3', 42.2, 9.0, 1000)
			])
		]
	});
	const points = buildProfilePoints(trip);
	// Nur 2 Punkte (mittlerer uebersprungen)
	assert.equal(points.length, 2);
	assert.equal(points[0].y, 500);
	assert.equal(points[1].y, 1000);
	// x-Cursor zaehlt aber die volle Distanz: Distanz w1→w2→w3 ≈ 2× ~11 km
	assert.ok(points[1].x > 15);
});

test('buildProfilePoints > AC-12: Waypoint mit elevation_m=undefined → übersprungen, x-Cursor läuft weiter', () => {
	const trip = tripWith({
		stages: [
			stage('s1', '2026-05-12', [
				wp('w1', 42.0, 9.0, 500),
				wp('w2', 42.1, 9.0, undefined),
				wp('w3', 42.2, 9.0, 1000)
			])
		]
	});
	const points = buildProfilePoints(trip);
	assert.equal(points.length, 2);
	assert.equal(points[0].y, 500);
	assert.equal(points[1].y, 1000);
	// Distanz inkl. uebersprungenem Mittelpunkt
	assert.ok(points[1].x > 15);
});

test('buildProfilePoints > Haversine-Genauigkeit: 2 bekannte Koordinaten → erwartete Distanz ±0.1 km', () => {
	// (42.1, 9.0) → (42.2, 9.1): erwartete Haversine-Distanz ≈ 13.6 km
	const trip = tripWith({
		stages: [
			stage('s1', '2026-05-12', [
				wp('w1', 42.1, 9.0, 500),
				wp('w2', 42.2, 9.1, 800)
			])
		]
	});
	const points = buildProfilePoints(trip);
	assert.equal(points.length, 2);
	// Erwartet ca. 13.6 km — Toleranz ±0.5 km, um Rundungsmodelle abzudecken
	assert.ok(points[1].x > 13.0);
	assert.ok(points[1].x < 14.5);
});

test('buildProfilePoints > alle Punkte haben definierte numerische x und y', () => {
	const trip = tripWith({
		stages: [
			stage('s1', '2026-05-12', [
				wp('w1', 42.0, 9.0, 500),
				wp('w2', 42.1, 9.1, 800)
			])
		]
	});
	const points: ProfilePoint[] = buildProfilePoints(trip);
	for (const p of points) {
		assert.equal(typeof p.x, 'number');
		assert.equal(typeof p.y, 'number');
		assert.equal(Number.isFinite(p.x), true);
		assert.equal(Number.isFinite(p.y), true);
		assert.equal(typeof p.stageId, 'string');
	}
});

// =============================================================================
// TDD RED: Issue #2110 — Track-Distanz statt Haversine, wenn eine Etappe
// vollstaendig vermessen ist (distance_from_start_km je Wegpunkt).
// Spec: docs/specs/modules/fix_2110_gui_gpx_km.md (AC-4)
// `distance_from_start_km` existiert im `Waypoint`-Type noch NICHT (kommt in
// Phase 6) — hier als lockeres Objekt-Literal gesetzt, `wp()` liefert den Rest.
// =============================================================================

test('AC-4: vollstaendig vermessene Etappe nutzt Track-Distanz fuer x-Werte + Boundaries, unvermessene Nachbaretappe bleibt Haversine, Cursor an der Grenze konsistent', () => {
	const s1w1 = { ...wp('w1', 47.0, 11.0, 800), distance_from_start_km: 0 };
	const s1w2 = { ...wp('w2', 47.001, 11.0, 900), distance_from_start_km: 3.0 };
	const s1w3 = { ...wp('w3', 47.002, 11.0, 850), distance_from_start_km: 8.0 };
	// Haversine (47.0,11.0)→(47.001,11.0)→(47.002,11.0) ≈ 0.22 km gesamt —
	// deutlich kleiner als die gesetzte Track-Distanz 8.0 km.

	// Etappe 2: unvermessen (kein distance_from_start_km) → bleibt Haversine.
	const s2w1 = wp('w4', 47.1, 11.1, 700);
	const s2w2 = wp('w5', 47.11, 11.11, 650);

	const trip = tripWith({
		stages: [
			stage('s1', '2026-05-11', [s1w1, s1w2, s1w3]),
			stage('s2', '2026-05-12', [s2w1, s2w2])
		]
	});

	const points = buildProfilePoints(trip);
	assert.equal(points.length, 5);

	// Innerhalb s1: Track-Differenzen statt Haversine.
	assert.ok(Math.abs(points[0].x - 0) < 1e-6, `w1 x sollte 0 sein, war ${points[0].x}`);
	assert.ok(
		Math.abs(points[1].x - 3.0) < 1e-6,
		`w2 x sollte Track-Distanz 3.0 km sein (Haversine wäre ~0.11 km), war ${points[1].x}`
	);
	assert.ok(
		Math.abs(points[2].x - 8.0) < 1e-6,
		`w3 x sollte Track-Distanz 8.0 km sein (Haversine wäre ~0.22 km), war ${points[2].x}`
	);

	// Etappengrenze s1→s2 (w3→w4): bleibt Haversine-basiert, Cursor läuft
	// aber konsistent weiter (kein Sprung, kein Reset auf 0).
	assert.ok(points[3].x > points[2].x, 'x-Cursor muss an der Etappengrenze monoton weiterlaufen');

	// Innerhalb s2 (unvermessen): Differenz bleibt Haversine-basiert.
	const s2SegmentHaversine = points[4].x - points[3].x;
	assert.ok(s2SegmentHaversine > 0 && s2SegmentHaversine < 5, 'Segment innerhalb s2 muss Haversine-Größenordnung haben (~1-2 km), nicht Track-Distanz');

	const boundaries = computeStageBoundaries(trip);
	const s1Boundary = boundaries.find((b) => b.stageId === 's1');
	assert.notEqual(s1Boundary, undefined);
	assert.ok(
		Math.abs(s1Boundary!.xStart - 0) < 1e-6 && Math.abs(s1Boundary!.xEnd - 8.0) < 1e-6,
		`s1-Boundary sollte xStart=0, xEnd=8.0 sein (Track-Distanz), war xStart=${s1Boundary!.xStart}, xEnd=${s1Boundary!.xEnd}`
	);
});

test('AC-4: Grenzsegment zwischen ZWEI vollstaendig vermessenen Etappen bleibt Haversine (distance_from_start_km ist etappen-relativ)', () => {
	// Etappe 1: vollstaendig vermessen, Track-Distanz 0 → 3.0 → 8.0 km.
	// Koordinaten eng beieinander (~0.11 km je Segment) → Track ≠ Haversine.
	const s1w1 = { ...wp('w1', 47.0, 11.0, 800), distance_from_start_km: 0 };
	const s1w2 = { ...wp('w2', 47.001, 11.0, 900), distance_from_start_km: 3.0 };
	const s1w3 = { ...wp('w3', 47.002, 11.0, 850), distance_from_start_km: 8.0 };

	// Etappe 2: EBENFALLS vollstaendig vermessen — und ihr Zaehler startet wieder
	// bei 0. Eine Differenz ueber die Etappengrenze hinweg (0 − 8.0 = −8.0) waere
	// unsinnig; ohne den `i > 0`-Guard griffe der Code zudem auf wps[-1] zu (NaN).
	const s2w1 = { ...wp('w4', 47.5, 11.0, 700), distance_from_start_km: 0 };
	const s2w2 = { ...wp('w5', 47.501, 11.0, 650), distance_from_start_km: 4.0 };
	const s2w3 = { ...wp('w6', 47.502, 11.0, 600), distance_from_start_km: 9.0 };

	const trip = tripWith({
		stages: [
			stage('s1', '2026-05-11', [s1w1, s1w2, s1w3]),
			stage('s2', '2026-05-12', [s2w1, s2w2, s2w3])
		]
	});

	const points = buildProfilePoints(trip);
	assert.equal(points.length, 6);

	// Innerhalb s1: Track-Distanz (Abgrenzung — nur das Grenzsegment ist betroffen).
	assert.ok(Math.abs(points[0].x - 0) < 1e-6, `w1 x sollte 0 sein, war ${points[0].x}`);
	assert.ok(Math.abs(points[1].x - 3.0) < 1e-6, `w2 x sollte 3.0 sein, war ${points[1].x}`);
	assert.ok(Math.abs(points[2].x - 8.0) < 1e-6, `w3 x sollte 8.0 sein, war ${points[2].x}`);

	// Grenzsegment w3 (47.002, 11.0) → w4 (47.5, 11.0): gleiche Laenge, dLat = 0.498°
	// → Haversine = 6371.0088 km × 0.498 × π/180 ≈ 55.375 km.
	const boundarySegment = points[3].x - points[2].x;
	assert.equal(
		Number.isFinite(boundarySegment),
		true,
		`Grenzsegment muss endlich sein (NaN = Zugriff auf wps[-1]), war ${boundarySegment}`
	);
	assert.ok(
		Math.abs(boundarySegment - 55.375) < 0.02,
		`Grenzsegment muss Haversine ≈ 55.375 km sein, war ${boundarySegment}`
	);
	// Explizit NICHT aus distance_from_start_km abgeleitet: weder −8.0 (0 − 8.0)
	// noch 0 (gleicher Zaehlerstand) noch 8.0 (Betrag davon).
	assert.ok(
		Math.abs(boundarySegment - -8.0) > 1e-6 &&
			Math.abs(boundarySegment - 0) > 1e-6 &&
			Math.abs(boundarySegment - 8.0) > 1e-6,
		`Grenzsegment darf keine distance_from_start_km-Differenz sein, war ${boundarySegment}`
	);
	// Cursor laeuft monoton weiter (eine dfs-Differenz waere negativ gewesen).
	assert.ok(points[3].x > points[2].x, 'x-Cursor muss an der Etappengrenze monoton steigen');

	// Innerhalb s2: wieder Track-Distanz, relativ zum Etappenstart (0 → 4.0 → 9.0).
	assert.ok(
		Math.abs(points[4].x - points[3].x - 4.0) < 1e-6,
		`Segment w4→w5 sollte Track-Distanz 4.0 km sein (Haversine wäre ~0.11 km), war ${points[4].x - points[3].x}`
	);
	assert.ok(
		Math.abs(points[5].x - points[3].x - 9.0) < 1e-6,
		`Segment w4→w6 sollte Track-Distanz 9.0 km sein (Haversine wäre ~0.22 km), war ${points[5].x - points[3].x}`
	);

	// Gleiche Regel in computeStageBoundaries. Dort wird `xStart` VOR der inneren
	// Schleife gesetzt, das Grenzsegment faellt also in die Spanne von s2:
	//   s2.xStart = 8.0 (s1-Track-Ende), s2.xEnd = 8.0 + 55.375 + 9.0.
	const boundaries = computeStageBoundaries(trip);
	const s2Boundary = boundaries.find((b) => b.stageId === 's2');
	assert.notEqual(s2Boundary, undefined);
	assert.ok(
		Math.abs(s2Boundary!.xStart - 8.0) < 1e-6,
		`s2.xStart sollte das s1-Track-Ende 8.0 km sein, war ${s2Boundary!.xStart}`
	);
	assert.ok(
		Math.abs(s2Boundary!.xEnd - s2Boundary!.xStart - (55.375 + 9.0)) < 0.02,
		`s2-Spanne sollte 55.375 km (Grenz-Haversine) + 9.0 km (s2-Track) sein, war ${s2Boundary!.xEnd - s2Boundary!.xStart}`
	);
});

// =============================================================================
// computeStageBoundaries
// =============================================================================

test('computeStageBoundaries > 3 Stages mit Waypoints → 3 Einträge mit xStart < xEnd, monotone Reihenfolge', () => {
	const trip = tripWith({
		stages: [
			stage('s1', '2026-05-11', [
				wp('w1', 42.0, 9.0, 500),
				wp('w2', 42.1, 9.0, 800)
			]),
			stage('s2', '2026-05-12', [
				wp('w3', 42.2, 9.1, 1000),
				wp('w4', 42.3, 9.2, 1200)
			]),
			stage('s3', '2026-05-13', [
				wp('w5', 42.4, 9.3, 700),
				wp('w6', 42.5, 9.4, 400)
			])
		]
	});
	const boundaries: StageBoundary[] = computeStageBoundaries(trip);
	assert.equal(boundaries.length, 3);

	// xStart < xEnd je Stage
	for (const b of boundaries) {
		assert.ok(b.xEnd > b.xStart);
	}

	// Monoton: vorherige xEnd ≤ nächste xStart
	assert.ok(boundaries[0].xEnd <= boundaries[1].xStart + 1e-6);
	assert.ok(boundaries[1].xEnd <= boundaries[2].xStart + 1e-6);

	// Reihenfolge der stageIds
	assert.equal(boundaries[0].stageId, 's1');
	assert.equal(boundaries[1].stageId, 's2');
	assert.equal(boundaries[2].stageId, 's3');
});

test('computeStageBoundaries > Reguläre Stages → codes T01, T02, T03', () => {
	const trip = tripWith({
		stages: [
			stage('s1', '2026-05-11', [wp('w1', 42.0, 9.0, 500)]),
			stage('s2', '2026-05-12', [wp('w2', 42.1, 9.1, 800)]),
			stage('s3', '2026-05-13', [wp('w3', 42.2, 9.2, 700)])
		]
	});
	const boundaries = computeStageBoundaries(trip);
	assert.equal(boundaries.length, 3);
	assert.equal(boundaries[0].code, 'T01');
	assert.equal(boundaries[1].code, 'T02');
	assert.equal(boundaries[2].code, 'T03');
});

test('computeStageBoundaries > Pause-Stage (gleiches Datum wie vorherige Stage, Wizard-Konvention) → code = "P"', () => {
	// Pause-Heuristik gemaess Spec: stage.date == previous stage.date → Pause
	const trip = tripWith({
		stages: [
			stage('s1', '2026-05-11', [wp('w1', 42.0, 9.0, 500)]),
			stage('s2', '2026-05-11', [], 'Pause'), // gleiches Datum wie s1 → Pause
			stage('s3', '2026-05-12', [wp('w3', 42.1, 9.1, 800)])
		]
	});
	const boundaries = computeStageBoundaries(trip);
	assert.equal(boundaries.length, 3);
	assert.equal(boundaries[0].code, 'T01');
	assert.equal(boundaries[1].code, 'P');
	// Naechste reguläre Stage faellt auf T02 (Pause nicht mitgezaehlt)
	assert.equal(boundaries[2].code, 'T02');
});

test('computeStageBoundaries > Stage ohne Waypoints → xStart === xEnd (Punkt-Boundary)', () => {
	const trip = tripWith({
		stages: [
			stage('s1', '2026-05-11', [wp('w1', 42.0, 9.0, 500)]),
			stage('s2', '2026-05-12', [])
		]
	});
	const boundaries = computeStageBoundaries(trip);
	assert.equal(boundaries.length, 2);
	const s2 = boundaries.find((b) => b.stageId === 's2');
	assert.notEqual(s2, undefined);
	assert.equal(s2!.xStart, s2!.xEnd);
});

test('computeStageBoundaries > Leerer Trip → leeres Array', () => {
	const trip = tripWith({ stages: [] });
	const boundaries = computeStageBoundaries(trip);
	assert.deepEqual(boundaries, []);
});

test('computeStageBoundaries > jede Boundary enthält stageId, xStart, xEnd, code', () => {
	const trip = tripWith({
		stages: [stage('s1', '2026-05-12', [wp('w1', 42.0, 9.0, 500)])]
	});
	const boundaries = computeStageBoundaries(trip);
	assert.equal(boundaries.length, 1);
	const b = boundaries[0];
	assert.equal(typeof b.stageId, 'string');
	assert.equal(typeof b.xStart, 'number');
	assert.equal(typeof b.xEnd, 'number');
	assert.equal(typeof b.code, 'string');
});

// =============================================================================
// formatStageCode
// =============================================================================

test('formatStageCode > AC-13: (0, false) === "T01"', () => {
	assert.equal(formatStageCode(0, false), 'T01');
});

test('formatStageCode > AC-13: (1, false) === "T02"', () => {
	assert.equal(formatStageCode(1, false), 'T02');
});

test('formatStageCode > AC-13: (2, true) === "P"', () => {
	assert.equal(formatStageCode(2, true), 'P');
});

test('formatStageCode > AC-13: (9, false) === "T10"', () => {
	assert.equal(formatStageCode(9, false), 'T10');
});

test('formatStageCode > (99, false) === "T100" (dreistellig, kein Padding-Verbot)', () => {
	assert.equal(formatStageCode(99, false), 'T100');
});

test('formatStageCode > isPause überschreibt nonPauseIndex (0, true) === "P"', () => {
	assert.equal(formatStageCode(0, true), 'P');
});

// =============================================================================
// getActiveStageId
// =============================================================================

test('getActiveStageId > AC-14: Trip-Status active mit Stage date === today → liefert Stage-ID', () => {
	const trip = tripWith({
		stages: [
			stage('s1', '2026-05-11', [wp('w1', 42.0, 9.0, 500)]),
			stage('s2', '2026-05-12', [wp('w2', 42.1, 9.1, 800)]),
			stage('s3', '2026-05-13', [wp('w3', 42.2, 9.2, 700)])
		]
	});
	const result = getActiveStageId(trip, TODAY);
	assert.equal(result, 's2');
});

test('getActiveStageId > AC-14: Trip-Status planned (Stages in Zukunft) → null', () => {
	const trip = tripWith({
		stages: [
			stage('s1', '2026-06-01', [wp('w1', 42.0, 9.0, 500)]),
			stage('s2', '2026-06-02', [wp('w2', 42.1, 9.1, 800)])
		]
	});
	const result = getActiveStageId(trip, TODAY);
	assert.equal(result, null);
});

test('getActiveStageId > Trip-Status archived (archived_at gesetzt) → null', () => {
	const trip = tripWith({
		stages: [
			stage('s1', '2026-05-12', [wp('w1', 42.0, 9.0, 500)])
		],
		archived_at: '2026-05-10T00:00:00Z'
	});
	const result = getActiveStageId(trip, TODAY);
	assert.equal(result, null);
});

test('getActiveStageId > Trip-Status paused → null', () => {
	const trip = tripWith({
		stages: [
			stage('s1', '2026-05-12', [wp('w1', 42.0, 9.0, 500)])
		],
		paused_at: '2026-05-12T00:00:00Z'
	});
	const result = getActiveStageId(trip, TODAY);
	assert.equal(result, null);
});

test('getActiveStageId > Trip-Status active aber keine Stage mit heutigem Datum (Lücke) → null', () => {
	// today = 2026-05-12 liegt zwischen 2026-05-11 und 2026-05-13 → status active,
	// aber es gibt keine Stage mit date === 2026-05-12 (Luecke).
	const trip = tripWith({
		stages: [
			stage('s1', '2026-05-11', [wp('w1', 42.0, 9.0, 500)]),
			stage('s3', '2026-05-13', [wp('w3', 42.2, 9.2, 700)])
		]
	});
	const result = getActiveStageId(trip, TODAY);
	assert.equal(result, null);
});

test('getActiveStageId > Trip ohne Stages → null (planned via deriveTripStatus)', () => {
	const trip = tripWith({ stages: [] });
	const result = getActiveStageId(trip, TODAY);
	assert.equal(result, null);
});
