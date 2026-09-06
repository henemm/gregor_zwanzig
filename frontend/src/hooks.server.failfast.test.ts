// Issue #2139: Prueft die WIRK-Stelle des Session-Secret-Gates im Frontend —
// den Top-Level-Aufruf in hooks.server.ts. Der Unit-Test in
// src/lib/sessionSecretGate.test.ts prueft nur die Funktion selbst; wird der
// Aufruf aus hooks.server.ts entfernt, bleibt er gruen.
//
// Geladen wird das echte Modul per import(); der Query-String erzwingt eine
// frische Auswertung je Fall (ESM wertet jede URL nur einmal aus).
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs \
//     --experimental-strip-types --test src/hooks.server.failfast.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';

register('../test-env-dynamic-private-stub-hooks.mjs', import.meta.url);

test('hooks.server.ts: Import wirft beim Default-Secret', async () => {
	process.env.GZ_SESSION_SECRET = 'dev-secret-change-me';
	await assert.rejects(() => import('./hooks.server.ts?case=default-secret'));
});

test('hooks.server.ts: Import wirft ohne gesetztes Secret', async () => {
	delete process.env.GZ_SESSION_SECRET;
	await assert.rejects(() => import('./hooks.server.ts?case=missing-secret'));
});

test('hooks.server.ts: Import gelingt mit gueltigem Secret', async () => {
	process.env.GZ_SESSION_SECRET = 'a-genuinely-random-forty-char-secret-12';
	const mod = await import('./hooks.server.ts?case=valid-secret');
	assert.equal(typeof mod.handle, 'function');
});
