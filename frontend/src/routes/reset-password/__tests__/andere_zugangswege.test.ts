// Issue #2961 (ADR-0115): die Seite „Passwort zurücksetzen" bietet „Alle anderen
// Zugangswege entfernen" an, standardmaessig aktiv. Die Action laeuft ECHT; nur
// die globale fetch-Funktion nimmt den Aufruf an die Go-API entgegen.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/routes/reset-password/__tests__/andere_zugangswege.test.ts

import { test, after } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../../../..');

register(
	pathToFileURL(path.join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

const { actions } = await import(pathToFileURL(path.join(FRONTEND, 'src/routes/reset-password/+page.server.ts')).href);

let gesendet: Record<string, unknown> | null = null;
const echterFetch = globalThis.fetch;
globalThis.fetch = async (_url: unknown, init?: RequestInit) => {
	gesendet = JSON.parse(String(init?.body ?? '{}'));
	return new Response('{"status":"ok"}', { status: 200, headers: { 'Content-Type': 'application/json' } });
};
after(() => {
	globalThis.fetch = echterFetch;
});

async function einreichen(felder: Record<string, string>): Promise<Record<string, unknown>> {
	gesendet = null;
	const form = new FormData();
	form.set('username', 'anna');
	form.set('token', 'abc123');
	form.set('new_password', 'neues-passwort-1');
	for (const [k, v] of Object.entries(felder)) form.set(k, v);
	await actions.default({ request: new Request('http://localhost/reset-password', { method: 'POST', body: form }), locals: { lang: 'de' } } as never);
	assert.ok(gesendet, 'die Action hat die Go-API nicht aufgerufen');
	return gesendet;
}

test('angehakt (Vorgabe): andere Zugangswege werden entfernt', async () => {
	const body = await einreichen({ andere_zugangswege_gewaehlt: '1', remove_other_access: '1' });
	assert.equal(body.remove_other_access, true);
});

test('abgewaehlt: Passkeys und Google-Verknuepfung bleiben', async () => {
	const body = await einreichen({ andere_zugangswege_gewaehlt: '1' });
	assert.equal(body.remove_other_access, false);
});

test('ohne Auswahl im Formular gilt die Vorgabe: entfernen', async () => {
	const body = await einreichen({});
	assert.equal(body.remove_other_access, true);
});
