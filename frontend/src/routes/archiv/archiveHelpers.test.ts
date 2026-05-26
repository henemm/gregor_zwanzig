// TDD RED: Issue #388 — Archiv-Bildschirm (Epic #368 Phase 2, Screen 3/6).
//
// Spec: docs/specs/modules/screen_archive_migration.md
//
// Mock-freie Unit-Tests (echte Trip/Stage-DTO-Form als plain Objekte, KEINE
// Mock()/patch()) fuer die zwei reinen Helfer der Archiv-Seite:
//   - filterArchived(trips, now): nur deriveTripStatus(...) === 'archived'.
//   - sortArchive(trips, mode):   'recent' (Enddatum absteigend),
//                                 'stages' (Etappen-Anzahl absteigend).
//
// RED vor Implementierung: ./archiveHelpers.ts existiert NICHT → Import FAIL.
//
// Ausfuehrung:
//   cd frontend && node --test --experimental-strip-types \
//     src/routes/archiv/archiveHelpers.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import { filterArchived, sortArchive } from './archiveHelpers.ts';
import type { Trip } from '$lib/types';

// --- Test-Fixtures: echte Trip-DTO-Form (plain Objekte, KEINE Mock()) ---------

function tripWith(overrides: Partial<Trip>): Trip {
	return {
		id: 't0',
		name: 'Test Trip',
		stages: [],
		...overrides
	} as Trip;
}

// Heute fix fuer deterministische Tests (kein new Date() ohne Argument).
const TODAY = new Date('2026-05-26T09:00:00Z');

// Explizit archiviert (archived_at gesetzt) → 'archived'.
const ARCHIVED_A = tripWith({
	id: 'arch-a',
	name: 'GR20 2024',
	archived_at: '2024-09-30T00:00:00Z',
	stages: [
		{ id: 'a1', name: 'D1', date: '2024-09-01', waypoints: [] },
		{ id: 'a2', name: 'D2', date: '2024-09-02', waypoints: [] },
		{ id: 'a3', name: 'D3', date: '2024-09-03', waypoints: [] }
	]
});

// Zweiter archivierter Trip, jüngeres Enddatum, weniger Etappen.
const ARCHIVED_B = tripWith({
	id: 'arch-b',
	name: 'KHW 2025',
	archived_at: '2025-08-15T00:00:00Z',
	stages: [
		{ id: 'b1', name: 'D1', date: '2025-08-10', waypoints: [] },
		{ id: 'b2', name: 'D2', date: '2025-08-11', waypoints: [] }
	]
});

// Aktiver Trip (Etappen schliessen heute ein) → NICHT archiviert.
const ACTIVE = tripWith({
	id: 'active',
	name: 'Stubai aktiv',
	stages: [
		{ id: 'c1', name: 'D1', date: '2026-05-25', waypoints: [] },
		{ id: 'c2', name: 'D2', date: '2026-05-27', waypoints: [] }
	]
});

// Geplanter Trip (alle Etappen in Zukunft) → NICHT archiviert.
const PLANNED = tripWith({
	id: 'planned',
	name: 'Zillertal geplant',
	stages: [{ id: 'd1', name: 'D1', date: '2026-07-01', waypoints: [] }]
});

// Pausierter Trip (paused_at gesetzt) → NICHT archiviert.
const PAUSED = tripWith({
	id: 'paused',
	name: 'Pausiert',
	paused_at: '2026-05-01T00:00:00Z',
	stages: [{ id: 'e1', name: 'D1', date: '2026-06-01', waypoints: [] }]
});

const ALL = [ACTIVE, ARCHIVED_A, PLANNED, ARCHIVED_B, PAUSED];

// --- filterArchived -----------------------------------------------------------

test('filterArchived: liefert nur archivierte Trips (archived_at gesetzt)', () => {
	const result = filterArchived(ALL, TODAY);
	const ids = result.map((t) => t.id).sort();
	assert.deepEqual(ids, ['arch-a', 'arch-b']);
});

test('filterArchived: aktive/geplante/pausierte erscheinen NICHT', () => {
	const result = filterArchived(ALL, TODAY);
	const ids = result.map((t) => t.id);
	assert.ok(!ids.includes('active'), 'aktiver Trip darf nicht auftauchen');
	assert.ok(!ids.includes('planned'), 'geplanter Trip darf nicht auftauchen');
	assert.ok(!ids.includes('paused'), 'pausierter Trip darf nicht auftauchen');
});

test('filterArchived: leere Liste → leeres Ergebnis', () => {
	assert.deepEqual(filterArchived([], TODAY), []);
});

test('filterArchived: keine archivierten Trips → leeres Ergebnis', () => {
	assert.deepEqual(filterArchived([ACTIVE, PLANNED, PAUSED], TODAY), []);
});

// --- sortArchive --------------------------------------------------------------

test("sortArchive 'recent': Enddatum absteigend (jüngstes zuerst)", () => {
	const sorted = sortArchive([ARCHIVED_A, ARCHIVED_B], 'recent');
	// ARCHIVED_B endet 2025-08-11, ARCHIVED_A endet 2024-09-03 → B zuerst.
	assert.deepEqual(sorted.map((t) => t.id), ['arch-b', 'arch-a']);
});

test("sortArchive 'stages': Etappen-Anzahl absteigend (meiste zuerst)", () => {
	const sorted = sortArchive([ARCHIVED_B, ARCHIVED_A], 'stages');
	// ARCHIVED_A hat 3 Etappen, ARCHIVED_B hat 2 → A zuerst.
	assert.deepEqual(sorted.map((t) => t.id), ['arch-a', 'arch-b']);
});

test('sortArchive: gibt eine neue Liste zurück (kein Mutieren des Inputs)', () => {
	const input = [ARCHIVED_A, ARCHIVED_B];
	const before = input.map((t) => t.id);
	sortArchive(input, 'recent');
	assert.deepEqual(input.map((t) => t.id), before, 'Input darf nicht mutiert werden');
});

test('sortArchive: leere Liste → leeres Ergebnis', () => {
	assert.deepEqual(sortArchive([], 'recent'), []);
	assert.deepEqual(sortArchive([], 'stages'), []);
});
