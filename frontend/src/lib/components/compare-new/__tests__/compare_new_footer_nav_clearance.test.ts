// TDD RED — Issue #2277 Scheibe S2b: der EditorStickyFooter in /compare/new
// reserviert keinen Leerraum mehr für die (dort nun ausgeblendete) BottomNav.
//
// Spec: docs/specs/modules/fix_2277_s2b_mobile_rahmen_angleichung.md (AC-7)
//
// Source-Inspection (Vorbild compareNewResponsiveSwitch.test.ts): für
// CompareNewEditor.svelte existiert kein SSR-Harness (kein Stub für den
// compare-wizard-state-Context). Reine Konfigurations-Anwesenheitsprüfung am
// konkreten Mount-Tag — das Verhalten von `navClearance` selbst ist durch die
// unveränderte EditorStickyFooter.svelte (`class:has-nav={navClearance}`) belegt.
//
// RED HEUTE: der Mount setzt kein `navClearance` (Default true).
//
// Ausführen:
//   cd frontend && npm test -- src/lib/components/compare-new/__tests__/compare_new_footer_nav_clearance.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const TARGET_FILE = join(here, '..', 'CompareNewEditor.svelte');

function footerMountTags(src: string): string[] {
	return [...src.matchAll(/<EditorStickyFooter\b[^>]*>/g)].map((m) => m[0]);
}

test('AC-7: der EditorStickyFooter-Mount (testid="cm-mobile-cta") trägt navClearance={false}', () => {
	const tags = footerMountTags(readFileSync(TARGET_FILE, 'utf-8'));
	const cta = tags.filter((t) => /\btestid="cm-mobile-cta"/.test(t));
	assert.equal(
		cta.length,
		1,
		`Messaufbau kaputt: erwartet genau einen <EditorStickyFooter testid="cm-mobile-cta">, gefunden ${cta.length}.`
	);
	assert.match(
		cta[0],
		/\bnavClearance=\{false\}/,
		`AC-7 FAIL: der Compare-Footer reserviert weiter Platz für die BottomNav — navClearance={false} fehlt am Mount: ${cta[0]}`
	);
});
