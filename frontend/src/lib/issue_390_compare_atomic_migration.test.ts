// TDD RED: Issue #390 — Compare-Screen: Migration auf Atomic-Bibliothek (Epic #368 Phase 2, 5/6)
//
// Spec:  docs/specs/modules/issue_390_compare_atomic_migration.md
//
// Source-Inspection-Tests: lesen echte .svelte-Quelldateien und prüfen,
// dass die Migration durchgeführt wurde. Kein Browser, keine Mocks.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test src/lib/issue_390_compare_atomic_migration.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';

const SRC = fileURLToPath(new URL('..', import.meta.url)); // -> frontend/src/

function read(rel: string): string {
	return readFileSync(join(SRC, rel), 'utf8');
}

test('AC-1a: compare/+page.svelte importiert Pill aus ui/pill', () => {
	const src = read('routes/compare/+page.svelte');
	assert.ok(
		src.includes("from '$lib/components/ui/pill/index.js'") ||
			src.includes("from '$lib/components/atoms/index.js'") ||
			src.includes("from '$lib/components/atoms'"),
		'Pill-Import fehlt in routes/compare/+page.svelte'
	);
});

// Obsolet durch Issue #439: /compare ist Tabellen-Übersicht, kein Mobile-Chip-Picker mehr.
test.skip('AC-1b: compare/+page.svelte hat aria-pressed auf dem Mobile-Chip-Button (obsolet durch #439)', () => {
	const src = read('routes/compare/+page.svelte');
	assert.ok(
		src.includes('aria-pressed'),
		'aria-pressed fehlt in routes/compare/+page.svelte — Mobile-Chips brauchen dieses ARIA-Attribut'
	);
});

test('AC-3: GroupSection.svelte enthält profileSignature(loc.activity_profile) für Location-Items', () => {
	const src = read('lib/components/compare/GroupSection.svelte');
	assert.ok(
		src.includes('profileSignature(loc.activity_profile)'),
		'profileSignature(loc.activity_profile) fehlt in GroupSection.svelte — Profil-Dot pro Location-Item nicht migriert'
	);
});

test('AC-5a: compare/+page.svelte enthält keine rohen Chip-Klassen mehr (rounded-full border border-border bg-muted)', () => {
	const src = read('routes/compare/+page.svelte');
	assert.ok(
		!src.includes('rounded-full border border-border bg-muted'),
		'Inline-Chip-Klasse "rounded-full border border-border bg-muted" noch in +page.svelte vorhanden — bitte entfernen'
	);
});
