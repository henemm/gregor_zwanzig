// TDD: Issue #153 — Epic #135 Step 2: deriveTripStatus pure function.
//
// Spec: docs/specs/modules/epic_135_step2_trip_detail_actions.md (§4)
//
// Ausführen:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/utils/tripStatus.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import { deriveTripStatus } from './tripStatus.ts';
import type { Trip } from '../types.ts';

function tripWith(overrides: Partial<Trip>): Trip {
	return {
		id: 't1',
		name: 'Test Trip',
		stages: [],
		...overrides
	} as Trip;
}

const TODAY = new Date('2026-05-12T12:00:00Z');

// AC-1: active wenn keine Flags + heute zwischen Stage-Daten.
test('AC-1: trip mit Stages umschliessend heute, keine Flags → active', () => {
	const trip = tripWith({
		stages: [
			{ id: 's1', name: 'D1', date: '2026-05-10', waypoints: [] },
			{ id: 's2', name: 'D2', date: '2026-05-12', waypoints: [] },
			{ id: 's3', name: 'D3', date: '2026-05-14', waypoints: [] }
		]
	});
	assert.equal(deriveTripStatus(trip, TODAY), 'active');
});

// AC-2: archived hat Vorrang vor paused (selbst wenn beide gesetzt sind).
test('AC-2: archived_at + paused_at beide gesetzt → archived (Vorrang)', () => {
	const trip = tripWith({
		archived_at: '2026-05-11T10:00:00Z',
		paused_at: '2026-05-11T09:00:00Z',
		stages: [{ id: 's1', name: 'D1', date: '2026-05-12', waypoints: [] }]
	});
	assert.equal(deriveTripStatus(trip, TODAY), 'archived');
});

// AC-3: paused hat Vorrang vor Datumsableitung.
test('AC-3: paused_at gesetzt + heute zwischen Stages → paused (Vorrang)', () => {
	const trip = tripWith({
		paused_at: '2026-05-11T09:00:00Z',
		stages: [
			{ id: 's1', name: 'D1', date: '2026-05-10', waypoints: [] },
			{ id: 's2', name: 'D2', date: '2026-05-14', waypoints: [] }
		]
	});
	assert.equal(deriveTripStatus(trip, TODAY), 'paused');
});

// AC-4: planned wenn keine Stages.
test('AC-4: trip ohne Stages + ohne Flags → planned', () => {
	const trip = tripWith({ stages: [] });
	assert.equal(deriveTripStatus(trip, TODAY), 'planned');
});

// AC-4-Variante: planned wenn alle Stages in der Zukunft liegen.
test('AC-4b: Stages alle in der Zukunft → planned', () => {
	const trip = tripWith({
		stages: [
			{ id: 's1', name: 'D1', date: '2026-06-01', waypoints: [] },
			{ id: 's2', name: 'D2', date: '2026-06-03', waypoints: [] }
		]
	});
	assert.equal(deriveTripStatus(trip, TODAY), 'planned');
});

// Edge-case: Stages alle in der Vergangenheit, keine Flags → planned
// (kein "archived" weil archived nur durch Flag entsteht, nicht durch Datum)
test('Edge: Stages alle in der Vergangenheit, keine Flags → planned', () => {
	const trip = tripWith({
		stages: [
			{ id: 's1', name: 'D1', date: '2026-04-01', waypoints: [] },
			{ id: 's2', name: 'D2', date: '2026-04-03', waypoints: [] }
		]
	});
	assert.equal(deriveTripStatus(trip, TODAY), 'planned');
});

// Edge: archived_at allein → archived (auch wenn keine Stages).
test('Edge: nur archived_at gesetzt → archived', () => {
	const trip = tripWith({ archived_at: '2026-05-01T00:00:00Z' });
	assert.equal(deriveTripStatus(trip, TODAY), 'archived');
});

// Edge: nur paused_at gesetzt → paused.
test('Edge: nur paused_at gesetzt → paused', () => {
	const trip = tripWith({ paused_at: '2026-05-01T00:00:00Z' });
	assert.equal(deriveTripStatus(trip, TODAY), 'paused');
});

// Edge: heute genau am Start-Datum → active.
test('Edge: heute = erstes Stage-Datum → active', () => {
	const trip = tripWith({
		stages: [
			{ id: 's1', name: 'D1', date: '2026-05-12', waypoints: [] },
			{ id: 's2', name: 'D2', date: '2026-05-14', waypoints: [] }
		]
	});
	assert.equal(deriveTripStatus(trip, TODAY), 'active');
});

// Edge: heute genau am End-Datum → active.
test('Edge: heute = letztes Stage-Datum → active', () => {
	const trip = tripWith({
		stages: [
			{ id: 's1', name: 'D1', date: '2026-05-10', waypoints: [] },
			{ id: 's2', name: 'D2', date: '2026-05-12', waypoints: [] }
		]
	});
	assert.equal(deriveTripStatus(trip, TODAY), 'active');
});

// Robustheit: Stages in unsortierter Reihenfolge — Funktion muss intern
// sortieren, damit first/last die echten Grenzen sind.
// Heute = 2026-05-12, Stages roh: [2026-06-03, 2026-05-10]
// → erwartete Grenzen nach Sort: [2026-05-10 … 2026-06-03] → active.
test('Robustheit: unsortierte Stages werden intern sortiert → active', () => {
	const trip = tripWith({
		stages: [
			{ id: 's1', name: 'D1', date: '2026-06-03', waypoints: [] },
			{ id: 's2', name: 'D2', date: '2026-05-10', waypoints: [] }
		]
	});
	assert.equal(deriveTripStatus(trip, TODAY), 'active');
});

// Robustheit: unsortierte Stages, heute liegt AUSSERHALB der echten Grenzen.
// Heute = 2026-05-12, Stages roh: [2026-06-03, 2026-05-20] (heute < beide)
// → naive Logik (first=2026-06-03, last=2026-05-20) gäbe falsches Ergebnis;
// nach Sort: [2026-05-20 … 2026-06-03] → planned (heute davor).
test('Robustheit: unsortierte Stages, heute davor → planned', () => {
	const trip = tripWith({
		stages: [
			{ id: 's1', name: 'D1', date: '2026-06-03', waypoints: [] },
			{ id: 's2', name: 'D2', date: '2026-05-20', waypoints: [] }
		]
	});
	assert.equal(deriveTripStatus(trip, TODAY), 'planned');
});
