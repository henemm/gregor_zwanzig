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

// F2b (Epic #1301): Alt-Editor + Helfer — Löschziele dieser Scheibe
const EDITOR_FILE          = join(COMPARE_DIR, 'CompareEditor.svelte');
const EDITOR_LOGIC_FILE    = join(COMPARE_DIR, 'compareEditorLogic.ts');
const EDITOR_AUTOSAVE_FILE = join(COMPARE_DIR, 'compareAutosave.ts');

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

// Issue #1256 Scheibe 4 (2026-07-14): Step3Idealwerte.svelte war bereits seit
// #1231 Slice 4/5 unbenutzter Totcode (Idealwerte laufen vollständig über
// CorridorEditor context="vergleich") — die #683-Garantie "muss erhalten
// bleiben" gilt für diese Datei nicht mehr fort. Test aktualisiert statt
// stillgelegt (Test-Politik CLAUDE.md, Muster Zeile 133/AC-2 Step5Versand).
test('AC-2 (aktualisiert #1256 Scheibe 4): Step3Idealwerte.svelte wurde gelöscht', () => {
	assert.strictEqual(
		existsSync(STEP3_FILE),
		false,
		`Step3Idealwerte.svelte muss gelöscht sein (Totcode, ersetzt durch CorridorEditor context="vergleich"), existiert aber noch: ${STEP3_FILE}`
	);
});

// Issue #1256 Scheibe 4 (2026-07-14): Step4Layout.svelte war nur noch eine
// redundante Hülle um den bereits fertigen LayoutTab-Organism — CompareEditor
// mountet <LayoutTab context="vergleich"> jetzt direkt (KL-4). Die #683-
// Garantie "muss erhalten bleiben" gilt für diese Datei nicht mehr fort.
test('AC-2 (aktualisiert #1256 Scheibe 4): Step4Layout.svelte wurde gelöscht', () => {
	assert.strictEqual(
		existsSync(STEP4_FILE),
		false,
		`Step4Layout.svelte muss gelöscht sein (redundante Hülle, ersetzt durch direkte <LayoutTab context="vergleich">-Einbettung), existiert aber noch: ${STEP4_FILE}`
	);
});

// Issue #1232 Scheibe 2b (2026-07-12): Step5Versand.svelte wurde durch den
// geteilten VersandTab-Organism (context="vergleich") + CompareInhaltSection
// ersetzt — die #683-Garantie "muss erhalten bleiben" gilt für diese Datei
// nicht mehr fort. Test aktualisiert statt stillgelegt (Test-Politik CLAUDE.md).
test('AC-2 (aktualisiert #1232 Scheibe 2b): Step5Versand.svelte wurde gelöscht', () => {
	assert.strictEqual(
		existsSync(STEP5_FILE),
		false,
		`Step5Versand.svelte muss gelöscht sein (ersetzt durch VersandTab/CompareInhaltSection), existiert aber noch: ${STEP5_FILE}`
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

// Issue #1250 Scheibe 0 (2026-07-13): toggleEnabled() war Legacy-Totcode
// (schrieb in den stillgelegten Legacy-Drittstack /api/subscriptions, #1131)
// und wurde entfernt -- die #683-Garantie "muss erhalten bleiben" gilt fuer
// diese Methode nicht mehr fort. Test aktualisiert statt stillgelegt
// (Test-Politik CLAUDE.md), Regressionsschutz jetzt in
// wizard_state_no_legacy_save.test.ts.
test('AC-3 (aktualisiert #1250 Scheibe 0): compareWizardState.svelte.ts enthält NICHT mehr "toggleEnabled"', () => {
	const src = readState();
	assert.strictEqual(
		/toggleEnabled/.test(src),
		false,
		'toggleEnabled() muss aus compareWizardState.svelte.ts entfernt sein (Legacy-Totcode, Issue #1250 Scheibe 0)'
	);
});

// =============================================================================
// F2b (Epic #1301): Alt-Editor CompareEditor.svelte + Helfer entfernt
// =============================================================================
// TDD RED — Epic #1301 F2b (Spec feat_1301_f2b_editor_loeschung.md AC-1/AC-3): rot bis zur Löschung in Phase 6.

test('F2b AC-1: CompareEditor.svelte (Alt-Editor) existiert nicht mehr', () => {
	assert.strictEqual(
		existsSync(EDITOR_FILE),
		false,
		`CompareEditor.svelte (Alt-Editor) muss gelöscht sein (Epic #1301 F2b), existiert aber noch: ${EDITOR_FILE}`
	);
});

test('F2b AC-1: compareEditorLogic.ts (Alt-Editor-Lock-Engine) existiert nicht mehr', () => {
	assert.strictEqual(
		existsSync(EDITOR_LOGIC_FILE),
		false,
		`compareEditorLogic.ts muss gelöscht sein (Epic #1301 F2b, abgelöst durch compareNewLogic.ts), existiert aber noch: ${EDITOR_LOGIC_FILE}`
	);
});

test('F2b AC-1: compareAutosave.ts (Alt-Editor-Autosave) existiert nicht mehr', () => {
	assert.strictEqual(
		existsSync(EDITOR_AUTOSAVE_FILE),
		false,
		`compareAutosave.ts muss gelöscht sein (Epic #1301 F2b, abgelöst durch den Hub-eigenen SaveController), existiert aber noch: ${EDITOR_AUTOSAVE_FILE}`
	);
});

test('F2b AC-1: Keine Produktionsdatei importiert CompareEditor.svelte, compareEditorLogic oder compareAutosave', () => {
	// Wortgrenzen/exakte Import-Pfade, damit CompareNewEditor / compareNewLogic
	// (F2a-Nachfolger) NICHT fälschlich matchen.
	const EDITOR_SVELTE_IMPORT_RE = /import[^;]*(?<![A-Za-z])CompareEditor\.svelte['"]/;
	const EDITOR_LOGIC_IMPORT_RE = /import[^;]*compareEditorLogic(\.ts)?['"]/;
	const EDITOR_AUTOSAVE_IMPORT_RE = /import[^;]*compareAutosave(\.ts)?['"]/;

	const files = collectSourceFiles(SRC_DIR);
	const hits: string[] = [];
	for (const f of files) {
		// Diese Test-Datei selbst und andere Test-Dateien überspringen
		if (f.endsWith('issue_683_wizard_remove.test.ts')) continue;
		if (f.includes('__tests__') || f.includes('.test.ts') || f.includes('.test.js')) continue;
		const content = readFileSync(f, 'utf-8');
		if (
			EDITOR_SVELTE_IMPORT_RE.test(content) ||
			EDITOR_LOGIC_IMPORT_RE.test(content) ||
			EDITOR_AUTOSAVE_IMPORT_RE.test(content)
		) {
			hits.push(f.replace(SRC_DIR + '/', ''));
		}
	}
	assert.deepStrictEqual(
		hits,
		[],
		`Folgende Produktionsdateien importieren noch den Alt-Editor oder seine Helfer ` +
			`(CompareEditor.svelte / compareEditorLogic / compareAutosave):\n  ${hits.join('\n  ')}`
	);
});

// =============================================================================
// AC-5: Route-Dateien importieren CompareEditor, NICHT CompareWizard
// =============================================================================

// TDD RED — Epic #1301 F2b (Spec feat_1301_f2b_editor_loeschung.md AC-1/AC-3): rot bis zur Löschung in Phase 6.
// AC-5 präzisiert (F2b, AC-3): die alte Prüfung matchte "CompareEditor" nur
// zufällig grün (Prosa-Kommentar in +page.svelte, nicht der tatsächliche Import).
// Ab F2a mountet /compare/new den Progressive-Tab-Editor CompareNewEditor
// (#622-Muster, s. feat_1301_f2a_compare_new_trip_pattern.md) — nicht mehr
// den Alt-Editor. Diese Fassung prüft Import UND Abwesenheit wortgrenzen-exakt.
test('AC-5 (präzisiert F2b): compare/new/+page.svelte importiert CompareNewEditor, NICHT den Alt-Editor CompareEditor.svelte', () => {
	assert.ok(existsSync(ROUTE_NEW), `Route-Datei fehlt: ${ROUTE_NEW}`);
	const src = readFileSync(ROUTE_NEW, 'utf-8');
	const hasCompareNewEditorImport =
		/import\s+CompareNewEditor\s+from\s+['"]\$lib\/components\/compare-new\/CompareNewEditor\.svelte['"]/.test(
			src
		);
	assert.ok(
		hasCompareNewEditorImport,
		"compare/new/+page.svelte muss CompareNewEditor aus '$lib/components/compare-new/CompareNewEditor.svelte' importieren"
	);
	const hasOldEditorImport = /import[^;]*(?<![A-Za-z])CompareEditor\.svelte['"]/.test(src);
	assert.strictEqual(
		hasOldEditorImport,
		false,
		'compare/new/+page.svelte darf den Alt-Editor CompareEditor.svelte nicht (mehr) importieren'
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

// Aktualisiert (Epic #1273 Scheibe S3): /compare/[id]/edit ist seit S3 ein
// reiner Redirect-Platzhalter auf den Hub (/compare/[id]) und rendert
// CompareEditor nicht mehr — Muster analog e2e/compare-edit-redirect.spec.ts
// AC-1 ("die alte CompareEditor-Seite darf nach dem Redirect nicht mehr
// rendern"), hier als Source-Inspection-Gegenstück.
test('AC-5 (aktualisiert Epic #1273 S3): compare/[id]/edit/+page.svelte importiert CompareEditor NICHT mehr (reiner Redirect-Platzhalter)', () => {
	assert.ok(existsSync(ROUTE_EDIT), `Route-Datei fehlt: ${ROUTE_EDIT}`);
	const src = readFileSync(ROUTE_EDIT, 'utf-8');
	assert.ok(
		!/CompareEditor/.test(src),
		'compare/[id]/edit/+page.svelte darf CompareEditor nicht mehr importieren/referenzieren — ' +
			'die Route ist seit Epic #1273 Scheibe S3 ein reiner Redirect-Platzhalter auf den Hub (/compare/[id])'
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
