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
