// TDD RED — Issue #683: Compare-Wizard entfernen.
// SPEC: docs/specs/modules/issue_683_compare_wizard_remove.md
//
// Prüft via Source-Inspection (node:test + readFileSync), dass der Wizard
// entfernt und die State-Klasse auf Datenfelder reduziert wurde.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/issue_683_wizard_remove.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync, readdirSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
// compare/ = __tests__/..
const COMPARE_DIR = join(here, '..');

// Datei-Pfade
const WIZARD_FILE = join(COMPARE_DIR, 'CompareWizard.svelte');
const STEP1_FILE  = join(COMPARE_DIR, 'steps', 'Step1Vergleich.svelte');
const STEP2_FILE  = join(COMPARE_DIR, 'steps', 'Step2Orte.svelte');
const STEP3_FILE  = join(COMPARE_DIR, 'steps', 'Step3Idealwerte.svelte');
const STEP4_FILE  = join(COMPARE_DIR, 'steps', 'Step4Layout.svelte');
const STEP5_FILE  = join(COMPARE_DIR, 'steps', 'Step5Versand.svelte');
const STATE_FILE  = join(COMPARE_DIR, 'compareWizardState.svelte.ts');

// Repo-Root (6x up: __tests__ → compare → components → lib → src → frontend → repo-root)
const REPO_ROOT   = join(here, '..', '..', '..', '..', '..', '..');
const SRC_DIR     = join(REPO_ROOT, 'frontend', 'src');

const ROUTE_NEW   = join(SRC_DIR, 'routes', 'compare', 'new', '+page.svelte');
const ROUTE_EDIT  = join(SRC_DIR, 'routes', 'compare', '[id]', 'edit', '+page.svelte');

// =============================================================================
// Hilfsfunktion: alle .svelte/.ts-Dateien in frontend/src rekursiv sammeln
// =============================================================================

function collectSourceFiles(dir: string): string[] {
	const results: string[] = [];
	if (!existsSync(dir)) return results;
	for (const entry of readdirSync(dir)) {
		const full = join(dir, entry);
		const st = statSync(full);
		if (st.isDirectory()) {
			results.push(...collectSourceFiles(full));
		} else if (/\.(svelte|ts|js)$/.test(entry)) {
			results.push(full);
		}
	}
	return results;
}

// =============================================================================
// AC-1: CompareWizard.svelte existiert nicht mehr
// =============================================================================

test('AC-1: CompareWizard.svelte wurde gelöscht', () => {
	assert.strictEqual(
		existsSync(WIZARD_FILE),
		false,
		`CompareWizard.svelte muss gelöscht sein, existiert aber noch: ${WIZARD_FILE}`
	);
});

test('AC-1: Keine Produktionsdatei importiert CompareWizard (die Svelte-Komponente)', () => {
	// Prüft: kein `import ... from '...CompareWizard.svelte'` und kein `<CompareWizard`-Tag
	// CompareWizardState ist die State-Klasse (bleibt erhalten) — diese ist explizit ausgenommen.
	const files = collectSourceFiles(SRC_DIR);
	const hits: string[] = [];
	for (const f of files) {
		// Diese Test-Datei selbst überspringen
		if (f.endsWith('issue_683_wizard_remove.test.ts')) continue;
		// Andere Test-Dateien überspringen (issue_440 testet die alte Wizard-Datei)
		if (f.includes('__tests__') || f.includes('.test.ts') || f.includes('.test.js')) continue;
		const content = readFileSync(f, 'utf-8');
		// Treffer: Import der Svelte-Komponente ODER Verwendung als Tag
		// Nicht treffen: CompareWizardState (State-Klasse, bleibt erhalten)
		const hasComponentImport = /import[^;]*CompareWizard\.svelte/.test(content);
		const hasComponentTag = /<CompareWizard[\s/>]/.test(content);
		// CompareWizard.svelte selbst überspringen (sie soll gelöscht werden — Test 1 greift)
		if (f.endsWith('CompareWizard.svelte')) continue;
		if (hasComponentImport || hasComponentTag) {
			hits.push(f.replace(SRC_DIR + '/', ''));
		}
	}
	assert.deepStrictEqual(
		hits,
		[],
		`Folgende Produktionsdateien importieren noch CompareWizard (Svelte-Komponente):\n  ${hits.join('\n  ')}`
	);
});

// =============================================================================
// AC-2: Step1 gelöscht, Steps 2–5 erhalten
// =============================================================================

test('AC-2: Step1Vergleich.svelte wurde gelöscht', () => {
	assert.strictEqual(
		existsSync(STEP1_FILE),
		false,
		`Step1Vergleich.svelte muss gelöscht sein, existiert aber noch: ${STEP1_FILE}`
	);
});

test('AC-2: Step2Orte.svelte ist noch vorhanden', () => {
	assert.ok(
		existsSync(STEP2_FILE),
		`Step2Orte.svelte fehlt — darf nicht gelöscht werden: ${STEP2_FILE}`
	);
});

test('AC-2: Step3Idealwerte.svelte ist noch vorhanden', () => {
	assert.ok(
		existsSync(STEP3_FILE),
		`Step3Idealwerte.svelte fehlt — darf nicht gelöscht werden: ${STEP3_FILE}`
	);
});

test('AC-2: Step4Layout.svelte ist noch vorhanden', () => {
	assert.ok(
		existsSync(STEP4_FILE),
		`Step4Layout.svelte fehlt — darf nicht gelöscht werden: ${STEP4_FILE}`
	);
});

test('AC-2: Step5Versand.svelte ist noch vorhanden', () => {
	assert.ok(
		existsSync(STEP5_FILE),
		`Step5Versand.svelte fehlt — darf nicht gelöscht werden: ${STEP5_FILE}`
	);
});

// =============================================================================
// AC-3: compareWizardState.svelte.ts — Stepper-Felder entfernt
// =============================================================================

function readState(): string {
	if (!existsSync(STATE_FILE)) {
		throw new Error(`compareWizardState.svelte.ts nicht gefunden: ${STATE_FILE}`);
	}
	return readFileSync(STATE_FILE, 'utf-8');
}

test('AC-3: compareWizardState.svelte.ts enthält NICHT mehr "currentStep"', () => {
	const src = readState();
	assert.strictEqual(
		/currentStep/.test(src),
		false,
		'currentStep muss aus compareWizardState.svelte.ts entfernt sein (Stepper-Feld)'
	);
});

test('AC-3: compareWizardState.svelte.ts enthält NICHT mehr "nextStep"', () => {
	const src = readState();
	assert.strictEqual(
		/nextStep/.test(src),
		false,
		'nextStep() muss aus compareWizardState.svelte.ts entfernt sein (Stepper-Methode)'
	);
});

test('AC-3: compareWizardState.svelte.ts enthält NICHT mehr "prevStep"', () => {
	const src = readState();
	assert.strictEqual(
		/prevStep/.test(src),
		false,
		'prevStep() muss aus compareWizardState.svelte.ts entfernt sein (Stepper-Methode)'
	);
});

test('AC-3: compareWizardState.svelte.ts enthält NICHT mehr "goToStep"', () => {
	const src = readState();
	assert.strictEqual(
		/goToStep/.test(src),
		false,
		'goToStep() muss aus compareWizardState.svelte.ts entfernt sein (Stepper-Methode)'
	);
});

test('AC-3: compareWizardState.svelte.ts enthält NICHT mehr "canAdvanceCurrent"', () => {
	const src = readState();
	assert.strictEqual(
		/canAdvanceCurrent/.test(src),
		false,
		'canAdvanceCurrent muss aus compareWizardState.svelte.ts entfernt sein (Stepper-Getter)'
	);
});

// Datenfelder MÜSSEN erhalten bleiben (diese Tests sollten bereits GRÜN sein)

test('AC-3: compareWizardState.svelte.ts enthält noch "saveNewPreset" (Datenfeld bleibt)', () => {
	const src = readState();
	assert.ok(
		/saveNewPreset/.test(src),
		'saveNewPreset() muss in compareWizardState.svelte.ts erhalten bleiben'
	);
});

test('AC-3: compareWizardState.svelte.ts enthält noch "toggleEnabled" (Datenfeld bleibt)', () => {
	const src = readState();
	assert.ok(
		/toggleEnabled/.test(src),
		'toggleEnabled() muss in compareWizardState.svelte.ts erhalten bleiben'
	);
});

// =============================================================================
// AC-5: Route-Dateien importieren CompareEditor, NICHT CompareWizard
// =============================================================================

test('AC-5: compare/new/+page.svelte importiert CompareEditor', () => {
	assert.ok(existsSync(ROUTE_NEW), `Route-Datei fehlt: ${ROUTE_NEW}`);
	const src = readFileSync(ROUTE_NEW, 'utf-8');
	assert.ok(
		/CompareEditor/.test(src),
		'compare/new/+page.svelte muss CompareEditor importieren'
	);
});

test('AC-5: compare/new/+page.svelte importiert NICHT mehr CompareWizard (Svelte-Komponente)', () => {
	assert.ok(existsSync(ROUTE_NEW), `Route-Datei fehlt: ${ROUTE_NEW}`);
	const src = readFileSync(ROUTE_NEW, 'utf-8');
	// CompareWizardState (State-Klasse) darf noch importiert sein — geprüft wird nur die Svelte-Komponente
	const hasComponentImport = /import[^;]*CompareWizard\.svelte/.test(src);
	const hasComponentTag = /<CompareWizard[\s/>]/.test(src);
	assert.strictEqual(
		hasComponentImport || hasComponentTag,
		false,
		'compare/new/+page.svelte darf CompareWizard.svelte nicht mehr importieren oder als Tag verwenden'
	);
});

test('AC-5: compare/[id]/edit/+page.svelte importiert CompareEditor', () => {
	assert.ok(existsSync(ROUTE_EDIT), `Route-Datei fehlt: ${ROUTE_EDIT}`);
	const src = readFileSync(ROUTE_EDIT, 'utf-8');
	assert.ok(
		/CompareEditor/.test(src),
		'compare/[id]/edit/+page.svelte muss CompareEditor importieren'
	);
});

test('AC-5: compare/[id]/edit/+page.svelte importiert NICHT mehr CompareWizard (Svelte-Komponente)', () => {
	assert.ok(existsSync(ROUTE_EDIT), `Route-Datei fehlt: ${ROUTE_EDIT}`);
	const src = readFileSync(ROUTE_EDIT, 'utf-8');
	// CompareWizardState (State-Klasse) darf noch importiert sein — geprüft wird nur die Svelte-Komponente
	const hasComponentImport = /import[^;]*CompareWizard\.svelte/.test(src);
	const hasComponentTag = /<CompareWizard[\s/>]/.test(src);
	assert.strictEqual(
		hasComponentImport || hasComponentTag,
		false,
		'compare/[id]/edit/+page.svelte darf CompareWizard.svelte nicht mehr importieren oder als Tag verwenden'
	);
});
