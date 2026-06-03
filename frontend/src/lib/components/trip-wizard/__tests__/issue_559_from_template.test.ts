// TDD RED — Issue #559: WizardState.fromTemplate() Methode.
// Spec: docs/specs/modules/issue_559_archiv_fertigstellen.md (AC-2, AC-5)
//
// fromTemplate() existiert noch nicht in wizardState.svelte.ts → Tests FEHLSCHLAGEN.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/trip-wizard/__tests__/issue_559_from_template.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const STATE_FILE = join(here, '..', 'wizardState.svelte.ts');

function src(): string {
	if (!existsSync(STATE_FILE)) {
		throw new Error(`wizardState.svelte.ts nicht gefunden: ${STATE_FILE}`);
	}
	return readFileSync(STATE_FILE, 'utf-8');
}

// =============================================================================
// AC-2: fromTemplate()-Methode existiert
// =============================================================================

test('AC-2: fromTemplate-Methode ist in wizardState.svelte.ts definiert', () => {
	const code = src();
	assert.ok(
		/fromTemplate\s*\(/.test(code),
		'fromTemplate() muss in WizardState definiert sein'
	);
});

// =============================================================================
// AC-2: fromTemplate kopiert activity
// =============================================================================

test('AC-2: fromTemplate übernimmt activity aus dem Vorlagen-Trip', () => {
	const code = src();
	// fromTemplate muss this.activity setzen
	const hasActivityAssign = /fromTemplate[\s\S]{0,600}this\.activity\s*=/.test(code);
	assert.ok(
		hasActivityAssign,
		'fromTemplate() muss this.activity = ... setzen'
	);
});

// =============================================================================
// AC-2: fromTemplate kopiert alertRules
// =============================================================================

test('AC-2: fromTemplate übernimmt alertRules aus dem Vorlagen-Trip', () => {
	const code = src();
	const hasAlertRules = /fromTemplate[\s\S]{0,600}this\.alertRules\s*=/.test(code);
	assert.ok(
		hasAlertRules,
		'fromTemplate() muss this.alertRules = ... setzen'
	);
});

// =============================================================================
// AC-5: fromTemplate setzt name NICHT (User trägt Name neu ein)
// =============================================================================

test('AC-5: fromTemplate setzt this.name nicht aus dem Vorlagen-Trip', () => {
	const code = src();
	// Isoliert den fromTemplate-Block und prüft dass kein this.name = template.name vorkommt
	const fromTemplateBlock = code.match(/fromTemplate\s*\([^)]*\)\s*\{[\s\S]*?(?=\n\s{1,4}[a-z]|\n\})/)?.[0] ?? '';
	assert.ok(
		!(/this\.name\s*=\s*[^(]*(template|trip)/.test(fromTemplateBlock)),
		'fromTemplate() darf this.name NICHT aus dem Vorlagen-Trip übernehmen'
	);
});

// =============================================================================
// AC-5: fromTemplate kopiert keine Waypoints (stages.waypoints wird geleert)
// =============================================================================

test('AC-5: fromTemplate löscht Waypoints aus kopierten Etappen', () => {
	const code = src();
	// fromTemplate muss Stages ohne Waypoints anlegen (waypoints: [] oder waypoints leer lassen)
	const fromTemplateBlock = code.match(/fromTemplate\s*\([^)]*\)\s*\{[\s\S]*?(?=\n\s{1,4}[a-zA-Z_$]|\n\})/)?.[0] ?? '';
	const hasWaypointsClear =
		/waypoints\s*:\s*\[\]/.test(fromTemplateBlock) ||
		/\.map\([^)]*=>\s*\(\s*\{[^}]*waypoints\s*:\s*\[\]/.test(fromTemplateBlock) ||
		/waypoints\s*:\s*\[\]/.test(code.slice(code.indexOf('fromTemplate')).slice(0, 800));
	assert.ok(
		hasWaypointsClear,
		'fromTemplate() muss Waypoints aus kopierten Etappen entfernen (waypoints: [])'
	);
});

// =============================================================================
// AC-5: fromTemplate kopiert keine Etappen-Daten (date wird nicht übernommen)
// =============================================================================

test('AC-5: fromTemplate übernimmt keine Stage-Daten (date wird leergelassen)', () => {
	const code = src();
	const fromTemplateStart = code.indexOf('fromTemplate');
	const block = code.slice(fromTemplateStart, fromTemplateStart + 800);
	// date darf nicht direkt aus dem Template übernommen werden
	assert.ok(
		!(/date\s*:\s*(?:stage|s|t)\.(date|[a-z_]+date)/.test(block)),
		'fromTemplate() darf stage.date nicht übernehmen'
	);
});
