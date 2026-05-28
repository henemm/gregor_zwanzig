// TDD RED — Issue #431: OutputLayoutEditor (trip-agnostischer geteilter Editor).
// SPEC: docs/specs/modules/issue_430_431_wizard_layout_step.md (AC-6, AC-8).
// TEST-MANIFEST: docs/specs/tests/issue_430_431_wizard_layout_step_tests.md.
//
// Diese Tests prüfen per Source-Inspection, dass der Editor:
//   - existiert
//   - KEINE API-Calls macht (trip-agnostisch)
//   - KEINE trip-Prop hat
//   - einen SMS-Sonderzweig im Template enthält (Listen-Mode statt Bucket-Editor)
//
// In der RED-Phase fehlt die Datei → existsSync() schlägt fehl.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/shared/__tests__/OutputLayoutEditor.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const EDITOR = join(here, '..', 'OutputLayoutEditor.svelte');

function readEditor(): string {
	return readFileSync(EDITOR, 'utf-8');
}

// =============================================================================
// AC-6: Datei existiert
// =============================================================================

test('AC-6: OutputLayoutEditor.svelte existiert unter frontend/src/lib/components/shared/', () => {
	assert.ok(
		existsSync(EDITOR),
		`OutputLayoutEditor.svelte fehlt: ${EDITOR}`,
	);
});

// =============================================================================
// AC-6: trip-agnostisch — keine API-Calls
// =============================================================================

test('AC-6: OutputLayoutEditor enthält keine API-Imports oder fetch-Calls', () => {
	const src = readEditor();
	// Trip-agnostisch heißt: keine direkten API-Aufrufe. Catalog/Presets werden
	// als Props übergeben, nicht hier geladen.
	assert.ok(
		!src.includes("from '$lib/api'") && !src.includes('from "$lib/api"'),
		'OutputLayoutEditor darf nicht "from \\$lib/api" importieren — trip-agnostisch.',
	);
	assert.ok(
		!src.includes('api.get(') && !src.includes('api.post(') &&
			!src.includes('api.put(') && !src.includes('api.delete('),
		'OutputLayoutEditor darf keine api.{get,post,put,delete}-Aufrufe machen.',
	);
	assert.ok(
		!/\bfetch\s*\(/.test(src),
		'OutputLayoutEditor darf keine direkten fetch-Aufrufe enthalten.',
	);
});

// =============================================================================
// AC-6: keine trip-Prop
// =============================================================================

test('AC-6: OutputLayoutEditor Props enthalten keine trip-Prop', () => {
	const src = readEditor();
	// Wir suchen in den `<script>`-Props nach `trip:` oder `Trip`-Type.
	// Toleranz: das Wort "Trip" darf in Kommentaren vorkommen — wir prüfen nur
	// Prop-Deklarationen via einfacher Heuristik.
	const propsBlock = (src.match(/interface\s+Props[\s\S]*?\}/) || [''])[0];
	assert.ok(
		propsBlock.length > 0,
		'OutputLayoutEditor sollte ein Props-Interface deklarieren.',
	);
	assert.ok(
		!/\btrip\s*:/.test(propsBlock),
		'Props-Interface darf keine `trip:`-Property enthalten — trip-agnostisch.',
	);
	assert.ok(
		!/:\s*Trip\b/.test(propsBlock),
		'Props-Interface darf keinen Trip-Type verwenden — trip-agnostisch.',
	);
});

// =============================================================================
// AC-8: SMS-Sonderzweig im Template
// =============================================================================

test('AC-8: OutputLayoutEditor hat SMS-Conditional ({#if channel === \'sms\'})', () => {
	const src = readEditor();
	// Toleriert beide Quote-Stile.
	const hasSmsCond = /\{#if\s+channel\s*===\s*['"]sms['"]/.test(src);
	assert.ok(
		hasSmsCond,
		'OutputLayoutEditor sollte {#if channel === "sms"}-Branch enthalten (SMS-Listen-Mode statt Bucket-Tabelle).',
	);
});
