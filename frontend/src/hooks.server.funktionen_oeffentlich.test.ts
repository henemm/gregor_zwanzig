// Issue #3319 — oeffentliche Funktionsuebersicht /funktionen + neun Unterseiten
// /funktionen/<slug>: Routing im ECHTEN `handle`.
// AC-4 (oeffentlich, ohne userId/Mandant, auch fuer Angemeldete erreichbar),
// AC-5 (nur `/`, exakt `/funktionen` und exakt die Pfade der Seitenliste offen;
// die Pfadmenge stammt aus derselben Seitenliste wie Navigation und Uebersicht).
// Spec: docs/specs/modules/oeffentliche_doku_3319.md (v1.1)
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
// Seitenliste ist die einzige Quelle der Unterseiten; fehlt sie, scheitern die
// Faelle einzeln mit klarer Meldung statt am Modul-Import.
let FUNKTIONEN_SEITEN: unknown = undefined;
let ladeFehler = '';
try {
	({ FUNKTIONEN_SEITEN } = await import('./lib/funktionen_seiten.ts'));
} catch (e) {
	ladeFehler = String(e);
}

/** Reihenfolge laut Spec, Implementation Details „Seitenstruktur“ (1–9). */
const SOLL_SLUGS = [
	'trips',
	'briefings',
	'alarme',
	'ortsvergleich',
	'kanaele',
	'befehle',
	'wetterdaten',
	'konto',
	'level'
] as const;

function slugs(): string[] {
	assert.ok(Array.isArray(FUNKTIONEN_SEITEN), `frontend/src/lib/funktionen_seiten.ts fehlt/exportiert FUNKTIONEN_SEITEN nicht ${ladeFehler}`);
	return (FUNKTIONEN_SEITEN as ReadonlyArray<{ slug: string }>).map((s) => s.slug);
}

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

test('AC-5: Seitenliste enthaelt genau die neun Slugs in der Reihenfolge der Spec', () => {
	assert.deepEqual(slugs(), [...SOLL_SLUGS]);
});

/** Alle zehn Funktions-Pfade: Uebersicht + je Slug der Seitenliste. */
const FUNKTIONS_PFADE = (): string[] => ['/funktionen', ...slugs().map((s) => `/funktionen/${s}`)];

test('AC-4: ausgeloggt auf /funktionen und jeder Unterseite -> 200, kein userId, kein Mandant, no-cache', async () => {
	const pfade = FUNKTIONS_PFADE();
	assert.equal(pfade.length, 10, 'Messaufbau: zehn Funktions-Pfade erwartet');
	for (const p of pfade) {
		const r = await rufe(p);
		assert.equal(r.status, 200, `${p} muss ohne Login offen sein`);
		assert.equal(r.location, undefined, `${p}: keine Weiterleitung`);
		assert.equal(r.locals.userId, undefined, `${p}: kein userId`);
		assert.equal(r.headers!.get('x-gz-mandant'), null, `${p}: kein Mandant-Header`);
		assert.equal(r.headers!.get('cache-control'), 'no-cache', `${p}: no-cache`);
	}
});

test('AC-4: Query aendert nichts, Uebersicht und Unterseite bleiben offen', async () => {
	assert.equal((await rufe('/funktionen?lang=en')).status, 200);
	assert.equal((await rufe('/funktionen/level?lang=en')).status, 200);
});

test('AC-4: angemeldet auf /funktionen und jeder Unterseite -> 200 mit userId', async () => {
	for (const p of FUNKTIONS_PFADE()) {
		const r = await rufe(p, cookieFuer('nutzer-a'));
		assert.equal(r.status, 200, p);
		assert.equal(r.locals.userId, 'nutzer-a', p);
	}
});

test('AC-4: ungueltige Sitzung auf einer Unterseite wird wie ausgeloggt behandelt', async () => {
	for (const p of ['/funktionen', '/funktionen/trips']) {
		const r = await rufe(p, 'x.y.1.deadbeef');
		assert.equal(r.status, 200, p);
		assert.equal(r.locals.userId, undefined, p);
		assert.equal(r.headers!.get('x-gz-mandant'), null, p);
	}
});

test('AC-5: Nachbarpfade bleiben geschuetzt (302 /login)', async () => {
	for (const p of [
		'/funktionen/unbekannt',
		'/funktionen/trips/x',
		'/funktionen/level/',
		'/funktionen/Trips',
		'/funktionenx',
		'/funktionen/',
		'/Funktionen',
		'/hilfe',
		'/account'
	]) {
		const r = await rufe(p);
		assert.equal(r.status, 302, `${p} muss umleiten`);
		assert.equal(r.location, '/login', `${p} -> /login`);
	}
	assert.equal((await rufe('/')).status, 200);
});
