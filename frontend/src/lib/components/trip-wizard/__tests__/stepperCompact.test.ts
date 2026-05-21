// TDD RED — Tests fuer bug_271_wizard_mobile_stepper.
// Spec: docs/specs/modules/bug_271_wizard_mobile_stepper.md
//
// Testet die reine Formatierungs-Funktion compactStepperText() aus
// ../stepperCompact.ts (noch nicht erstellt → Tests schlagen fehl).
//
// Ausfuehrung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/trip-wizard/__tests__/stepperCompact.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import { compactStepperText } from '../stepperCompact.ts';

const LABELS = ['Profil & Eckdaten', 'GPX-Import', 'Wegpunkte', 'Briefings'];

test('compactStepperText: Step 1 liefert "1 / 4 · Profil & Eckdaten"', () => {
	assert.equal(compactStepperText(1, LABELS), '1 / 4 · Profil & Eckdaten');
});

test('compactStepperText: Step 2 liefert "2 / 4 · GPX-Import"', () => {
	assert.equal(compactStepperText(2, LABELS), '2 / 4 · GPX-Import');
});

test('compactStepperText: Step 3 liefert "3 / 4 · Wegpunkte"', () => {
	assert.equal(compactStepperText(3, LABELS), '3 / 4 · Wegpunkte');
});

test('compactStepperText: Step 4 liefert "4 / 4 · Briefings"', () => {
	assert.equal(compactStepperText(4, LABELS), '4 / 4 · Briefings');
});

test('compactStepperText: funktioniert mit beliebiger Label-Anzahl (3 Labels)', () => {
	assert.equal(compactStepperText(2, ['A', 'B', 'C']), '2 / 3 · B');
});
