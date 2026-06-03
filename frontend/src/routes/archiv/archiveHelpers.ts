// Issue #388 — Archiv-Bildschirm (Epic #368 Phase 2, Screen 3/6).
//
// Spec: docs/specs/modules/screen_archive_migration.md
//
// Zwei reine Helfer fuer die Archiv-Seite. Keine Seiteneffekte, kein Fetch —
// die Seite laedt die Trips und reicht sie hier durch.

import type { Trip } from '$lib/types';
// Relativer Wert-Import (statt $lib-Alias), damit der reine Helfer auch unter
// dem Node-Test-Runner (`node --test --experimental-strip-types`) auflösbar
// bleibt. Vite löst $lib-Alias und relativen Pfad zur Laufzeit identisch auf.
import { deriveTripStatus } from '../../lib/utils/tripStatus.ts';

export type ArchiveSortMode = 'recent' | 'stages';

/** Sortiertes Etappen-Enddatum (ISO YYYY-MM-DD), '' wenn keine datierten Etappen. */
function endDate(trip: Trip): string {
	const dates = (trip.stages ?? [])
		.map((s) => s.date)
		.filter((d): d is string => !!d)
		.map((d) => d.slice(0, 10))
		.sort();
	return dates.length ? dates[dates.length - 1] : '';
}

/** Nur Trips, deren Status 'archived' ist (archived_at gesetzt). */
export function filterArchived(trips: Trip[], now: Date): Trip[] {
	return (trips ?? []).filter((t) => deriveTripStatus(t, now) === 'archived');
}

/**
 * Sortiert eine Kopie der Liste:
 *   - 'recent': Enddatum absteigend (jüngstes Ende zuerst).
 *   - 'stages': Etappen-Anzahl absteigend (meiste zuerst).
 */
export function sortArchive(trips: Trip[], mode: ArchiveSortMode): Trip[] {
	const list = [...(trips ?? [])];
	if (mode === 'stages') {
		return list.sort((a, b) => (b.stages?.length ?? 0) - (a.stages?.length ?? 0));
	}
	// 'recent' — Enddatum absteigend; leeres Enddatum landet hinten.
	return list.sort((a, b) => endDate(b).localeCompare(endDate(a)));
}

/**
 * Erzeugt die Ereignis-Zusammenfassung für die "Was passiert ist"-Spalte.
 * Issue #559 AC-3.
 */
export function formatEventSummary(briefings: number, alerts: number): string {
	if (!briefings && !alerts) return '—';
	const b = `${briefings} Briefing${briefings !== 1 ? 's' : ''}`;
	if (!alerts) return b;
	return `${b} · ${alerts} Alert${alerts !== 1 ? 's' : ''}`;
}
