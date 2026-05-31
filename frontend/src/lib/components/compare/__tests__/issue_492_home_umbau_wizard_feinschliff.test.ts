// TDD RED — Issue #492: Home-Umbau + Wizard-Feinschliff (Block D, Epic #485)
//
// Spec: docs/specs/modules/issue_492_home_umbau_wizard_feinschliff.md
//
// Source-Inspection-Tests (kein DOM-Rendering, keine Mocks).
// Methodik: node:test + readFileSync — prüft Datei-Invarianten.
//
// RED-Erwartung (vor Implementation):
//   - +page.server.ts hat noch /api/subscriptions → FAIL
//   - +page.svelte fehlen WORKSPACE-Eyebrow, activePresets, etc. → FAIL
//   - CompareKachel.svelte nutzt noch kein CompareTile → FAIL
//   - CompareWizard.svelte hat noch confirm() statt ConfirmDialog → FAIL
//   - compareWizardState.svelte.ts navigiert noch zu '/compare' ohne ID → FAIL
//
// Ausführen:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/issue_492_home_umbau_wizard_feinschliff.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';

// Pfad-Auflösung: Testdatei liegt in compare/__tests__/
// '../../../../routes/' geht: __tests__ → compare → components → lib → src → routes
const ROUTES  = fileURLToPath(new URL('../../../../routes/', import.meta.url));
const COMPARE = fileURLToPath(new URL('../', import.meta.url));

const SERVER_TS    = join(ROUTES, '+page.server.ts');
const HOME_PAGE    = join(ROUTES, '+page.svelte');
const KACHEL       = join(ROUTES, '_home/CompareKachel.svelte');
const WIZARD       = join(COMPARE, 'CompareWizard.svelte');
const WIZARD_STATE = join(COMPARE, 'compareWizardState.svelte.ts');

// ─── AC-1 / AC-4: +page.server.ts — API-Endpunkt ────────────────────────────

test('#492 server: /api/subscriptions entfernt (AC-1)', () => {
	const src = readFileSync(SERVER_TS, 'utf-8');
	assert.ok(
		!src.includes('/api/subscriptions'),
		'+page.server.ts darf /api/subscriptions nicht mehr enthalten — muss auf /api/compare/presets umgestellt sein'
	);
});

test('#492 server: /api/compare/presets vorhanden (AC-1)', () => {
	const src = readFileSync(SERVER_TS, 'utf-8');
	assert.match(
		src,
		/\/api\/compare\/presets/,
		'+page.server.ts muss /api/compare/presets laden'
	);
});

test('#492 server: Return-Typ ist presets (AC-1)', () => {
	const src = readFileSync(SERVER_TS, 'utf-8');
	assert.match(
		src,
		/return\s*\{[^}]*presets/,
		'+page.server.ts muss { presets } zurückgeben'
	);
});

// ─── AC-4: +page.svelte — SectionH Header ────────────────────────────────────

test('#492 home: WORKSPACE Eyebrow vorhanden (AC-4)', () => {
	const src = readFileSync(HOME_PAGE, 'utf-8');
	assert.match(
		src,
		/WORKSPACE/,
		'+page.svelte muss Eyebrow "WORKSPACE" enthalten'
	);
});

test('#492 home: Aktive Orts-Vergleiche Titel vorhanden (AC-4)', () => {
	const src = readFileSync(HOME_PAGE, 'utf-8');
	assert.match(
		src,
		/Aktive Orts-Vergleiche/,
		'+page.svelte muss Sektions-Titel "Aktive Orts-Vergleiche" enthalten'
	);
});

test('#492 home: Kicker-Text vorhanden (AC-4)', () => {
	const src = readFileSync(HOME_PAGE, 'utf-8');
	assert.match(
		src,
		/Laufen automatisch/,
		'+page.svelte muss Kicker "Laufen automatisch — Briefing kommt in die Kanäle" enthalten'
	);
});

test('#492 home: Alle anzeigen Link zu /compare in Snippet-Kontext (AC-4)', () => {
	const src = readFileSync(HOME_PAGE, 'utf-8');
	// Nach Implementation gibt es einen Snippet mit href="/compare" und Text "Alle anzeigen" direkt daneben (<70 Zeichen).
	// Aktuell: href="/compare" links sagen "Neuer Vergleich", "Alle anzeigen" ist für /trips-Archiv → kein Match.
	assert.match(
		src,
		/href="\/compare"[\s\S]{0,70}Alle anzeigen|Alle anzeigen[\s\S]{0,70}href="\/compare"/,
		'+page.svelte muss href="/compare" und "Alle anzeigen" innerhalb von 70 Zeichen nebeneinander haben (compare-Snippet)'
	);
});

// ─── AC-1: +page.svelte — Filterlogik ────────────────────────────────────────

test('#492 home: deriveStatusFromPreset importiert und genutzt (AC-1)', () => {
	const src = readFileSync(HOME_PAGE, 'utf-8');
	assert.match(
		src,
		/deriveStatusFromPreset/,
		'+page.svelte muss deriveStatusFromPreset für Filterung aktiver Vergleiche nutzen'
	);
});

test('#492 home: activePresets-Derivat vorhanden (AC-1)', () => {
	const src = readFileSync(HOME_PAGE, 'utf-8');
	assert.match(
		src,
		/activePresets/,
		'+page.svelte muss activePresets-Variable (oder -Derivat) für gefilterte Anzeige haben'
	);
});

test('#492 home: subscriptions-Variable entfernt (AC-1)', () => {
	const src = readFileSync(HOME_PAGE, 'utf-8');
	// data.subscriptions darf nicht mehr genutzt werden
	assert.ok(
		!src.includes('data.subscriptions'),
		'+page.svelte darf data.subscriptions nicht mehr referenzieren — muss data.presets nutzen'
	);
});

// ─── AC-2 / AC-3: CompareKachel.svelte — Thin-Wrapper ────────────────────────

test('#492 kachel: CompareTile importiert (AC-2, AC-3)', () => {
	const src = readFileSync(KACHEL, 'utf-8');
	assert.match(
		src,
		/CompareTile/,
		'CompareKachel.svelte muss CompareTile importieren und nutzen'
	);
});

test('#492 kachel: compact-Prop gesetzt (AC-2)', () => {
	const src = readFileSync(KACHEL, 'utf-8');
	assert.match(
		src,
		/compact/,
		'CompareKachel.svelte muss compact-Prop an CompareTile weitergeben'
	);
});

test('#492 kachel: Klick-Navigation zu /compare/{id} (AC-2)', () => {
	const src = readFileSync(KACHEL, 'utf-8');
	assert.match(
		src,
		/\/compare\/.*sub\.id|goto.*compare.*sub\.id/,
		'CompareKachel.svelte muss bei Klick zu /compare/{id} navigieren'
	);
});

test('#492 kachel: Edit-Navigation zu /compare/{id}/edit (AC-3)', () => {
	const src = readFileSync(KACHEL, 'utf-8');
	assert.match(
		src,
		/\/edit.*sub\.id|sub\.id.*\/edit/,
		'CompareKachel.svelte muss Edit-Aktion zu /compare/{id}/edit navigieren (onAction oder href)'
	);
});

test('#492 kachel: ComparePreset als Props-Typ (AC-2)', () => {
	const src = readFileSync(KACHEL, 'utf-8');
	assert.match(
		src,
		/ComparePreset/,
		'CompareKachel.svelte muss ComparePreset statt Subscription als Props-Typ nutzen'
	);
});

// ─── AC-5 / AC-6 / AC-7: CompareWizard.svelte ───────────────────────────────

test('#492 wizard: kein nativer confirm() mehr (AC-6)', () => {
	const src = readFileSync(WIZARD, 'utf-8');
	// confirm( ohne window. oder mit window. — beide müssen weg
	assert.ok(
		!src.includes('confirm('),
		'CompareWizard.svelte darf kein window.confirm() mehr aufrufen — muss ConfirmDialog nutzen'
	);
});

test('#492 wizard: ConfirmDialog importiert und genutzt (AC-6)', () => {
	const src = readFileSync(WIZARD, 'utf-8');
	assert.match(
		src,
		/ConfirmDialog/,
		'CompareWizard.svelte muss ConfirmDialog aus molecules importieren'
	);
});

test('#492 wizard: cancelDialogOpen State vorhanden (AC-6)', () => {
	const src = readFileSync(WIZARD, 'utf-8');
	assert.match(
		src,
		/cancelDialogOpen/,
		'CompareWizard.svelte muss cancelDialogOpen State-Variable für Create-Abbrechen haben'
	);
});

test('#492 wizard: discardDialogOpen State vorhanden (AC-7)', () => {
	const src = readFileSync(WIZARD, 'utf-8');
	assert.match(
		src,
		/discardDialogOpen/,
		'CompareWizard.svelte muss discardDialogOpen State-Variable für Edit-Verwerfen haben'
	);
});

test('#492 wizard: Zurück-Button im Edit-Mode-Footer (AC-5)', () => {
	const src = readFileSync(WIZARD, 'utf-8');
	assert.match(
		src,
		/← Zurück|Zurück/,
		'CompareWizard.svelte muss ← Zurück Button im Edit-Mode-Footer haben'
	);
});

test('#492 wizard: prevStep-Aufruf im Footer (AC-5)', () => {
	const src = readFileSync(WIZARD, 'utf-8');
	assert.match(
		src,
		/prevStep/,
		'CompareWizard.svelte muss prevStep() im Footer-Button aufrufen'
	);
});

test('#492 wizard: Zurück-Button nur ab Schritt 2 (AC-5)', () => {
	const src = readFileSync(WIZARD, 'utf-8');
	// Muss einen Guard currentStep > 1 oder currentStep !== 1 haben
	assert.match(
		src,
		/currentStep\s*[>!]=?\s*[12]|[12]\s*[<!=]=?\s*currentStep/,
		'CompareWizard.svelte muss ← Zurück nur wenn currentStep > 1 zeigen'
	);
});

// ─── AC-7 / AC-8: compareWizardState.svelte.ts — save()-Navigation ──────────

test('#492 state: save() navigiert zu /compare/{id} im Edit-Mode (AC-8)', () => {
	const src = readFileSync(WIZARD_STATE, 'utf-8');
	assert.match(
		src,
		/\/compare\/.*subscriptionId|subscriptionId.*\/compare\//,
		'compareWizardState save() muss im Edit-Mode zu /compare/{subscriptionId} navigieren'
	);
});

test('#492 state: save()-Navigation ist bedingt (isEditMode && subscriptionId) (AC-8)', () => {
	const src = readFileSync(WIZARD_STATE, 'utf-8');
	// Muss eine Bedingung haben die isEditMode und subscriptionId für die Navigation prüft
	// Die goto-Zeile muss den Zielstring bedingt aufbauen
	assert.match(
		src,
		/goto\s*\([^)]*subscriptionId/s,
		'compareWizardState save() muss goto() mit subscriptionId als Ziel aufrufen'
	);
});
