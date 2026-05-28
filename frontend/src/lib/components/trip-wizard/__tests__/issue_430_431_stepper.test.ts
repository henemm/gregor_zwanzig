// TDD RED — Issue #430 + #431: Stepper-Erweiterungen (5 Schritte, Mobile-Progressbar)
// + TripWizardShell-Anpassungen (Labels, Eyebrow, Save-Button-Logik).
// SPEC: docs/specs/modules/issue_430_431_wizard_layout_step.md.
// TEST-MANIFEST: docs/specs/tests/issue_430_431_wizard_layout_step_tests.md.
//
// Diese Tests beschreiben die NOCH NICHT existierenden Erweiterungen:
//   - Neue Pure-Function progressBarSegments(current, total) in stepperCompact.ts
//   - Stepper.svelte Mobile rendert Progressbar mit 5 Segmenten
//   - TripWizardShell.svelte: stepLabels mit 5 Einträgen, Eyebrow "VON 5",
//     Save-Button heißt "Trip speichern" auf Step 5
//
// Tests mischen Pure-Logic (progressBarSegments) und Source-Inspection
// (readFileSync für .svelte-Dateien) — bewährtes Muster aus
// WeatherMetricsMobileView.test.ts.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/trip-wizard/__tests__/issue_430_431_stepper.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const STEPPER_SVELTE = join(here, '..', 'Stepper.svelte');
const SHELL_SVELTE   = join(here, '..', 'TripWizardShell.svelte');

function readStepper(): string { return readFileSync(STEPPER_SVELTE, 'utf-8'); }
function readShell():   string { return readFileSync(SHELL_SVELTE,   'utf-8'); }

// =============================================================================
// AC-2: progressBarSegments — neue Pure-Function in stepperCompact.ts
// =============================================================================

test('AC-2: progressBarSegments(3, 5) liefert [done, done, active, pending, pending]', async () => {
	// In der RED-Phase fehlt der Export — ImportError oder undefined.
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

// =============================================================================
// AC-2: Stepper.svelte Mobile-Variante rendert Progressbar
// =============================================================================

test('AC-2: Stepper.svelte Mobile-Variante enthält Progressbar-Markup', () => {
	const src = readStepper();
	// Soll-Mockup: 5-Segment-Progressbar. Der Source muss einen testid-Marker
	// für die Progressbar haben, der von Playwright + E2E-Tests anfassbar ist.
	assert.ok(
		src.includes('trip-wizard-stepper-progress') ||
			src.includes('progress-bar') ||
			src.includes('progressBarSegments'),
		'Stepper-Mobile sollte Progressbar-Marker (data-testid="trip-wizard-stepper-progress" oder progress-bar-CSS-Klasse oder progressBarSegments-Import) enthalten.',
	);
});

test('AC-1: Stepper.svelte akzeptiert current als 1..5 (Type-Update im Props-Interface)', () => {
	const src = readStepper();
	// Source-Check: das Props-Interface erlaubt jetzt Wert 5 explizit oder als number.
	// Akzeptiert: "current: 1 | 2 | 3 | 4 | 5" oder "current: number" (generisch).
	const has5 = /current:\s*(1\s*\|\s*2\s*\|\s*3\s*\|\s*4\s*\|\s*5|number)/.test(src);
	assert.ok(
		has5,
		'Stepper Props.current sollte 1|2|3|4|5 oder number erlauben (heute nur 1|2|3|4)',
	);
});

// =============================================================================
// AC-1 / AC-3: TripWizardShell — 5 Step-Labels + Eyebrow "VON 5"
// =============================================================================

test('AC-1: TripWizardShell.svelte enthält 5-Element-stepLabels (Route/Etappen/Wetter/Layout/Reports)', () => {
	const src = readShell();
	// Heute: ['Route', 'Etappen', 'Wetter', 'Reports']
	// Soll: ['Route', 'Etappen', 'Wetter', 'Layout', 'Reports']
	assert.ok(src.includes("'Layout'"), 'stepLabels muss "Layout" zwischen "Wetter" und "Reports" enthalten');
	assert.ok(src.includes("'Route'"));
	assert.ok(src.includes("'Etappen'"));
	assert.ok(src.includes("'Wetter'"));
	assert.ok(src.includes("'Reports'"));
});

test('AC-3: TripWizardShell.svelte Eyebrow zeigt "SCHRITT N VON 5 · NEUER TRIP"', () => {
	const src = readShell();
	assert.ok(
		src.includes('VON 5'),
		'Eyebrow muss "SCHRITT N VON 5" enthalten (heute: VON 4)',
	);
});

// =============================================================================
// AC-12: Save-Button-Logik — "Trip speichern" auf Step 5
// =============================================================================

test('AC-12: TripWizardShell — Save-Button-Label "Trip speichern"', () => {
	const src = readShell();
	assert.ok(
		src.includes('Trip speichern'),
		'Save-Button auf Step 5 muss "Trip speichern" heißen (heute: "Speichern")',
	);
});

test('AC-12: TripWizardShell — Weiter-Button nur unter Step 5 sichtbar', () => {
	const src = readShell();
	// Heute: `currentStep < 4`. Soll: `currentStep < 5`.
	const cond = /currentStep\s*<\s*5/.test(src);
	assert.ok(
		cond,
		'Weiter-Button-Bedingung muss `currentStep < 5` sein (heute: < 4)',
	);
});
