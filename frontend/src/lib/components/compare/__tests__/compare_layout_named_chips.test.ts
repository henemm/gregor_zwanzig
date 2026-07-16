// TDD RED — Issue #1267: CompareTabs.svelte übergibt echte Ortsnamen an
// CompareLayoutRow statt einer reinen Zahl (channelChipCount(...) direkt
// als cols-Prop).
//
// Source-Inspection-Test (KEIN Mock, KEIN jsdom-Mount — Projekt-Idiom, siehe
// compare_editor_layout_tab_wiring.test.ts).
//
// Spec: docs/specs/modules/issue_1267_compare_layout_row_named_chips.md
//
// RED-Erwartung (vor Implementierung): beide Tests FAIL, weil
// CompareTabs.svelte cols={channelChipCount(...)} noch als rohe Zahl an
// beide CompareLayoutRow-Call-Sites (mobile dense + Desktop) übergibt.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/compare_layout_named_chips.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const TABS_FILE = join(here, '..', 'CompareTabs.svelte');
const src = () => readFileSync(TABS_FILE, 'utf-8');

test('#1267 AC-1/AC-2: CompareLayoutRow-Call-Sites übergeben kein rohes channelChipCount(...) mehr als cols', () => {
	const s = src();
	const OLD_PATTERN = /cols=\{channelChipCount\(CHANNEL_COLS\[ch\], preset\.location_ids\.length\)\}/;
	assert.ok(
		!OLD_PATTERN.test(s),
		'CompareTabs.svelte: cols wird weiterhin als rohe Zahl aus channelChipCount(...) übergeben — muss ein Namens-Array (Ortsnamen) sein'
	);
});

test('#1267 AC-1: beide CompareLayoutRow-Call-Sites übergeben einen Namens-Ausdruck statt einer rohen channelChipCount-Zahl', () => {
	const s = src();
	const layoutRowCallSites = [...s.matchAll(/<CompareLayoutRow[^>]*cols=\{([^}]+)\}/g)];
	assert.equal(
		layoutRowCallSites.length,
		2,
		'Erwartet genau 2 CompareLayoutRow-Call-Sites (mobile dense + Desktop) in CompareTabs.svelte'
	);
	for (const m of layoutRowCallSites) {
		const expr = m[1].trim();
		assert.ok(
			!/^channelChipCount\(/.test(expr),
			`cols-Ausdruck "${expr}" ist weiterhin eine rohe channelChipCount(...)-Zahl statt eines Namens-Arrays`
		);
	}
});
