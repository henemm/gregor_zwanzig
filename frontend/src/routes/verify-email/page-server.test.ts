// Issue #1219 (Scheibe 2b) — Bestätigungsseite /verify-email
//
// Spec: docs/specs/modules/fix_1219_verify_flow_2b.md
//
// AC-1: `load({url})` liest user/token aus der Query, mock-frei — echter
// URL-Objekt-Aufruf, kein Mock des SvelteKit-Runtime-Kontexts.
//
// AC-4 (Source-Sentinel, doc-compliance-test): +page.server.ts postet an
// /api/auth/verify-email und mappt `token expired` bzw. den ungültig-Zweig
// auf die jeweilige deutsche Fehlermeldung.
//
// Ausführen:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/routes/verify-email/page-server.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

import { load } from './+page.server.ts';

const __dirname = dirname(fileURLToPath(import.meta.url));

test('AC-1: load liest user/token aus der Query', async () => {
	// GIVEN: eine URL mit user- und token-Query-Parametern
	// WHEN: load({url}) aufgerufen wird
	// THEN: werden beide Werte 1:1 zurückgegeben
	const result = await load({ url: new URL('https://x.de/verify-email?user=alice&token=abc123') } as any);
	assert.deepEqual(result, { user: 'alice', token: 'abc123' });
});

test('AC-1: load liefert leere Strings ohne Query-Parameter', async () => {
	// GIVEN: eine URL ohne user/token
	// WHEN: load({url}) aufgerufen wird
	// THEN: werden leere Strings zurückgegeben (kein undefined/null)
	const result = await load({ url: new URL('https://x.de/verify-email') } as any);
	assert.deepEqual(result, { user: '', token: '' });
});

// doc-compliance-test
test('AC-4: +page.server.ts postet an /api/auth/verify-email und mappt token-expired vs. invalid', () => {
	// GIVEN: der Source-Text von +page.server.ts
	// WHEN: nach dem Endpoint und der Fehler-Mapping-Logik gesucht wird
	// THEN: kommt der Endpoint-Pfad vor, und beide Fehlermeldungs-Zweige existieren
	const src = readFileSync(join(__dirname, '+page.server.ts'), 'utf-8');
	assert.ok(src.includes('/api/auth/verify-email'), 'Endpoint /api/auth/verify-email fehlt');
	assert.ok(src.includes('token expired'), "Fehler-Mapping für 'token expired' fehlt");
	assert.ok(
		src.includes('ungültig oder wurde bereits verwendet'),
		'Fehler-Mapping für den ungültig-Zweig fehlt'
	);
});
