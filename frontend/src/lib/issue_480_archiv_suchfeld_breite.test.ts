// TDD RED: Issue #480 — Archiv Suchfeld-Breite
//
// Spec:  docs/specs/modules/issue_480_archiv_suchfeld_breite.md
//
// Source-Inspection-Tests: liest echte .svelte-Quelldatei und prüft das Layout.
// Kein Browser, keine Mocks.
//
// RED-Erwartungen (vor der Implementierung):
//   AC-1: Such-Wrapper hat noch flex:0 0 380px → FAIL (flex:1 fehlt)
//   AC-2: Search-Wrapper enthält noch 380px-Fixierung → FAIL
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test src/lib/issue_480_archiv_suchfeld_breite.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';

const SRC = fileURLToPath(new URL('..', import.meta.url)); // -> frontend/src/

function read(rel: string): string {
	return readFileSync(join(SRC, rel), 'utf8');
}

// ---------------------------------------------------------------------------
// AC-1: Suchfeld-Wrapper nutzt flex:1 (wächst auf verfügbaren Raum)
// ---------------------------------------------------------------------------

test('AC-1: Suchfeld-Wrapper in archiv/+page.svelte hat position:relative;flex:1', () => {
	const src = read('routes/archiv/+page.svelte');
	// Der Such-Wrapper muss position:relative kombiniert mit flex:1 haben.
	// (flex:1 taucht auch in der accuracyBar auf — daher kombinierten Check nutzen.)
	assert.ok(
		src.includes('position:relative;flex:1') || src.includes('position: relative; flex: 1'),
		'Suchfeld-Wrapper hat kein position:relative;flex:1 — Suchfeld nimmt nicht die volle verfügbare Breite ein'
	);
});

// ---------------------------------------------------------------------------
// AC-2: Fixierte 380px-Breite ist entfernt
// ---------------------------------------------------------------------------

test('AC-2: Suchfeld-Wrapper in archiv/+page.svelte hat kein flex:0 0 380px mehr', () => {
	const src = read('routes/archiv/+page.svelte');
	assert.ok(
		!src.includes('flex:0 0 380px') && !src.includes('flex: 0 0 380px'),
		'Suchfeld-Wrapper hat noch flex:0 0 380px — fixierte Breite muss auf flex:1 geändert werden'
	);
});
