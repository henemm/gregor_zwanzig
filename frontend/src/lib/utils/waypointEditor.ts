// waypointEditor.ts — Pure Functions for Waypoint-Editor (Epic #137)
// Spec: docs/specs/modules/epic_137_wegpunkt_editor.md AC-14
//
// Issue #495: SVG-Projektion entfernt — Leaflet übernimmt sie.
// `boundingBox` bleibt (eigene Tests).

import type { Waypoint } from '$lib/types';

export interface BoundingBox {
	minLat: number;
	maxLat: number;
	minLon: number;
	maxLon: number;
	cosLat: number;
}

/**
 * Berechnet die Bounding Box einer Waypoint-Liste mit cosLat-Korrektur.
 * Bei leerem Array: alle Werte 0.
 */
export function boundingBox(waypoints: Waypoint[]): BoundingBox {
	if (waypoints.length === 0) {
		return { minLat: 0, maxLat: 0, minLon: 0, maxLon: 0, cosLat: 0 };
	}
	const lats = waypoints.map((w) => w.lat);
	const lons = waypoints.map((w) => w.lon);
	const minLat = Math.min(...lats);
	const maxLat = Math.max(...lats);
	const minLon = Math.min(...lons);
	const maxLon = Math.max(...lons);
	const centerLat = (minLat + maxLat) / 2;
	const cosLat = Math.cos((centerLat * Math.PI) / 180);
	return { minLat, maxLat, minLon, maxLon, cosLat };
}

/**
 * Linear interpolierter neuer Wegpunkt aus einer fraction (0..1) über den
 * Wegpunkt-Index-Raum. Gibt lat/lon/elevation_m + Einfügeindex zurück.
 * Issue #296-FE. Spec: docs/specs/modules/issue_296_fe_profile_editor.md §3 (AC-7).
 *
 *   floatIdx = fraction * (n-1); i = floor(floatIdx); t = floatIdx - i.
 *   Felder = lerp(wp[i], wp[i+1], t). insertAfterIndex = i.
 *
 * Edge-Cases:
 *   - n === 0 → Nullpunkt {0,0,0, insertAfterIndex -1}
 *   - n === 1 → exakt wp[0], insertAfterIndex 0
 *   - fraction wird auf [0,1] geclamped
 */
export function interpolateWaypoint(
	waypoints: Waypoint[],
	fraction: number
): { lat: number; lon: number; elevation_m: number; insertAfterIndex: number } {
	const n = waypoints.length;
	if (n === 0) {
		return { lat: 0, lon: 0, elevation_m: 0, insertAfterIndex: -1 };
	}
	if (n === 1) {
		const a = waypoints[0];
		return { lat: a.lat, lon: a.lon, elevation_m: a.elevation_m, insertAfterIndex: 0 };
	}

	const f = Math.min(1, Math.max(0, fraction));
	const floatIdx = f * (n - 1);
	let i = Math.floor(floatIdx);
	if (i >= n - 1) i = n - 2; // fraction === 1 → letztes Segment, t === 1
	const t = floatIdx - i;

	const a = waypoints[i];
	const b = waypoints[i + 1];
	return {
		lat: a.lat + (b.lat - a.lat) * t,
		lon: a.lon + (b.lon - a.lon) * t,
		elevation_m: a.elevation_m + (b.elevation_m - a.elevation_m) * t,
		insertAfterIndex: i
	};
}

