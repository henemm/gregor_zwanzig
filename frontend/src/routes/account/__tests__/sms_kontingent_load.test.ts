// Issue #2412 S4b (Sammel-Issue #2153) — `load()` reicht das SMS-Kontingent durch.
// Spec: docs/specs/modules/sms_daily_usage_anzeige.md — AC-1 (Datenweg), AC-7 (Fail-Soft).
//
// Die echte `load()` aus account/+page.server.ts wird aufgerufen, nur die
// Netzgrenze (`fetch`) ist ersetzt. Muster: premium_sms_link_code_load.test.ts.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/routes/account/__tests__/sms_kontingent_load.test.ts

import { test, describe, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';

register(new URL('./server-load-resolve.hooks.mjs', import.meta.url));

const { load } = (await import('../+page.server.ts')) as any;

const NUTZUNG = {
	sms: { used: 3, limit: 10, reserve: 2 },
	premium_sms: { used: 0, limit: 0, reserve: 3, reply_overshoot: 3 }
};

let antwort: 'ok' | 'no-content' | 'non-ok' | 'network-error' = 'ok';
let abgerufen: string[] = [];

async function fetchDouble(input: any, init?: any) {
	const url = String(input);
	if (url.includes('/api/auth/sms-daily-usage')) {
		abgerufen.push(String(init?.headers?.Cookie ?? ''));
		if (antwort === 'network-error') throw new TypeError('fetch failed');
		if (antwort === 'non-ok') return { ok: false, status: 500, json: async () => ({}) };
		if (antwort === 'no-content') {
			return { ok: true, status: 204, json: async () => { throw new SyntaxError('Unexpected end of JSON input'); } };
		}
		return { ok: true, status: 200, json: async () => structuredClone(NUTZUNG) };
	}
	return { ok: false, status: 404, json: async () => ({}) };
}

const event = () => ({
	cookies: { get: (name: string) => (name === 'gz_session' ? 'sess-2412' : undefined) }
});

let originalFetch: typeof globalThis.fetch;
before(() => {
	originalFetch = globalThis.fetch;
	globalThis.fetch = fetchDouble as unknown as typeof globalThis.fetch;
});
after(() => {
	globalThis.fetch = originalFetch;
});

describe('#2412 S4b — load() liefert smsDailyUsage', () => {
	test('200 → smsDailyUsage ist die Backend-Antwort, abgerufen mit Session-Cookie', async () => {
		antwort = 'ok';
		abgerufen = [];
		const result: any = await load(event());
		assert.deepStrictEqual(result?.smsDailyUsage, NUTZUNG);
		assert.deepStrictEqual(abgerufen, ['gz_session=sess-2412']);
	});

	for (const fall of ['no-content', 'non-ok', 'network-error'] as const) {
		test(`${fall} → smsDailyUsage === null (Fail-Soft, Block bleibt aus)`, async () => {
			antwort = fall;
			const result: any = await load(event());
			assert.ok(result && 'smsDailyUsage' in result, 'load() muss smsDailyUsage zurückgeben.');
			assert.equal(result.smsDailyUsage, null);
		});
	}
});
