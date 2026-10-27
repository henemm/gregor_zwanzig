// TDD RED — Mengen-Quoten je Tier im Account sichtbar (S5, Issue #2482,
// Sammel-Issue #2153, Epic #2138).
// Spec: docs/specs/modules/mengen_quoten_je_tier.md — AC-13, AC-15.
//
// `mengenQuoteHelpers.ts` existiert in der RED-Phase noch NICHT -> der
// Import wirft einen Modul-Resolve-Fehler und alle Tests scheitern.
//
// Architektur: Pure-Funktionen in `.ts`, testbar via node:test (Muster
// smsDailyUsageHelpers.ts/.test.ts) — `+page.svelte` verdrahtet sie nur.
// Profil-Vertrag: `quota: {trips, compare_presets, locations}`, je Zahl
// oder `null` (= unbegrenzt, Admin/Ausnahme-Konto).
//
// Ausfuehrung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/utils/mengenQuoteHelpers.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { countActive, formatQuotaUsage } from './mengenQuoteHelpers.ts';

describe('AC-13: formatQuotaUsage — "x von N", unbegrenzt nur "x"', () => {
	test('2 von 3 (Free, Trips)', () => {
		assert.equal(formatQuotaUsage(2, 3), '2 von 3');
	});

	test('Grenze erreicht: 3 von 3', () => {
		assert.equal(formatQuotaUsage(3, 3), '3 von 3');
	});

	test('Bestand ueber der Grenze (Herabstufung): 6 von 3', () => {
		assert.equal(formatQuotaUsage(6, 3), '6 von 3');
	});

	test('unbegrenzt (null) → nur die Anzahl', () => {
		assert.equal(formatQuotaUsage(12, null), '12');
	});

	test('Feld fehlt (undefined) → nur die Anzahl, kein "von undefined"', () => {
		assert.equal(formatQuotaUsage(4, undefined), '4');
	});

	test('AC-15: kein anderer Begriff als Trip in der Ausgabe', () => {
		assert.doesNotMatch(formatQuotaUsage(2, 3), /tour/i);
	});
});

describe('AC-13: countActive — dieselbe Zaehlregel wie im Server (nur nicht archivierte)', () => {
	test('archivierte Eintraege zaehlen nicht', () => {
		const liste = [
			{ id: 'a' },
			{ id: 'b', archived_at: null },
			{ id: 'c', archived_at: '2026-09-01T10:00:00Z' },
		];
		assert.equal(countActive(liste), 2);
	});

	test('leere oder fehlende Liste → 0', () => {
		assert.equal(countActive([]), 0);
		assert.equal(countActive(undefined), 0);
	});
});
