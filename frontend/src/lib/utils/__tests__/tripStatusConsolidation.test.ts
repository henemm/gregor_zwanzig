// TDD RED: Issue #1271 — Statuswiderspruch FERTIG/GEPLANT konsolidieren.
//
// Spec: docs/specs/modules/fix_1271_status_zeitformat.md (AC-3, AC-4, AC-5, AC-6, AC-8)
//
// Reproduziert den gemeldeten Widerspruch aus Nutzersicht: derselbe Trip
// zeigt im Detail-Header ("Geplant", via deriveTripStatus) einen anderen
// Status als in Liste/Cockpit ("Fertig", via tripStatus), weil zwei
// parallele Ableitungsfunktionen existieren. Nach dem Fix liefert
// deriveTripStatus() sechs kanonische Zustände (inkl. NEU: draft, finished),
// tripStatus() wird reiner Thin-Wrapper darauf.
//
// RED vor Implementierung: 'finished'/'draft' existieren noch nicht als
// TripStatus-Werte, deriveTripStatus() fällt für beide Fälle auf 'planned'
// zurück, tripStatus() kennt paused_at nicht.
//
// Ausführen:
//   cd frontend && npm test -- src/lib/utils/__tests__/tripStatusConsolidation.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import { deriveTripStatus, tripStatus, activeOrNextTrip } from '../tripStatus.ts';
import type { Trip } from '../../types.ts';

function tripWith(overrides: Partial<Trip>): Trip {
	return {
		id: 't1',
		name: 'Test Trip',
		stages: [],
		...overrides
	} as Trip;
}

const TODAY = new Date('2026-05-12T12:00:00Z');

// ---------------------------------------------------------------------------
// AC-3/AC-6: 'finished' — vergangene Etappen, nicht archiviert.
// Das ist der Kern des gemeldeten Widerspruchs (#1271): deriveTripStatus()
// lieferte hierfür bisher 'planned' — genau das, was im Detail-Header
// fälschlich als "Geplant" angezeigt wurde, während die Liste (via des
// alten tripStatus()) bereits korrekt "Fertig" zeigte.
// ---------------------------------------------------------------------------

test('AC-3/#1271: Trip mit vergangenen Etappen, nicht archiviert → deriveTripStatus liefert finished (nicht planned)', () => {
	const trip = tripWith({
		stages: [
			{ id: 's1', name: 'D1', date: '2026-04-01', waypoints: [] },
			{ id: 's2', name: 'D2', date: '2026-04-03', waypoints: [] }
		]
	});
	assert.equal(deriveTripStatus(trip, TODAY), 'finished');
});

test('AC-3/#1271: archived_at hat weiterhin Vorrang vor finished (Prioritätsreihenfolge unverändert)', () => {
	const trip = tripWith({
		archived_at: '2026-04-05T00:00:00Z',
		stages: [{ id: 's1', name: 'D1', date: '2026-04-01', waypoints: [] }]
	});
	assert.equal(deriveTripStatus(trip, TODAY), 'archived');
});

test('#1271: paused_at hat Vorrang vor finished, auch wenn alle Etappen vergangen sind', () => {
	const trip = tripWith({
		paused_at: '2026-04-05T00:00:00Z',
		stages: [{ id: 's1', name: 'D1', date: '2026-04-01', waypoints: [] }]
	});
	assert.equal(deriveTripStatus(trip, TODAY), 'paused');
});

// ---------------------------------------------------------------------------
// AC-5: 'draft' — keine datierten Etappen. Bisher fiel das auf 'planned'
// zurück (identisch zu "alle Etappen in der Zukunft"), wodurch der Header
// für Entwürfe denselben Status wie für fertig geplante Trips zeigte.
// ---------------------------------------------------------------------------

test('AC-5/#1271: Trip ohne Etappen → deriveTripStatus liefert draft (nicht planned)', () => {
	const trip = tripWith({ stages: [] });
	assert.equal(deriveTripStatus(trip, TODAY), 'draft');
});

test('AC-5/#1271: Trip mit Etappen ohne date-Feld → draft', () => {
	const trip = tripWith({
		stages: [{ id: 's1', name: 'D1', date: undefined as unknown as string, waypoints: [] }]
	});
	assert.equal(deriveTripStatus(trip, TODAY), 'draft');
});

// ---------------------------------------------------------------------------
// AC-4: tripStatus() (Liste/Cockpit-Wrapper) muss künftig paused_at kennen.
// Bisher ignorierte tripStatus() paused_at komplett — ein pausierter Trip
// mit heute-aktivem Etappen-Datum zeigte in Liste/Cockpit fälschlich
// "aktiv" statt "pausiert".
// ---------------------------------------------------------------------------

test('AC-4/#1271: tripStatus() liefert pausiert für paused_at-Trip, auch wenn Etappen heute aktiv sind', () => {
	const trip = tripWith({
		paused_at: '2026-05-01T00:00:00Z',
		stages: [
			{ id: 's1', name: 'D1', date: '2026-05-10', waypoints: [] },
			{ id: 's2', name: 'D2', date: '2026-05-14', waypoints: [] }
		]
	});
	assert.equal(tripStatus(trip, TODAY), 'pausiert');
});

test('#1271: tripStatus() liefert draft für Trip ohne datierte Etappen (Konsistenz mit deriveTripStatus)', () => {
	const trip = tripWith({ stages: [] });
	assert.equal(tripStatus(trip, TODAY), 'draft');
});

// ---------------------------------------------------------------------------
// AC-8 (Regressionsschutz + dokumentierte Verhaltenskorrektur): Ein
// pausierter Trip mit heute-aktivem Etappen-Datum darf nach der
// Konsolidierung NICHT mehr als Cockpit-Hero gewählt werden — vorher wurde
// er fälschlich als 'aktiv' erkannt und gewann gegen einen echten,
// nicht-pausierten aktiven Trip.
// ---------------------------------------------------------------------------

test('AC-8/#1271: activeOrNextTrip wählt NICHT den pausierten Trip, wenn ein echter aktiver Trip existiert', () => {
	const paused = tripWith({
		id: 'paused-trip',
		paused_at: '2026-05-01T00:00:00Z',
		stages: [
			{ id: 's1', name: 'D1', date: '2026-05-10', waypoints: [] },
			{ id: 's2', name: 'D2', date: '2026-05-14', waypoints: [] }
		]
	});
	const genuinelyActive = tripWith({
		id: 'real-active',
		stages: [
			{ id: 's1', name: 'D1', date: '2026-05-11', waypoints: [] },
			{ id: 's2', name: 'D2', date: '2026-05-13', waypoints: [] }
		]
	});
	const hero = activeOrNextTrip([paused, genuinelyActive], TODAY);
	assert.equal(hero?.id, 'real-active');
});

test('AC-8/#1271: activeOrNextTrip wählt bei AUSSCHLIESSLICH pausiertem, datums-aktivem Trip die nächste anstehende Tour statt den pausierten', () => {
	const paused = tripWith({
		id: 'paused-only',
		paused_at: '2026-05-01T00:00:00Z',
		stages: [
			{ id: 's1', name: 'D1', date: '2026-05-10', waypoints: [] },
			{ id: 's2', name: 'D2', date: '2026-05-14', waypoints: [] }
		]
	});
	const upcoming = tripWith({
		id: 'upcoming',
		stages: [{ id: 's1', name: 'D1', date: '2026-06-01', waypoints: [] }]
	});
	const hero = activeOrNextTrip([paused, upcoming], TODAY);
	assert.equal(hero?.id, 'upcoming');
});
