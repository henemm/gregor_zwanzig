// waypointEditor.ts — Pure Functions for Waypoint-Editor (Epic #137)
// Spec: docs/specs/modules/epic_137_wegpunkt_editor.md AC-14, AC-15

import type { Stage, Waypoint } from '$lib/types';

export interface MapPosition {
	waypointId: string;
	x: number;
	y: number;
}

export interface BoundingBox {
	minLat: number;
	maxLat: number;
	minLon: number;
	maxLon: number;
	cosLat: number;
}

/**
 * Entfernt `suggested: true` aus allen Waypoints aller Stages.
 * Gibt neue Stage-Objekte zurück — mutiert das Original nicht.
 * `suggested: false` wird ebenfalls entfernt (sauber gestrippte Payload).
 */
export function stripSuggested(stages: Stage[]): Stage[] {
	return stages.map((s) => ({
		...s,
		waypoints: s.waypoints.map((w) => {
			const { suggested: _suggested, ...rest } = w;
			return rest as Waypoint;
		})
	}));
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
 * Normiert Waypoint-Koordinaten einer Stage auf SVG-Viewport-Koordinaten.
 * Padding: 8px von allen Seiten. cosLat-Korrektur für x-Achse.
 */
export function buildMapPositions(
	stage: Stage,
	svgWidth: number,
	svgHeight: number
): MapPosition[] {
	const waypoints = stage.waypoints;
	if (waypoints.length === 0) return [];

	const padding = 8;
	const innerW = svgWidth - 2 * padding;
	const innerH = svgHeight - 2 * padding;

	if (waypoints.length === 1) {
		return [{ waypointId: waypoints[0].id, x: svgWidth / 2, y: svgHeight / 2 }];
	}

	const bb = boundingBox(waypoints);
	const xRange = (bb.maxLon - bb.minLon) * bb.cosLat;
	const yRange = bb.maxLat - bb.minLat;

	return waypoints.map((w) => {
		let x: number;
		let y: number;

		if (xRange === 0) {
			x = svgWidth / 2;
		} else {
			x = padding + ((w.lon - bb.minLon) * bb.cosLat / xRange) * innerW;
		}

		if (yRange === 0) {
			y = svgHeight / 2;
		} else {
			// Lat wächst nach Norden → y invertieren (SVG-Ursprung oben links)
			y = padding + ((bb.maxLat - w.lat) / yRange) * innerH;
		}

		return { waypointId: w.id, x, y };
	});
}
