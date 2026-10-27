// Issue #2520 — Loader von `/`: ohne Sitzung keine Go-API-Aufrufe (AC-4),
// mit Sitzung Cockpit-Daten je Nutzer (AC-3).
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/routes/page-server.oeffentliche_startseite.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';

register('../../test-env-dynamic-private-stub-hooks.mjs', import.meta.url);

const { load } = await import('./+page.server.ts');

const echterFetch = globalThis.fetch;

function cookies(wert?: string) {
	return { get: (n: string) => (n === 'gz_session' ? wert : undefined) };
}

test('AC-4: ohne userId kein einziger fetch, oeffentlich: true', async () => {
	let aufrufe = 0;
	globalThis.fetch = (async () => {
		aufrufe++;
		assert.fail('Go-API darf ohne Sitzung nicht aufgerufen werden');
	}) as typeof fetch;
	try {
		const data = (await load({ locals: {}, cookies: cookies(undefined) } as never)) as Record<string, unknown>;
		assert.equal(aufrufe, 0);
		assert.deepEqual(data, { oeffentlich: true, trips: [], presets: [], cockpitStatus: null });
	} finally {
		globalThis.fetch = echterFetch;
	}
});

test('AC-3: mit userId je Nutzer eigene Daten, oeffentlich: false', async () => {
	globalThis.fetch = (async (url: string, init: { headers: Record<string, string> }) => {
		const wer = init.headers.Cookie;
		const body = String(url).endsWith('/api/trips') ? [{ id: `trip-${wer}` }] : [];
		return new Response(JSON.stringify(body), { status: 200 });
	}) as unknown as typeof fetch;
	try {
		const a = (await load({ locals: { userId: 'a' }, cookies: cookies('A') } as never)) as Record<string, unknown>;
		const b = (await load({ locals: { userId: 'b' }, cookies: cookies('B') } as never)) as Record<string, unknown>;
		assert.equal(a.oeffentlich, false);
		assert.equal(b.oeffentlich, false);
		assert.deepEqual(a.trips, [{ id: 'trip-gz_session=A' }]);
		assert.deepEqual(b.trips, [{ id: 'trip-gz_session=B' }]);
	} finally {
		globalThis.fetch = echterFetch;
	}
});
