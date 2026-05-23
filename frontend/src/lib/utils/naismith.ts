// naismith.ts — clientseitige Live-Berechnung der Naismith-Ankunftszeiten.
// Issue #296-FE. Spec: docs/specs/modules/issue_296_fe_profile_editor.md §1 (AC-5, AC-6)
//
// Konstanten + Formel gespiegelt aus:
//   - src/app/models.py EtappenConfig (Single Source: speed_flat_kmh=4.0,
//     speed_ascent_mh=300.0, speed_descent_mh=500.0)
//   - internal/model/naismith.go (naismithHours, ComputeStageArrivals, Clamp 23:59)
// Bei Änderung dort: hier nachziehen, damit Editor-Anzeige (vor Save) ==
// persistierter Wert (nach Save) == Pipeline-Zeit.
//
// Distanz: gemeinsame haversineKm aus headerStats.ts (DRY, kein eigener Haversine).

import { haversineKm } from '../components/email-preview/headerStats.ts';
import type { Stage } from '../types';

const SPEED_FLAT_KMH = 4.0;
const SPEED_ASCENT_MH = 300.0;
const SPEED_DESCENT_MH = 500.0;

const DEFAULT_START_TIME = '08:00';
const MAX_MINUTES = 24 * 60 - 1; // "23:59" — Clamp analog naismith.go::formatHHMM

/** Angepasste Naismith's Rule (SUMME, nicht max!). distKm + Höhenmeter → Stunden. */
export function naismithHours(distKm: number, ascentM: number, descentM: number): number {
	return distKm / SPEED_FLAT_KMH + ascentM / SPEED_ASCENT_MH + descentM / SPEED_DESCENT_MH;
}

/** Parst "HH:MM" in Minuten ab Mitternacht; unsinnige Zeit → Default. (naismith.go::parseStartMinutes) */
function parseStartMinutes(startTime?: string): number {
	const s = startTime && startTime !== '' ? startTime : DEFAULT_START_TIME;
	const m = /^(\d{1,2}):(\d{1,2})$/.exec(s);
	if (m) {
		const h = Number(m[1]);
		const min = Number(m[2]);
		if (h >= 0 && h <= 23 && min >= 0 && min <= 59) {
			return h * 60 + min;
		}
	}
	const [dh, dm] = DEFAULT_START_TIME.split(':').map(Number);
	return dh * 60 + dm;
}

/** Formatiert Minuten ab Mitternacht als "HH:MM", Clamp auf "23:59". (naismith.go::formatHHMM) */
function formatHHMM(totalMin: number): string {
	const clamped = totalMin > MAX_MINUTES ? MAX_MINUTES : totalMin;
	const h = Math.floor(clamped / 60);
	const m = clamped % 60;
	return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
}

/**
 * Kumulative Ankunftszeiten pro Wegpunkt einer Stage als "HH:MM".
 * startTime "HH:MM" (default "08:00"). Distanz via haversineKm (headerStats).
 * Pausentag (0 Wegpunkte) → []. Erster Wegpunkt = startTime.
 * Spiegelt naismith.go::ComputeStageArrivals.
 */
export function computeArrivalTimes(stage: Stage, startTime?: string): string[] {
	const wps = stage.waypoints;
	if (!wps || wps.length === 0) return [];

	let cur = parseStartMinutes(startTime);
	const arrivals: string[] = [formatHHMM(Math.round(cur))];

	for (let i = 1; i < wps.length; i++) {
		const prev = wps[i - 1];
		const wp = wps[i];
		const dist = haversineKm(prev, wp);
		const dElev = wp.elevation_m - prev.elevation_m;
		const ascent = Math.max(0, dElev);
		const descent = Math.max(0, -dElev);
		cur += naismithHours(dist, ascent, descent) * 60.0;
		arrivals.push(formatHHMM(Math.round(cur)));
	}

	return arrivals;
}
