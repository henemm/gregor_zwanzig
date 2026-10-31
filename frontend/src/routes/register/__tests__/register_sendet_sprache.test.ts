// Issue #2648 (i18n S3) — AC-5: die Registrierung uebernimmt die Sprache, die
// der Besucher gerade sah (`locals.lang`), als Feld `language` im Request an
// `POST /api/auth/register`. Echte Action; nur die globale fetch-Funktion
// (Netzgrenze zur Go-API) faengt den Request-Body ab (Muster aus
// register_einladung.test.ts).
// Spec: docs/specs/modules/i18n_s3_sprachumschalter_konto_2648.md
//
//   cd frontend && npm test -- src/routes/register/__tests__/register_sendet_sprache.test.ts

import { test, describe, after } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../../../..');
const base = pathToFileURL(FRONTEND + '/').href;

register(pathToFileURL(path.join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href, base);

const { actions } = (await import(
	pathToFileURL(path.join(FRONTEND, 'src/routes/register/+page.server.ts')).href
)) as any;

let koerper: Record<string, unknown>[] = [];
const echterFetch = globalThis.fetch;
globalThis.fetch = (async (url: any, init: any) => {
	if (String(url).endsWith('/api/auth/register')) koerper.push(JSON.parse(init.body));
	return new Response('{}', { status: 201, headers: { 'Content-Type': 'application/json' } });
}) as unknown as typeof fetch;
after(() => {
	globalThis.fetch = echterFetch;
});

async function registriere(lang: 'de' | 'en', invite?: string): Promise<Record<string, unknown>> {
	koerper = [];
	const body = new FormData();
	body.set('username', 'wanderer');
	body.set('email', 'w@example.org');
	body.set('password', 'geheim-genug');
	body.set('confirmPassword', 'geheim-genug');
	if (invite) body.set('invite', invite);
	try {
		await actions.default({
			request: new Request('http://localhost/register', { method: 'POST', body }),
			locals: { lang }
		});
	} catch (e) {
		// Erfolg leitet per redirect (Ausnahme) auf /login?registered=1.
		assert.equal((e as { location?: string }).location, '/login?registered=1');
	}
	assert.equal(koerper.length, 1, 'genau ein Register-Request erwartet');
	return koerper[0];
}

describe('AC-5: Registrierung sendet language aus locals.lang', () => {
	test('locals.lang = en ergibt "language":"en", uebrige Felder unveraendert', async () => {
		assert.deepEqual(await registriere('en'), {
			username: 'wanderer',
			password: 'geheim-genug',
			email: 'w@example.org',
			language: 'en'
		});
	});

	test('locals.lang = de ergibt "language":"de"', async () => {
		assert.equal((await registriere('de')).language, 'de');
	});

	test('Einladungstoken bleibt erhalten', async () => {
		assert.deepEqual(await registriere('en', 'tok/1'), {
			username: 'wanderer',
			password: 'geheim-genug',
			email: 'w@example.org',
			language: 'en',
			invite: 'tok/1'
		});
	});
});
