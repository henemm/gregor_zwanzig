// TDD GREEN — Tests fuer Epic #136 Sub-Spec #160 (Wizard-Shell + Stepper).
//
// Kontext-Referenz: docs/specs/modules/epic_136_step0_shell.md §3
//   stepperStateOf(index, current) -> 'done' | 'active' | 'pending'
//   - i + 1 < current  -> 'done'
//   - i + 1 === current -> 'active'
//   - i + 1 > current  -> 'pending'
//
// Ausfuehrung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/trip-wizard/__tests__/Stepper.test.ts
//
// Hinweis Spec-Praezisierung (Phase GREEN): die Stepper-State-Logik wurde aus
// Stepper.svelte in `../stepperState.ts` extrahiert. Begruendung: das
// Test-Setup (`node --experimental-strip-types`) kann `.svelte`-Dateien nicht
// importieren — der Svelte-Compiler laeuft hier nicht. Logik in einer
// separaten `.ts`-Datei haelt den Test pure-function und damit unabhaengig
// vom Svelte-Compiler. Das Briefing zur GREEN-Phase listet `stepperState.ts`
// explizit als Datei.

// --- Globals fuer Svelte-5-Runen einrichten BEVOR Modul-Import -----------
type RuneFn = (v: unknown) => unknown;
const g = globalThis as unknown as Record<string, RuneFn>;
if (typeof g.$state !== 'function') g.$state = (v: unknown) => v;
if (typeof g.$derived !== 'function') g.$derived = (v: unknown) => v;
if (typeof g.$props !== 'function') g.$props = (() => ({})) as unknown as RuneFn;

import { test } from 'node:test';
import assert from 'node:assert/strict';

import { stepperStateOf } from '../stepperState.ts';

test('stepperStateOf: index 0, current 1 → active (erster Step aktiv)', () => {
	assert.equal(stepperStateOf(0, 1), 'active');
});

test('stepperStateOf: index 1, current 1 → pending (zweiter Step pending)', () => {
	assert.equal(stepperStateOf(1, 1), 'pending');
});

test('stepperStateOf: index 0, current 2 → done (erster Step done bei current=2)', () => {
	assert.equal(stepperStateOf(0, 2), 'done');
});

test('stepperStateOf: index 0, current 4 → done (erster Step done bei current=4)', () => {
	assert.equal(stepperStateOf(0, 4), 'done');
});

test('stepperStateOf: index 3, current 4 → active (vierter Step aktiv bei current=4)', () => {
	assert.equal(stepperStateOf(3, 4), 'active');
});

test('stepperStateOf: index 2, current 4 → done (dritter Step done bei current=4)', () => {
	assert.equal(stepperStateOf(2, 4), 'done');
});
