// TDD: Issue #1006 — Login-Rückleitung nur bei relativem Pfad (kein Open-Redirect).
//
// Spec: docs/specs/modules/issue_1010_1006_stille_fehler.md (AC-4)
//
// Ausfuehren:
//   cd frontend && node --experimental-strip-types --test src/lib/utils/safeRedirect.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { safeRedirectPath } from './safeRedirect.ts';

test('AC-4: relativer Pfad wird uebernommen', () => {
	assert.equal(safeRedirectPath('/trips/abc?tab=stages'), '/trips/abc?tab=stages');
});

test('AC-4: fehlender Wert faellt auf Startseite zurueck', () => {
	assert.equal(safeRedirectPath(null), '/');
	assert.equal(safeRedirectPath(undefined), '/');
	assert.equal(safeRedirectPath(''), '/');
});

test('AC-4: protokollrelativer //-Pfad (Open-Redirect) wird abgelehnt', () => {
	assert.equal(safeRedirectPath('//evil.example.com'), '/');
});

test('AC-4: absolute externe URL wird abgelehnt', () => {
	assert.equal(safeRedirectPath('https://evil.example.com'), '/');
	assert.equal(safeRedirectPath('evil.example.com'), '/');
});

// Adversary-Finding F001 im Bündel #1010/#1006 (CRITICAL): Backslash-Varianten, die der Browser
// per WHATWG-URL-Normalisierung zu einer externen URL auflöst — '/\evil.com'
// wird de facto wie '//evil.com' behandelt, bestand aber die reine '//'-Blacklist.
test('AC-4/F001: Backslash-Open-Redirect-Payloads werden abgelehnt', () => {
	assert.equal(safeRedirectPath('/\\evil.com'), '/');
	assert.equal(safeRedirectPath('/\\\\evil.com'), '/');
	assert.equal(safeRedirectPath('/\t/\\evil.com'), '/'); // echtes Tab-Zeichen
	assert.equal(safeRedirectPath('/\n\\evil.com'), '/'); // echtes Newline-Zeichen
});

// Bewusste Härte: ein literaler Backslash im Query-Teil (z.B. aus einem
// %5C-encodierten Wert, der von searchParams.get() bereits dekodiert wurde)
// wird ebenfalls abgelehnt — legitime interne Pfade enthalten nie ein '\'.
test('AC-4/F001: literaler Backslash im Query-Teil wird abgelehnt', () => {
	assert.equal(safeRedirectPath('/trips/abc?x=a\\b'), '/');
});
