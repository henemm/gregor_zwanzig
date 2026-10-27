// TDD RED — SMS-/Premium-SMS-Tageskontingent im Account sichtbar (S4b,
// Sammel-Issue #2153, Einzel-Issue #2412, Epic #2138).
// Spec: docs/specs/modules/sms_daily_usage_anzeige.md — AC-2, AC-7.
//
// `smsDailyUsageHelpers.ts` existiert in der RED-Phase noch NICHT -> der
// Import wirft einen Modul-Resolve-Fehler und alle Tests scheitern.
//
// Architektur: Pure-Funktion in `.ts`, testbar via node:test (Muster
// premiumSmsLinkCodeHelpers.ts/.test.ts) — `+page.svelte` verdrahtet sie nur.
//
// Ausfuehrung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/utils/smsDailyUsageHelpers.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { shouldShowSmsUsageRow } from './smsDailyUsageHelpers.ts';

// =========================================================================
// AC-2 / AC-7: Sichtbarkeit einer Kontingent-Zeile folgt ausschliesslich
// `limit > 0` -- dieselbe Regel fuer SMS und Premium-SMS.
// =========================================================================

describe('AC-2/AC-7: shouldShowSmsUsageRow — Zeile nur bei limit > 0', () => {
	test('limit=10 (Standard-Tier, SMS erlaubt) → true', () => {
		assert.equal(shouldShowSmsUsageRow(10), true);
	});

	test('limit=15 (Premium-Tier, Premium-SMS erlaubt) → true', () => {
		assert.equal(shouldShowSmsUsageRow(15), true);
	});

	test('limit=0 (Free-Tier bzw. kein Premium-SMS-Zugriff) → false', () => {
		assert.equal(shouldShowSmsUsageRow(0), false);
	});

	test('limit=undefined (Antwort fehlt/Feld fehlt) → false', () => {
		assert.equal(shouldShowSmsUsageRow(undefined), false);
	});
});
