// Issue #2194 (E-Mail als Login-Kennung), AC-14 / AC-9 Frontend-Teil:
// passkey.ts reicht die eingegebene Kennung — jetzt die E-Mail-Adresse — unveraendert
// an `POST /api/auth/passkey/login/begin` weiter; die `@`-Weiche entscheidet der Go-Server.
// Ein Konto-ID ohne `@` (Testkonten) geht ebenso unveraendert durch.
//
// WAECHTER, heute gruen: passkey.ts transportiert die Kennung bereits unveraendert.
// Der Test haelt fest, dass GREEN sie nicht umformt (kein Kleinschreiben/Trimmen
// clientseitig, kein neuer Body-Schluessel — der Vertrag gehoert dem Go-Teil, heute
// `username`).
//
// Ersetzt ist nur die Netzgrenze `fetch` (Antwort 401), damit loginWithPasskey vor
// dem Browser-Dialog (`navigator.credentials.get`) mit `invalid_credentials` endet.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/passkey_kennung_ist_email.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

const { loginWithPasskey } = await import('./passkey.ts');

async function beginKoerper(kennung: string): Promise<{ url: string; body: Record<string, unknown> }> {
	const echterFetch = globalThis.fetch;
	let gesehen: { url: string; body: Record<string, unknown> } | null = null;
	globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
		gesehen = { url: String(input), body: JSON.parse(String(init?.body ?? '{}')) };
		return new Response('{"code":"invalid_credentials"}', { status: 401 });
	}) as typeof fetch;
	try {
		await assert.rejects(loginWithPasskey(kennung), /invalid_credentials/);
	} finally {
		globalThis.fetch = echterFetch;
	}
	assert.ok(gesehen, 'loginWithPasskey hat keine Anfrage gestellt');
	return gesehen!;
}

describe('#2194 Waechter — Passkey-Login mit Kennung reicht die E-Mail-Adresse unveraendert weiter', () => {
	test('waechter_passkey_email_kennung_geht_unveraendert_an_login_begin', async () => {
		const { url, body } = await beginKoerper('Anna@Beispiel.de');
		assert.equal(url, '/api/auth/passkey/login/begin');
		assert.deepEqual(
			Object.values(body),
			['Anna@Beispiel.de'],
			`Die eingegebene E-Mail-Adresse muss unveraendert (einziger Wert) im Begin-Body stehen, ist: ${JSON.stringify(body)}`
		);
	});

	test('waechter_passkey_konto_id_ohne_at_geht_unveraendert_an_login_begin', async () => {
		const { body } = await beginKoerper('tg-live-e2e');
		assert.deepEqual(Object.values(body), ['tg-live-e2e'], `ID-Pfad (Testkonten) veraendert: ${JSON.stringify(body)}`);
	});
});
