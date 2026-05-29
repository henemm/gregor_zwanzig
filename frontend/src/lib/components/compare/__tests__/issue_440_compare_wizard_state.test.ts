// TDD RED — Issue #440: CompareWizardState Source-Inspection-Tests.
// SPEC: docs/specs/modules/issue_440_compare_wizard_shell_step1_step2.md
//
// Prüft compareWizardState.svelte.ts per Source-Inspection (analog
// issue_430_431_wizard_state.test.ts). Da node:test $lib-Aliases nicht
// auflösen kann, lesen wir die .ts-Datei direkt.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/issue_440_compare_wizard_state.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const STATE_FILE = join(here, '..', 'compareWizardState.svelte.ts');

function read(): string {
	if (!existsSync(STATE_FILE)) {
		throw new Error(`compareWizardState.svelte.ts nicht gefunden — Datei muss erst erstellt werden`);
	}
	return readFileSync(STATE_FILE, 'utf-8');
}

// =============================================================================
// Datei-Existenz
// =============================================================================

test('AC-INFRA: compareWizardState.svelte.ts existiert', () => {
	assert.ok(
		existsSync(STATE_FILE),
		`compareWizardState.svelte.ts fehlt unter: ${STATE_FILE}`
	);
});

// =============================================================================
// AC-1 + AC-2: State-Felder (Create + Edit Prefill)
// =============================================================================

test('AC-1: currentStep hat Type 1|2|3|4|5', () => {
	const src = read();
	const ok = /currentStep\s*[=:][^;]{0,60}\$state\s*<[^>]*1[^>]*\|[^>]*5[^>]*>/.test(src)
		|| /currentStep\s*=\s*\$state\s*<\s*1\s*\|\s*2\s*\|\s*3\s*\|\s*4\s*\|\s*5\s*>/.test(src);
	assert.ok(ok, 'currentStep muss Typ 1|2|3|4|5 haben');
});

test('AC-1: name-Feld als $state vorhanden', () => {
	const src = read();
	assert.ok(/name\s*=\s*\$state\s*\(/.test(src), 'name muss als $state-Feld vorhanden sein');
});

test('AC-1: region-Feld als $state vorhanden', () => {
	const src = read();
	assert.ok(/region\s*=\s*\$state\s*\(/.test(src), 'region muss als $state-Feld vorhanden sein');
});

test('AC-1: activityProfile-Feld als $state vorhanden', () => {
	const src = read();
	assert.ok(/activityProfile\s*=\s*\$state/.test(src), 'activityProfile muss als $state-Feld vorhanden sein');
});

test('AC-1 + AC-2: pickedIds-Feld als $state vorhanden (Location-IDs)', () => {
	const src = read();
	assert.ok(/pickedIds\s*=\s*\$state/.test(src), 'pickedIds muss als $state<string[]>-Feld vorhanden sein');
});

test('AC-2: isEditMode-Feld als $state vorhanden', () => {
	const src = read();
	assert.ok(/isEditMode\s*=\s*\$state/.test(src), 'isEditMode muss als $state-Feld vorhanden sein');
});

test('AC-2: subscriptionId-Feld als $state vorhanden', () => {
	const src = read();
	assert.ok(/subscriptionId\s*=\s*\$state/.test(src), 'subscriptionId muss als $state-Feld vorhanden sein');
});

test('AC-2: existingDisplayConfig-Feld für round-trip Sicherheit vorhanden', () => {
	const src = read();
	assert.ok(
		/existingDisplayConfig\s*=\s*\$state/.test(src),
		'existingDisplayConfig muss als $state-Feld vorhanden sein (round-trip-Sicherheit für display_config)'
	);
});

// =============================================================================
// AC-5 + AC-6: canAdvanceStep1 prüft name.trim().length > 0
// =============================================================================

test('AC-5 + AC-6: canAdvanceCurrent / canAdvanceStep1 vorhanden', () => {
	const src = read();
	assert.ok(
		/canAdvanceCurrent/.test(src),
		'canAdvanceCurrent muss als Getter vorhanden sein'
	);
});

test('AC-5 + AC-6: canAdvanceStep1 prüft name.trim().length > 0', () => {
	const src = read();
	// Entweder als eigener Getter oder inline im canAdvanceCurrent-Switch
	const hasNameCheck = /name\.trim\(\)\.length\s*>\s*0/.test(src)
		|| /name\.trim\(\)\s*!==\s*''/.test(src)
		|| /name\.trim\(\)\.length\s*>=\s*1/.test(src);
	assert.ok(
		hasNameCheck,
		'Step-1-Validation muss name.trim().length > 0 prüfen'
	);
});

// =============================================================================
// AC-7 + AC-8 + AC-9: canAdvanceStep2 prüft pickedIds.length >= 2
// =============================================================================

test('AC-7: canAdvanceStep2 prüft pickedIds.length >= 2', () => {
	const src = read();
	const hasLocationCheck = /pickedIds\.length\s*>=\s*2/.test(src);
	assert.ok(
		hasLocationCheck,
		'Step-2-Validation muss pickedIds.length >= 2 prüfen'
	);
});

// =============================================================================
// AC-3 + AC-4: goToStep — nur im Edit-Modus
// =============================================================================

test('AC-3 + AC-4: goToStep-Methode vorhanden', () => {
	const src = read();
	assert.ok(/goToStep\s*\(/.test(src), 'goToStep-Methode muss vorhanden sein');
});

test('AC-3 + AC-4: goToStep prüft isEditMode', () => {
	const src = read();
	// goToStep muss isEditMode prüfen, um im Create-Modus blockiert zu sein
	const methodMatch = src.match(/goToStep\s*\([^)]*\)[^{]*\{[\s\S]{0,300}?\n\s*\}/);
	assert.ok(methodMatch, 'goToStep-Methode muss im Source gefunden werden');
	assert.ok(
		/isEditMode/.test(methodMatch![0]),
		'goToStep muss isEditMode prüfen (kein freies Springen im Create-Modus)'
	);
});

// =============================================================================
// AC-13: toggleEnabled-Methode für Sofort-Pausieren
// =============================================================================

test('AC-13: toggleEnabled-Methode vorhanden', () => {
	const src = read();
	assert.ok(/toggleEnabled\s*\(/.test(src), 'toggleEnabled()-Methode muss vorhanden sein');
});

test('AC-13: toggleEnabled ruft PUT /api/subscriptions/{id} auf', () => {
	const src = read();
	const hasApiCall = /\/api\/subscriptions/.test(src) && /put|PUT/.test(src);
	assert.ok(hasApiCall, 'toggleEnabled muss PUT /api/subscriptions verwenden');
});

// =============================================================================
// save()-Methode
// =============================================================================

test('save()-Methode vorhanden mit async', () => {
	const src = read();
	assert.ok(/async\s+save\s*\(/.test(src), 'save() muss als async-Methode vorhanden sein');
});

test('save() verwendet lazy imports (analog wizardState)', () => {
	const src = read();
	// Lazy imports: import() innerhalb der Methode (nicht oben)
	// Prüfe, dass `$app/navigation` oder `$lib/api` NICHT im top-level import-Block steht
	const topLevelImportBlock = src.split('class ')[0];
	const hasTopLevelAppNav = /import.*\$app\/navigation/.test(topLevelImportBlock);
	const hasTopLevelApi = /^import.*\$lib\/api/m.test(topLevelImportBlock);
	assert.ok(
		!hasTopLevelAppNav,
		'$app/navigation darf nicht top-level importiert sein (lazy import für Unit-Test-Kompatibilität)'
	);
	assert.ok(
		!hasTopLevelApi,
		'$lib/api darf nicht top-level importiert sein (lazy import für Unit-Test-Kompatibilität)'
	);
});
