// Issue #2520 — oeffentliche Startseite: Routing im ECHTEN `handle`.
// AC-1/2/3/4/11. Spec: docs/specs/modules/oeffentliche_startseite_2520.md
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/hooks.server.oeffentliche_startseite.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHmac } from 'node:crypto';
import { register } from 'node:module';

register('../test-env-dynamic-private-stub-hooks.mjs', import.meta.url);

const SECRET = 'a-genuinely-random-forty-char-secret-12';
process.env.GZ_SESSION_SECRET = SECRET;
delete process.env.GZ_TEST_FIXTURE_DIR;

// @ts-expect-error Cache-Busting-Query, zur Laufzeit vom Stub-Hook aufgeloest
const { handle } = await import('./hooks.server.ts?case=startseite-2520');

function cookieFuer(userId: string): string {
	const sid = 'sess1';
	const ts = 1700000000;
	const sig = createHmac('sha256', SECRET).update(`${userId}:${sid}:${ts}`).digest('hex');
	return `${userId}.${sid}.${ts}.${sig}`;
}

type Ergebnis = { status: number; location?: string; headers?: Headers; locals: Record<string, unknown> };

async function rufe(pfad: string, cookie?: string): Promise<Ergebnis> {
	const url = new URL(`http://localhost${pfad}`);
	const locals: Record<string, unknown> = {};
	const event = {
		url,
		locals,
		cookies: { get: (n: string) => (n === 'gz_session' ? cookie : undefined) }
	};
	const resolve = async () =>
		new Response('<html></html>', { status: 200, headers: { 'content-type': 'text/html' } });
	try {
		const res: Response = await handle({ event, resolve } as unknown as Parameters<typeof handle>[0]);
		return { status: res.status, headers: res.headers, locals };
	} catch (e) {
		const r = e as { status?: number; location?: string };
		if (typeof r.status === 'number') return { status: r.status, location: r.location, locals };
		throw e;
	}
}

test('AC-1: ausgeloggt auf / -> 200, keine Weiterleitung', async () => {
	const r = await rufe('/');
	assert.equal(r.status, 200);
	assert.equal(r.location, undefined);
});

test('AC-2: ausgeloggt auf geschuetzten Pfaden -> 302 /login; nur exakt / offen', async () => {
	for (const p of ['/trips', '/compare', '/admin', '/trips/abc', '/x/', '//', '/archiv', '/landing']) {
		const r = await rufe(p);
		assert.equal(r.status, 302, `${p} muss umleiten`);
		assert.equal(r.location, '/login', `${p} -> /login`);
	}
});

test('AC-2: Query aendert nichts, / bleibt offen', async () => {
	assert.equal((await rufe('/?x=1')).status, 200);
});

test('AC-3: eingeloggt auf / -> Mandant-Header, userId gesetzt', async () => {
	const r = await rufe('/', cookieFuer('nutzer-a'));
	assert.equal(r.status, 200);
	assert.ok(r.headers!.get('x-gz-mandant'), 'Mandant-Header fehlt');
	assert.equal(r.locals.userId, 'nutzer-a');
	const b = await rufe('/', cookieFuer('nutzer-b'));
	assert.notEqual(b.headers!.get('x-gz-mandant'), r.headers!.get('x-gz-mandant'));
});

test('AC-3: ungueltige Sitzung auf / wird wie ausgeloggt behandelt (Startseite, kein userId)', async () => {
	const r = await rufe('/', 'x.y.1.deadbeef');
	assert.equal(r.status, 200);
	assert.equal(r.locals.userId, undefined);
	assert.equal(r.headers!.get('x-gz-mandant'), null);
});

test('AC-4: ausgeloggt auf / -> kein x-gz-mandant, kein userId, no-cache', async () => {
	const r = await rufe('/');
	assert.equal(r.headers!.get('x-gz-mandant'), null);
	assert.equal(r.locals.userId, undefined);
	assert.equal(r.headers!.get('cache-control'), 'no-cache');
});

test('AC-11: /register bleibt ohne Anmeldung erreichbar', async () => {
	const r = await rufe('/register?invite=abc');
	assert.equal(r.status, 200);
});
