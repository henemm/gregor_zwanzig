// TDD RED — Issue #432: TripWizardShell Import-Swap auf Step5Reports.
// SPEC: docs/specs/modules/issue_432_step3_step5_polish.md (AC-14).
// TEST-MANIFEST: docs/specs/tests/issue_432_step3_step5_polish_tests.md.
//
// Source-Inspection-Tests. Heute (vor Implementation):
//   - Shell importiert Step4Reports → AC-15 rot
//   - Shell mountet <Step4Reports /> bei currentStep === 5 → AC-15 rot
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/trip-wizard/__tests__/issue_432_shell_step5_import.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const SHELL = join(here, '..', 'TripWizardShell.svelte');

function read(): string { return readFileSync(SHELL, 'utf-8'); }

// =============================================================================
// AC-14: Shell importiert Step5Reports (nicht mehr Step4Reports)
// =============================================================================

test('AC-14: TripWizardShell importiert Step5Reports', () => {
	const src = read();
	const has = /import\s+Step5Reports\s+from\s+['"]\.\/steps\/Step5Reports\.svelte['"]/.test(src);
	assert.ok(
		has,
		'TripWizardShell muss `import Step5Reports from "./steps/Step5Reports.svelte";` enthalten',
	);
});

test('AC-14: TripWizardShell importiert KEIN Step4Reports mehr', () => {
	const src = read();
	const has = /import\s+Step4Reports/.test(src);
	assert.ok(
		!has,
		'TripWizardShell darf keinen Import von Step4Reports mehr haben (durch Step5Reports ersetzt)',
	);
});

test('AC-14: TripWizardShell mountet Step5Reports bei currentStep === 5', () => {
	const src = read();
	const has = /currentStep\s*===\s*5[\s\S]{0,200}<\s*Step5Reports\b/.test(src);
	assert.ok(
		has,
		'TripWizardShell muss bei currentStep === 5 <Step5Reports /> rendern (heute: <Step4Reports />)',
	);
});

test('AC-14: TripWizardShell mountet KEINE Step4Reports-Komponente mehr', () => {
	const src = read();
	const has = /<\s*Step4Reports\b/.test(src);
	assert.ok(
		!has,
		'TripWizardShell darf <Step4Reports />-Mount nicht mehr enthalten',
	);
});
