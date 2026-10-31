// Issue #2647 (i18n S2) — AC-1 und AC-6: die Sprache wirkt je Anfrage bis ins
// gerenderte HTML. Gemessen wird die ECHTE Kette (keine Mocks):
//   hooks.server.ts `handle` (Cookie/Accept-Language -> locals.lang,
//   transformPageChunk ersetzt %lang% in der echten app.html)
//   -> +layout.server.ts `load` (Profil-`language` ueberschreibt locals.lang)
//   -> +page.server.ts `load`
//   -> +layout.svelte (setzt locale) mit +page.svelte als Kind, svelte/server.
// Ersetzt ist nur die Netzgrenze `fetch` (Profil-/Daten-Abruf an die Go-API)
// und das SvelteKit-`resolve`, das hier die echte app.html befuellt.
// Spec: docs/specs/modules/i18n_s2_frontend_sprachkern_2647.md
//
//   cd frontend && npm test -- src/routes/__tests__/sprache_je_anfrage_ssr.test.ts

import { test, describe, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { createHmac } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { register } from 'node:module';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { FRONTEND, ROUTES, render, Page, ohneKommentare, sichtbar, profilNeu } from './onboardingSsr.ts';

// Nach onboardingSsr registriert = zuerst gefragt: $env/dynamic/private -> process.env.
register(pathToFileURL(path.join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);

const SECRET = 'a-genuinely-random-forty-char-secret-12';
process.env.GZ_SESSION_SECRET = SECRET;
delete process.env.GZ_TEST_FIXTURE_DIR;

const { handle } = (await import(pathToFileURL(path.join(FRONTEND, 'src/hooks.server.ts')).href + '?case=sprache-2647')) as any;
const { load: layoutLoad } = (await import(pathToFileURL(path.join(ROUTES, '+layout.server.ts')).href)) as any;
const { load: pageLoad } = (await import(pathToFileURL(path.join(ROUTES, '+page.server.ts')).href)) as any;
const Layout = (await import(pathToFileURL(path.join(ROUTES, '+layout.svelte')).href)).default;
const Startseite = (await import(pathToFileURL(path.join(ROUTES, '_start/Startseite.svelte')).href)).default;
const { trFor, locale } = (await import(pathToFileURL(path.join(FRONTEND, 'src/lib/i18n/index.ts')).href)) as typeof import('../../lib/i18n/index.ts');

const APP_HTML = readFileSync(path.join(FRONTEND, 'src/app.html'), 'utf-8');

function sitzungFuer(userId: string): string {
	const sid = 'sess1';
	const ts = 1700000000;
	const sig = createHmac('sha256', SECRET).update(`${userId}:${sid}:${ts}`).digest('hex');
	return `${userId}.${sid}.${ts}.${sig}`;
}

// ─── Netzgrenze: Go-API ─────────────────────────────────────────────────────
const PROFIL: Record<string, Record<string, unknown>> = {
	[sitzungFuer('nutzer-a')]: profilNeu({ id: 'nutzer-a', display_name: 'Anna', language: 'en' }),
	[sitzungFuer('nutzer-b')]: profilNeu({ id: 'nutzer-b', display_name: 'Bernd', language: 'de' })
};
async function fetchDouble(input: unknown, init?: { headers?: Record<string, string> }) {
	const url = String(input);
	const sitzung = String(init?.headers?.Cookie ?? '').replace('gz_session=', '');
	if (url.endsWith('/api/auth/profile')) {
		const p = PROFIL[sitzung];
		return p ? { ok: true, status: 200, json: async () => p } : { ok: false, status: 401, json: async () => ({}) };
	}
	if (url.endsWith('/api/trips') || url.endsWith('/api/compare/presets')) {
		return { ok: true, status: 200, json: async () => [] };
	}
	return { ok: false, status: 503, json: async () => ({}) };
}
let originalFetch: typeof globalThis.fetch;
before(() => {
	originalFetch = globalThis.fetch;
	globalThis.fetch = fetchDouble as unknown as typeof globalThis.fetch;
});
after(() => {
	globalThis.fetch = originalFetch;
	locale.set('de');
});

type Anfrage = { sitzung?: string; gzLang?: string; acceptLanguage?: string; kind?: 'seite' | 'startseite' };
type Antwort = { html: string; data: Record<string, any>; locals: Record<string, unknown> };

/** Eine Seitenanfrage auf `/` durch die echte Kette. */
async function anfrage(a: Anfrage): Promise<Antwort> {
	const url = new URL('http://localhost/');
	const headers = new Headers();
	if (a.acceptLanguage) headers.set('accept-language', a.acceptLanguage);
	const jar: Record<string, string | undefined> = { gz_session: a.sitzung, gz_lang: a.gzLang };
	const locals: Record<string, unknown> = {};
	const event = { url, locals, request: new Request(url, { headers }), cookies: { get: (n: string) => jar[n] } };
	let data: Record<string, any> = {};
	const resolve = async (ev: typeof event, opts?: { transformPageChunk?: (x: { html: string; done: boolean }) => string | Promise<string> }) => {
		data = { ...(await layoutLoad({ locals: ev.locals, cookies: ev.cookies })), ...(await pageLoad({ locals: ev.locals, cookies: ev.cookies })) };
		(globalThis as Record<string, unknown>).__gzLayoutTestPath = '/';
		const kind = a.kind === 'startseite' ? (r: unknown) => (Startseite as any)(r, {}) : (r: unknown) => (Page as any)(r, { data });
		const { head, body } = render(Layout, { props: { data, children: kind } });
		let html = APP_HTML.replace('%sveltekit.head%', head).replace('%sveltekit.body%', body);
		if (opts?.transformPageChunk) html = await opts.transformPageChunk({ html, done: true });
		return new Response(html, { status: 200, headers: { 'content-type': 'text/html' } });
	};
	const res: Response = await handle({ event, resolve });
	return { html: ohneKommentare(await res.text()), data, locals };
}

const htmlLang = (html: string) => /<html\b[^>]*\blang="([^"]*)"/.exec(html)?.[1];

describe('AC-1: angemeldet mit Profil language "en", ohne Cookie und Header', () => {
	test('<html lang="en">, data.lang en, englische Katalogtexte im Cockpit', async () => {
		const r = await anfrage({ sitzung: sitzungFuer('nutzer-a') });
		assert.equal(htmlLang(r.html), 'en');
		assert.equal(r.data.lang, 'en');
		assert.equal(r.locals.lang, 'en', 'Layout-Loader schreibt locals.lang zurueck');
		const text = sichtbar(r.html);
		assert.ok(text.includes(trFor('en', 'nav.hilfe')), 'Seitenleiste: englischer Hilfe-Eintrag fehlt');
		assert.ok(text.includes(trFor('en', 'onboarding.willkommen.titel')), 'Willkommen-Titel nicht englisch');
		assert.ok(!text.includes(trFor('de', 'onboarding.willkommen.titel')), 'deutscher Willkommen-Titel sichtbar');
	});
	test('Startseiten-Inhalt in derselben Anfrage: „Sign up" und „Sign in"', async () => {
		const r = await anfrage({ sitzung: sitzungFuer('nutzer-a'), kind: 'startseite' });
		assert.equal(htmlLang(r.html), 'en');
		const text = sichtbar(r.html);
		assert.ok(text.includes('Sign up'), 'Sign up fehlt');
		assert.ok(text.includes('Sign in'), 'Sign in fehlt');
		assert.ok(!text.includes(trFor('de', 'start.cta.register')), 'deutscher Registrieren-Knopf sichtbar');
	});
	test('kein %lang% bleibt im HTML stehen', async () => {
		const r = await anfrage({ sitzung: sitzungFuer('nutzer-a') });
		assert.ok(!r.html.includes('%lang%'));
	});
});

describe('AC-6: drei Anfragen nacheinander, keine uebernimmt den Zustand der vorigen', () => {
	test('Nutzer A (en) -> Nutzer B (de) -> Besucher mit Accept-Language en', async () => {
		const a = await anfrage({ sitzung: sitzungFuer('nutzer-a') });
		// B hat Profil de, aber einen Browser auf Englisch: das Profil gewinnt.
		const b = await anfrage({ sitzung: sitzungFuer('nutzer-b'), acceptLanguage: 'en-US,en;q=0.9' });
		const c = await anfrage({ acceptLanguage: 'en-GB' });

		assert.deepEqual([a.data.lang, b.data.lang, c.data.lang], ['en', 'de', 'en']);
		assert.deepEqual([htmlLang(a.html), htmlLang(b.html), htmlLang(c.html)], ['en', 'de', 'en']);

		const ta = sichtbar(a.html);
		const tb = sichtbar(b.html);
		const tc = sichtbar(c.html);
		assert.ok(ta.includes(trFor('en', 'onboarding.willkommen.titel')), 'A nicht englisch');
		assert.ok(tb.includes(trFor('de', 'onboarding.willkommen.titel')), 'B nicht deutsch');
		assert.ok(!tb.includes(trFor('en', 'onboarding.willkommen.titel')), 'B hat Englisch von A geerbt');
		assert.ok(tb.includes(trFor('de', 'nav.hilfe')), 'B: deutsche Seitenleiste fehlt');
		assert.ok(tc.includes('Sign up') && tc.includes('Sign in'), 'Besucher: englische Startseite fehlt');
		assert.ok(!tc.includes(trFor('de', 'start.cta.login')), 'Besucher: deutscher Text sichtbar');
	});
	test('Besucher ohne Header nach einem englischen Nutzer: Deutsch, byte-gleiche Texte', async () => {
		await anfrage({ sitzung: sitzungFuer('nutzer-a') });
		const d = await anfrage({});
		assert.equal(d.data.lang, 'de');
		assert.equal(htmlLang(d.html), 'de');
		const text = sichtbar(d.html);
		assert.ok(text.includes('Registrieren') && text.includes('Anmelden'));
		assert.ok(!text.includes('Sign up'));
	});
	test('Cookie gz_lang=en gilt fuer Besucher, Profil schlaegt Cookie fuer Angemeldete', async () => {
		const v = await anfrage({ gzLang: 'en' });
		assert.equal(htmlLang(v.html), 'en');
		const b = await anfrage({ sitzung: sitzungFuer('nutzer-b'), gzLang: 'en' });
		assert.equal(htmlLang(b.html), 'de');
		assert.equal(b.data.lang, 'de');
	});
});
