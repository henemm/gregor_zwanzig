// TDD RED: Issue #498 — Etappen-Datum nachträglich bearbeiten (Kaskaden-Logik).
//
// Spec: docs/design-requests/stage_date_edit.md
//
// Reine Logik-Tests für addDays() und Cascade-Trigger.
// Kein DOM, keine Mocks.
//
// RED-Erwartung: Module edit/cascade.ts existiert noch nicht → Import-Fehler.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/edit/cascade.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import { addDays, computeCascadeDelta } from './cascade.ts';

// =============================================================================
// addDays() — pure date arithmetic auf ISO YYYY-MM-DD.
// =============================================================================

test('AC-1: addDays addiert positive Tage innerhalb des Monats', () => {
	assert.equal(addDays('2026-05-07', 2), '2026-05-09');
});

test('AC-2: addDays überspringt Monatsgrenze korrekt', () => {
	assert.equal(addDays('2026-01-31', 1), '2026-02-01');
});

test('AC-3: addDays mit negativem delta verschiebt rückwärts', () => {
	assert.equal(addDays('2026-05-09', -2), '2026-05-07');
});

test('AC-4: addDays über Jahresgrenze', () => {
	assert.equal(addDays('2026-12-31', 1), '2027-01-01');
});

test('AC-5: addDays delta=0 lässt Datum unverändert', () => {
	assert.equal(addDays('2026-05-07', 0), '2026-05-07');
});

// =============================================================================
// computeCascadeDelta() — Diff in Tagen zwischen zwei ISO-Daten.
// Wird benötigt um zu entscheiden, ob ein Kaskaden-Vorschlag auftaucht.
// =============================================================================

test('AC-6: computeCascadeDelta gleiche Daten → 0 (kein Trigger)', () => {
	assert.equal(computeCascadeDelta('2026-05-07', '2026-05-07'), 0);
});

test('AC-7: computeCascadeDelta +2 Tage', () => {
	assert.equal(computeCascadeDelta('2026-05-07', '2026-05-09'), 2);
});

test('AC-8: computeCascadeDelta -3 Tage (rückwärts)', () => {
	assert.equal(computeCascadeDelta('2026-05-10', '2026-05-07'), -3);
});

test('AC-9: computeCascadeDelta über Monatsgrenze', () => {
	assert.equal(computeCascadeDelta('2026-01-30', '2026-02-02'), 3);
});
