// TDD RED — Onboarding S2, AC-16: der Aufruf-Knopf fuer Ortsvergleiche fuehrt
// ohne angefangenen Vergleich auf /compare/new, mit angefangenem auf dessen Hub.
// Spec docs/specs/modules/onboarding_willkommen_checkliste.md.
//
// Vertrag: die Funktion zieht aus +page.svelte:104 als reiner Export um nach
//   frontend/src/routes/_home/compareCta.ts
//   export function buildCompareCtaHref(firstIncomplete: ComparePreset | null): string
// Heute ist sie eine Closure ohne Parameter (liest firstIncomplete aus der Seite);
// als reine Funktion wird genau dieser Wert zum Parameter. Die berechnete
// Schrittnummer floss schon heute nicht ins Ziel ein und entfaellt.
// +page.svelte importiert sie von dort (Verdrahtung unten, doc-compliance).
//
//   cd frontend && npm test -- src/routes/_home/__tests__/compare_cta_ziel.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

// Pfadregel #1409: Pruefling relativ zur Testdatei.
const HERE = path.dirname(fileURLToPath(import.meta.url));
const MODUL = path.resolve(HERE, '..', 'compareCta.ts');
const SEITE = path.resolve(HERE, '..', '..', '+page.svelte');

const mod: Record<string, unknown> = await import(pathToFileURL(MODUL).href).catch(() => ({}));

function ziel(firstIncomplete: Record<string, unknown> | null): string {
	assert.equal(
		typeof mod.buildCompareCtaHref,
		'function',
		'frontend/src/routes/_home/compareCta.ts exportiert keine Funktion buildCompareCtaHref'
	);
	return (mod.buildCompareCtaHref as (p: unknown) => string)(firstIncomplete);
}

const angefangen = { id: 'cmp-42', name: 'Entwurf', location_ids: [], schedule: 'daily', display_config: {} };

describe('AC-16: buildCompareCtaHref', () => {
	test('kein angefangener Ortsvergleich => /compare/new (nicht die Liste /compare)', () => {
		assert.equal(ziel(null), '/compare/new');
	});
	test('angefangener Ortsvergleich => dessen Hub /compare/<id>', () => {
		assert.equal(ziel(angefangen), '/compare/cmp-42');
	});
	test('Wächter: das Ziel haengt an der id, nicht an einem festen Wert', () => {
		assert.equal(ziel({ ...angefangen, id: 'cmp-7' }), '/compare/cmp-7');
	});
});

// doc-compliance-test
test('AC-16: +page.svelte nutzt den Export aus _home/compareCta statt einer eigenen Kopie', () => {
	assert.ok(existsSync(SEITE));
	const src = readFileSync(SEITE, 'utf-8');
	assert.match(src, /import\s*\{[^}]*\bbuildCompareCtaHref\b[^}]*\}\s*from\s*['"]\.\/_home\/compareCta(\.js|\.ts)?['"]/);
	assert.doesNotMatch(src, /function\s+buildCompareCtaHref\s*\(/, 'eigene Funktionskopie in +page.svelte');
});
