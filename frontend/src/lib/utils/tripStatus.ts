// Spec: docs/specs/modules/epic_135_step2_trip_detail_actions.md (§4)
// Pure function. Reihenfolge (verbindlich):
//   1. archived_at gesetzt → 'archived'
//   2. paused_at gesetzt → 'paused'
//   3. heute zwischen erstem und letztem Stage-Datum → 'active'
//   4. sonst → 'planned'

import type { Trip } from '$lib/types';

export type TripStatus = 'planned' | 'active' | 'paused' | 'archived';

export function deriveTripStatus(trip: Trip, now: Date): TripStatus {
	if (trip.archived_at != null) return 'archived';
	if (trip.paused_at != null) return 'paused';

	const stages = trip.stages ?? [];
	if (stages.length === 0) return 'planned';

	const dates = stages.map((s) => s.date).filter((d): d is string => !!d);
	if (dates.length === 0) return 'planned';

	// Lokal sortieren — Stages dürfen in beliebiger Reihenfolge ankommen.
	// ISO-Datumsstrings (YYYY-MM-DD) sind lexikographisch == chronologisch sortierbar.
	const sorted = [...dates].sort();

	// Datums-Vergleich auf Tageskorn (Zeit auf 00:00 normalisieren).
	const first = new Date(sorted[0] + 'T00:00:00Z');
	const last = new Date(sorted[sorted.length - 1] + 'T00:00:00Z');
	const today = new Date(now.toISOString().slice(0, 10) + 'T00:00:00Z');

	if (today >= first && today <= last) return 'active';
	return 'planned';
}

// ---------------------------------------------------------------------------
// Issue #386 — Startseite-Cockpit (Epic #368 Phase 2). Deutschsprachige
// Status-Variante + Hero-Selektion. Aus _home/TripKachel.svelte extrahiert,
// damit Kachel und Cockpit dieselbe Quelle teilen.
// Spec: docs/specs/modules/screen_home_migration.md
// ---------------------------------------------------------------------------

export type HomeTripStatus = 'aktiv' | 'geplant' | 'fertig' | 'draft';

/** Lokales ISO-Datum (YYYY-MM-DD) aus einem Date (Tageskorn). */
function isoDay(now: Date): string {
	const y = now.getFullYear();
	const m = String(now.getMonth() + 1).padStart(2, '0');
	const d = String(now.getDate()).padStart(2, '0');
	return `${y}-${m}-${d}`;
}

/** Sortierte Etappen-Datumsstrings (ISO == lexikographisch == chronologisch). */
function sortedDates(trip: Trip): string[] {
	return (trip.stages ?? [])
		.map((s) => s.date)
		.filter((d): d is string => !!d)
		.map((d) => d.slice(0, 10))
		.sort();
}

/**
 * Deutschsprachiger Trip-Status fürs Cockpit:
 *   - `archived_at` gesetzt → 'fertig'
 *   - keine datierten Etappen → 'draft'
 *   - letztes Etappen-Datum < heute → 'fertig'
 *   - erstes Etappen-Datum ≤ heute ≤ letztes → 'aktiv'
 *   - sonst (alle in Zukunft) → 'geplant'
 */
export function tripStatus(trip: Trip, now: Date = new Date()): HomeTripStatus {
	if (trip.archived_at != null) return 'fertig';
	const dates = sortedDates(trip);
	if (dates.length === 0) return 'draft';
	const today = isoDay(now);
	if (dates[dates.length - 1] < today) return 'fertig';
	if (dates[0] <= today) return 'aktiv';
	return 'geplant';
}

/**
 * Wählt die Hero-Tour fürs Cockpit:
 *   1. heute aktive Tour (erste in Eingabereihenfolge), sonst
 *   2. nächste anstehende Tour (kleinstes Etappen-Startdatum ≥ heute), sonst
 *   3. null (alle abgeschlossen oder Liste leer).
 */
export function activeOrNextTrip(trips: Trip[], now: Date = new Date()): Trip | null {
	const list = trips ?? [];
	const active = list.find((t) => tripStatus(t, now) === 'aktiv');
	if (active) return active;

	const today = isoDay(now);
	let best: Trip | null = null;
	let bestStart: string | null = null;
	for (const t of list) {
		if (tripStatus(t, now) !== 'geplant') continue;
		const dates = sortedDates(t);
		const start = dates[0];
		if (!start || start < today) continue;
		if (bestStart === null || start < bestStart) {
			bestStart = start;
			best = t;
		}
	}
	return best;
}

/** 0-basierter Index der heutigen Etappe (Original-Reihenfolge), sonst -1. */
export function todayStageIndex(trip: Trip, now: Date = new Date()): number {
	const today = isoDay(now);
	const stages = trip.stages ?? [];
	return stages.findIndex((s) => (s.date ?? '').slice(0, 10) === today);
}
