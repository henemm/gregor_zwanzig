// Issue #2647 (i18n S2) — AC-2: Sprachaufloesung Cookie `gz_lang` >
// `Accept-Language` > `de`, einmal gegen die reine Funktion `resolveLang` und
// einmal gegen das ECHTE `handle` aus hooks.server.ts (Wirkort `locals.lang`).
// Spec: docs/specs/modules/i18n_s2_frontend_sprachkern_2647.md
//
//   cd frontend && npm test -- src/lib/i18n/__tests__/sprachaufloesung.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { resolveLang, parseAcceptLanguage } from '../resolveLang.ts';

register('../../../../test-env-dynamic-private-stub-hooks.mjs', import.meta.url);
process.env.GZ_SESSION_SECRET = 'a-genuinely-random-forty-char-secret-12';
delete process.env.GZ_TEST_FIXTURE_DIR;

// @ts-expect-error Cache-Busting-Query, zur Laufzeit vom Stub-Hook aufgeloest
const { handle } = await import('../../../hooks.server.ts?case=sprachaufloesung-2647');

type Fall = { name: string; cookie?: string; acceptLanguage?: string; soll: 'de' | 'en' };

const FAELLE: Fall[] = [
	{ name: 'Accept-Language en-GB ergibt en', acceptLanguage: 'en-GB,en;q=0.9', soll: 'en' },
	{ name: 'Accept-Language fr-FR ergibt de', acceptLanguage: 'fr-FR,fr;q=0.9', soll: 'de' },
	{ name: 'Cookie de schlaegt Accept-Language en', cookie: 'de', acceptLanguage: 'en', soll: 'de' },
	{ name: 'ungueltiges Cookie xx faellt auf den Header zurueck', cookie: 'xx', acceptLanguage: 'en-US', soll: 'en' },
	{ name: 'ohne Cookie und Header ergibt de', soll: 'de' }
];

describe('AC-2: resolveLang (reine Funktion)', () => {
	for (const f of FAELLE) {
		test(f.name, () => {
			assert.equal(resolveLang({ cookie: f.cookie, acceptLanguage: f.acceptLanguage }), f.soll);
		});
	}
	test('Cookie en ohne Header ergibt en; null-Werte sind erlaubt', () => {
		assert.equal(resolveLang({ cookie: 'en', acceptLanguage: null }), 'en');
		assert.equal(resolveLang({ cookie: undefined, acceptLanguage: null }), 'de');
	});
	test('parseAcceptLanguage nimmt den ersten unterstuetzten Eintrag', () => {
		assert.equal(parseAcceptLanguage('fr-FR, en;q=0.8, de;q=0.7'), 'en');
		assert.equal(parseAcceptLanguage('fr-CH, de-CH;q=0.9'), 'de');
		assert.equal(parseAcceptLanguage('it, es'), null);
		assert.equal(parseAcceptLanguage(''), null);
		assert.equal(parseAcceptLanguage(null), null);
	});
});

async function localsNach(f: Fall): Promise<Record<string, unknown>> {
	const url = new URL('http://localhost/');
	const headers = new Headers();
	if (f.acceptLanguage) headers.set('accept-language', f.acceptLanguage);
	const locals: Record<string, unknown> = {};
	const event = {
		url,
		locals,
		request: new Request(url, { headers }),
		cookies: { get: (n: string) => (n === 'gz_lang' ? f.cookie : undefined) }
	};
	const resolve = async () =>
		new Response('<html lang="%lang%"></html>', { status: 200, headers: { 'content-type': 'text/html' } });
	await handle({ event, resolve } as unknown as Parameters<typeof handle>[0]);
	return locals;
}

describe('AC-2: das echte handle setzt locals.lang', () => {
	for (const f of FAELLE) {
		test(f.name, async () => {
			assert.equal((await localsNach(f)).lang, f.soll);
		});
	}
});
