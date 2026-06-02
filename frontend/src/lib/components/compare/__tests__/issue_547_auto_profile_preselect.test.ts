// TDD RED — Issue #547: Auto-Profil-Vorauswahl im Compare-Wizard (AC-6–9)
//
// Spec: docs/specs/modules/issue_547_auto_profile_preselect.md
//
// Source-Inspection-Tests (node:test, kein DOM-Rendering).
// Prüft: profileManuallyOverridden, dominantProfile, $effect-Blöcke in
// CompareWizard.svelte und den onManualProfileChange-Callback in Step1Vergleich.svelte.
//
// RED-Erwartung (vor Implementation):
//   CompareWizard.svelte hat noch keinen auto-select-Code → alle Tests FAIL
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/issue_547_auto_profile_preselect.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const COMPARE_DIR = join(here, '..');
const STEPS_DIR = join(COMPARE_DIR, 'steps');

const WIZARD_FILE = join(COMPARE_DIR, 'CompareWizard.svelte');
const STEP1_FILE  = join(STEPS_DIR, 'Step1Vergleich.svelte');

function readWizard(): string {
	if (!existsSync(WIZARD_FILE)) {
		throw new Error(`CompareWizard.svelte nicht gefunden: ${WIZARD_FILE}`);
	}
	return readFileSync(WIZARD_FILE, 'utf-8');
}

function readStep1(): string {
	if (!existsSync(STEP1_FILE)) {
		throw new Error(`Step1Vergleich.svelte nicht gefunden: ${STEP1_FILE}`);
	}
	return readFileSync(STEP1_FILE, 'utf-8');
}

// =============================================================================
// Voraussetzungen
// =============================================================================

test('Voraussetzung: CompareWizard.svelte existiert', () => {
	assert.ok(existsSync(WIZARD_FILE), `CompareWizard.svelte fehlt: ${WIZARD_FILE}`);
});

test('Voraussetzung: Step1Vergleich.svelte existiert', () => {
	assert.ok(existsSync(STEP1_FILE), `Step1Vergleich.svelte fehlt: ${STEP1_FILE}`);
});

// =============================================================================
// AC-8: profileManuallyOverridden State in CompareWizard
// =============================================================================

test('AC-8: CompareWizard.svelte deklariert profileManuallyOverridden als $state', () => {
	const src = readWizard();
	assert.match(
		src,
		/profileManuallyOverridden\s*=\s*\$state\s*\(\s*false\s*\)/,
		'CompareWizard.svelte muss profileManuallyOverridden = $state(false) enthalten'
	);
});

test('AC-8: CompareWizard.svelte definiert handleManualProfileChange-Funktion', () => {
	const src = readWizard();
	assert.match(
		src,
		/function\s+handleManualProfileChange\s*\(\s*\)/,
		'CompareWizard.svelte muss function handleManualProfileChange() definieren'
	);
});

test('AC-8: handleManualProfileChange setzt profileManuallyOverridden auf true', () => {
	const src = readWizard();
	assert.match(
		src,
		/handleManualProfileChange[\s\S]{0,100}profileManuallyOverridden\s*=\s*true/,
		'handleManualProfileChange muss profileManuallyOverridden = true setzen'
	);
});

// =============================================================================
// AC-6/7: dominantProfile Derived in CompareWizard
// =============================================================================

test('AC-6: CompareWizard.svelte deklariert dominantProfile als $derived.by', () => {
	const src = readWizard();
	assert.match(
		src,
		/dominantProfile\s*=\s*\$derived\.by/,
		'CompareWizard.svelte muss dominantProfile = $derived.by(...) enthalten'
	);
});

test('AC-6: dominantProfile-Berechnung filtert "allgemein" heraus', () => {
	const src = readWizard();
	assert.match(
		src,
		/!==\s*['"]allgemein['"]/,
		'dominantProfile-Berechnung muss allgemein-Profile ausschließen'
	);
});

test('AC-7: dominantProfile-Berechnung prüft >50%-Schwelle', () => {
	const src = readWizard();
	assert.match(
		src,
		/>\s*0\.5/,
		'dominantProfile muss >0.5 Schwelle prüfen (mehr als 50%)'
	);
});

test('AC-6: dominantProfile verwendet wiz.pickedIds', () => {
	const src = readWizard();
	assert.match(
		src,
		/wiz\.pickedIds/,
		'dominantProfile muss wiz.pickedIds für die Berechnung verwenden'
	);
});

// =============================================================================
// AC-6: Auto-Apply $effect in CompareWizard
// =============================================================================

test('AC-6: CompareWizard.svelte enthält Auto-Apply $effect mit profileManuallyOverridden-Guard', () => {
	const src = readWizard();
	// Prüft dass ein $effect vorhanden ist, der profileManuallyOverridden prüft
	assert.match(
		src,
		/\$effect\s*\(\s*\(\s*\)\s*=>\s*\{[\s\S]{0,300}profileManuallyOverridden[\s\S]{0,300}\}/,
		'CompareWizard.svelte muss einen $effect mit profileManuallyOverridden-Abfrage enthalten'
	);
});

test('AC-6: Auto-Apply $effect prüft dominantProfile vor dem Setzen', () => {
	const src = readWizard();
	assert.match(
		src,
		/\$effect\s*\(\s*\(\s*\)\s*=>\s*\{[\s\S]{0,400}dominantProfile[\s\S]{0,400}wiz\.activityProfile\s*=/,
		'Auto-Apply $effect muss dominantProfile prüfen und dann wiz.activityProfile setzen'
	);
});

test('AC-6: Auto-Apply $effect blockiert bei vorhandenen idealRanges (Edit-Schutz)', () => {
	const src = readWizard();
	assert.match(
		src,
		/idealRanges/,
		'Auto-Apply $effect muss idealRanges als Guard berücksichtigen'
	);
});

// =============================================================================
// AC-9: Override-Reset $effect in CompareWizard
// =============================================================================

test('AC-9: CompareWizard.svelte enthält Reset-$effect der auf pickedIds reagiert', () => {
	const src = readWizard();
	// Prüft dass ein zweiter $effect wiz.pickedIds als Abhängigkeit hat und Override resettet
	assert.match(
		src,
		/\$effect\s*\(\s*\(\s*\)\s*=>\s*\{[\s\S]{0,200}wiz\.pickedIds[\s\S]{0,200}\}/,
		'CompareWizard.svelte muss einen $effect mit wiz.pickedIds-Abhängigkeit enthalten'
	);
});

test('AC-9: Reset-$effect setzt profileManuallyOverridden auf false', () => {
	const src = readWizard();
	// Muss mindestens zweimal profileManuallyOverridden vorkommen:
	// einmal bei = true (in handleManualProfileChange) und einmal bei = false (in $effect)
	const resetMatches = src.match(/profileManuallyOverridden\s*=\s*false/g);
	assert.ok(
		resetMatches && resetMatches.length >= 1,
		'CompareWizard.svelte muss profileManuallyOverridden = false setzen (Reset-$effect)'
	);
});

// =============================================================================
// AC-8: onManualProfileChange Callback-Prop in Step1Vergleich
// =============================================================================

test('AC-8: Step1Vergleich.svelte deklariert onManualProfileChange im Props-Interface', () => {
	const src = readStep1();
	assert.match(
		src,
		/onManualProfileChange\s*\??\s*:\s*\(\s*\)\s*=>\s*void/,
		'Step1Vergleich.svelte muss onManualProfileChange?: () => void im Props-Interface haben'
	);
});

test('AC-8: Step1Vergleich.svelte destructuriert onManualProfileChange aus $props()', () => {
	const src = readStep1();
	assert.match(
		src,
		/onManualProfileChange[\s\S]{0,50}=\s*\$props\(\)/,
		'Step1Vergleich.svelte muss onManualProfileChange aus $props() destructurieren'
	);
});

test('AC-8: handleProfileSelect in Step1 ruft onManualProfileChange?.() auf', () => {
	const src = readStep1();
	assert.match(
		src,
		/onManualProfileChange\s*\?\.\s*\(\s*\)/,
		'handleProfileSelect muss onManualProfileChange?.() aufrufen'
	);
});

// =============================================================================
// AC-8: CompareWizard übergibt Callback an Step1Vergleich
// =============================================================================

test('AC-8: CompareWizard.svelte übergibt onManualProfileChange an Step1Vergleich', () => {
	const src = readWizard();
	assert.match(
		src,
		/Step1Vergleich[\s\S]{0,200}onManualProfileChange/,
		'CompareWizard.svelte muss onManualProfileChange={handleManualProfileChange} an Step1Vergleich übergeben'
	);
});
