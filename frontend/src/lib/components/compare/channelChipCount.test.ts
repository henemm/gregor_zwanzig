// TDD — Issue #1097 (angepasst #1232 Scheibe 3a): Layout-Tab EMAIL zeigt
// Orts-Anzahl statt Budget-Zahl.
//
// Reine Verhaltenstests auf `channelChipCount` (KEIN Mock, KEINE
// Dateiinhalt-Prüfung). CHANNEL_COL_BUDGET.email ist seit #1232 Scheibe 3a
// als `Infinity` modelliert (statt des Literal-Werts `99` — Kappungs-
// Konsolidierung auf die einzige Quelle CHANNEL_COL_BUDGET in
// metricsEditor.ts). Verhalten identisch: channelChipCount(Infinity, N) === N
// === channelChipCount(99, N) für jede praktisch vorkommende Orts-Anzahl
// N < 99. Der Fix (#1097) deckelt das Budget auf preset.location_ids.length.
//
// Ausführung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/compare/channelChipCount.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { channelChipCount } from './channelChipCount.ts';

describe('channelChipCount — Bug-Reproduktion #1097 (EMAIL-Budget = Infinity seit #1232)', () => {
	test('EMAIL-Budget Infinity bei 8 Orten → 8 Chips (nicht "unendlich viele")', () => {
		assert.equal(channelChipCount(Infinity, 8), 8);
	});

	test('TELEGRAM-Budget 8 bei 8 Orten → 8 Chips (Zufallstreffer im Bug, bleibt korrekt)', () => {
		assert.equal(channelChipCount(8, 8), 8);
	});
});

describe('channelChipCount — Budget-Deckelung bei weniger Orten (N=3)', () => {
	test('EMAIL-Budget Infinity bei 3 Orten → 3 Chips', () => {
		assert.equal(channelChipCount(Infinity, 3), 3);
	});

	test('TELEGRAM-Budget 8 bei 3 Orten → 3 Chips (vor dem Fix fälschlich 8)', () => {
		assert.equal(channelChipCount(8, 3), 3);
	});
});

describe('channelChipCount — SMS-Sonderfall bleibt unverändert', () => {
	test('SMS-Budget 0 bei 8 Orten → 0 (min(0, N) === 0 → "flach · ohne Spalten")', () => {
		assert.equal(channelChipCount(0, 8), 0);
	});

	test('SMS-Budget 0 bei 0 Orten → 0', () => {
		assert.equal(channelChipCount(0, 0), 0);
	});
});

describe('channelChipCount — Deckelung nur nach unten (kein Hochskalieren)', () => {
	test('Budget kleiner als Orts-Anzahl bleibt hartes Limit (TELEGRAM bei 20 Orten → 8)', () => {
		assert.equal(channelChipCount(8, 20), 8);
	});
});
