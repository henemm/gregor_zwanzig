// Issue #2676 (i18n G2), AC-5 (Konto-Seite): falsches aktuelles Passwort wird
// am Code wrong_password erkannt. Geprueft wird die Funktion, die die Seite
// tatsaechlich aufruft (frontend/src/routes/account/passwortAendernError.ts).
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/routes/account/__tests__/passwort_aendern_error.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> account -> routes -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../..');

const { passwortAendernErrorMessage } = await import(
	pathToFileURL(path.join(FRONTEND, 'src/routes/account/passwortAendernError.ts')).href
);

// Fehlerobjekt wie es der API-Client nach WriteError wirft (code + Uebergangsfeld error).
const falschesPasswort = {
	code: 'wrong_password',
	error: 'wrong_password',
	message: 'Das Passwort ist falsch.',
	status: 403,
};

test('AC-5: code wrong_password zeigt „Aktuelles Passwort ist falsch"', () => {
	assert.equal(passwortAendernErrorMessage(falschesPasswort), 'Aktuelles Passwort ist falsch');
});

test('AC-5: nur das Feld error (ohne code) loest die Meldung nicht aus', () => {
	// Die Seite entscheidet am code, nicht am Uebergangsfeld error.
	assert.equal(passwortAendernErrorMessage({ error: 'wrong_password' }), 'wrong_password');
});

test('AC-5: anderer Code zeigt den Text aus error (bisheriges Verhalten)', () => {
	assert.equal(
		passwortAendernErrorMessage({ code: 'validation_failed', error: 'validation_failed' }),
		'validation_failed'
	);
});

test('AC-5: ohne Fehlerobjekt zeigt die Seite den Standardsatz', () => {
	assert.equal(passwortAendernErrorMessage(undefined), 'Passwort ändern fehlgeschlagen');
});
