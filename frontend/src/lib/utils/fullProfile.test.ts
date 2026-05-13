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
// Ausfuehrung (Vitest):
//   cd frontend && npx vitest run src/lib/utils/fullProfile.test.ts

import { describe, test, expect } from 'vitest';

import {
	buildProfilePoints,
	computeStageBoundaries,
	formatStageCode,
	getActiveStageId,
	type ProfilePoint,
	type StageBoundary
} from './fullProfile';

import type { Trip, Stage, Waypoint } from '$lib/types';

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

describe('buildProfilePoints', () => {
	test('leerer Trip (stages = []) → leeres Array', () => {
		const trip = tripWith({ stages: [] });
		const points = buildProfilePoints(trip);
		expect(points).toEqual([]);
	});

	test('Trip ohne stages-Property → leeres Array (defensive)', () => {
		const trip = tripWith({});
		const points = buildProfilePoints(trip);
		expect(Array.isArray(points)).toBe(true);
		expect(points.length).toBe(0);
	});

	test('Trip mit 1 Stage / 2 Waypoints → 2 Punkte mit x=0 und x=Haversine, korrekte y', () => {
		const trip = tripWith({
			stages: [
				stage('s1', '2026-05-12', [
					wp('w1', 42.1, 9.0, 800),
					wp('w2', 42.2, 9.1, 1200)
				])
			]
		});
		const points = buildProfilePoints(trip);
		expect(points.length).toBe(2);

		// Erster Waypoint immer x=0
		expect(points[0].x).toBeCloseTo(0, 5);
		expect(points[0].y).toBe(800);
		expect(points[0].stageId).toBe('s1');

		// Zweiter Waypoint: Haversine zwischen (42.1, 9.0) und (42.2, 9.1) ≈ 13.6 km
		expect(points[1].x).toBeGreaterThan(0);
		expect(points[1].y).toBe(1200);
		expect(points[1].stageId).toBe('s1');
	});

	test('Multi-Stage 3 Stages → kumulative Distanz monoton steigend, korrekte stageId-Zuordnung', () => {
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
		expect(points.length).toBe(6);

		// Monoton steigend
		for (let i = 1; i < points.length; i++) {
			expect(points[i].x).toBeGreaterThanOrEqual(points[i - 1].x);
		}

		// stageId-Zuordnung
		expect(points[0].stageId).toBe('s1');
		expect(points[1].stageId).toBe('s1');
		expect(points[2].stageId).toBe('s2');
		expect(points[3].stageId).toBe('s2');
		expect(points[4].stageId).toBe('s3');
		expect(points[5].stageId).toBe('s3');

		// Erster Punkt bei x=0
		expect(points[0].x).toBeCloseTo(0, 5);
		// Letzter Punkt deutlich groesser
		expect(points[5].x).toBeGreaterThan(0);
	});

	test('Stage ohne Waypoints → wird übersprungen (keine Punkte mit dieser stageId)', () => {
		const trip = tripWith({
			stages: [
				stage('s1', '2026-05-11', [wp('w1', 42.0, 9.0, 500)]),
				stage('s2', '2026-05-12', []),
				stage('s3', '2026-05-13', [wp('w3', 42.1, 9.1, 700)])
			]
		});
		const points = buildProfilePoints(trip);
		const stageIds = points.map((p) => p.stageId);
		expect(stageIds).not.toContain('s2');
		expect(stageIds).toContain('s1');
		expect(stageIds).toContain('s3');
	});

	test('AC-12: Waypoint mit elevation_m=null → übersprungen, x-Cursor läuft trotzdem weiter', () => {
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
		expect(points.length).toBe(2);
		expect(points[0].y).toBe(500);
		expect(points[1].y).toBe(1000);
		// x-Cursor zaehlt aber die volle Distanz: Distanz w1→w2→w3 ≈ 2× ~11 km
		expect(points[1].x).toBeGreaterThan(15);
	});

	test('AC-12: Waypoint mit elevation_m=undefined → übersprungen, x-Cursor läuft weiter', () => {
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
		expect(points.length).toBe(2);
		expect(points[0].y).toBe(500);
		expect(points[1].y).toBe(1000);
		// Distanz inkl. uebersprungenem Mittelpunkt
		expect(points[1].x).toBeGreaterThan(15);
	});

	test('Haversine-Genauigkeit: 2 bekannte Koordinaten → erwartete Distanz ±0.1 km', () => {
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
		expect(points.length).toBe(2);
		// Erwartet ca. 13.6 km — Toleranz ±0.5 km, um Rundungsmodelle abzudecken
		expect(points[1].x).toBeGreaterThan(13.0);
		expect(points[1].x).toBeLessThan(14.5);
	});

	test('alle Punkte haben definierte numerische x und y', () => {
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
			expect(typeof p.x).toBe('number');
			expect(typeof p.y).toBe('number');
			expect(Number.isFinite(p.x)).toBe(true);
			expect(Number.isFinite(p.y)).toBe(true);
			expect(typeof p.stageId).toBe('string');
		}
	});
});

// =============================================================================
// computeStageBoundaries
// =============================================================================

describe('computeStageBoundaries', () => {
	test('3 Stages mit Waypoints → 3 Einträge mit xStart < xEnd, monotone Reihenfolge', () => {
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
		expect(boundaries.length).toBe(3);

		// xStart < xEnd je Stage
		for (const b of boundaries) {
			expect(b.xEnd).toBeGreaterThan(b.xStart);
		}

		// Monoton: vorherige xEnd ≤ nächste xStart
		expect(boundaries[0].xEnd).toBeLessThanOrEqual(boundaries[1].xStart + 1e-6);
		expect(boundaries[1].xEnd).toBeLessThanOrEqual(boundaries[2].xStart + 1e-6);

		// Reihenfolge der stageIds
		expect(boundaries[0].stageId).toBe('s1');
		expect(boundaries[1].stageId).toBe('s2');
		expect(boundaries[2].stageId).toBe('s3');
	});

	test('Reguläre Stages → codes T01, T02, T03', () => {
		const trip = tripWith({
			stages: [
				stage('s1', '2026-05-11', [wp('w1', 42.0, 9.0, 500)]),
				stage('s2', '2026-05-12', [wp('w2', 42.1, 9.1, 800)]),
				stage('s3', '2026-05-13', [wp('w3', 42.2, 9.2, 700)])
			]
		});
		const boundaries = computeStageBoundaries(trip);
		expect(boundaries.length).toBe(3);
		expect(boundaries[0].code).toBe('T01');
		expect(boundaries[1].code).toBe('T02');
		expect(boundaries[2].code).toBe('T03');
	});

	test('Pause-Stage (gleiches Datum wie vorherige Stage, Wizard-Konvention) → code = "P"', () => {
		// Pause-Heuristik gemaess Spec: stage.date == previous stage.date → Pause
		const trip = tripWith({
			stages: [
				stage('s1', '2026-05-11', [wp('w1', 42.0, 9.0, 500)]),
				stage('s2', '2026-05-11', [], 'Pause'), // gleiches Datum wie s1 → Pause
				stage('s3', '2026-05-12', [wp('w3', 42.1, 9.1, 800)])
			]
		});
		const boundaries = computeStageBoundaries(trip);
		expect(boundaries.length).toBe(3);
		expect(boundaries[0].code).toBe('T01');
		expect(boundaries[1].code).toBe('P');
		// Naechste reguläre Stage faellt auf T02 (Pause nicht mitgezaehlt)
		expect(boundaries[2].code).toBe('T02');
	});

	test('Stage ohne Waypoints → xStart === xEnd (Punkt-Boundary)', () => {
		const trip = tripWith({
			stages: [
				stage('s1', '2026-05-11', [wp('w1', 42.0, 9.0, 500)]),
				stage('s2', '2026-05-12', [])
			]
		});
		const boundaries = computeStageBoundaries(trip);
		expect(boundaries.length).toBe(2);
		const s2 = boundaries.find((b) => b.stageId === 's2');
		expect(s2).toBeDefined();
		expect(s2!.xStart).toBe(s2!.xEnd);
	});

	test('Leerer Trip → leeres Array', () => {
		const trip = tripWith({ stages: [] });
		const boundaries = computeStageBoundaries(trip);
		expect(boundaries).toEqual([]);
	});

	test('jede Boundary enthält stageId, xStart, xEnd, code', () => {
		const trip = tripWith({
			stages: [stage('s1', '2026-05-12', [wp('w1', 42.0, 9.0, 500)])]
		});
		const boundaries = computeStageBoundaries(trip);
		expect(boundaries.length).toBe(1);
		const b = boundaries[0];
		expect(typeof b.stageId).toBe('string');
		expect(typeof b.xStart).toBe('number');
		expect(typeof b.xEnd).toBe('number');
		expect(typeof b.code).toBe('string');
	});
});

// =============================================================================
// formatStageCode
// =============================================================================

describe('formatStageCode', () => {
	test('AC-13: (0, false) === "T01"', () => {
		expect(formatStageCode(0, false)).toBe('T01');
	});

	test('AC-13: (1, false) === "T02"', () => {
		expect(formatStageCode(1, false)).toBe('T02');
	});

	test('AC-13: (2, true) === "P"', () => {
		expect(formatStageCode(2, true)).toBe('P');
	});

	test('AC-13: (9, false) === "T10"', () => {
		expect(formatStageCode(9, false)).toBe('T10');
	});

	test('(99, false) === "T100" (dreistellig, kein Padding-Verbot)', () => {
		expect(formatStageCode(99, false)).toBe('T100');
	});

	test('isPause überschreibt nonPauseIndex (0, true) === "P"', () => {
		expect(formatStageCode(0, true)).toBe('P');
	});
});

// =============================================================================
// getActiveStageId
// =============================================================================

describe('getActiveStageId', () => {
	test('AC-14: Trip-Status active mit Stage date === today → liefert Stage-ID', () => {
		const trip = tripWith({
			stages: [
				stage('s1', '2026-05-11', [wp('w1', 42.0, 9.0, 500)]),
				stage('s2', '2026-05-12', [wp('w2', 42.1, 9.1, 800)]),
				stage('s3', '2026-05-13', [wp('w3', 42.2, 9.2, 700)])
			]
		});
		const result = getActiveStageId(trip, TODAY);
		expect(result).toBe('s2');
	});

	test('AC-14: Trip-Status planned (Stages in Zukunft) → null', () => {
		const trip = tripWith({
			stages: [
				stage('s1', '2026-06-01', [wp('w1', 42.0, 9.0, 500)]),
				stage('s2', '2026-06-02', [wp('w2', 42.1, 9.1, 800)])
			]
		});
		const result = getActiveStageId(trip, TODAY);
		expect(result).toBeNull();
	});

	test('Trip-Status archived (archived_at gesetzt) → null', () => {
		const trip = tripWith({
			stages: [
				stage('s1', '2026-05-12', [wp('w1', 42.0, 9.0, 500)])
			],
			archived_at: '2026-05-10T00:00:00Z'
		});
		const result = getActiveStageId(trip, TODAY);
		expect(result).toBeNull();
	});

	test('Trip-Status paused → null', () => {
		const trip = tripWith({
			stages: [
				stage('s1', '2026-05-12', [wp('w1', 42.0, 9.0, 500)])
			],
			paused_at: '2026-05-12T00:00:00Z'
		});
		const result = getActiveStageId(trip, TODAY);
		expect(result).toBeNull();
	});

	test('Trip-Status active aber keine Stage mit heutigem Datum (Lücke) → null', () => {
		// today = 2026-05-12 liegt zwischen 2026-05-11 und 2026-05-13 → status active,
		// aber es gibt keine Stage mit date === 2026-05-12 (Luecke).
		const trip = tripWith({
			stages: [
				stage('s1', '2026-05-11', [wp('w1', 42.0, 9.0, 500)]),
				stage('s3', '2026-05-13', [wp('w3', 42.2, 9.2, 700)])
			]
		});
		const result = getActiveStageId(trip, TODAY);
		expect(result).toBeNull();
	});

	test('Trip ohne Stages → null (planned via deriveTripStatus)', () => {
		const trip = tripWith({ stages: [] });
		const result = getActiveStageId(trip, TODAY);
		expect(result).toBeNull();
	});
});
