// Bug #555 — addModeHint wird bei Etappen-Wechsel nicht zurückgesetzt.
//
// Root Cause: handleStageActivate() setzt activeWaypointId = null,
// vergisst aber addModeHint = false.
//
// Source-Inspection-Tests (kein DOM-Rendering, keine Mocks).
// Methodik: node:test + readFileSync — prüft Datei-Invarianten.
//
// Ausführen:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/edit/bug_555_addmodehint_reset.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const EDIT_STAGES_PANEL = join(here, 'EditStagesPanelNew.svelte');

function extractFunction(src: string, fnName: string): string {
	const start = src.indexOf(`function ${fnName}`);
	if (start === -1) return '';
	// Einfaches Brace-Matching: ab dem ersten '{' bis zum schließenden '}'
	let depth = 0;
	let inFn = false;
	let end = start;
	for (let i = start; i < src.length; i++) {
		if (src[i] === '{') { depth++; inFn = true; }
		else if (src[i] === '}') { depth--; }
		if (inFn && depth === 0) { end = i + 1; break; }
	}
	return src.slice(start, end);
}

// ────────────────────────────────────────────────────────────────────────────
// AC-1: Etappen-Wechsel blendet addModeHint aus
// ────────────────────────────────────────────────────────────────────────────

describe('#555 handleStageActivate setzt addModeHint zurück', () => {
	test('AC-1: handleStageActivate enthält addModeHint = false', () => {
		const src = readFileSync(EDIT_STAGES_PANEL, 'utf-8');
		const fn = extractFunction(src, 'handleStageActivate');
		assert.ok(
			fn.length > 0,
			'handleStageActivate muss in EditStagesPanelNew.svelte existieren'
		);
		assert.ok(
			/addModeHint\s*=\s*false/.test(fn),
			'handleStageActivate muss addModeHint = false setzen, tut es aber nicht.\n' +
			`Gefundener Funktionsblock:\n${fn}`
		);
	});

	// ────────────────────────────────────────────────────────────────────────
	// AC-2: Kein ungewollter Reset — addModeHint wird nur in handleStageActivate
	// zurückgesetzt, nicht bei handleWaypointActivate (andere Funktion)
	// ────────────────────────────────────────────────────────────────────────

	test('AC-2: handleStageActivate enthält Guard gegen Selbst-Selektion', () => {
		const src = readFileSync(EDIT_STAGES_PANEL, 'utf-8');
		const fn = extractFunction(src, 'handleStageActivate');
		assert.ok(
			/if\s*\(\s*stageId\s*===\s*activeStageId\s*\)\s*return/.test(fn),
			'handleStageActivate muss bei Selbst-Selektion früh returnen (Guard), ' +
			'damit addModeHint nicht versehentlich gelöscht wird.\n' +
			`Gefundener Funktionsblock:\n${fn}`
		);
	});

	// ────────────────────────────────────────────────────────────────────────
	// AC-3: addModeHint-State ist vorhanden und korrekt initialisiert
	// ────────────────────────────────────────────────────────────────────────

	test('AC-3: addModeHint ist mit false initialisiert', () => {
		const src = readFileSync(EDIT_STAGES_PANEL, 'utf-8');
		assert.ok(
			/let\s+addModeHint\s*=\s*\$state\(false\)/.test(src),
			'addModeHint muss als $state(false) deklariert sein'
		);
	});
});
