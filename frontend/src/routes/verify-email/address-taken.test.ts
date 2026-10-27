// TDD RED — Issue #2147 Scheibe B2 (Epic #2138), AC-17 (Teil Bestaetigungsseite):
// Loest der Nutzer einen Link ein, dessen Adresse inzwischen einem anderen
// Konto gehoert, antwortet der Verify-Endpunkt `409 {"error":"address_taken"}`.
// Die Bestaetigungsseite zeigt dann „Diese Adresse gehoert inzwischen zu einem
// anderen Konto" — keinen rohen Fehlercode und nicht die allgemeine
// „ungueltig"-Meldung.
// Spec: docs/specs/modules/adresswechsel_nach_bestaetigung.md §9, AC-17.
//
// Kein Mock-Theater: die Action laeuft ECHT, nur die globale `fetch`-Funktion
// (die die Action bar aufruft) liefert eine vorgegebene Antwort — die
// Zuordnung Antwort -> Meldung wird real durchlaufen. Muster:
// src/routes/register/__tests__/register_email_taken.test.ts.
//
// RED heute: `+page.server.ts:36-40` kennt nur `token expired`; alles andere
// (auch 409 address_taken) faellt auf „ungueltig oder bereits verwendet".
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/routes/verify-email/address-taken.test.ts

import { test, describe, after } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// verify-email -> routes -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../..');

// $env/dynamic/private (apiBase.ts) + $lib/*.js-Aufloesung.
register(
	pathToFileURL(path.join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

const { actions } = await import(
	pathToFileURL(path.join(FRONTEND, 'src/routes/verify-email/+page.server.ts')).href
);

const MELDUNG_ADRESSE_VERGEBEN = 'Diese Adresse gehört inzwischen zu einem anderen Konto';
const MELDUNG_ABGELAUFEN =
	'Der Bestätigungslink ist abgelaufen. Bitte ändere deine Adresse erneut, um einen neuen Link zu erhalten.';
const MELDUNG_UNGUELTIG = 'Der Bestätigungslink ist ungültig oder wurde bereits verwendet.';

/** Antwort, die die naechste `fetch`-Anfrage der Action erhaelt. */
let naechsteAntwort: { status: number; koerper: string } = { status: 500, koerper: '{}' };
let angefragteUrls: string[] = [];
const echterFetch = globalThis.fetch;
// Bewusster Test-Ersatz der globalen fetch-Funktion.
globalThis.fetch = async (input: RequestInfo | URL) => {
	angefragteUrls.push(String(input));
	return new Response(naechsteAntwort.koerper, {
		status: naechsteAntwort.status,
		headers: { 'Content-Type': 'application/json' }
	});
};
after(() => {
	globalThis.fetch = echterFetch;
});

async function bestaetigen(status: number, koerper: string) {
	naechsteAntwort = { status, koerper };
	angefragteUrls = [];
	const body = new FormData();
	body.set('user', 'konto-ac17');
	body.set('token', 'token-ac17');
	const ereignis = {
		request: new Request('http://localhost/verify-email', { method: 'POST', body })
	};
	const ergebnis = (await actions.default(
		ereignis as unknown as Parameters<typeof actions.default>[0]
	)) as { status?: number; data?: { error?: string } };
	assert.ok(
		angefragteUrls.some((u) => u.endsWith('/api/auth/verify-email')),
		`Die Action muss den Verify-Endpunkt aufrufen, aufgerufen: ${JSON.stringify(angefragteUrls)}`
	);
	return ergebnis;
}

describe('#2147 Scheibe B2 AC-17 — Bestaetigungsseite meldet address_taken verstaendlich', () => {
	test('409_address_taken_zeigt_adresse_gehoert_anderem_konto', async () => {
		const ergebnis = await bestaetigen(409, JSON.stringify({ error: 'address_taken' }));
		const meldung = ergebnis?.data?.error ?? '';
		assert.ok(
			meldung.includes(MELDUNG_ADRESSE_VERGEBEN),
			`AC-17: erwartet „${MELDUNG_ADRESSE_VERGEBEN}", bekommen: ${meldung}`
		);
		assert.ok(
			!meldung.includes('address_taken'),
			`AC-17: der rohe Fehlercode darf nicht angezeigt werden, bekommen: ${meldung}`
		);
		assert.notEqual(
			meldung,
			MELDUNG_UNGUELTIG,
			'AC-17: address_taken darf nicht auf die allgemeine „ungueltig"-Meldung fallen.'
		);
	});

	// Regressionswaechter (heute gruen): die bestehenden Codes behalten ihre
	// bisherige Meldung.
	test('regression_400_token_expired_behaelt_ablauf_meldung', async () => {
		const ergebnis = await bestaetigen(400, JSON.stringify({ error: 'token expired' }));
		assert.equal(ergebnis?.data?.error, MELDUNG_ABGELAUFEN);
	});

	test('regression_400_invalid_token_behaelt_ungueltig_meldung', async () => {
		const ergebnis = await bestaetigen(400, JSON.stringify({ error: 'invalid token' }));
		assert.equal(ergebnis?.data?.error, MELDUNG_UNGUELTIG);
	});
});
