// TDD RED: Issue #418 — Segmented.svelte API-Alignment mit Design-System-Katalog
//
// Spec: docs/specs/modules/issue_418_segmented_api.md
//
// Source-Inspection-Tests (kein Render, keine Mocks): prüft ob Segmented.svelte
// die Alias-Props (items/value/onChange/size) deklariert und ob app.css die
// size-Varianten enthält.
//
// RED: Alle Tests schlagen fehl, weil die Alias-Props noch nicht implementiert sind.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test src/lib/components/ui/segmented/issue_418.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, resolve } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
// here = .../frontend/src/lib/components/ui/segmented
// 4 levels up → frontend/src/
// 6 levels up → project root (gregor_zwanzig/)
const frontendSrc = resolve(here, '../../../../');
const projectRoot = resolve(here, '../../../../../../');

const segmented  = readFileSync(join(here, 'Segmented.svelte'), 'utf-8');
const appCss     = readFileSync(join(frontendSrc, 'app.css'), 'utf-8');
const catalogMd  = readFileSync(join(projectRoot, 'docs/design-system/COMPONENTS.md'), 'utf-8');

// ── AC-1: SOLL-API-Props ──────────────────────────────────────────────────────

test('#418 AC-1: Segmented.svelte deklariert SOLL-Prop "items"', () => {
	assert.ok(
		/\bitems\b/.test(segmented),
		'Prop "items" fehlt in Segmented.svelte — SOLL-API nicht implementiert'
	);
});

test('#418 AC-1: Segmented.svelte enthält resolvedValue-Derived für Alias-Auflösung', () => {
	assert.ok(
		/resolvedValue/.test(segmented),
		'"resolvedValue" fehlt — Alias-Derived für value/selected nicht implementiert'
	);
});

test('#418 AC-1: Segmented.svelte deklariert SOLL-Prop "onChange"', () => {
	assert.ok(
		/\bonChange\b/.test(segmented),
		'Prop "onChange" fehlt in Segmented.svelte — SOLL-API nicht implementiert'
	);
});

test('#418 AC-1: Segmented.svelte enthält resolvedItems-Derived für Alias-Auflösung', () => {
	assert.ok(
		/resolvedItems/.test(segmented),
		'"resolvedItems" fehlt — Alias-Derived-Logik nicht implementiert'
	);
});

// ── AC-2: IST-API bleibt erhalten (Alias) ────────────────────────────────────

test('#418 AC-2: Segmented.svelte deklariert BEIDE Prop-Sets (options UND items)', () => {
	assert.ok(
		/\boptions\b/.test(segmented) && /\bitems\b/.test(segmented),
		'Segmented.svelte muss sowohl "options" (IST) als auch "items" (SOLL) deklarieren'
	);
});

test('#418 AC-2: Segmented.svelte enthält resolvedChange-Derived (belegt IST+SOLL werden zusammengeführt)', () => {
	assert.ok(
		/resolvedChange/.test(segmented),
		'"resolvedChange" fehlt — Alias-Derived für onChange/onselect nicht implementiert'
	);
});

// ── AC-3 + AC-4: size-Prop ────────────────────────────────────────────────────

test('#418 AC-3/4: Segmented.svelte deklariert size-Prop', () => {
	assert.ok(
		/\bsize\b/.test(segmented),
		'Prop "size" fehlt in Segmented.svelte'
	);
});

test('#418 AC-3/4: Segmented.svelte setzt data-size auf Container-Element', () => {
	assert.ok(
		/data-size/.test(segmented),
		'"data-size" fehlt im Template — size-Attribut wird nicht gesetzt'
	);
});

test('#418 AC-3: app.css enthält [data-size="sm"]-Regel für segmented-item', () => {
	assert.ok(
		/\[data-slot="segmented"\]\[data-size="sm"\]/.test(appCss) ||
		/\[data-size="sm"\].*segmented-item/.test(appCss),
		'Keine [data-size="sm"]-Regel für segmented in app.css'
	);
});

test('#418 AC-3: app.css enthält [data-size="md"]-Regel für segmented-item', () => {
	assert.ok(
		/\[data-slot="segmented"\]\[data-size="md"\]/.test(appCss) ||
		/\[data-size="md"\].*segmented-item/.test(appCss),
		'Keine [data-size="md"]-Regel für segmented in app.css'
	);
});

// ── AC-5: COMPONENTS.md — IST-API als primäre API ────────────────────────────

test('#418 AC-5: COMPONENTS.md zeigt "options" als primäre Segmented-Prop', () => {
	// Der Katalog-Eintrag für Segmented muss "options" als erste/primäre Prop zeigen
	const segLine = catalogMd.split('\n').find(l => l.includes('<Segmented>') || l.includes('Segmented'));
	assert.ok(segLine, 'Segmented-Eintrag in COMPONENTS.md nicht gefunden');
	const optsIdx    = segLine.indexOf('options');
	const itemsIdx   = segLine.indexOf('items');
	assert.ok(optsIdx !== -1, '"options" fehlt im Segmented-Katalogeintrag');
	assert.ok(
		optsIdx < itemsIdx || itemsIdx === -1,
		'"options" muss als primäre API vor "items" im Katalogeintrag stehen'
	);
});
