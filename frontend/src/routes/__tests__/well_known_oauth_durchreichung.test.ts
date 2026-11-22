// Issue #3281 (MCP-Konnektor „Gregor Wetter“, Scheibe 2) — AC-6: die
// OAuth-Metadaten unter `/.well-known/oauth-*` erreichen Go ueber SvelteKit
// (nginx leitet die Wurzelpfade an SvelteKit, nicht an Go).
//
// Kein Mock: die echte Route laeuft mit echtem `fetch` gegen einen lokalen
// `node:http`-Server an Stelle der Go-API; der echte `handle` laesst die Pfade
// ohne Anmeldung durch.
//
//   cd frontend && npm test -- src/routes/__tests__/well_known_oauth_durchreichung.test.ts
//
// Der Test liegt bewusst NICHT unter `.well-known/`: `node --test` sucht ohne
// Dateiangabe nicht in Punkt-Verzeichnissen, die CI liefe sonst an ihm vorbei.

import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { createServer, type IncomingHttpHeaders, type Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> routes -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../..');

register(
	pathToFileURL(path.join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

type Ankunft = { methode: string; pfad: string; kopf: IncomingHttpHeaders };
const ankuenfte: Ankunft[] = [];
let server: Server;

before(async () => {
	server = createServer((req, res) => {
		ankuenfte.push({ methode: req.method ?? '', pfad: req.url ?? '', kopf: req.headers });
		res.writeHead(200, { 'content-type': 'application/json', 'access-control-allow-origin': '*' });
		res.end(JSON.stringify({ resource: 'https://gregor.test/api/mcp' }));
	});
	await new Promise<void>((fertig) => server.listen(0, '127.0.0.1', fertig));
	process.env.GZ_API_BASE = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
	process.env.GZ_SESSION_SECRET = 'a-genuinely-random-forty-char-secret-12';
});

after(() => server.close());

const route = await import(
	pathToFileURL(path.join(FRONTEND, 'src/routes/.well-known/[...pfad]/+server.ts')).href
);

async function rufe(pfadUndSuche: string, kopf: Record<string, string> = {}): Promise<Response> {
	ankuenfte.length = 0;
	const url = new URL(`http://localhost:4173${pfadUndSuche}`);
	return route.GET({
		request: new Request(url, { headers: kopf }),
		url,
		params: { pfad: url.pathname.slice('/.well-known/'.length) },
		cookies: { get: (n: string) => (n === 'gz_session' ? 'sitzung-a' : undefined) }
	});
}

test('AC-6: Metadaten der Ressource und des Servers kommen unveraendert von Go', async () => {
	for (const p of [
		'/.well-known/oauth-protected-resource',
		'/.well-known/oauth-protected-resource/api/mcp',
		'/.well-known/oauth-authorization-server'
	]) {
		const antwort = await rufe(p, { accept: 'application/json' });
		assert.equal(antwort.status, 200, p);
		assert.equal(ankuenfte.length, 1, p);
		assert.equal(ankuenfte[0].methode, 'GET');
		assert.equal(ankuenfte[0].pfad, p);
		assert.deepEqual(await antwort.json(), { resource: 'https://gregor.test/api/mcp' });
		assert.equal(antwort.headers.get('access-control-allow-origin'), '*');
	}
});

test('kein Cookie und keine Anmeldung gehen an Go', async () => {
	await rufe('/.well-known/oauth-authorization-server', { cookie: 'gz_session=sitzung-a' });
	assert.equal(ankuenfte[0].kopf.cookie, undefined);
	assert.equal(ankuenfte[0].kopf.authorization, undefined);
});

test('andere /.well-known-Pfade erreichen Go nicht', async () => {
	for (const p of [
		'/.well-known/security.txt',
		'/.well-known/oauth-andere',
		'/.well-known/oauth-protected-resource/anders',
		'/.well-known/oauth-protected-resource/api/mcp/..',
		'/.well-known/oauth-authorization-server/x'
	]) {
		const antwort = await rufe(p);
		assert.equal(antwort.status, 404, p);
		assert.equal(ankuenfte.length, 0, `${p} darf Go nicht erreichen`);
	}
});

test('der echte handle laesst die Metadaten ohne Anmeldung durch', async () => {
	// @ts-expect-error Cache-Busting-Query, zur Laufzeit vom Stub-Hook aufgeloest
	const { handle } = await import('../../hooks.server.ts?case=well-known-3281');
	const resolve = async () => new Response('{}', { status: 200, headers: { 'content-type': 'application/json' } });
	for (const p of ['/.well-known/oauth-protected-resource/api/mcp', '/.well-known/oauth-authorization-server']) {
		const url = new URL(`http://localhost${p}`);
		const event = { url, locals: {}, request: new Request(url), cookies: { get: () => undefined } };
		const res: Response = await handle({ event, resolve } as never);
		assert.equal(res.status, 200, `${p} darf nicht auf /login umleiten`);
	}
	const url = new URL('http://localhost/.well-known/andere');
	const event = { url, locals: {}, request: new Request(url), cookies: { get: () => undefined } };
	await assert.rejects(
		async () => handle({ event, resolve } as never),
		(e: { status?: number }) => e.status === 302,
		'andere /.well-known-Pfade bleiben anmeldepflichtig'
	);
});
