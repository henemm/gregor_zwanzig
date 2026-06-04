// TDD RED — Issue #583: Archiv Screen Design-Fidelity
//
// Spec: docs/specs/modules/issue_583_archiv_design_fidelity.md
//
// Source-Inspection-Tests (lesen +page.svelte als String).
// Kein Browser, kein Netzwerk, keine Mocks.
//
// Ausführung:
//   node --experimental-strip-types --test \
//     src/routes/archiv/issue_583_archiv_design_fidelity.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const PAGE = join(here, '+page.svelte');

function src(): string {
	return readFileSync(PAGE, 'utf-8');
}

// =============================================================================
// AC-1: Segmented als eigenständiger Default-Import
// =============================================================================

test('AC-1: +page.svelte importiert Segmented als Default-Import (nicht im Barrel)', () => {
	const code = src();
	assert.ok(
		code.includes("import Segmented from"),
		'+page.svelte muss "import Segmented from ..." enthalten — kein reiner Barrel-Import { Segmented, ... }'
	);
});

// =============================================================================
// AC-2: Btn als eigenständige Named-Import-Zeile
// =============================================================================

test('AC-2: +page.svelte hat "import { Btn" als eigenständige Import-Zeile', () => {
	const code = src();
	assert.ok(
		code.includes("import { Btn"),
		'+page.svelte muss "import { Btn" auf einer eigenen Zeile haben — nicht in einem Barrel-Import zusammen mit Segmented'
	);
});

test('AC-2: Segmented und Btn stehen NICHT im selben destrukturierten Import', () => {
	const code = src();
	// Prüft, dass keine Zeile BEIDE Namen im selben { } Import hat
	const sharedImport = /import\s*\{[^}]*\bSegmented\b[^}]*\bBtn\b[^}]*\}|import\s*\{[^}]*\bBtn\b[^}]*\bSegmented\b[^}]*\}/;
	assert.ok(
		!sharedImport.test(code),
		'Segmented und Btn dürfen nicht im selben destrukturierten Import stehen'
	);
});

// =============================================================================
// AC-3: Card-Atom für Tabellen-Wrapper
// =============================================================================

test('AC-3: +page.svelte importiert Card aus den Atoms', () => {
	const code = src();
	assert.ok(
		code.includes("import { Card") || code.includes("import Card"),
		'+page.svelte muss Card importieren (für den Tabellen-Wrapper)'
	);
});

test('AC-3: Tabellen-Wrapper nutzt <Card (kein rohes <div data-slot="card">', () => {
	const code = src();
	assert.ok(
		code.includes('<Card'),
		'Tabellen-Wrapper muss <Card verwenden (Card-Atom aus atoms)'
	);
	// Kein rohes <div data-slot="card" mit manuellen Border/Radius-Styles
	const rawCardDiv = /<div[^>]*data-slot="card"[^>]*border-radius/;
	assert.ok(
		!rawCardDiv.test(code),
		'Kein rohes <div data-slot="card" mit manuellen Border-Radius-Styles erlaubt — <Card> verwenden'
	);
});

// =============================================================================
// AC-4: Footer-Token --g-ink-4
// =============================================================================

test('AC-4: Footer-Zähler nutzt var(--g-ink-4)', () => {
	const code = src();
	assert.ok(
		code.includes('var(--g-ink-4)'),
		'Footer-Zähler muss var(--g-ink-4) verwenden'
	);
});

test('AC-4: var(--g-ink-muted) kommt im archiv/+page.svelte nicht mehr vor', () => {
	const code = src();
	assert.ok(
		!code.includes('var(--g-ink-muted)'),
		'var(--g-ink-muted) muss durch var(--g-ink-4) ersetzt werden'
	);
});

// =============================================================================
// AC-5: Header-Wrapper mit Flex-Layout
// =============================================================================

test('AC-5: Header-Wrapper enthält display:flex', () => {
	const code = src();
	assert.ok(
		code.includes('display:flex') || code.includes('display: flex'),
		'Header-Wrapper muss display:flex enthalten (1:1 aus JSX-Handoff)'
	);
});

test('AC-5: Header-Wrapper enthält justify-content:space-between', () => {
	const code = src();
	assert.ok(
		code.includes('justify-content:space-between') || code.includes('justify-content: space-between'),
		'Header-Wrapper muss justify-content:space-between enthalten (1:1 aus JSX-Handoff)'
	);
});

// =============================================================================
// AC-6: Regressions-Check — bestehende #388-Tests via node:test-Runner
//        (wird separat als: node --test src/routes/archiv/issue_388.test.ts ausgeführt)
//        Hier nur Smoke: Datei existiert und enthält unsere Kernstrukturen.
// =============================================================================

test('AC-6 (Smoke): +page.svelte enthält nach wie vor Segmented-Nutzung im Template', () => {
	const code = src();
	assert.ok(
		code.includes('<Segmented'),
		'<Segmented>-Nutzung im Template muss erhalten bleiben (AC-6 Regression)'
	);
});

test('AC-6 (Smoke): +page.svelte enthält nach wie vor BriefingHistoryDialog', () => {
	const code = src();
	assert.ok(
		code.includes('BriefingHistoryDialog'),
		'BriefingHistoryDialog muss erhalten bleiben (AC-6 Regression)'
	);
});
