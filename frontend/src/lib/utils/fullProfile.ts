// Epic #135 Step 4 — Pure-Functions fuer Full-Profil (Issues #156 + #157).
// Spec: docs/specs/modules/epic_135_step4_left_column.md
//
// Vier Pure-Functions:
//   - buildProfilePoints(trip): kumulative {x,y,stageId}-Liste ueber alle Waypoints
//   - computeStageBoundaries(trip): pro Stage {xStart,xEnd,code}
//   - formatStageCode(nonPauseIndex,isPause): 'T01' | 'T02' | ... | 'P'
//   - getActiveStageId(trip,now): heutige Stage-ID wenn Trip 'active', sonst null
//
// Seiteneffektfrei. Haversine-Distanz analog zu email-preview/headerStats.ts.

import type { Trip, Stage, Waypoint } from '$lib/types';
import { deriveTripStatus } from './tripStatus.ts';

export interface ProfilePoint {
	x: number; // kumulative Distanz in km
	y: number; // elevation_m
	stageId: string;
}

export interface StageBoundary {
	stageId: string;
	xStart: number;
	xEnd: number;
	code: string;
}

const EARTH_RADIUS_KM = 6371.0088;

function haversineKm(a: Waypoint, b: Waypoint): number {
	const toRad = (deg: number) => (deg * Math.PI) / 180;
	const dLat = toRad(b.lat - a.lat);
	const dLon = toRad(b.lon - a.lon);
	const lat1 = toRad(a.lat);
	const lat2 = toRad(b.lat);
	const x =
		Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;
	return 2 * EARTH_RADIUS_KM * Math.asin(Math.min(1, Math.sqrt(x)));
}

function hasElevation(wp: Waypoint): boolean {
	const e = wp.elevation_m as number | null | undefined;
	return e !== null && e !== undefined && Number.isFinite(e);
}

/**
 * Iteriert ueber alle Stages und Waypoints in Reihenfolge und liefert pro Waypoint
 * mit gueltigem `elevation_m` einen `{x,y,stageId}`-Punkt. Der x-Cursor (cumKm)
 * wird stage-uebergreifend monoton hochgezaehlt — auch bei uebersprungenen
 * Waypoints (null/undefined elevation).
 */
export function buildProfilePoints(trip: Trip): ProfilePoint[] {
	const stages = trip?.stages ?? [];
	const points: ProfilePoint[] = [];
	let cumKm = 0;
	let prevWp: Waypoint | null = null;

	for (const stage of stages) {
		const wps = stage?.waypoints ?? [];
		for (const wp of wps) {
			if (prevWp !== null) {
				cumKm += haversineKm(prevWp, wp);
			}
			if (hasElevation(wp)) {
				points.push({ x: cumKm, y: wp.elevation_m, stageId: stage.id });
			}
			prevWp = wp;
		}
	}

	return points;
}

/**
 * Liefert pro Stage `{stageId, xStart, xEnd, code}`. Der x-Cursor wird parallel zu
 * `buildProfilePoints` mitgefuehrt (Distanz zwischen aufeinanderfolgenden Waypoints,
 * stage-uebergreifend). Stages ohne Waypoints behalten `xStart === xEnd`.
 * Code-Heuristik:
 *   - Stage mit `date` identisch zur vorherigen Stage → Pause ('P')
 *   - sonst: 'T' + (nonPauseIndex + 1) zweistellig
 */
export function computeStageBoundaries(trip: Trip): StageBoundary[] {
	const stages = trip?.stages ?? [];
	const out: StageBoundary[] = [];
	let cumKm = 0;
	let prevWp: Waypoint | null = null;
	let nonPauseIndex = 0;
	let prevDate: string | null = null;

	for (const stage of stages) {
		const wps = stage?.waypoints ?? [];
		const isPause = prevDate !== null && stage.date === prevDate;
		const code = formatStageCode(nonPauseIndex, isPause);

		const xStart = cumKm;
		// Distanzen innerhalb der Stage durchlaufen.
		for (const wp of wps) {
			if (prevWp !== null) {
				cumKm += haversineKm(prevWp, wp);
			}
			prevWp = wp;
		}
		const xEnd = cumKm;

		out.push({ stageId: stage.id, xStart, xEnd, code });

		if (!isPause) {
			nonPauseIndex++;
		}
		prevDate = stage.date ?? prevDate;
	}

	return out;
}

/**
 * Stage-Code-Format:
 *   formatStageCode(0, false) === 'T01'
 *   formatStageCode(9, false) === 'T10'
 *   formatStageCode(99, false) === 'T100'  // dreistellig erlaubt
 *   formatStageCode(_, true)   === 'P'
 */
export function formatStageCode(nonPauseIndex: number, isPause: boolean): string {
	if (isPause) return 'P';
	const n = nonPauseIndex + 1;
	return 'T' + String(n).padStart(2, '0');
}

/**
 * Liefert die heutige Stage-ID, wenn `deriveTripStatus(trip, now) === 'active'`
 * und es eine Stage mit `date === today` gibt. Sonst `null`.
 */
export function getActiveStageId(trip: Trip, now: Date): string | null {
	if (deriveTripStatus(trip, now) !== 'active') return null;
	const y = now.getFullYear();
	const m = String(now.getMonth() + 1).padStart(2, '0');
	const d = String(now.getDate()).padStart(2, '0');
	const today = `${y}-${m}-${d}`;

	const stages = trip?.stages ?? [];
	const match = stages.find((s) => (s.date ?? '').slice(0, 10) === today);
	return match?.id ?? null;
}
