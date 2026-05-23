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
 * Berechnet Header-Statistiken für eine Etappe aus ihren Waypoints.
 *
 * - distanceKm: Summe der Haversine-Distanzen zwischen aufeinanderfolgenden Waypoints
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
	let distanceKm = 0;
	let ascentM = 0;
	let descentM = 0;
	let maxElevationM = wps[0].elevation_m;

	for (let i = 0; i < wps.length; i++) {
		if (wps[i].elevation_m > maxElevationM) {
			maxElevationM = wps[i].elevation_m;
		}
		if (i > 0) {
			distanceKm += haversineKm(wps[i - 1], wps[i]);
			const delta = wps[i].elevation_m - wps[i - 1].elevation_m;
			if (delta > 0) ascentM += delta;
			else descentM += -delta;
		}
	}

	return {
		distanceKm: Math.round(distanceKm * 100) / 100,
		ascentM: Math.round(ascentM),
		descentM: Math.round(descentM),
		maxElevationM: Math.round(maxElevationM),
		segmentCount: wps.length - 1
	};
}
