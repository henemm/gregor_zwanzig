// TDD RED: Issue #386 — Startseite-Cockpit (Epic #368 Phase 2, Screen 1/6).
//
// Spec: docs/specs/modules/screen_home_migration.md
//
// Zwei Test-Gruppen (mock-frei, echte Trip/Stage-DTO-Form als plain Objekte):
//   1) tripStatus.ts-Util: tripStatus / activeOrNextTrip / todayStageIndex.
//   2) Cockpit-Source-Inspection (kein Render): +page.svelte komponiert aus der
//      Phase-1-Bibliothek (Card/Pill/Dot/Eyebrow/Btn/StagePill/ElevSparkline/
//      SectionH/BriefingTimelineRow), behandelt Hero (aktiv + nächste), leeren
//      Zustand und Rückwärtskompatibilität (TripKachel/CompareKachel).
//
// RED vor Implementierung:
//   - tripStatus/activeOrNextTrip/todayStageIndex existieren NICHT → Import/Assert FAIL.
//   - +page.svelte ist noch das alte Kachel-Grid → Source-Asserts FAIL.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test src/lib/utils/homeCockpit.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

import { tripStatus, activeOrNextTrip, todayStageIndex } from './tripStatus.ts';
import { stageStripState } from '../../routes/_home/cockpitHelpers.ts';
import type { Trip } from '../types.ts';

const here = dirname(fileURLToPath(import.meta.url));
const PAGE = join(here, '../../routes/+page.svelte');
const readPage = () => readFileSync(PAGE, 'utf-8');

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

// Tour, deren Etappen heute (2026-05-12) einschließen → aktiv, Tag 2 von 3.
const ACTIVE_TRIP = tripWith({
	id: 'khw',
	name: 'KHW 403',
	stages: [
		{ id: 's1', name: 'D1', date: '2026-05-11', waypoints: [] },
		{ id: 's2', name: 'D2', date: '2026-05-12', waypoints: [] },
		{ id: 's3', name: 'D3', date: '2026-05-13', waypoints: [] }
	]
});

// Tour, deren Etappen alle in der Zukunft liegen → geplant.
const PLANNED_TRIP = tripWith({
	id: 'gr20',
	name: 'GR20',
	stages: [
		{ id: 'p1', name: 'D1', date: '2026-06-01', waypoints: [] },
		{ id: 'p2', name: 'D2', date: '2026-06-02', waypoints: [] }
	]
});

// Tour, deren Etappen alle in der Vergangenheit liegen → fertig.
const FINISHED_TRIP = tripWith({
	id: 'tmb',
	name: 'TMB',
	stages: [
		{ id: 'f1', name: 'D1', date: '2026-04-01', waypoints: [] },
		{ id: 'f2', name: 'D2', date: '2026-04-02', waypoints: [] }
	]
});

// Tour ganz ohne datierte Etappen → draft.
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

test('AC-1: activeOrNextTrip → heute aktive Tour gewinnt vor geplanter', () => {
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

test('todayStageIndex → -1 bei Tour ohne Etappen', () => {
	assert.equal(todayStageIndex(DRAFT_TRIP, TODAY), -1);
});

// ============================================================================
// 1b) Etappen-Streifen-Zustand (stageStripState) — Fix F001 (Issue #386)
// ============================================================================

test('AC-4/F001: geplante Tour (todayIdx < 0) → ALLE Etappen future, nie active', () => {
	// Hero ist "Nächste Tour": keine Etappe läuft heute → kein 'active'.
	assert.equal(stageStripState(-1, 0), 'future');
	assert.equal(stageStripState(-1, 1), 'future');
	assert.equal(stageStripState(-1, 2), 'future');
});

test('AC-4: aktive Tour (todayIdx = 2, 5 Etappen) → done/done/active/future/future', () => {
	const todayIdx = 2;
	assert.equal(stageStripState(todayIdx, 0), 'done');
	assert.equal(stageStripState(todayIdx, 1), 'done');
	assert.equal(stageStripState(todayIdx, 2), 'active');
	assert.equal(stageStripState(todayIdx, 3), 'future');
	assert.equal(stageStripState(todayIdx, 4), 'future');
});

// ============================================================================
// 2) Cockpit-Source-Inspection (+page.svelte)
// ============================================================================

test('AC-9/AC-12: +page.svelte importiert aus der Phase-1-Atomic-Bibliothek', () => {
	const src = readPage();
	assert.match(src, /from ['"]\$lib\/components\/atoms['"]/, 'atoms-Barrel nicht importiert');
	assert.match(
		src,
		/from ['"]\$lib\/components\/molecules['"]/,
		'molecules-Barrel nicht importiert'
	);
});

test('AC-1/AC-2/AC-4: Cockpit nutzt Hero-Bausteine (StagePill, ElevSparkline, Pill, Card)', () => {
	const src = readPage();
	for (const baustein of ['StagePill', 'ElevSparkline', 'Pill', 'Card']) {
		assert.match(src, new RegExp('\\b' + baustein + '\\b'), `${baustein} fehlt im Cockpit`);
	}
});

test('AC-1/AC-11: Hero-Pill unterscheidet aktive Tour ("Tag X von Y") und nächste Tour', () => {
	const src = readPage();
	assert.match(src, /Tag /, 'Live-Label "Tag X von Y" fehlt');
	assert.match(src, /Nächste Tour/, 'AC-11-Label "Nächste Tour" fehlt');
});

test('AC-5: "Was geht heute raus" nutzt BriefingTimelineRow aus report_config', () => {
	const src = readPage();
	assert.match(src, /BriefingTimelineRow/, 'BriefingTimelineRow fehlt');
	assert.match(src, /report_config/, 'report_config wird nicht gelesen');
});

test('AC-6: Alarm-Karte zeigt sauberen Leerzustand, KEINEN Fake-Zähler', () => {
	const src = readPage();
	// Hardcodierte Mock-Zähler aus der Vorlage dürfen NICHT übernommen werden.
	assert.doesNotMatch(src, /2 ausgelöst/, 'Fake-Alarm-Zähler "2 ausgelöst" aus Mock übernommen');
});

test('AC-12: Rückwärtskompatibilität — TripKachel + CompareKachel bleiben erreichbar', () => {
	const src = readPage();
	assert.match(src, /TripKachel/, 'TripKachel (Weitere Touren) fehlt');
	assert.match(src, /CompareKachel/, 'CompareKachel (Orts-Vergleiche) fehlt');
});

test('AC-8: Leerzustand bleibt erhalten (EmptyKachel)', () => {
	const src = readPage();
	assert.match(src, /EmptyKachel/, 'EmptyKachel (Leerzustand) fehlt');
});

test('AC-9: keine Hex-Farbliterale im Cockpit (nur Sandbox-Tokens)', () => {
	const src = readPage();
	// 3- oder 6-stellige Hex-Literale in Style-Kontexten sind verboten.
	const offenders = [...src.matchAll(/#[0-9a-fA-F]{3,6}\b/g)].map((m) => m[0]);
	assert.equal(offenders.length, 0, `Hex-Literale gefunden: ${offenders.join(', ')}`);
});
