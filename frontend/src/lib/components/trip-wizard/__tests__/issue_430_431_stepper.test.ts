// Issue #430 + #431: Stepper-Erweiterungen (5 Schritte, Mobile-Progressbar)
// SPEC: docs/specs/modules/issue_430_431_wizard_layout_step.md.
// TEST-MANIFEST: docs/specs/tests/issue_430_431_wizard_layout_step_tests.md.
//
// Verhaltens-Tests für die reine Funktion progressBarSegments(current, total)
// in stepperCompact.ts. Die ursprünglichen Source-Inspection-Tests
// (readFileSync gegen Stepper.svelte / TripWizardShell.svelte) wurden
// entfernt — Dateiinhalt-Checks sind laut CLAUDE.md verboten (Präzedenz #893).
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/trip-wizard/__tests__/issue_430_431_stepper.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

// =============================================================================
// AC-2: progressBarSegments — Pure-Function in stepperCompact.ts
// =============================================================================

test('AC-2: progressBarSegments(3, 5) liefert [done, done, active, pending, pending]', async () => {
	const mod = await import('../stepperCompact.ts');
	const fn = (mod as unknown as { progressBarSegments?: (c: number, t: number) => string[] })
		.progressBarSegments;
	assert.ok(fn, 'progressBarSegments-Export fehlt in stepperCompact.ts');
	const result = fn(3, 5);
	assert.deepEqual(result, ['done', 'done', 'active', 'pending', 'pending']);
});

test('AC-2: progressBarSegments(1, 5) liefert [active, pending, pending, pending, pending]', async () => {
	const mod = await import('../stepperCompact.ts');
	const fn = (mod as unknown as { progressBarSegments?: (c: number, t: number) => string[] })
		.progressBarSegments;
	assert.ok(fn);
	const result = fn(1, 5);
	assert.deepEqual(result, ['active', 'pending', 'pending', 'pending', 'pending']);
});

test('AC-2: progressBarSegments(5, 5) liefert [done, done, done, done, active]', async () => {
	const mod = await import('../stepperCompact.ts');
	const fn = (mod as unknown as { progressBarSegments?: (c: number, t: number) => string[] })
		.progressBarSegments;
	assert.ok(fn);
	const result = fn(5, 5);
	assert.deepEqual(result, ['done', 'done', 'done', 'done', 'active']);
});
