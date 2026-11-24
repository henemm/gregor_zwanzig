// Issue #3319 — oeffentliche Funktionsuebersicht /funktionen: Routing im ECHTEN `handle`.
// AC-4 (oeffentlich, ohne userId/Mandant), AC-5 (nur `/` und exakt `/funktionen` offen).
// Spec: docs/specs/modules/oeffentliche_doku_3319.md
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/hooks.server.funktionen_oeffentlich.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHmac } from 'node:crypto';
import { register } from 'node:module';

register('../test-env-dynamic-private-stub-hooks.mjs', import.meta.url);

const SECRET = 'a-genuinely-random-forty-char-secret-12';
process.env.GZ_SESSION_SECRET = SECRET;
delete process.env.GZ_TEST_FIXTURE_DIR;

// @ts-expect-error Cache-Busting-Query, zur Laufzeit vom Stub-Hook aufgeloest
const { handle } = await import('./hooks.server.ts?case=funktionen-3319');

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
		request: new Request(url),
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

test('AC-4: ausgeloggt auf /funktionen -> 200, keine Weiterleitung, kein userId, kein Mandant, no-cache', async () => {
	const r = await rufe('/funktionen');
	assert.equal(r.status, 200);
	assert.equal(r.location, undefined);
	assert.equal(r.locals.userId, undefined);
	assert.equal(r.headers!.get('x-gz-mandant'), null);
	assert.equal(r.headers!.get('cache-control'), 'no-cache');
});

test('AC-4: Query aendert nichts, /funktionen bleibt offen', async () => {
	assert.equal((await rufe('/funktionen?lang=en')).status, 200);
});

test('AC-4: angemeldet auf /funktionen -> 200 mit userId', async () => {
	const r = await rufe('/funktionen', cookieFuer('nutzer-a'));
	assert.equal(r.status, 200);
	assert.equal(r.locals.userId, 'nutzer-a');
});

test('AC-4: ungueltige Sitzung auf /funktionen wird wie ausgeloggt behandelt', async () => {
	const r = await rufe('/funktionen', 'x.y.1.deadbeef');
	assert.equal(r.status, 200);
	assert.equal(r.locals.userId, undefined);
	assert.equal(r.headers!.get('x-gz-mandant'), null);
});

test('AC-5: Nachbarpfade bleiben geschuetzt (302 /login), nur / und exakt /funktionen offen', async () => {
	for (const p of ['/funktionen/x', '/funktionenx', '/funktionen/', '/hilfe', '/account', '/Funktionen']) {
		const r = await rufe(p);
		assert.equal(r.status, 302, `${p} muss umleiten`);
		assert.equal(r.location, '/login', `${p} -> /login`);
	}
	assert.equal((await rufe('/')).status, 200);
	assert.equal((await rufe('/funktionen')).status, 200);
});
