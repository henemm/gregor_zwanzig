// Issue #2676 (i18n G2), AC-5 — Link-Pruefung auf der Seite „Passwort zurücksetzen".
// Spec: docs/specs/modules/i18n_g2_go_handler_auth_2676.md.
//
// Die Action laeuft ECHT; nur die globale fetch-Funktion liefert die neue Go-Antwort
// {"code": ...} (Fehlerobjekt aus WriteError). Die Zuordnung Code -> Hinweis wird real
// durchlaufen; keine Spiegelung der Logik im Test.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/routes/reset-password/__tests__/abgelaufener_link.test.ts

import { test, after } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> reset-password -> routes -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../..');

register(
	pathToFileURL(path.join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

const { actions } = await import(
	pathToFileURL(path.join(FRONTEND, 'src/routes/reset-password/+page.server.ts')).href
);

let naechsteAntwort: { status: number; koerper: string } = { status: 500, koerper: '{}' };
const echterFetch = globalThis.fetch;
globalThis.fetch = async () =>
	new Response(naechsteAntwort.koerper, {
		status: naechsteAntwort.status,
		headers: { 'Content-Type': 'application/json' },
	});
after(() => {
	globalThis.fetch = echterFetch;
});

async function einreichen(antwort: { status: number; koerper: string }): Promise<string> {
	naechsteAntwort = antwort;
	const form = new FormData();
	form.set('username', 'anna');
	form.set('token', 'abc123');
	form.set('new_password', 'neues-passwort-1');
	const request = new Request('http://localhost/reset-password', { method: 'POST', body: form });
	const ergebnis = (await actions.default({ request, locals: { lang: 'de' } } as never)) as { data?: { error?: string } };
	return ergebnis.data?.error ?? '';
}

test('AC-5: code token_expired zeigt den Hinweis „Token abgelaufen"', async () => {
	const meldung = await einreichen({
		status: 400,
		koerper: JSON.stringify({ code: 'token_expired', message: 'The link has expired.' }),
	});
	assert.equal(meldung, 'Token abgelaufen');
});

test('AC-5: code invalid_token zeigt den Hinweis „Ungültiger Token"', async () => {
	const meldung = await einreichen({
		status: 400,
		koerper: JSON.stringify({ code: 'invalid_token', message: 'The link is invalid.' }),
	});
	assert.equal(meldung, 'Ungültiger Token');
});
