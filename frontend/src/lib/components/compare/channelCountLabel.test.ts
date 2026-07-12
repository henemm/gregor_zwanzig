// Design-Fidelity 2026-07 Fix 1 — Singular/Plural-Weiche für die Kanal-Anzeige.
//
// Reiner Verhaltenstest auf `channelCountLabel` (KEIN Mock). Vorbild:
// CompareTabs.svelte:248 zeigte bereits korrekt "1 Kanal"/"N Kanäle" —
// compare/[id]/+page.svelte:204 zeigte fälschlich immer "Kanäle" (auch bei
// n=1). Der Helper konsolidiert beide Stellen auf eine Quelle.
//
// Ausführung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/compare/channelCountLabel.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { channelCountLabel } from './subscriptionHelpers.ts';

describe('channelCountLabel', () => {
	test('0 Kanäle → "0 Kanäle" (Plural bleibt bei 0)', () => {
		assert.equal(channelCountLabel(0), '0 Kanäle');
	});

	test('1 Kanal → "1 Kanal" (Singular)', () => {
		assert.equal(channelCountLabel(1), '1 Kanal');
	});

	test('2 Kanäle → "2 Kanäle" (Plural)', () => {
		assert.equal(channelCountLabel(2), '2 Kanäle');
	});
});
