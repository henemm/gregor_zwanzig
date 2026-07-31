// TDD RED — Issue #1395 Scheibe S4: SaveIndicator.svelte hat noch keinen
// 'conflict'-Zweig.
// Spec: docs/specs/modules/issue_1395_s4_conflict_retry.md — AC-1/AC-4.
//
// Kein Rendering-Harness für Svelte-5-Runen im node:test-Setup — daher
// source-inspizierende Tests (Präzedenz:
// frontend/src/lib/components/shared/__tests__/weatherMetricsTabDayWindowSave.test.ts).

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const SAVE_INDICATOR = join(here, '..', 'SaveIndicator.svelte');
const src = readFileSync(SAVE_INDICATOR, 'utf-8');

/** Isoliert den `{:else if controller.state === '<value>'}`-Zweig bis zum
 *  nächsten `{:else`/`{/if}`. */
function stateBranchBlock(value: string): string {
	const marker = `state === '${value}'`;
	const start = src.indexOf(marker);
	assert.ok(start >= 0, `SaveIndicator.svelte: kein '${value}'-Zweig gefunden`);
	const blockStart = src.indexOf('}', start) + 1;
	const nextElse = src.indexOf('{:else', blockStart);
	const nextEndIf = src.indexOf('{/if}', blockStart);
	const end = nextElse >= 0 && (nextEndIf < 0 || nextElse < nextEndIf) ? nextElse : nextEndIf;
	assert.ok(end > blockStart, `SaveIndicator.svelte: Ende des '${value}'-Zweigs nicht gefunden`);
	return src.slice(blockStart, end);
}

describe('AC-1: der Konflikt-Zweig bietet einen Wiederholen-Knopf', () => {
	test('test_conflictBranch_rendersRetryButtonCallingRetryConflict', () => {
		const block = stateBranchBlock('conflict');

		assert.match(block, /<button\b/i, "der 'conflict'-Zweig muss ein <button>-Element rendern");
		assert.match(
			block,
			/retryConflict\(\)/,
			"der Klick-Handler des Knopfs muss controller.retryConflict() aufrufen"
		);
	});
});

describe('AC-4: der generische Fehler-Zweig bekommt KEINEN Wiederholen-Knopf', () => {
	test('test_errorBranch_hasNoRetryButton', () => {
		const block = stateBranchBlock('error');

		assert.ok(
			!/retryConflict\(\)/.test(block),
			"der 'error'-Zweig darf retryConflict() nicht aufrufen — ein Retry-Knopf wäre bei generischen Fehlern irreführend"
		);
	});
});
