// TDD RED — Epic #1301 Scheibe F3 (#989): Offscreen-Ghost-Elemente auf
// /compare/new durch das etablierte Trip-Responsive-Muster #661 ersetzen.
// SPEC: docs/specs/modules/feat_1301_f3_deadcode_offscreen.md (AC-5, AC-6, AC-7)
//
// Prüft via Source-Inspection (node:test + readFileSync), dass
// CompareNewEditor.svelte den Desktop-Block auf ≤899px per `display: none
// !important` versteckt (statt per position:fixed/-9999px-Offscreen) und ein
// eigenständiges, State-gebundenes Mobile-Namensfeld besitzt.
// Referenzmuster: frontend/src/lib/components/trip-new/TripNewEditor.svelte
// (:1039-1061, .tn-desktop/.tn-mobile mit display:none !important).
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/compare-new/__tests__/compareNewResponsiveSwitch.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
// compare-new/ = __tests__/..
const TARGET_FILE = join(here, '..', 'CompareNewEditor.svelte');

function readTarget(): string {
	return readFileSync(TARGET_FILE, 'utf-8');
}

function extractBlock(src: string, startMarker: string, endMarker: string): string {
	const startIdx = src.indexOf(startMarker);
	if (startIdx === -1) return '';
	const endIdx = src.indexOf(endMarker, startIdx);
	if (endIdx === -1) return '';
	return src.slice(startIdx, endIdx + endMarker.length);
}

// =============================================================================
// AC-5: Kein Offscreen-Muster mehr; .cm-desktop wird auf ≤899px per
// display:none !important versteckt (Trip-Muster #661)
// =============================================================================

test('AC-5: CompareNewEditor.svelte enthält keine Offscreen-Koordinaten (-9999px) mehr', () => {
	const src = readTarget();
	assert.strictEqual(
		/-9999px/.test(src),
		false,
		'CompareNewEditor.svelte darf das Offscreen-Muster (top/left: -9999px) für .cm-desktop nicht mehr enthalten — Trip-Muster #661 verlangt display:none statt Verschiebung'
	);
});

test('AC-5: .cm-desktop wird im @media (max-width: 899px)-Block per display:none !important versteckt (Trip-Muster #661, Referenz TripNewEditor.svelte:1050-1052)', () => {
	const src = readTarget();
	assert.ok(
		/\.cm-desktop\s*\{\s*display:\s*none\s*!important;\s*\}/.test(src),
		'.cm-desktop muss innerhalb @media (max-width: 899px) als reine display:none-Regel vorliegen (kein position:fixed/-9999px-Offscreen mehr)'
	);
});

// =============================================================================
// AC-6: eigenständiges Mobile-Namensfeld, gebunden auf denselben State
// =============================================================================

test('AC-6: .cm-mobile-Block enthält ein eigenständiges Namensfeld data-testid="compare-editor-name-mobile" gebunden auf wiz.name', () => {
	const src = readTarget();
	const mobileBlock = extractBlock(src, '<div class="cm-mobile"', '<!-- /.cm-mobile -->');
	assert.notStrictEqual(
		mobileBlock,
		'',
		'.cm-mobile-Block (<div class="cm-mobile" ...> ... <!-- /.cm-mobile -->) nicht gefunden — Marker haben sich verschoben?'
	);
	const inputRe =
		/<input\b(?=[^>]*data-testid="compare-editor-name-mobile")(?=[^>]*bind:value=\{wiz\.name\})[^>]*\/?>/;
	assert.ok(
		inputRe.test(mobileBlock),
		'.cm-mobile-Block muss ein <input data-testid="compare-editor-name-mobile" bind:value={wiz.name} ...> enthalten (Vorbild TripNewEditor.svelte:797-799, Desktop-Pendant compare-editor-name bleibt unverändert)'
	);
});

// =============================================================================
// AC-7: Desktop-Verhalten unverändert — .cm-mobile bleibt außerhalb der
// Media-Query per display:none !important versteckt
// =============================================================================

test('AC-7: .cm-mobile bleibt außerhalb des Media-Query per display: none !important versteckt (Desktop-Basisverhalten unverändert)', () => {
	const src = readTarget();
	assert.ok(
		/\.cm-mobile\s*\{\s*display:\s*none\s*!important;\s*\}/.test(src),
		'.cm-mobile muss als Basis-Regel (außerhalb @media) display: none !important tragen — unverändertes Vorher-Verhalten für Desktop-Viewports'
	);
});
