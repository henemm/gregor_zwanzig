// Issue #3281 (MCP-Konnektor, Nacharbeit) — der Ruecksprung der Anmeldeseite
// (`/login?redirect=…`, z. B. zur Autorisierung des Konnektors) gilt fuer ALLE
// dort angebotenen Wege: Google-Knopf und Code-Anmeldung („Magic-Link“) tragen
// ihn weiter, die Code-Anmeldung springt nach Erfolg dorthin. Passkey:
// src/lib/passkey_ruecksprung.test.ts; Google-Callback: Go
// internal/handler/auth_oauth_ruecksprung_test.go.
//
// Kein Mock: echte Seiten (serverseitig gerendert) und echte Actions gegen
// einen HTTP-Server an Stelle der Go-API.
//
//   cd frontend && npm test -- src/routes/login/__tests__/login_ruecksprung_alle_wege.test.ts

import { test, after } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { createServer } from 'node:http';
import type { AddressInfo } from 'node:net';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> login -> routes -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../..');

register(pathToFileURL(path.join(HERE, 'app-stores-url-stub-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
register(
	pathToFileURL(path.join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);
register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);

const goApi = createServer((_req, res) => {
	res.writeHead(200, { 'Content-Type': 'application/json', 'Set-Cookie': 'gz_session=u.s.1.sig; Path=/' });
	res.end('{}');
});
await new Promise<void>((fertig) => goApi.listen(0, '127.0.0.1', fertig));
process.env.GZ_API_BASE = `http://127.0.0.1:${(goApi.address() as AddressInfo).port}`;
after(() => goApi.close());

const { render } = await import('svelte/server');
const seite = async (p: string) => (await import(pathToFileURL(path.join(FRONTEND, p)).href)).default;
const Login = await seite('src/routes/login/+page.svelte');
const MagicLink = await seite('src/routes/magic-link/+page.svelte');
const magicAction = (await import(pathToFileURL(path.join(FRONTEND, 'src/routes/magic-link/+page.server.ts')).href)).actions;
const verifyAction = (await import(pathToFileURL(path.join(FRONTEND, 'src/routes/magic-link/verify/+page.server.ts')).href))
	.actions;

const AUTHORIZE = '/api/mcp/oauth/authorize?response_type=code&client_id=c_x&code_challenge=abc&state=z';
const MIT = `?redirect=${encodeURIComponent(AUTHORIZE)}`;

function hrefs(html: string): string[] {
	return [...html.matchAll(/href="([^"]*)"/g)].map((m) => m[1].replaceAll('&amp;', '&'));
}

function loginLinks(seitenUrl: string): string[] {
	(globalThis as { __gzLoginTestUrl?: string }).__gzLoginTestUrl = seitenUrl;
	return hrefs(render(Login, { props: { form: null, data: { googleEnabled: true } } }).body);
}

test('Login-Seite: Google-Knopf und Code-Anmeldung tragen den Ruecksprung', () => {
	const links = loginLinks(`http://localhost/login${MIT}`);
	assert.ok(links.includes(`/api/auth/google/init${MIT}`), `Google-Link: ${links.join(' ')}`);
	assert.ok(links.includes(`/magic-link${MIT}`), `Code-Link: ${links.join(' ')}`);
});

test('Login-Seite: ohne oder mit fremdem Ruecksprung bleiben die Links schlicht', () => {
	for (const adresse of ['http://localhost/login', `http://localhost/login?redirect=${encodeURIComponent('//evil.example')}`]) {
		const links = loginLinks(adresse);
		assert.ok(links.includes('/api/auth/google/init'), adresse);
		assert.ok(links.includes('/magic-link'), adresse);
	}
});

async function codeAnfordern(adresse: string): Promise<Record<string, unknown>> {
	const body = new FormData();
	body.set('email', 'anna@beispiel.de');
	const url = new URL(adresse);
	return magicAction.default({ request: new Request(url, { method: 'POST', body }), url, locals: { lang: 'de' } } as never);
}

test('Code anfordern: der Weg zur Code-Eingabe traegt den Ruecksprung', async () => {
	const ergebnis = await codeAnfordern(`http://localhost/magic-link${MIT}`);
	assert.equal(ergebnis.redirect, AUTHORIZE);
	const links = hrefs(render(MagicLink, { props: { form: ergebnis } }).body);
	const ziel = links.find((l) => l.startsWith('/magic-link/verify'));
	assert.ok(ziel, `Link zur Code-Eingabe fehlt: ${links.join(' ')}`);
	const u = new URL(ziel, 'http://localhost');
	assert.equal(u.searchParams.get('email'), 'anna@beispiel.de');
	assert.equal(u.searchParams.get('redirect'), AUTHORIZE);
});

test('Code anfordern: fremder Ruecksprung wird nicht weitergetragen', async () => {
	const ergebnis = await codeAnfordern(`http://localhost/magic-link?redirect=${encodeURIComponent('https://evil.example')}`);
	assert.ok(!ergebnis.redirect, String(ergebnis.redirect));
	const ziel = hrefs(render(MagicLink, { props: { form: ergebnis } }).body).find((l) => l.startsWith('/magic-link/verify'));
	assert.ok(ziel && !ziel.includes('redirect'), String(ziel));
});

async function codeEinloesen(adresse: string): Promise<string> {
	const body = new FormData();
	body.set('email', 'anna@beispiel.de');
	body.set('code', '12345678');
	const url = new URL(adresse);
	try {
		await verifyAction.default({
			request: new Request(url, { method: 'POST', body }),
			cookies: { set: () => {} },
			locals: { lang: 'de' },
			url
		} as never);
	} catch (e) {
		const r = e as { status?: number; location?: string };
		assert.equal(r.status, 302);
		return r.location ?? '';
	}
	assert.fail('Code-Anmeldung hat nicht weitergeleitet');
}

test('Code einloesen: nach Erfolg zum Ruecksprung, sonst auf /', async () => {
	assert.equal(await codeEinloesen(`http://localhost/magic-link/verify?email=a${MIT.replace('?', '&')}`), AUTHORIZE);
	assert.equal(await codeEinloesen('http://localhost/magic-link/verify?email=a'), '/');
	assert.equal(await codeEinloesen(`http://localhost/magic-link/verify?redirect=${encodeURIComponent('/\\evil.example')}`), '/');
});
