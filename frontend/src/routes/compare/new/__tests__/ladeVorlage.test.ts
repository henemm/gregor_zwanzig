// Issue #2277 Scheibe S2c — Server-Load von /compare/new?from=<id> (AC-6, AC-8).
// Spec: docs/specs/modules/feat_2277_s2c_compare_from_vorlage.md
//
// Gemessen wird der ECHTE `load()` aus +page.server.ts gegen einen Ersatz-`fetch`
// an der Netzgrenze (kein Netz). Geprüft wird, welche Requests er absetzt
// (URL exakt, Session-Cookie exakt) und was er als `vorlage` zurückgibt.
//
// Ausführen:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/routes/compare/new/__tests__/ladeVorlage.test.ts

import { test, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HIER = dirname(fileURLToPath(import.meta.url));
const FRONTEND = resolve(HIER, '../../../../..');
register(
	pathToFileURL(join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

const API = 'http://api.test';
process.env.GZ_API_BASE = API;

const { load } = (await import(pathToFileURL(join(HIER, '..', '+page.server.ts')).href)) as {
	load: (e: unknown) => Promise<Record<string, unknown>>;
};

const PRESETS = `${API}/api/compare/presets/`;
const ORTE = [{ id: 'a', name: 'A' }];
const VORLAGE = { id: 'cmp-1', name: 'Korsika Nord', location_ids: ['a'] };

type Antwort = () => Response;
let presetAntwort: Antwort;
let aufrufe: { url: string; headers: Record<string, string> }[];
const echtesFetch = globalThis.fetch;

const json = (body: unknown, status = 200) =>
	new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

beforeEach(() => {
	aufrufe = [];
	presetAntwort = () => json(VORLAGE);
	globalThis.fetch = (async (url: string, init?: RequestInit) => {
		const u = String(url);
		aufrufe.push({ url: u, headers: (init?.headers ?? {}) as Record<string, string> });
		if (u === `${API}/api/locations`) return json(ORTE);
		if (u === `${API}/api/auth/profile`) return json({ mail: 'a@b.c' });
		if (u.startsWith(PRESETS)) return presetAntwort();
		throw new Error(`unerwarteter Request: ${u}`);
	}) as typeof fetch;
});
afterEach(() => {
	globalThis.fetch = echtesFetch;
});

function aufruf(query: string, session: string | undefined = 'sess-A') {
	return load({
		cookies: { get: (k: string) => (k === 'gz_session' ? session : undefined) },
		url: new URL(`https://gz.test/compare/new${query}`)
	});
}
const presetAufrufe = () => aufrufe.filter((a) => a.url.startsWith(PRESETS));

test('AC-6 eigene Vorlage: exakte URL, Session-Cookie des Nutzers durchgereicht', async () => {
	const daten = await aufruf('?from=cmp-1');
	assert.deepEqual(daten.vorlage, VORLAGE);
	assert.deepEqual(daten.locations, ORTE);
	const p = presetAufrufe();
	assert.equal(p.length, 1);
	assert.equal(p[0].url, `${PRESETS}cmp-1`);
	assert.equal(p[0].headers['Cookie'], 'gz_session=sess-A');
});

test('AC-6 zweiter Nutzer: dessen eigenes Cookie wird gesendet, nie ein fremdes', async () => {
	await aufruf('?from=cmp-1', 'sess-B');
	assert.equal(presetAufrufe()[0].headers['Cookie'], 'gz_session=sess-B');
});

for (const status of [404, 403, 500]) {
	test(`AC-6 Antwort ${status} (fremde/unbekannte ID) => vorlage null, keine Fehlerseite`, async () => {
		presetAntwort = () => json({ error: 'not found' }, status);
		const daten = await aufruf('?from=cmp-fremd');
		assert.strictEqual(daten.vorlage, null);
		assert.deepEqual(daten.locations, ORTE);
	});
}

for (const status of [403, 404]) {
	test(`AC-6 Antwort ${status} MIT gueltigem Vorlagen-Body => vorlage null (Status entscheidet)`, async () => {
		presetAntwort = () => json({ id: 'cmp-A', name: 'Fremd', location_ids: ['a'] }, status);
		const daten = await aufruf('?from=cmp-A');
		assert.strictEqual(daten.vorlage, null);
	});
}

test('AC-6 Netzfehler beim Vorlagen-Abruf => vorlage null, Orte trotzdem geladen', async () => {
	presetAntwort = () => {
		throw new TypeError('fetch failed');
	};
	const daten = await aufruf('?from=cmp-1');
	assert.strictEqual(daten.vorlage, null);
	assert.deepEqual(daten.locations, ORTE);
});

test('AC-6 HTML statt JSON (200) => vorlage null', async () => {
	presetAntwort = () =>
		new Response('<html>Login</html>', { status: 200, headers: { 'Content-Type': 'text/html' } });
	assert.strictEqual((await aufruf('?from=cmp-1')).vorlage, null);
});

test('AC-6 ungueltiges Format (null / ohne location_ids) => vorlage null', async () => {
	presetAntwort = () => json(null);
	assert.strictEqual((await aufruf('?from=cmp-1')).vorlage, null);
	presetAntwort = () => json({ id: 'cmp-1', name: 'X' });
	assert.strictEqual((await aufruf('?from=cmp-1')).vorlage, null);
});

test('AC-8 ohne from: kein Vorlagen-Request, vorlage null', async () => {
	const daten = await aufruf('');
	assert.strictEqual(daten.vorlage, null);
	assert.equal(presetAufrufe().length, 0);
});

test('AC-8 leeres from: kein Vorlagen-Request, vorlage null', async () => {
	const daten = await aufruf('?from=');
	assert.strictEqual(daten.vorlage, null);
	assert.equal(presetAufrufe().length, 0);
});

test('from mit "/" und "?" wird als EIN Pfadsegment kodiert', async () => {
	await aufruf(`?from=${encodeURIComponent('a/../b?x=1')}`);
	const p = presetAufrufe();
	assert.equal(p.length, 1);
	assert.equal(p[0].url, `${PRESETS}a%2F..%2Fb%3Fx%3D1`);
});
