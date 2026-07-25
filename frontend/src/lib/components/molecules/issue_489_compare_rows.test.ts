// TDD RED: Issue #489 — Block A2 (Epic #485): 3 Compare-Row-Molecules
//
// Spec: docs/specs/modules/issue_489_compare_row_molecules.md
//
// Source-Inspection-Tests (node:test, kein Render, keine Mocks):
//   Datei-Existenz, index.ts-Re-Exporte, Schlüssel-Props,
//   Rang-Badge-Logik, Pill-Tone-Mapping, SMS-Sonderfall.
//
// RED vor Implementierung: Dateien fehlen → alle Asserts schlagen fehl.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test src/lib/components/molecules/issue_489_compare_rows.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const read = (f: string) => readFileSync(join(here, f), 'utf-8');
const has = (f: string) => existsSync(join(here, f));

// ──────────────────────────────────────────────────────────────────────────────
// AC-4 (Datei-Existenz + index.ts Re-Exporte)
// ──────────────────────────────────────────────────────────────────────────────

// Issue #1360: CompareLayoutRow.svelte ist geloescht (Attrappen-Zeile ohne
// Handler, Spec compare_layout_tab_dissolution § Dependencies) — aus allen
// Listen dieser Suite entfernt. Die uebrigen 2 Molecules bleiben unveraendert.
test('#489 AC-4a: alle 2 Komponenten-Dateien existieren in molecules/', () => {
	assert.ok(has('CompareLocationRow.svelte'), 'molecules/CompareLocationRow.svelte fehlt');
	assert.ok(has('CompareIdealRow.svelte'),    'molecules/CompareIdealRow.svelte fehlt');
	assert.ok(!has('CompareLayoutRow.svelte'), 'CompareLayoutRow.svelte muss mit #1360 geloescht sein');
});

test('#489 AC-4b: index.ts re-exportiert alle 2 Komponenten', () => {
	const idx = read('index.ts');
	assert.ok(/CompareLocationRow/.test(idx), 'index.ts exportiert CompareLocationRow nicht');
	assert.ok(/CompareIdealRow/.test(idx),    'index.ts exportiert CompareIdealRow nicht');
	assert.ok(!/CompareLayoutRow/.test(idx), 'index.ts darf CompareLayoutRow nicht mehr exportieren (#1360)');
});

// ──────────────────────────────────────────────────────────────────────────────
// AC-1: CompareLocationRow
// ──────────────────────────────────────────────────────────────────────────────

test('#489 AC-1a: CompareLocationRow hat Props loc, index, dense, alt', () => {
	const src = read('CompareLocationRow.svelte');
	assert.ok(/\bloc\b/.test(src),   'CompareLocationRow: prop loc fehlt');
	assert.ok(/\bindex\b/.test(src), 'CompareLocationRow: prop index fehlt');
	assert.ok(/\bdense\b/.test(src), 'CompareLocationRow: prop dense fehlt');
	assert.ok(/\balt\b/.test(src),   'CompareLocationRow: prop alt fehlt');
});

test('#489 AC-1b: CompareLocationRow zeigt Rang-Badge mit padStart(2)', () => {
	const src = read('CompareLocationRow.svelte');
	assert.ok(/padStart\s*\(\s*2/.test(src), 'CompareLocationRow: padStart(2) für Rang-Badge fehlt');
});

test('#489 AC-1c: CompareLocationRow nutzt --g-accent für Rang-Badge', () => {
	const src = read('CompareLocationRow.svelte');
	assert.ok(/g-accent/.test(src), 'CompareLocationRow: --g-accent für Rang-Badge fehlt');
});

test('#489 AC-1d: CompareLocationRow zeigt elevation_m als Höhe', () => {
	const src = read('CompareLocationRow.svelte');
	assert.ok(/elevation_m/.test(src), 'CompareLocationRow: elevation_m fehlt');
});

test('#489 AC-1e: CompareLocationRow zeigt Gruppe nur wenn truthy', () => {
	const src = read('CompareLocationRow.svelte');
	// Entweder conditional rendering mit loc.group oder optionale Anzeige
	assert.ok(
		/loc\.group/.test(src),
		'CompareLocationRow: loc.group (bedingte Gruppen-Anzeige) fehlt'
	);
});

test('#489 AC-1f: CompareLocationRow alternating background via alt-Prop', () => {
	const src = read('CompareLocationRow.svelte');
	assert.ok(/g-card-alt/.test(src), 'CompareLocationRow: --g-card-alt für alt-Prop fehlt');
});

test('#489 AC-1g: CompareLocationRow hat unteren Divider (--g-rule-soft)', () => {
	const src = read('CompareLocationRow.svelte');
	assert.ok(/g-rule-soft/.test(src), 'CompareLocationRow: --g-rule-soft Divider fehlt');
});

// ──────────────────────────────────────────────────────────────────────────────
// AC-2: CompareIdealRow
// ──────────────────────────────────────────────────────────────────────────────
// Stil-Konventionen (Svelte 5, kein Tailwind, CSS-Tokens)
// ──────────────────────────────────────────────────────────────────────────────

test('#489 Konvention: alle 2 Komponenten nutzen $props() (Svelte 5)', () => {
	for (const name of ['CompareLocationRow', 'CompareIdealRow']) {
		const src = read(`${name}.svelte`);
		assert.ok(/\$props\(/.test(src), `${name}: $props() fehlt (Svelte 5 Pflicht)`);
	}
});

test('#489 Konvention: keine Tailwind-Klassen in den 2 Komponenten', () => {
	// Tailwind-Klassen sind class="..." oder class:xxx Direktiven mit Tailwind-Namen
	// Prüfe auf typische Tailwind-Muster wie "flex", "items-center" als class-String
	const TAILWIND_PATTERN = /class="[^"]*(?:flex|items-|gap-|p-\d|m-\d|text-\[|font-mono|border-)[^"]*"/;
	for (const name of ['CompareLocationRow', 'CompareIdealRow']) {
		const src = read(`${name}.svelte`);
		assert.ok(
			!TAILWIND_PATTERN.test(src),
			`${name}: Tailwind-Klassen gefunden — nur Inline-Styles mit CSS-Variablen erlaubt`
		);
	}
});

test('#489 Konvention: alle 2 Komponenten nutzen --g-font-mono', () => {
	for (const name of ['CompareLocationRow', 'CompareIdealRow']) {
		const src = read(`${name}.svelte`);
		assert.ok(/g-font-mono/.test(src), `${name}: --g-font-mono fehlt`);
	}
});
