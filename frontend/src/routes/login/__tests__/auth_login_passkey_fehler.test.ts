// Issue #2650 (i18n F1) — Adversary F002: die Zuordnung der Passkey-Fehler auf
// Katalogschluessel wird einzeln geprueft. Abbruch (NotAllowedError, AbortError)
// -> auth.login.passkey_abgebrochen; alles andere -> auth.login.passkey_fehlgeschlagen.
// Die Funktion ist im Modul-Skript von login/+page.svelte exportiert; der Aufruf
// ist echt (kein Mock). Die Texte selbst laufen in der Golden-/Sprachtestdatei.
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/routes/login/__tests__/auth_login_passkey_fehler.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { ROUTES } from '../../__tests__/auth_zweisprachig_harness.ts';

const modul = (await import(pathToFileURL(path.join(ROUTES, 'login/+page.svelte')).href)) as {
	passkeyFehlertext: (e: unknown) => string;
};

describe('#2650 F002 — passkeyFehlertext ordnet Abbruch und Fehlschlag richtig zu', () => {
	test('F002_NotAllowedError_ist_abbruch', () => {
		assert.equal(modul.passkeyFehlertext({ name: 'NotAllowedError' }), 'auth.login.passkey_abgebrochen');
	});
	test('F002_AbortError_ist_abbruch', () => {
		assert.equal(modul.passkeyFehlertext({ name: 'AbortError' }), 'auth.login.passkey_abgebrochen');
	});
	test('F002_anderer_fehler_ist_fehlschlag', () => {
		assert.equal(modul.passkeyFehlertext({ name: 'SecurityError' }), 'auth.login.passkey_fehlgeschlagen');
	});
	test('F002_ohne_fehlername_ist_fehlschlag', () => {
		assert.equal(modul.passkeyFehlertext(undefined), 'auth.login.passkey_fehlgeschlagen');
	});
});
