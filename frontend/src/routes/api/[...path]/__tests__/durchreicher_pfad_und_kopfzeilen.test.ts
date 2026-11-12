// Issue #2961 (FE3) — der Durchreicher `/api/[...path]` gegen einen echten
// HTTP-Server an Stelle der Go-API.
//
// Spec: docs/specs/modules/security_haertung_2026_11_frontend.md (AC-2, AC-3)
//
// Kein Mock: die echte Route laeuft mit echtem `fetch` gegen einen lokalen
// `node:http`-Server, der festhaelt, was bei ihm ankommt (Pfad, Kopfzeilen).
// Dasselbe gilt fuer die Seiten-Loader von Trip- und Vergleichs-Ansicht.
//
// Ausfuehren:
//   cd frontend && npm test -- 'src/routes/api/[...path]/__tests__/durchreicher_pfad_und_kopfzeilen.test.ts'

import { test, describe, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { createServer, type IncomingHttpHeaders, type Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> [...path] -> api -> routes -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../../..');

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
		res.writeHead(200, { 'content-type': 'application/json' });
		res.end(JSON.stringify({ id: 'x', location_ids: [] }));
	});
	await new Promise<void>((fertig) => server.listen(0, '127.0.0.1', fertig));
	process.env.GZ_API_BASE = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});

after(() => {
	server.close();
});

const durchreicher = await import(
	pathToFileURL(path.join(FRONTEND, 'src/routes/api/[...path]/+server.ts')).href
);

function keks(werte: Record<string, string>) {
	return { get: (name: string) => werte[name] };
}

async function rufe(pfadUndSuche: string, kopf: Record<string, string> = {}, methode = 'GET') {
	ankuenfte.length = 0;
	const url = new URL(`http://localhost:4173${pfadUndSuche}`);
	const request = new Request(url, {
		method: methode,
		headers: kopf,
		body: methode === 'GET' ? undefined : '{}'
	});
	const handler = durchreicher[methode];
	const antwort: Response = await handler({
		request,
		url,
		params: { path: url.pathname.slice('/api/'.length) },
		cookies: keks({ gz_session: 'sitzung-a', fremd: 'nicht-weiter' })
	});
	return antwort;
}

describe('AC-3: Durchreicher — Pfad', () => {
	test('ein gueltiger Pfad samt Abfrage kommt unveraendert an', async () => {
		const antwort = await rufe('/api/trips/abc/weather-config?x=1');
		assert.equal(antwort.status, 200);
		assert.equal(ankuenfte.length, 1);
		assert.equal(ankuenfte[0].pfad, '/api/trips/abc/weather-config?x=1');
	});

	for (const pfad of ['/api/trips/..%2Fauth%2Fprofile', '/api/trips/a%2Fb', '/api/trips//x', '/api/trips/%2e']) {
		test(`unzulaessiger Pfad ${pfad} wird mit 400 abgewiesen und erreicht die Go-API nicht`, async () => {
			const antwort = await rufe(pfad);
			assert.equal(antwort.status, 400);
			assert.equal(ankuenfte.length, 0, 'die Anfrage wurde trotzdem weitergegeben');
		});
	}
});

describe('AC-3: Durchreicher — Kopfzeilen', () => {
	test('nur die Positivliste und die Sitzung kommen an', async () => {
		await rufe(
			'/api/trips/abc',
			{
				'content-type': 'application/json',
				accept: 'application/json',
				'accept-language': 'de',
				'if-match': '"v1"',
				'x-real-ip': '203.0.113.5',
				cookie: 'gz_session=aus-dem-kopf; fremd=1',
				authorization: 'Bearer abc',
				'x-forwarded-for': '198.51.100.7',
				'x-forwarded-proto': 'http',
				'x-gz-core-auth': 'raten',
				'x-gz-lang': 'en'
			},
			'PUT'
		);
		assert.equal(ankuenfte.length, 1);
		const kopf = ankuenfte[0].kopf;
		assert.equal(ankuenfte[0].methode, 'PUT');
		assert.equal(kopf['if-match'], '"v1"');
		assert.equal(kopf['x-real-ip'], '203.0.113.5');
		assert.equal(kopf['accept-language'], 'de');
		assert.equal(kopf.cookie, 'gz_session=sitzung-a');
		for (const verboten of [
			'authorization',
			'x-forwarded-for',
			'x-forwarded-proto',
			'x-gz-core-auth',
			'x-gz-lang'
		]) {
			assert.equal(kopf[verboten], undefined, `${verboten} wurde an die Go-API weitergegeben`);
		}
	});
});

describe('AC-2: Seiten-Loader kodieren die Kennung', () => {
	const ereignis = (id: string) => ({
		params: { id },
		cookies: keks({ gz_session: 'sitzung-a' }),
		locals: { lang: 'de' },
		url: new URL(`http://localhost/x/${encodeURIComponent(id)}`)
	});

	test('Trip-Ansicht: eine Kennung mit Abfragezeichen bleibt ein Pfadsegment', async () => {
		const { load } = await import(
			pathToFileURL(path.join(FRONTEND, 'src/routes/trips/[id]/+page.server.ts')).href
		);
		ankuenfte.length = 0;
		await load(ereignis('abc?admin=1'));
		const trip = ankuenfte.find((a) => a.pfad.startsWith('/api/trips/'));
		assert.equal(trip?.pfad, '/api/trips/abc%3Fadmin=1');
	});

	test('Trip-Ansicht: eine Kennung mit Pfadtrenner ergibt 404 ohne Aufruf', async () => {
		const { load } = await import(
			pathToFileURL(path.join(FRONTEND, 'src/routes/trips/[id]/+page.server.ts')).href
		);
		ankuenfte.length = 0;
		await assert.rejects(load(ereignis('../auth/profile')), (e: { status?: number }) => e.status === 404);
		assert.equal(ankuenfte.filter((a) => a.pfad.startsWith('/api/trips/')).length, 0);
	});

	test('Vergleichs-Ansicht: Kennung kodiert, ungueltige Kennung 404', async () => {
		const { load } = await import(
			pathToFileURL(path.join(FRONTEND, 'src/routes/compare/[id]/+page.server.ts')).href
		);
		ankuenfte.length = 0;
		await load(ereignis('v#1'));
		assert.ok(ankuenfte.some((a) => a.pfad === '/api/compare/presets/v%231'));
		ankuenfte.length = 0;
		await assert.rejects(load(ereignis('..')), (e: { status?: number }) => e.status === 404);
		assert.equal(ankuenfte.filter((a) => a.pfad.startsWith('/api/compare/presets/')).length, 0);
	});

	test('Trip anlegen: ?from= wird kodiert, ungueltig wird nicht abgefragt', async () => {
		const { load } = await import(
			pathToFileURL(path.join(FRONTEND, 'src/routes/trips/new/+page.server.ts')).href
		);
		ankuenfte.length = 0;
		await load({
			url: new URL('http://localhost/trips/new?from=' + encodeURIComponent('t1?x=1')),
			cookies: keks({ gz_session: 'sitzung-a' })
		});
		assert.ok(ankuenfte.some((a) => a.pfad === '/api/trips/t1%3Fx=1'));
		ankuenfte.length = 0;
		await load({
			url: new URL('http://localhost/trips/new?from=' + encodeURIComponent('../auth/profile')),
			cookies: keks({ gz_session: 'sitzung-a' })
		});
		assert.equal(ankuenfte.filter((a) => a.pfad.startsWith('/api/trips/')).length, 0);
	});
});
