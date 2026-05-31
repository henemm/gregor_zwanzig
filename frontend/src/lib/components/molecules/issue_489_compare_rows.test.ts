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

test('#489 AC-4a: alle 3 Komponenten-Dateien existieren in molecules/', () => {
	assert.ok(has('CompareLocationRow.svelte'), 'molecules/CompareLocationRow.svelte fehlt');
	assert.ok(has('CompareIdealRow.svelte'),    'molecules/CompareIdealRow.svelte fehlt');
	assert.ok(has('CompareLayoutRow.svelte'),   'molecules/CompareLayoutRow.svelte fehlt');
});

test('#489 AC-4b: index.ts re-exportiert alle 3 Komponenten', () => {
	const idx = read('index.ts');
	assert.ok(/CompareLocationRow/.test(idx), 'index.ts exportiert CompareLocationRow nicht');
	assert.ok(/CompareIdealRow/.test(idx),    'index.ts exportiert CompareIdealRow nicht');
	assert.ok(/CompareLayoutRow/.test(idx),   'index.ts exportiert CompareLayoutRow nicht');
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

test('#489 AC-2a: CompareIdealRow hat Props item, dense, last', () => {
	const src = read('CompareIdealRow.svelte');
	assert.ok(/\bitem\b/.test(src),  'CompareIdealRow: prop item fehlt');
	assert.ok(/\bdense\b/.test(src), 'CompareIdealRow: prop dense fehlt');
	assert.ok(/\blast\b/.test(src),  'CompareIdealRow: prop last fehlt');
});

test('#489 AC-2b: CompareIdealRow Pill-Tone-Mapping hoch→accent, mittel→default, niedrig→ghost', () => {
	const src = read('CompareIdealRow.svelte');
	assert.ok(/accent/.test(src),   'CompareIdealRow: tone "accent" (hoch) fehlt');
	assert.ok(/default/.test(src),  'CompareIdealRow: tone "default" (mittel) fehlt');
	assert.ok(/ghost/.test(src),    'CompareIdealRow: tone "ghost" (niedrig) fehlt');
});

test('#489 AC-2c: CompareIdealRow importiert Pill aus atoms', () => {
	const src = read('CompareIdealRow.svelte');
	assert.ok(
		/import\b[^;]*\bPill\b[^;]*\bfrom\b/.test(src),
		'CompareIdealRow: echter Pill-Import aus atoms fehlt'
	);
});

test('#489 AC-2d: CompareIdealRow last-Prop unterdrückt Divider', () => {
	const src = read('CompareIdealRow.svelte');
	assert.ok(/last/.test(src) && /g-rule-soft/.test(src),
		'CompareIdealRow: last-Prop + Divider-Unterdrückung fehlt');
});

test('#489 AC-2e: CompareIdealRow nutzt $derived() für Tone-Mapping', () => {
	const src = read('CompareIdealRow.svelte');
	assert.ok(/\$derived\(/.test(src), 'CompareIdealRow: $derived() für Tone-Mapping fehlt (kein Svelte 5)');
});

// ──────────────────────────────────────────────────────────────────────────────
// AC-3: CompareLayoutRow
// ──────────────────────────────────────────────────────────────────────────────

test('#489 AC-3a: CompareLayoutRow hat Props channel, cols, dense', () => {
	const src = read('CompareLayoutRow.svelte');
	assert.ok(/\bchannel\b/.test(src), 'CompareLayoutRow: prop channel fehlt');
	assert.ok(/\bcols\b/.test(src),    'CompareLayoutRow: prop cols fehlt');
	assert.ok(/\bdense\b/.test(src),   'CompareLayoutRow: prop dense fehlt');
});

test('#489 AC-3b: CompareLayoutRow SMS-Sonderfall: cols===0 zeigt Hint-Text', () => {
	const src = read('CompareLayoutRow.svelte');
	assert.ok(
		/flach[\s·•]*ohne\s+Spalten|flach\s*·\s*ohne Spalten/.test(src),
		'CompareLayoutRow: SMS-Hint-Text „flach · ohne Spalten" fehlt'
	);
});

test('#489 AC-3c: CompareLayoutRow cols===0 → keine Chips (isSmsFlat-Logik)', () => {
	const src = read('CompareLayoutRow.svelte');
	assert.ok(
		/cols\s*===?\s*0|cols\s*==\s*0/.test(src),
		'CompareLayoutRow: cols===0 SMS-Sonderfall-Bedingung fehlt'
	);
});

test('#489 AC-3d: CompareLayoutRow importiert Pill aus atoms', () => {
	const src = read('CompareLayoutRow.svelte');
	assert.ok(
		/import\b[^;]*\bPill\b[^;]*\bfrom\b/.test(src),
		'CompareLayoutRow: echter Pill-Import aus atoms fehlt'
	);
});

test('#489 AC-3e: CompareLayoutRow erstes Chip accent, restliche default', () => {
	const src = read('CompareLayoutRow.svelte');
	assert.ok(/accent/.test(src),  'CompareLayoutRow: tone "accent" für erstes Chip fehlt');
	assert.ok(/default/.test(src), 'CompareLayoutRow: tone "default" für restliche Chips fehlt');
});

// ──────────────────────────────────────────────────────────────────────────────
// Stil-Konventionen (Svelte 5, kein Tailwind, CSS-Tokens)
// ──────────────────────────────────────────────────────────────────────────────

test('#489 Konvention: alle 3 Komponenten nutzen $props() (Svelte 5)', () => {
	for (const name of ['CompareLocationRow', 'CompareIdealRow', 'CompareLayoutRow']) {
		const src = read(`${name}.svelte`);
		assert.ok(/\$props\(/.test(src), `${name}: $props() fehlt (Svelte 5 Pflicht)`);
	}
});

test('#489 Konvention: keine Tailwind-Klassen in den 3 Komponenten', () => {
	// Tailwind-Klassen sind class="..." oder class:xxx Direktiven mit Tailwind-Namen
	// Prüfe auf typische Tailwind-Muster wie "flex", "items-center" als class-String
	const TAILWIND_PATTERN = /class="[^"]*(?:flex|items-|gap-|p-\d|m-\d|text-\[|font-mono|border-)[^"]*"/;
	for (const name of ['CompareLocationRow', 'CompareIdealRow', 'CompareLayoutRow']) {
		const src = read(`${name}.svelte`);
		assert.ok(
			!TAILWIND_PATTERN.test(src),
			`${name}: Tailwind-Klassen gefunden — nur Inline-Styles mit CSS-Variablen erlaubt`
		);
	}
});

test('#489 Konvention: alle 3 Komponenten nutzen --g-font-mono', () => {
	for (const name of ['CompareLocationRow', 'CompareIdealRow', 'CompareLayoutRow']) {
		const src = read(`${name}.svelte`);
		assert.ok(/g-font-mono/.test(src), `${name}: --g-font-mono fehlt`);
	}
});
