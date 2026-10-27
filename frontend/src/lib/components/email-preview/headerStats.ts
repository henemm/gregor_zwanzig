// Issue #183 — Email-Preview Header: pure-function Stats-Berechnung.
// Spec: docs/specs/modules/issue_183_email_preview_header.md

import type { Stage, Waypoint } from '../../types';

export interface HeaderStats {
	distanceKm: number;
	ascentM: number;
	descentM: number;
	maxElevationM: number;
	segmentCount: number;
}

const EARTH_RADIUS_KM = 6371.0088;

/** Haversine-Distanz zwischen zwei Punkten in km. */
export function haversineKm(a: Waypoint, b: Waypoint): number {
	const toRad = (deg: number) => (deg * Math.PI) / 180;
	const dLat = toRad(b.lat - a.lat);
	const dLon = toRad(b.lon - a.lon);
	const lat1 = toRad(a.lat);
	const lat2 = toRad(b.lat);
	const x =
		Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;
	return 2 * EARTH_RADIUS_KM * Math.asin(Math.min(1, Math.sqrt(x)));
}

/**
 * Issue #2110 — true, wenn ALLE Wegpunkte der Etappe eine echte, aus dem GPX-Track
 * vermessene Distanz (`distance_from_start_km`) tragen. Nur dann darf die Track-Distanz
 * statt der Haversine-Luftlinie genutzt werden; ein einziger fehlender Wert lässt die
 * GESAMTE Etappe auf Haversine zurückfallen (kein segmentweises Mischen).
 */
export function stageHasFullTrackDistance(wps: Waypoint[] | null | undefined): boolean {
	if (!wps || wps.length === 0) return false;
	return wps.every((wp) => {
		const d = wp?.distance_from_start_km;
		return d !== undefined && d !== null && Number.isFinite(d);
	});
}

/**
 * Berechnet Header-Statistiken für eine Etappe aus ihren Waypoints.
 *
 * - distanceKm: Track-Distanz (letzter minus erster `distance_from_start_km`), wenn die
 *   Etappe vollständig vermessen ist (#2110), sonst Summe der Haversine-Distanzen
 *   zwischen aufeinanderfolgenden Waypoints
 * - ascentM: Summe positiver Höhendifferenzen
 * - descentM: Summe negativer Höhendifferenzen (als positiver Wert)
 * - maxElevationM: Max über alle Waypoints
 * - segmentCount: Anzahl Strecken zwischen Waypoints (= len - 1)
 *
 * Defensive Defaults: null/undef Stage oder leere Waypoints → alle Stats = 0.
 */
export function computeHeaderStats(stage: Stage | null | undefined): HeaderStats {
	const empty: HeaderStats = {
		distanceKm: 0,
		ascentM: 0,
		descentM: 0,
		maxElevationM: 0,
		segmentCount: 0
	};
	if (!stage || !stage.waypoints || stage.waypoints.length === 0) {
		return empty;
	}
	const wps = stage.waypoints;
	const useTrack = stageHasFullTrackDistance(wps);
	let distanceKm = 0;
	let ascentM = 0;
	let descentM = 0;
	let maxElevationM = wps[0].elevation_m;

	for (let i = 0; i < wps.length; i++) {
		if (wps[i].elevation_m > maxElevationM) {
			maxElevationM = wps[i].elevation_m;
		}
		if (i > 0) {
			if (!useTrack) distanceKm += haversineKm(wps[i - 1], wps[i]);
			const delta = wps[i].elevation_m - wps[i - 1].elevation_m;
			if (delta > 0) ascentM += delta;
			else descentM += -delta;
		}
	}

	if (useTrack) {
		distanceKm =
			(wps[wps.length - 1].distance_from_start_km as number) -
			(wps[0].distance_from_start_km as number);
	}

	return {
		distanceKm: Math.round(distanceKm * 100) / 100,
		ascentM: Math.round(ascentM),
		descentM: Math.round(descentM),
		maxElevationM: Math.round(maxElevationM),
		segmentCount: wps.length - 1
	};
}
