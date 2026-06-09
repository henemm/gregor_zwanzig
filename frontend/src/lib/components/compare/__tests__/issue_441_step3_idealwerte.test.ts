// TDD RED — Issue #441: Compare Wizard Step 3 (Idealwerte) Source-Inspection-Tests.
// SPEC: docs/specs/modules/issue_441_compare_wizard_step3_idealwerte.md
//
// Prüft via readFileSync (Source-Inspection), kein DOM/Svelte-Rendering:
//   - compareMetricDefs.ts: Exports PROFILE_METRICS_WITH_SCALES, IDEAL_DEFAULTS, Typen
//   - Step3Idealwerte.svelte: Existenz, testids, getContext, $effect Defaults-Logik
//   - compareWizardState.svelte.ts: idealRanges-Feld, save()-Erweiterung
//   - CompareWizard.svelte: Step3-Import + currentStep===3 Branch
//   - Step1Vergleich.svelte: Profil-Wechsel-Confirm-Guard
//   - compare/[id]/edit/+page.svelte: ideal_ranges aus display_config laden
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/issue_441_step3_idealwerte.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
// Repo-Root: __tests__ → compare → components → lib → src → frontend → repo-root (6x ..)
const repoRoot = join(here, '..', '..', '..', '..', '..', '..');

const METRIC_DEFS  = join(here, '..', 'compareMetricDefs.ts');
const STEP3        = join(here, '..', 'steps', 'Step3Idealwerte.svelte');
const STATE        = join(here, '..', 'compareWizardState.svelte.ts');
const SHELL        = join(here, '..', 'CompareWizard.svelte');
const STEP1        = join(here, '..', 'steps', 'Step1Vergleich.svelte');
const EDIT_PAGE    = join(repoRoot, 'frontend', 'src', 'routes', 'compare', '[id]', 'edit', '+page.svelte');

function readOrThrow(path: string, label: string): string {
	if (!existsSync(path)) throw new Error(`${label} nicht gefunden: ${path}`);
	return readFileSync(path, 'utf-8');
}

// =============================================================================
// compareMetricDefs.ts — AC-1, AC-2, AC-3, AC-4, AC-9, AC-10
// =============================================================================

test('AC-INFRA: compareMetricDefs.ts existiert', () => {
	assert.ok(existsSync(METRIC_DEFS), `compareMetricDefs.ts fehlt: ${METRIC_DEFS}`);
});

test('AC-1: compareMetricDefs.ts exportiert PROFILE_METRICS_WITH_SCALES', () => {
	const src = readOrThrow(METRIC_DEFS, 'compareMetricDefs.ts');
	assert.ok(
		/export.*PROFILE_METRICS_WITH_SCALES/.test(src),
		'compareMetricDefs.ts muss PROFILE_METRICS_WITH_SCALES exportieren'
	);
});

test('AC-4: compareMetricDefs.ts exportiert IDEAL_DEFAULTS', () => {
	const src = readOrThrow(METRIC_DEFS, 'compareMetricDefs.ts');
	assert.ok(
		/export.*IDEAL_DEFAULTS/.test(src),
		'compareMetricDefs.ts muss IDEAL_DEFAULTS exportieren'
	);
});

test('AC-2: MetricDef hat kind-Diskriminator (range|enum)', () => {
	const src = readOrThrow(METRIC_DEFS, 'compareMetricDefs.ts');
	assert.ok(
		/'range'\s*\|\s*'enum'|"range"\s*\|\s*"enum"/.test(src),
		"MetricDef muss kind: 'range' | 'enum' enthalten"
	);
});

test('AC-3: compareMetricDefs.ts enthält thunder_level_max als enum-Metrik', () => {
	const src = readOrThrow(METRIC_DEFS, 'compareMetricDefs.ts');
	assert.ok(
		/thunder_level_max/.test(src) && /enum/.test(src),
		'thunder_level_max muss als kind=enum in compareMetricDefs.ts definiert sein'
	);
});

test('AC-3: enumValues für thunder_level_max enthält NONE, MED, HIGH', () => {
	const src = readOrThrow(METRIC_DEFS, 'compareMetricDefs.ts');
	assert.ok(
		/NONE/.test(src) && /MED/.test(src) && /HIGH/.test(src),
		"enumValues muss 'NONE', 'MED', 'HIGH' enthalten"
	);
});

test('AC-10: MetricDef hat rangeMin und rangeMax Felder', () => {
	const src = readOrThrow(METRIC_DEFS, 'compareMetricDefs.ts');
	assert.ok(
		/rangeMin/.test(src) && /rangeMax/.test(src),
		'MetricDef muss rangeMin und rangeMax haben (für Skala-Endpunkte)'
	);
});

test('AC-1: PROFILE_METRICS_WITH_SCALES enthält alle 4 Profile (WINTERSPORT, ALPINE_TOURING, SUMMER_TREKKING, ALLGEMEIN)', () => {
	const src = readOrThrow(METRIC_DEFS, 'compareMetricDefs.ts');
	assert.ok(/WINTERSPORT/.test(src),    'WINTERSPORT muss in PROFILE_METRICS_WITH_SCALES sein');
	assert.ok(/ALPINE_TOURING/.test(src), 'ALPINE_TOURING muss in PROFILE_METRICS_WITH_SCALES sein');
	assert.ok(/SUMMER_TREKKING/.test(src),'SUMMER_TREKKING muss in PROFILE_METRICS_WITH_SCALES sein');
	assert.ok(/ALLGEMEIN/.test(src),      'ALLGEMEIN muss in PROFILE_METRICS_WITH_SCALES sein');
});

test('AC-4: IDEAL_DEFAULTS enthält Einträge für WINTERSPORT (snow_depth_cm)', () => {
	const src = readOrThrow(METRIC_DEFS, 'compareMetricDefs.ts');
	assert.ok(
		/snow_depth_cm/.test(src),
		'IDEAL_DEFAULTS muss snow_depth_cm-Default für WINTERSPORT enthalten'
	);
});

// =============================================================================
// Step3Idealwerte.svelte — AC-1, AC-2, AC-3, AC-4, AC-7, AC-9, AC-10
// =============================================================================

test('AC-INFRA: Step3Idealwerte.svelte existiert', () => {
	assert.ok(existsSync(STEP3), `Step3Idealwerte.svelte fehlt: ${STEP3}`);
});

test('AC-1: Step3 hat data-testid="compare-wizard-step-3"', () => {
	const src = readOrThrow(STEP3, 'Step3Idealwerte.svelte');
	assert.ok(
		/data-testid=["']compare-wizard-step-3["']/.test(src),
		'Step3 muss data-testid="compare-wizard-step-3" haben'
	);
});

test('AC-1: Step3 importiert aus compareMetricDefs.ts', () => {
	const src = readOrThrow(STEP3, 'Step3Idealwerte.svelte');
	assert.ok(
		/compareMetricDefs/.test(src),
		'Step3 muss PROFILE_METRICS_WITH_SCALES aus compareMetricDefs importieren'
	);
});

test('AC-1: Step3 nutzt getContext("compare-wizard-state")', () => {
	const src = readOrThrow(STEP3, 'Step3Idealwerte.svelte');
	assert.ok(
		/'compare-wizard-state'|"compare-wizard-state"/.test(src),
		'Step3 muss getContext("compare-wizard-state") nutzen'
	);
});

test('AC-2: Step3 hat testid compare-step3-min-{key} für range-Metriken', () => {
	const src = readOrThrow(STEP3, 'Step3Idealwerte.svelte');
	assert.ok(
		/compare-step3-min-/.test(src),
		'Step3 muss data-testid="compare-step3-min-{key}" für Min-Inputs haben'
	);
});

test('AC-2: Step3 hat testid compare-step3-max-{key}', () => {
	const src = readOrThrow(STEP3, 'Step3Idealwerte.svelte');
	assert.ok(
		/compare-step3-max-/.test(src),
		'Step3 muss data-testid="compare-step3-max-{key}" für Max-Inputs/Select haben'
	);
});

test('AC-3: Step3 hat Segmented-Control für thunder_level_max (enum-Sonderfall)', () => {
	// Issue #680 AC-7: Segmented-Control (Buttons) statt Select für enum-Metriken.
	// # doc-compliance-test
	const src = readOrThrow(STEP3, 'Step3Idealwerte.svelte');
	// Segmented-Control: data-testid="compare-step3-max-{key}" als Container-div + Buttons
	const hasEnumControl =
		/compare-step3-max-/.test(src) && /setEnumMax|kind.*enum/.test(src);
	assert.ok(
		hasEnumControl,
		'Step3 muss einen Segmented-Control-Container (compare-step3-max-*) für enum-Metriken haben'
	);
});

test('AC-4: Step3 hat $effect für Default-Befüllung aus IDEAL_DEFAULTS', () => {
	const src = readOrThrow(STEP3, 'Step3Idealwerte.svelte');
	assert.ok(
		/\$effect/.test(src),
		'Step3 muss $effect für das Setzen der IDEAL_DEFAULTS beim ersten Rendern haben'
	);
});

test('AC-4: $effect schreibt nur wenn Key noch nicht belegt (kein Überschreiben)', () => {
	const src = readOrThrow(STEP3, 'Step3Idealwerte.svelte');
	// Muss einen "key in state.idealRanges" oder "!(key in ...)" Guard haben
	const hasGuard = /in\s+state\.idealRanges|hasOwnProperty|idealRanges\[.*\]\s*===\s*undefined/.test(src);
	assert.ok(
		hasGuard,
		'$effect muss prüfen ob Key bereits belegt ist (Edit-Modus-Schutz, AC-5)'
	);
});

test('AC-9: Step3 hat Fallback auf ALLGEMEIN wenn kein Profil gewählt', () => {
	const src = readOrThrow(STEP3, 'Step3Idealwerte.svelte');
	assert.ok(
		/ALLGEMEIN/.test(src),
		'Step3 muss Fallback auf ALLGEMEIN-Metriken haben wenn activityProfile null ist'
	);
});

test('AC-10: Step3 hat testid compare-step3-scale-min-{key}', () => {
	const src = readOrThrow(STEP3, 'Step3Idealwerte.svelte');
	assert.ok(
		/compare-step3-scale-min-/.test(src),
		'Step3 muss data-testid="compare-step3-scale-min-{key}" für Skala-Endpunkt haben'
	);
});

test('AC-10: Step3 hat testid compare-step3-scale-max-{key}', () => {
	const src = readOrThrow(STEP3, 'Step3Idealwerte.svelte');
	assert.ok(
		/compare-step3-scale-max-/.test(src),
		'Step3 muss data-testid="compare-step3-scale-max-{key}" für Skala-Endpunkt haben'
	);
});

// =============================================================================
// compareWizardState.svelte.ts — AC-7, AC-8
// =============================================================================

test('AC-8: compareWizardState hat idealRanges als $state-Feld', () => {
	const src = readOrThrow(STATE, 'compareWizardState.svelte.ts');
	assert.ok(
		/idealRanges\s*=\s*\$state/.test(src),
		'compareWizardState muss idealRanges als $state-Feld haben'
	);
});

test('AC-8: save() schreibt ideal_ranges in display_config', () => {
	const src = readOrThrow(STATE, 'compareWizardState.svelte.ts');
	assert.ok(
		/ideal_ranges/.test(src),
		'save() muss ideal_ranges in den display_config-Payload schreiben'
	);
});

test('AC-7: canAdvanceCurrent gibt true zurück für Step 3', () => {
	const src = readOrThrow(STATE, 'compareWizardState.svelte.ts');
	// Entweder expliziter case 3 → true oder default → true (für Steps 3-5)
	const hasStep3True = /case\s+3\s*:\s*return\s+true/.test(src)
		|| /default\s*:\s*return\s+true/.test(src);
	assert.ok(
		hasStep3True,
		'canAdvanceCurrent muss für Step 3 true zurückgeben (kein Pflichtfeld)'
	);
});

test('AC-8: idealRanges-Bedingung schließt leeres Objekt aus (kein ideal_ranges: {} im Payload)', () => {
	const src = readOrThrow(STATE, 'compareWizardState.svelte.ts');
	// Muss Object.keys(this.idealRanges).length > 0 oder ähnliches haben
	const hasLengthCheck = /Object\.keys\s*\(\s*this\.idealRanges\s*\)\.length/.test(src)
		|| /idealRanges.*length\s*>\s*0/.test(src);
	assert.ok(
		hasLengthCheck,
		'save() darf ideal_ranges nicht als leeres Objekt in display_config schreiben'
	);
});

// =============================================================================
// CompareWizard.svelte — Step3-Integration
// =============================================================================

test('AC-INFRA: CompareWizard importiert Step3Idealwerte', () => {
	const src = readOrThrow(SHELL, 'CompareWizard.svelte');
	assert.ok(
		/Step3Idealwerte/.test(src),
		'CompareWizard.svelte muss Step3Idealwerte importieren'
	);
});

test('AC-INFRA: CompareWizard rendert Step3 bei currentStep === 3', () => {
	const src = readOrThrow(SHELL, 'CompareWizard.svelte');
	assert.ok(
		/currentStep\s*===\s*3/.test(src),
		'CompareWizard muss currentStep === 3 Branch für Step3Idealwerte haben'
	);
});

// =============================================================================
// Step1Vergleich.svelte — AC-6
// =============================================================================

test('AC-6: Step1 hat Profil-Wechsel-Guard mit confirm()', () => {
	const src = readOrThrow(STEP1, 'Step1Vergleich.svelte');
	assert.ok(
		/confirm\s*\(/.test(src),
		'Step1 muss confirm()-Dialog für Profil-Wechsel-Bestätigung haben (AC-6)'
	);
});

test('AC-6: Step1 prüft ob idealRanges nicht leer vor Profil-Wechsel', () => {
	const src = readOrThrow(STEP1, 'Step1Vergleich.svelte');
	const hasIdealRangesCheck = /idealRanges/.test(src);
	assert.ok(
		hasIdealRangesCheck,
		'Step1 muss state.idealRanges prüfen bevor Profil-Wechsel-Confirm ausgelöst wird'
	);
});

test('AC-6: Step1 setzt idealRanges = {} bei Profil-Wechsel-Bestätigung', () => {
	const src = readOrThrow(STEP1, 'Step1Vergleich.svelte');
	assert.ok(
		/idealRanges\s*=\s*\{\s*\}/.test(src),
		'Step1 muss state.idealRanges = {} setzen wenn Profil-Wechsel bestätigt wird'
	);
});

// =============================================================================
// compare/[id]/edit/+page.svelte — AC-5
// =============================================================================

test('AC-5: Edit-Page lädt ideal_ranges aus display_config in State', () => {
	const src = readOrThrow(EDIT_PAGE, 'compare/[id]/edit/+page.svelte');
	assert.ok(
		/ideal_ranges/.test(src),
		'Edit-Page muss display_config.ideal_ranges in state.idealRanges laden (AC-5)'
	);
});

test('AC-5: Edit-Page setzt state.idealRanges aus existingDisplayConfig', () => {
	const src = readOrThrow(EDIT_PAGE, 'compare/[id]/edit/+page.svelte');
	assert.ok(
		/state\.idealRanges/.test(src),
		'Edit-Page muss state.idealRanges aus existingDisplayConfig.ideal_ranges setzen'
	);
});
