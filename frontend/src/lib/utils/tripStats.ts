// Issue #302 — Aggregierte Trip-Statistiken (Etappenanzahl + Summe km + Summe Höhenmeter).
// Spec: docs/specs/modules/issue_302_trip_detail_page.md
//
// Reine Pure-Function. Summiert `computeHeaderStats(stage)` über alle Stages —
// `headerStats` rundet bereits pro Stage, das ist für den Trip-Header gewollt
// ("ehrliche Anzeige aus geprüften Pro-Etappen-Werten").

import { computeHeaderStats } from '../components/email-preview/headerStats.ts';
import type { Trip } from '../types.ts';

export interface TripStats {
	stages: number;
	kmTotal: number;
	ascentM: number;
}

export function computeTripStats(trip: Trip): TripStats {
	const stages = trip.stages ?? [];
	let kmTotal = 0;
	let ascentM = 0;
	for (const stage of stages) {
		const s = computeHeaderStats(stage);
		kmTotal += s.distanceKm ?? 0;
		ascentM += s.ascentM ?? 0;
	}
	return { stages: stages.length, kmTotal, ascentM };
}
