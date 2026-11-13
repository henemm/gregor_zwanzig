// Issue #2961 (ADR-0115): Adresswechsel und Passkey-Aenderungen verlangen einen
// frischen Nachweis. Geprueft wird, dass die Konto-Seite die 403-Antwort
// `reauth_required` erkennt — sowohl als API-Fehlerobjekt (Profil-Speichern)
// als auch aus $lib/passkey (echte Funktion, nur die globale fetch-Funktion
// liefert die Server-Antwort) — und die Dialog-Fehler verstaendlich uebersetzt.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/routes/account/__tests__/nachweis_vor_kontoaenderung.test.ts

import { test, after } from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../../../..');

const { brauchtNachweis, nachweisFehlerText } = (await import(
	pathToFileURL(path.join(FRONTEND, 'src/routes/account/nachweis.ts')).href
)) as {
	brauchtNachweis: (e: unknown) => boolean;
	nachweisFehlerText: (e: unknown, fallback: string) => string;
};
const { deletePasskey } = (await import(pathToFileURL(path.join(FRONTEND, 'src/lib/passkey.ts')).href)) as {
	deletePasskey: (id: string) => Promise<void>;
};

let antwort: { status: number; koerper: string } = { status: 200, koerper: '{}' };
const echterFetch = globalThis.fetch;
globalThis.fetch = async () =>
	new Response(antwort.koerper, { status: antwort.status, headers: { 'Content-Type': 'application/json' } });
after(() => {
	globalThis.fetch = echterFetch;
});

test('403 reauth_required aus dem Profil-Speichern verlangt den Nachweis', () => {
	assert.equal(brauchtNachweis({ status: 403, error: 'reauth_required', code: 'reauth_required' }), true);
	assert.equal(brauchtNachweis({ status: 403, error: 'origin_forbidden' }), false);
	assert.equal(brauchtNachweis({ status: 409, error: 'email_taken' }), false);
	assert.equal(brauchtNachweis(null), false);
});

test('Passkey entfernen ohne Nachweis: $lib/passkey meldet reauth_required', async () => {
	antwort = { status: 403, koerper: JSON.stringify({ code: 'reauth_required', error: 'reauth_required' }) };
	const fehler = await deletePasskey('AQID').then(
		() => null,
		(e: unknown) => e
	);
	assert.ok(fehler instanceof Error);
	assert.equal(brauchtNachweis(fehler), true);

	antwort = { status: 500, koerper: '{}' };
	const anderer = await deletePasskey('AQID').then(
		() => null,
		(e: unknown) => e
	);
	assert.equal(brauchtNachweis(anderer), false, 'ein anderer Serverfehler ist kein Nachweis-Fall');
});

test('Fehler im Nachweis-Dialog werden verstaendlich uebersetzt', () => {
	assert.equal(nachweisFehlerText({ error: 'wrong_password' }, 'x'), 'Das Passwort ist falsch.');
	assert.equal(nachweisFehlerText({ error: 'reauth_required' }, 'x'), 'Bitte Passwort oder Code eingeben.');
	assert.equal(nachweisFehlerText({ error: 'invalid_code' }, 'x'), 'Der Code ist falsch, abgelaufen oder bereits benutzt.');
	assert.equal(nachweisFehlerText({}, 'Ersatz'), 'Ersatz');
});
