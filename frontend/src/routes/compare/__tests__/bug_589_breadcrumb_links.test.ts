// TDD RED: Bug #589 — Compare-Detail Breadcrumb nicht anklickbar
//
// Spec: docs/specs/modules/bug_589_compare_breadcrumb_links.md
//
// Source-Inspection-Tests: lesen echte .svelte-Quelldateien und prüfen,
// dass der Breadcrumb navigierbare Links enthält. Kein Browser, keine Mocks.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test src/routes/compare/__tests__/bug_589_breadcrumb_links.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';

const SRC = fileURLToPath(new URL('../../..', import.meta.url)); // -> frontend/src/

function read(rel: string): string {
	return readFileSync(join(SRC, rel), 'utf8');
}

const PAGE = 'routes/compare/[id]/+page.svelte';

test('AC-1: "ORTS-VERGLEICHE" ist ein Link auf /compare (Desktop-Breadcrumb)', () => {
	const src = read(PAGE);
	assert.ok(
		/<a[^>]+href="\/compare"[^>]*>\s*ORTS-VERGLEICHE\s*<\/a>/.test(src),
		'ORTS-VERGLEICHE muss als <a href="/compare">ORTS-VERGLEICHE</a> im Desktop-Breadcrumb erscheinen'
	);
});

test('AC-2: "WORKSPACE" ist ein Link auf /', () => {
	const src = read(PAGE);
	const hasWorkspaceLink =
		src.includes('href="/"') ||
		src.match(/<a[^>]+href="\/"[^>]*>\s*WORKSPACE\s*<\/a>/) !== null;
	assert.ok(
		hasWorkspaceLink,
		'Kein <a href="/"> für WORKSPACE in compare/[id]/+page.svelte — "WORKSPACE" muss auf / verlinken'
	);
});

test('AC-3: "DETAIL" ist kein Link — statischer Text', () => {
	const src = read(PAGE);
	assert.ok(
		!src.match(/<a[^>]*>\s*DETAIL\s*<\/a>/i),
		'"DETAIL" darf kein <a>-Element sein — es ist die aktuelle Seite'
	);
});

test('AC-4: Breadcrumb-Links haben visuelles Hover-Feedback', () => {
	const src = read(PAGE);
	const hasHoverStyle =
		src.includes('hover:underline') ||
		(src.includes('.breadcrumb-link:hover') && src.includes('text-decoration: underline'));
	assert.ok(
		hasHoverStyle,
		'Breadcrumb-Links benötigen Hover-Feedback (.breadcrumb-link:hover mit text-decoration: underline)'
	);
});
