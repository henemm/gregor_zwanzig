// TDD RED — Issue #2147 Scheibe B1 (#2311, Epic #2138), AC-15: die
// Registrierungs-Action unterscheidet den Adress-Konflikt (`email_taken`) vom
// Kennungs-Konflikt (`user already exists`) und zeigt dafuer eine eigene,
// verstaendliche Meldung statt der pauschalen "Benutzername bereits vergeben".
// Spec: docs/specs/modules/adress_eindeutigkeit_schreibpfade.md §7, AC-15.
//
// Kein Mock-Theater im Sinne der Projektregel: die Action laeuft ECHT, nur
// die globale `fetch`-Funktion (die die Action bar aufruft, ohne sie ueber
// den Event zu beziehen) wird durch eine vorgegebene Antwort ersetzt — die
// Action-Logik selbst (Statuscode -> Fehlermeldung) wird real durchlaufen.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/routes/register/__tests__/register_email_taken.test.ts

import { test, describe, after } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> register -> routes -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../..');

// $env/dynamic/private (apiBase.ts) + $lib/*.js-Aufloesung — Vorbild:
// login_email_unbestaetigt_verzweigung.test.ts.
register(
	pathToFileURL(path.join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

const { actions } = await import(
	pathToFileURL(path.join(FRONTEND, 'src/routes/register/+page.server.ts')).href
);

/** Antwort, die die naechste `fetch`-Anfrage der Action erhaelt. */
let naechsteAntwort: { status: number; koerper: string } = { status: 500, koerper: '{}' };
const echterFetch = globalThis.fetch;
// Bewusster Test-Ersatz der globalen fetch-Funktion.
globalThis.fetch = async () =>
	new Response(naechsteAntwort.koerper, {
		status: naechsteAntwort.status,
		headers: { 'Content-Type': 'application/json' },
	});
after(() => {
	globalThis.fetch = echterFetch;
});

async function registrieren(status: number, koerper: string) {
	naechsteAntwort = { status, koerper };
	const body = new FormData();
	body.set('username', 'neuling-ac15');
	body.set('email', 'belegt-ac15@beispiel.de');
	body.set('password', 'geheim1234');
	body.set('confirmPassword', 'geheim1234');
	const ereignis = { request: new Request('http://localhost/register', { method: 'POST', body }) };
	return actions.default(ereignis as unknown as Parameters<typeof actions.default>[0]);
}

describe('#2147 Scheibe B1 AC-15 — Registrierung meldet email_taken verstaendlich', () => {
	test('409_email_taken_zeigt_adresskonflikt_nicht_benutzername_vergeben', async () => {
		const ergebnis = (await registrieren(409, JSON.stringify({ error: 'email_taken' }))) as {
			status: number;
			data: { error?: string };
		};
		assert.ok(ergebnis, 'AC-15: die Action muss bei 409 ein fail()-Ergebnis liefern.');
		assert.notEqual(
			ergebnis.data.error,
			'Benutzername bereits vergeben',
			'AC-15: ein Adresskonflikt darf nicht als Kennungskonflikt gemeldet werden.'
		);
		assert.ok(
			ergebnis.data.error &&
				/e-mail|adresse/i.test(ergebnis.data.error) &&
				!/benutzername/i.test(ergebnis.data.error),
			`AC-15: erwartet einen adressbezogenen Hinweis, bekommen: ${ergebnis.data.error}`
		);
	});

	// Regressionswaechter (AC-4): der Kennungskonflikt behaelt seine bisherige
	// Meldung — voraussichtlich schon heute gruen.
	test('409_user_already_exists_behaelt_die_bisherige_meldung', async () => {
		const ergebnis = (await registrieren(409, JSON.stringify({ error: 'user already exists' }))) as {
			status: number;
			data: { error?: string };
		};
		assert.equal(
			ergebnis.data.error,
			'Benutzername bereits vergeben',
			'AC-4/AC-15: der Kennungskonflikt behaelt seine bisherige Meldung.'
		);
	});
});
