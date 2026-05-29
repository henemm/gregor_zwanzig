// TDD RED — Issue #440: CompareWizard-Shell + Steps Source-Inspection-Tests.
// SPEC: docs/specs/modules/issue_440_compare_wizard_shell_step1_step2.md
//
// Prüft:
//   - CompareWizard.svelte: Shell-Root, Footer-Buttons, Eyebrow-Logik, Context
//   - Step1Vergleich.svelte: Name, Region, Aktivitätsprofil-Tiles
//   - Step2Orte.svelte: Smart-Import, Library, Counter
//   - Stepper.svelte: onStepClick-Prop (Edit-Modus Klickbarkeit)
//   - subscription.go: summer_trekking in Validation-Whitelist (AC-14)
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/issue_440_compare_wizard_shell.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));

const SHELL   = join(here, '..', 'CompareWizard.svelte');
const STEP1   = join(here, '..', 'steps', 'Step1Vergleich.svelte');
const STEP2   = join(here, '..', 'steps', 'Step2Orte.svelte');
const STEPPER = join(here, '..', '..', 'trip-wizard', 'Stepper.svelte');
// Repo-Root: __tests__ → compare → components → lib → src → frontend → repo-root (6x ..).
const SUB_GO  = join(here, '..', '..', '..', '..', '..', '..', 'internal', 'handler', 'subscription.go');

function readOrThrow(path: string, label: string): string {
	if (!existsSync(path)) throw new Error(`${label} nicht gefunden: ${path}`);
	return readFileSync(path, 'utf-8');
}

// =============================================================================
// CompareWizard.svelte — Shell-Existenz + Root-TestID
// =============================================================================

test('AC-INFRA: CompareWizard.svelte existiert', () => {
	assert.ok(existsSync(SHELL), `CompareWizard.svelte fehlt unter: ${SHELL}`);
});

test('AC-1: CompareWizard hat data-testid="compare-wizard-shell"', () => {
	const src = readOrThrow(SHELL, 'CompareWizard.svelte');
	assert.ok(
		/data-testid=["']compare-wizard-shell["']/.test(src),
		'CompareWizard.svelte muss data-testid="compare-wizard-shell" enthalten'
	);
});

test('AC-1: CompareWizard setzt context "compare-wizard-state"', () => {
	const src = readOrThrow(SHELL, 'CompareWizard.svelte');
	assert.ok(
		/'compare-wizard-state'|"compare-wizard-state"/.test(src),
		'CompareWizard muss den Context "compare-wizard-state" setzen oder lesen'
	);
});

test('AC-1: CompareWizard hat Eyebrow-Komponente für Modus-Label', () => {
	const src = readOrThrow(SHELL, 'CompareWizard.svelte');
	assert.ok(
		/Eyebrow|compare-wizard-header-eyebrow/.test(src),
		'CompareWizard muss Eyebrow-Komponente oder testid compare-wizard-header-eyebrow enthalten'
	);
});

// =============================================================================
// Footer-Buttons Create-Modus (AC-5, AC-6)
// =============================================================================

test('AC-5 + AC-6: Footer hat compare-wizard-footer-next (Weiter-Button)', () => {
	const src = readOrThrow(SHELL, 'CompareWizard.svelte');
	assert.ok(
		/data-testid=["']compare-wizard-footer-next["']/.test(src),
		'Footer muss data-testid="compare-wizard-footer-next" enthalten'
	);
});

test('AC-5: Weiter-Button disabled wenn !canAdvanceCurrent', () => {
	const src = readOrThrow(SHELL, 'CompareWizard.svelte');
	assert.ok(
		/canAdvanceCurrent/.test(src),
		'CompareWizard muss canAdvanceCurrent für Weiter-Button-Disabled verwenden'
	);
});

test('AC-12: Footer hat compare-wizard-footer-cancel (Abbrechen-Button)', () => {
	const src = readOrThrow(SHELL, 'CompareWizard.svelte');
	assert.ok(
		/data-testid=["']compare-wizard-footer-cancel["']/.test(src),
		'Footer muss data-testid="compare-wizard-footer-cancel" enthalten'
	);
});

// =============================================================================
// Footer-Buttons Edit-Modus (AC-13)
// =============================================================================

test('AC-13: Footer hat compare-wizard-footer-save (Speichern-Button)', () => {
	const src = readOrThrow(SHELL, 'CompareWizard.svelte');
	assert.ok(
		/data-testid=["']compare-wizard-footer-save["']/.test(src),
		'Footer muss data-testid="compare-wizard-footer-save" enthalten'
	);
});

test('AC-13: Footer hat compare-wizard-footer-discard (Verwerfen-Button)', () => {
	const src = readOrThrow(SHELL, 'CompareWizard.svelte');
	assert.ok(
		/data-testid=["']compare-wizard-footer-discard["']/.test(src),
		'Footer muss data-testid="compare-wizard-footer-discard" enthalten'
	);
});

test('AC-3 + AC-4: CompareWizard übergibt onStepClick an Stepper (Edit-Modus)', () => {
	const src = readOrThrow(SHELL, 'CompareWizard.svelte');
	assert.ok(
		/onStepClick/.test(src),
		'CompareWizard muss onStepClick an Stepper weitergeben (Edit-Modus klickbare Schritte)'
	);
});

// =============================================================================
// Step1Vergleich.svelte — Felder (AC-5, AC-6)
// =============================================================================

test('AC-INFRA: Step1Vergleich.svelte existiert', () => {
	assert.ok(existsSync(STEP1), `Step1Vergleich.svelte fehlt unter: ${STEP1}`);
});

test('AC-5 + AC-6: Step1 hat data-testid="compare-step1-name"', () => {
	const src = readOrThrow(STEP1, 'Step1Vergleich.svelte');
	assert.ok(
		/data-testid=["']compare-step1-name["']/.test(src),
		'Step1Vergleich muss data-testid="compare-step1-name" enthalten'
	);
});

test('AC-2: Step1 hat data-testid="compare-step1-region"', () => {
	const src = readOrThrow(STEP1, 'Step1Vergleich.svelte');
	assert.ok(
		/data-testid=["']compare-step1-region["']/.test(src),
		'Step1Vergleich muss data-testid="compare-step1-region" enthalten'
	);
});

test('AC-2: Step1 hat Aktivitätsprofil-Tile für wintersport', () => {
	const src = readOrThrow(STEP1, 'Step1Vergleich.svelte');
	assert.ok(
		/compare-step1-tile-wintersport/.test(src),
		'Step1Vergleich muss data-testid="compare-step1-tile-wintersport" enthalten'
	);
});

test('AC-14: Step1 hat Aktivitätsprofil-Tile für summer_trekking', () => {
	const src = readOrThrow(STEP1, 'Step1Vergleich.svelte');
	assert.ok(
		/compare-step1-tile-summer_trekking/.test(src),
		'Step1Vergleich muss data-testid="compare-step1-tile-summer_trekking" enthalten'
	);
});

test('AC-2: Step1 hat Aktivitätsprofil-Tile für allgemein', () => {
	const src = readOrThrow(STEP1, 'Step1Vergleich.svelte');
	assert.ok(
		/compare-step1-tile-allgemein/.test(src),
		'Step1Vergleich muss data-testid="compare-step1-tile-allgemein" enthalten'
	);
});

// =============================================================================
// Step2Orte.svelte — Smart-Import + Library + Counter (AC-7..AC-11)
// =============================================================================

test('AC-INFRA: Step2Orte.svelte existiert', () => {
	assert.ok(existsSync(STEP2), `Step2Orte.svelte fehlt unter: ${STEP2}`);
});

test('AC-10 + AC-11: Step2 hat data-testid="compare-step2-smart-import-input"', () => {
	const src = readOrThrow(STEP2, 'Step2Orte.svelte');
	assert.ok(
		/data-testid=["']compare-step2-smart-import-input["']/.test(src),
		'Step2Orte muss data-testid="compare-step2-smart-import-input" enthalten'
	);
});

test('AC-10 + AC-11: Step2 hat data-testid="compare-step2-resolve-btn"', () => {
	const src = readOrThrow(STEP2, 'Step2Orte.svelte');
	assert.ok(
		/data-testid=["']compare-step2-resolve-btn["']/.test(src),
		'Step2Orte muss data-testid="compare-step2-resolve-btn" enthalten'
	);
});

test('AC-2: Step2 hat data-testid="compare-step2-library"', () => {
	const src = readOrThrow(STEP2, 'Step2Orte.svelte');
	assert.ok(
		/data-testid=["']compare-step2-library["']/.test(src),
		'Step2Orte muss data-testid="compare-step2-library" enthalten'
	);
});

test('AC-7 + AC-8 + AC-9: Step2 hat data-testid="compare-step2-counter"', () => {
	const src = readOrThrow(STEP2, 'Step2Orte.svelte');
	assert.ok(
		/data-testid=["']compare-step2-counter["']/.test(src),
		'Step2Orte muss data-testid="compare-step2-counter" enthalten'
	);
});

test('AC-7: Step2 Counter zeigt "min. 2 Orte nötig" wenn < 2 ausgewählt', () => {
	const src = readOrThrow(STEP2, 'Step2Orte.svelte');
	// Entweder als Template-String oder als Variable
	assert.ok(
		/min\.\s*2\s*Orte\s*n/.test(src),
		'Step2Orte muss Text "min. 2 Orte nötig" für < 2 Auswahl enthalten'
	);
});

test('AC-8: Step2 Counter zeigt "passt" wenn 2–5 ausgewählt', () => {
	const src = readOrThrow(STEP2, 'Step2Orte.svelte');
	assert.ok(
		/'passt'|"passt"/.test(src),
		'Step2Orte muss Text "passt" für 2–5 Orte enthalten'
	);
});

test('AC-9: Step2 Counter zeigt "viel — Empfehlung 3–5" wenn > 5', () => {
	const src = readOrThrow(STEP2, 'Step2Orte.svelte');
	assert.ok(
		/viel|Empfehlung\s*3/.test(src),
		'Step2Orte muss Text "viel — Empfehlung 3–5" für > 5 Orte enthalten'
	);
});

test('AC-10: Step2 ruft /api/locations/resolve auf', () => {
	const src = readOrThrow(STEP2, 'Step2Orte.svelte');
	assert.ok(
		/locations\/resolve/.test(src),
		'Step2Orte muss POST /api/locations/resolve für Smart-Import aufrufen'
	);
});

// =============================================================================
// Stepper.svelte — onStepClick-Prop (AC-3, AC-4)
// =============================================================================

test('AC-3 + AC-4: Stepper.svelte hat onStepClick-Prop', () => {
	const src = readFileSync(STEPPER, 'utf-8');
	assert.ok(
		/onStepClick/.test(src),
		'Stepper.svelte muss optionale onStepClick-Prop für Edit-Modus-Klickbarkeit haben'
	);
});

test('AC-4: Stepper.svelte bindet onclick wenn onStepClick gesetzt', () => {
	const src = readFileSync(STEPPER, 'utf-8');
	// onclick-Handler muss vorhanden sein, der onStepClick aufruft
	assert.ok(
		/onclick.*onStepClick|onStepClick.*onclick/.test(src.replace(/\n/g, ' ')),
		'Stepper.svelte muss onclick-Handler haben, der onStepClick aufruft'
	);
});

// =============================================================================
// AC-14: subscription.go enthält summer_trekking in Validation-Whitelist
// =============================================================================

test('AC-14: subscription.go enthält "summer_trekking" in ActivityProfile-Validation', () => {
	assert.ok(
		existsSync(SUB_GO),
		`subscription.go nicht gefunden: ${SUB_GO}`
	);
	const src = readFileSync(SUB_GO, 'utf-8');
	assert.ok(
		/summer_trekking/.test(src),
		'subscription.go muss "summer_trekking" in der ActivityProfile-Validation-Whitelist enthalten'
	);
});
