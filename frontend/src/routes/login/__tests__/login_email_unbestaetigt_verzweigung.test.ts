// Issue #2271 AC-12 — Waechter fuer die VERZWEIGUNG in der `login`-Action
// (`frontend/src/routes/login/+page.server.ts`, Zeile 43-48).
//
// Der Befund (Gegenpruefung, F001): die Unterscheidung zwischen "403 weil die
// Adresse unbestaetigt ist" und "403 aus irgendeinem anderen Grund" war in der
// gesamten Merge-Ampel unsichtbar. Wer den inneren Zweig spaeter verbreitert
// (`grund?.error === 'email_not_verified'` -> `true`), bekaeme bei JEDEM 403
// den Hinweis "bestaetige deine E-Mail-Adresse" -- eine falsche Auskunft an der
// Anmeldemaske, und nichts haette es gemeldet. Genau diese Verfaelschung faengt
// `zweiter_403_grund_fuehrt_nicht_zum_email_hinweis`.
//
// Kein Mock-Theater: die Action laeuft ECHT. Statt `fetch` zu ersetzen, steht
// an der Stelle der Go-API ein echter HTTP-Server auf 127.0.0.1, der Status und
// Koerper so ausliefert wie `internal/api` es tut; `GZ_API_BASE` zeigt darauf.
// Gemessen wird beides: was die Action zurueckgibt (`status` + `data.error` --
// Fall 2 und Fall 3 rendern identisches HTML, nur der Status trennt sie) UND
// was die echte Seite daraus serverseitig rendert (`svelte/server`).
//
// Pfadregel #1409: Pruefling relativ zu DIESER Datei aufgeloest.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/routes/login/__tests__/login_email_unbestaetigt_verzweigung.test.ts

import { test, describe, after } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { createServer } from 'node:http';
import type { AddressInfo } from 'node:net';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> login -> routes -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../..');

// Reihenfolge wie in login_erstes_bild.test.ts: erst die lokalen Stubs, dann
// die geteilte SSR-Kette. `$env/dynamic/private` reicht `process.env` durch
// (Vorbild: src/hooks.server.failfast.test.ts) -- nur so laesst sich die
// Basis-URL der Go-API vor dem Aufruf auf den Testserver zeigen.
register(
	pathToFileURL(path.join(HERE, 'app-stores-stub-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);
register(
	pathToFileURL(path.join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);
register(
	pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

/** Antwort, die der Go-API-Platzhalter beim naechsten Aufruf ausliefert. */
let naechsteAntwort: { status: number; koerper: string } = { status: 500, koerper: '{}' };
let letzterPfad = '';

const goApi = createServer((req, res) => {
	letzterPfad = req.url ?? '';
	res.writeHead(naechsteAntwort.status, { 'Content-Type': 'application/json' });
	res.end(naechsteAntwort.koerper);
});
await new Promise<void>((fertig) => goApi.listen(0, '127.0.0.1', fertig));
process.env.GZ_API_BASE = `http://127.0.0.1:${(goApi.address() as AddressInfo).port}`;
after(() => goApi.close());

const { actions } = await import(
	pathToFileURL(path.join(FRONTEND, 'src/routes/login/+page.server.ts')).href
);
const { render } = await import('svelte/server');
const Login = (
	await import(pathToFileURL(path.join(FRONTEND, 'src/routes/login/+page.svelte')).href)
).default;

type Ausgang = { status: number; data: { error?: string; username?: string } };

/** Ruft die echte `login`-Action gegen die vorgegebene Go-API-Antwort auf. */
async function meldeAn(status: number, koerper: string): Promise<Ausgang> {
	naechsteAntwort = { status, koerper };
	const body = new FormData();
	body.set('username', 'wanderer');
	body.set('password', 'geheim-genug-fuer-den-test');
	const ereignis = {
		request: new Request('http://localhost/login?/login', { method: 'POST', body }),
		cookies: {
			set() {
				throw new Error('Kein Fehlerfall darf eine Sitzung setzen.');
			},
		},
		url: new URL('http://localhost/login'),
	};
	const ergebnis = await actions.login(
		ereignis as unknown as Parameters<typeof actions.login>[0]
	);
	assert.ok(ergebnis, 'Die Action hat kein Ergebnis geliefert (unerwarteter Erfolgspfad).');
	return ergebnis as Ausgang;
}

/** Was der Nutzer zu sehen bekaeme: die echte Seite, serverseitig gerendert. */
function seiteMit(ergebnis: Ausgang): string {
	return render(Login, {
		props: { form: ergebnis.data, data: { googleEnabled: false } },
	}).body;
}

const HINWEIS = 'data-testid="login-error-email-not-verified"';
const ALLGEMEIN = 'Benutzername oder Passwort nicht korrekt.';

describe('#2271 AC-12 — nur der Grund `email_not_verified` fuehrt zum Postfach-Hinweis', () => {
	test('403_mit_email_not_verified_zeigt_den_hinweis', async () => {
		const ergebnis = await meldeAn(403, JSON.stringify({ error: 'email_not_verified' }));
		assert.equal(letzterPfad, '/api/auth/login', 'Die Action hat den Login-Endpunkt nicht gerufen.');
		assert.equal(ergebnis.status, 403, 'AC-12: der unbestaetigte Fall behaelt den Status 403.');
		assert.equal(ergebnis.data.error, 'email_not_verified');
		const html = seiteMit(ergebnis);
		assert.ok(
			html.includes(HINWEIS),
			'AC-12: bei `email_not_verified` fehlt der Hinweisblock mit dem Weg zum Postfach.'
		);
	});

	test('zweiter_403_grund_fuehrt_nicht_zum_email_hinweis', async () => {
		// Die tragende Gegenprobe: ein 403 aus einem ANDEREN Grund darf den
		// Postfach-Hinweis nicht ausloesen. Wird `grund?.error === 'email_not_verified'`
		// verbreitert, faellt genau dieser Fall um.
		const ergebnis = await meldeAn(403, JSON.stringify({ error: 'forbidden' }));
		assert.notEqual(
			ergebnis.data.error,
			'email_not_verified',
			'Ein 403 mit dem Grund `forbidden` wird faelschlich als unbestaetigte Adresse ausgegeben — ' +
				'der Nutzer bekaeme "bestaetige deine E-Mail-Adresse" fuer etwas ganz anderes (F001).'
		);
		assert.equal(
			ergebnis.status,
			401,
			'Ein 403 ohne den Grund `email_not_verified` faellt in den allgemeinen Zweig (401).'
		);
		const html = seiteMit(ergebnis);
		assert.ok(!html.includes(HINWEIS), 'Der Postfach-Hinweisblock steht bei fremdem 403-Grund in der Seite.');
		assert.ok(html.includes(ALLGEMEIN), 'Die allgemeine Fehlermeldung fehlt beim fremden 403-Grund.');
	});

	test('401_bleibt_bei_der_bisherigen_meldung', async () => {
		const ergebnis = await meldeAn(401, JSON.stringify({ error: 'invalid credentials' }));
		assert.equal(ergebnis.status, 401);
		assert.equal(ergebnis.data.error, 'Invalid credentials');
		const html = seiteMit(ergebnis);
		assert.ok(!html.includes(HINWEIS), 'Der neue Hinweisblock darf bei falschem Passwort nicht erscheinen.');
		assert.ok(html.includes(ALLGEMEIN), 'Bei 401 fehlt die Meldung "Benutzername oder Passwort nicht korrekt."');
	});
});
