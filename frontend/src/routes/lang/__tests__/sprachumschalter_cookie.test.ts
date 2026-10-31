// Issue #2648 (i18n S3) — AC-1/AC-2: Besucher-Umschalter `POST /lang`.
// Spec: docs/specs/modules/i18n_s3_sprachumschalter_konto_2648.md
//
// Kein Mock-Theater: der ECHTE `POST`-Handler laeuft mit echtem `Request`
// (Formular-Body, Referer). Das Cookie-Objekt ist die Schnittstelle zu
// SvelteKit und merkt sich nur, was der Handler setzt. Danach laeuft das ECHTE
// `handle` mit dem gesetzten Cookie und die ECHTE Startseite wird SSR-gerendert
// (Wirkort: `lang`-Attribut und Startseitentexte beim naechsten Aufruf).
//
//   cd frontend && npm test -- src/routes/lang/__tests__/sprachumschalter_cookie.test.ts

import { test, describe, after } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> lang -> routes -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../..');
const base = pathToFileURL(FRONTEND + '/').href;

register(pathToFileURL(path.join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href, base);
register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, base);
process.env.GZ_SESSION_SECRET = 'a-genuinely-random-forty-char-secret-12';
delete process.env.GZ_TEST_FIXTURE_DIR;

const { POST } = await import(pathToFileURL(path.join(FRONTEND, 'src/routes/lang/+server.ts')).href);
const { handle } = await import(
	pathToFileURL(path.join(FRONTEND, 'src/hooks.server.ts')).href + '?case=sprachumschalter-2648'
);
const { render } = await import('svelte/server');
const Startseite = (
	await import(pathToFileURL(path.join(FRONTEND, 'src/routes/_start/Startseite.svelte')).href)
).default;
const { locale, trFor } = await import(pathToFileURL(path.join(FRONTEND, 'src/lib/i18n/index.ts')).href);
after(() => locale.set('de'));

type Gesetzt = { name: string; wert: string; opts: Record<string, unknown> };

/** Ruft den echten Handler; liefert gesetzte Cookies und die Rueckleitung. */
async function poste(
	lang: string,
	referer: string | null,
	origin = 'http://localhost'
): Promise<{ cookies: Gesetzt[]; status: number; location: string }> {
	const body = new FormData();
	body.set('lang', lang);
	const headers = new Headers();
	if (referer !== null) headers.set('referer', referer);
	const url = new URL(`${origin}/lang`);
	const request = new Request(url, { method: 'POST', body, headers });
	const gesetzt: Gesetzt[] = [];
	const cookies = {
		set: (name: string, wert: string, opts: Record<string, unknown>) => gesetzt.push({ name, wert, opts }),
		get: () => undefined
	};
	try {
		await POST({ request, cookies, url } as never);
	} catch (e) {
		const r = e as { status?: number; location?: string };
		if (typeof r.status === 'number' && typeof r.location === 'string') {
			return { cookies: gesetzt, status: r.status, location: r.location };
		}
		throw e;
	}
	assert.fail('POST /lang hat nicht zurueckgeleitet');
}

/** Naechster Aufruf: echtes handle mit Cookie gz_lang, Seite = echte Startseite. */
async function naechsterAufruf(cookieWert: string): Promise<{ html: string; locals: Record<string, unknown> }> {
	const url = new URL('http://localhost/');
	const locals: Record<string, unknown> = {};
	const event = {
		url,
		locals,
		request: new Request(url),
		cookies: { get: (n: string) => (n === 'gz_lang' ? cookieWert : undefined) }
	};
	const resolve = async (ev: typeof event, opts: { transformPageChunk: (a: { html: string; done: boolean }) => string }) => {
		// So wie +layout.svelte: Store aus der aufgeloesten Sprache.
		locale.set(ev.locals.lang);
		const seite = render(Startseite).body;
		const html = opts.transformPageChunk({ html: `<html lang="%lang%"><body>${seite}</body></html>`, done: true });
		return new Response(html, { status: 200, headers: { 'content-type': 'text/html' } });
	};
	const antwort: Response = await handle({ event, resolve } as never);
	return { html: await antwort.text(), locals };
}

describe('AC-1: Besucher waehlt EN', () => {
	test('Cookie gz_lang=en mit Path=/, Max-Age 1 Jahr, SameSite=Lax, ohne HttpOnly; 303 auf dieselbe Seite', async () => {
		const r = await poste('en', 'http://localhost/?von=start');
		assert.equal(r.cookies.length, 1, 'genau ein Cookie erwartet');
		const c = r.cookies[0];
		assert.equal(c.name, 'gz_lang');
		assert.equal(c.wert, 'en');
		assert.equal(c.opts.path, '/');
		assert.equal(c.opts.maxAge, 31536000);
		assert.equal(c.opts.sameSite, 'lax');
		assert.equal(c.opts.httpOnly, false);
		assert.equal(c.opts.secure, false, 'ohne https kein Secure');
		assert.equal(r.status, 303);
		assert.equal(r.location, '/?von=start');
	});

	test('auf https traegt das Cookie Secure', async () => {
		const r = await poste('de', 'https://gregor20.henemm.com/login', 'https://gregor20.henemm.com');
		assert.equal(r.cookies[0].wert, 'de');
		assert.equal(r.cookies[0].opts.secure, true);
		assert.equal(r.location, '/login');
	});

	test('naechster Aufruf mit dem Cookie: lang="en" und englische Startseitentexte', async () => {
		const r = await poste('en', 'http://localhost/');
		const { html, locals } = await naechsterAufruf(r.cookies[0].wert);
		assert.equal(locals.lang, 'en');
		assert.match(html, /<html lang="en">/);
		const titelEn = trFor('en', 'start.hero.title');
		assert.notEqual(titelEn, trFor('de', 'start.hero.title'), 'Messaufbau: Titel in beiden Sprachen gleich');
		assert.ok(html.includes(titelEn), 'englischer Startseitentitel fehlt');
		assert.ok(!html.includes(trFor('de', 'start.hero.title')), 'deutscher Startseitentitel noch sichtbar');
	});

	test('der Endpunkt ist ohne Anmeldung erreichbar (kein Umweg ueber /login)', async () => {
		const url = new URL('http://localhost/lang');
		const event = {
			url,
			locals: {} as Record<string, unknown>,
			request: new Request(url, { method: 'POST' }),
			cookies: { get: () => undefined }
		};
		let erreicht = false;
		const resolve = async () => {
			erreicht = true;
			return new Response(null, { status: 303, headers: { location: '/' } });
		};
		try {
			await handle({ event, resolve } as never);
		} catch (e) {
			assert.fail(`handle leitete um statt durchzulassen: ${(e as { location?: string }).location}`);
		}
		assert.ok(erreicht, 'POST /lang erreicht den Endpunkt nicht');
	});
});

describe('AC-2: Negativfaelle', () => {
	test('ungueltiger Wert fr: kein Cookie, Rueckleitung trotzdem', async () => {
		const r = await poste('fr', 'http://localhost/register');
		assert.equal(r.cookies.length, 0, 'fr darf kein Cookie setzen');
		assert.equal(r.status, 303);
		assert.equal(r.location, '/register');
	});

	test('fremder Referer: Rueckleitung auf / statt auf die fremde Adresse', async () => {
		const r = await poste('en', 'https://boese.example/x');
		assert.equal(r.status, 303);
		assert.equal(r.location, '/');
	});

	// F001: gleicher Ursprung, aber Pfad, den der Browser als fremden Host deutet.
	for (const referer of ['http://localhost//evil.com/x', 'http://localhost/\\evil.com']) {
		test(`Referer ${referer}: Rueckleitung auf / (keine offene Weiterleitung)`, async () => {
			const r = await poste('en', referer);
			assert.equal(r.status, 303);
			assert.equal(r.location, '/');
		});
	}

	test('fehlender Referer: Rueckleitung auf /', async () => {
		const r = await poste('en', null);
		assert.equal(r.location, '/');
	});
});
