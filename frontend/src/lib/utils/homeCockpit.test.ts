// Issue #386 — Startseite-Cockpit (Epic #368 Phase 2, Screen 1/6).
//
// Spec: docs/specs/modules/screen_home_migration.md
//
// Test-Gruppen (mock-frei, echte Trip/Stage-DTO-Form als plain Objekte):
//   1) tripStatus.ts-Util: tripStatus / activeOrNextTrip / todayStageIndex.
//   1b) stageStripState (Fix F001).
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test src/lib/utils/homeCockpit.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import { tripStatus, activeOrNextTrip, todayStageIndex } from './tripStatus.ts';
import { stageStripState } from '../../routes/_home/cockpitHelpers.ts';
import type { Trip } from '../types.ts';

// --- Test-Fixtures: echte Trip-DTO-Form (plain Objekte, KEINE Mock()) ---------

function tripWith(overrides: Partial<Trip>): Trip {
	return {
		id: 't1',
		name: 'Test Trip',
		stages: [],
		...overrides
	} as Trip;
}

// Heute fix für deterministische Tests (kein new Date() ohne Argument).
const TODAY = new Date('2026-05-12T09:00:00Z');

// Trip, dessen Etappen heute (2026-05-12) einschließen → aktiv, Tag 2 von 3.
const ACTIVE_TRIP = tripWith({
	id: 'khw',
	name: 'KHW 403',
	stages: [
		{ id: 's1', name: 'D1', date: '2026-05-11', waypoints: [] },
		{ id: 's2', name: 'D2', date: '2026-05-12', waypoints: [] },
		{ id: 's3', name: 'D3', date: '2026-05-13', waypoints: [] }
	]
});

// Trip, dessen Etappen alle in der Zukunft liegen → geplant.
const PLANNED_TRIP = tripWith({
	id: 'gr20',
	name: 'GR20',
	stages: [
		{ id: 'p1', name: 'D1', date: '2026-06-01', waypoints: [] },
		{ id: 'p2', name: 'D2', date: '2026-06-02', waypoints: [] }
	]
});

// Trip, dessen Etappen alle in der Vergangenheit liegen → fertig.
const FINISHED_TRIP = tripWith({
	id: 'tmb',
	name: 'TMB',
	stages: [
		{ id: 'f1', name: 'D1', date: '2026-04-01', waypoints: [] },
		{ id: 'f2', name: 'D2', date: '2026-04-02', waypoints: [] }
	]
});

// Trip ganz ohne datierte Etappen → draft.
const DRAFT_TRIP = tripWith({ id: 'draft', name: 'Entwurf', stages: [] });

// ============================================================================
// 1) tripStatus-Util
// ============================================================================

test('AC-1: tripStatus → aktiv wenn heute zwischen erster und letzter Etappe', () => {
	assert.equal(tripStatus(ACTIVE_TRIP, TODAY), 'aktiv');
});

test('AC-11: tripStatus → geplant wenn alle Etappen in der Zukunft', () => {
	assert.equal(tripStatus(PLANNED_TRIP, TODAY), 'geplant');
});

test('AC-7: tripStatus → fertig wenn alle Etappen in der Vergangenheit', () => {
	assert.equal(tripStatus(FINISHED_TRIP, TODAY), 'fertig');
});

test('tripStatus → draft wenn keine datierten Etappen', () => {
	assert.equal(tripStatus(DRAFT_TRIP, TODAY), 'draft');
});

test('tripStatus → fertig wenn archived_at gesetzt (auch ohne Vergangenheit)', () => {
	const t = tripWith({ id: 'a', archived_at: '2026-05-01T00:00:00Z', stages: PLANNED_TRIP.stages });
	assert.equal(tripStatus(t, TODAY), 'fertig');
});

test('AC-1: activeOrNextTrip → heute aktiver Trip gewinnt vor geplantem', () => {
	const picked = activeOrNextTrip([PLANNED_TRIP, ACTIVE_TRIP, FINISHED_TRIP], TODAY);
	assert.equal(picked?.id, 'khw');
});

test('AC-11: activeOrNextTrip → keine aktiv → nächste anstehende (frühestes Startdatum ≥ heute)', () => {
	const soon = tripWith({
		id: 'soon',
		stages: [{ id: 'x', name: 'D1', date: '2026-05-20', waypoints: [] }]
	});
	const later = tripWith({
		id: 'later',
		stages: [{ id: 'y', name: 'D1', date: '2026-07-01', waypoints: [] }]
	});
	const picked = activeOrNextTrip([later, FINISHED_TRIP, soon], TODAY);
	assert.equal(picked?.id, 'soon');
});

test('AC-11: activeOrNextTrip → alle abgeschlossen → null', () => {
	assert.equal(activeOrNextTrip([FINISHED_TRIP], TODAY), null);
});

test('AC-8: activeOrNextTrip → leere Liste → null', () => {
	assert.equal(activeOrNextTrip([], TODAY), null);
});

test('AC-1: todayStageIndex → 0-basierter Index der heutigen Etappe', () => {
	assert.equal(todayStageIndex(ACTIVE_TRIP, TODAY), 1); // s2 = 2026-05-12
});

test('AC-4: todayStageIndex → -1 wenn keine Etappe heute ist', () => {
	assert.equal(todayStageIndex(PLANNED_TRIP, TODAY), -1);
});

test('todayStageIndex → -1 bei Trip ohne Etappen', () => {
	assert.equal(todayStageIndex(DRAFT_TRIP, TODAY), -1);
});

// ============================================================================
// 1b) Etappen-Streifen-Zustand (stageStripState) — Fix F001 (Issue #386)
// ============================================================================

test('AC-4/F001: geplanter Trip (todayIdx < 0) → ALLE Etappen future, nie active', () => {
	// Hero ist "Nächster Trip": keine Etappe läuft heute → kein 'active'.
	assert.equal(stageStripState(-1, 0), 'future');
	assert.equal(stageStripState(-1, 1), 'future');
	assert.equal(stageStripState(-1, 2), 'future');
});

test('AC-4: aktiver Trip (todayIdx = 2, 5 Etappen) → done/done/active/future/future', () => {
	const todayIdx = 2;
	assert.equal(stageStripState(todayIdx, 0), 'done');
	assert.equal(stageStripState(todayIdx, 1), 'done');
	assert.equal(stageStripState(todayIdx, 2), 'active');
	assert.equal(stageStripState(todayIdx, 3), 'future');
	assert.equal(stageStripState(todayIdx, 4), 'future');
});

// Die frühere Gruppe "2) Cockpit-Source-Inspection (+page.svelte)" (8 Tests,
// readFileSync + Regex gegen +page.svelte) wurde entfernt: Dateiinhalt-Checks
// sind laut CLAUDE.md verboten (Präzedenz #893). Die Verhaltens-Tests der
// Gruppen 1 und 1b oben bleiben unverändert bestehen.
