// Issue #2648 (i18n S3) — AC-3/AC-4: Spracheinstellung im Konto.
// Spec: docs/specs/modules/i18n_s3_sprachumschalter_konto_2648.md
//
// Kein Mock-Theater: der Speicherweg der Komponente (`speichereSprache` aus
// dem Modul-Skript von SpracheAuswahl.svelte) laeuft ECHT ueber den echten
// `api`-Client; der echte Layout-Loader (+layout.server.ts) liest danach das
// Profil. Ersetzt ist nur die Netzgrenze: das Test-`fetch` stellt die Go-API je
// Nutzer nach (Profil je Sitzung, Merge des Feldes `language` wie in Go).
//
//   cd frontend && npm test -- src/routes/account/__tests__/sprache_im_konto.test.ts

import { test, describe, after, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { get } from 'svelte/store';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> account -> routes -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../..');
const SRC = path.join(FRONTEND, 'src');
const base = pathToFileURL(FRONTEND + '/').href;
register(pathToFileURL(path.join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href, base);
register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, base);
register(pathToFileURL(path.join(HERE, 'app-navigation-stub-hooks.mjs')).href, base);
process.env.GZ_API_BASE = 'http://go-api.test';

const modul = await import(pathToFileURL(path.join(SRC, 'lib/components/account/SpracheAuswahl.svelte')).href);
const SpracheAuswahl = modul.default;
const speichereSprache: (neu: 'de' | 'en') => Promise<{ meldung: string; fehler: string }> =
	modul.speichereSprache;
const { load: layoutLoad } = await import(pathToFileURL(path.join(SRC, 'routes/+layout.server.ts')).href);
const { locale, trFor } = await import(pathToFileURL(path.join(SRC, 'lib/i18n/index.ts')).href);
const { render } = await import('svelte/server');

// --- Go-API-Nachbildung je Nutzer ------------------------------------------
type Profil = { id: string; display_name: string; language?: string; mail_to?: string };
let profile: Record<string, Profil> = {};
let browserNutzer = 'user-a'; // Sitzung, die der Browser bei relativen Abrufen mitschickt
let putKoerper: { nutzer: string; body: string }[] = [];
let putStatus = 200;

const echterFetch = globalThis.fetch;
globalThis.fetch = (async (url: unknown, init: RequestInit = {}) => {
	const u = String(url);
	const methode = (init.method ?? 'GET').toUpperCase();
	if (methode === 'PUT' && u === '/api/auth/profile') {
		putKoerper.push({ nutzer: browserNutzer, body: String(init.body) });
		if (putStatus !== 200) {
			return new Response('{"code":"invalid_language","message":"x"}', { status: putStatus });
		}
		Object.assign(profile[browserNutzer], JSON.parse(String(init.body)));
		return Response.json(profile[browserNutzer]);
	}
	if (methode === 'GET' && u === 'http://go-api.test/api/auth/profile') {
		const cookie = new Headers(init.headers).get('cookie') ?? '';
		const nutzer = cookie.match(/gz_session=([^;]+)/)?.[1] ?? '';
		const p = profile[nutzer];
		return p ? Response.json({ ...p, language: p.language ?? 'de' }) : new Response('{}', { status: 401 });
	}
	throw new Error(`unerwarteter Abruf ${methode} ${u}`);
}) as typeof fetch;
after(() => {
	globalThis.fetch = echterFetch;
	locale.set('de');
});

beforeEach(() => {
	profile = {
		'user-a': { id: 'user-a', display_name: 'Anna', language: 'de', mail_to: 'a@example.org' },
		'user-b': { id: 'user-b', display_name: 'Bert', language: 'de', mail_to: 'b@example.org' }
	};
	putKoerper = [];
	putStatus = 200;
	browserNutzer = 'user-a';
	locale.set('de');
});

/** Echter Layout-Loader fuer einen angemeldeten Nutzer (Cookie-Lang = de). */
async function layoutLang(nutzer: string): Promise<string> {
	const locals: Record<string, unknown> = { userId: nutzer, lang: 'de' };
	const cookies = { get: (n: string) => (n === 'gz_session' ? nutzer : undefined) };
	const data = await layoutLoad({ locals, cookies } as never);
	return data.lang;
}

describe('AC-3: Nutzer A waehlt Englisch, Nutzer B bleibt Deutsch', () => {
	test('genau {"language":"en"} an PUT /api/auth/profile; A danach en, B weiterhin de', async () => {
		const r = await speichereSprache('en');
		assert.equal(putKoerper.length, 1);
		assert.deepEqual(putKoerper[0], { nutzer: 'user-a', body: '{"language":"en"}' });
		assert.equal(r.fehler, '');
		// A sieht englische Texte: Store und Rueckmeldung in Englisch.
		assert.equal(get(locale), 'en');
		assert.equal(r.meldung, trFor('en', 'konto.sprache.gespeichert'));
		assert.notEqual(r.meldung, trFor('de', 'konto.sprache.gespeichert'));
		assert.equal(await layoutLang('user-a'), 'en');
		assert.equal(await layoutLang('user-b'), 'de');
		// Adressfeld nicht mitgeschickt, darum unveraendert.
		assert.equal(profile['user-a'].mail_to, 'a@example.org');
	});

	test('Auswahl zeigt Titel, beide Optionen und die aktuelle Sprache als gewaehlt', () => {
		locale.set('en');
		const html = render(SpracheAuswahl).body;
		assert.ok(html.includes(trFor('en', 'konto.sprache.titel')));
		assert.ok(html.includes(trFor('en', 'konto.sprache.option_de')));
		assert.ok(html.includes(trFor('en', 'konto.sprache.option_en')));
		assert.match(html, /<option value="en"[^>]*selected/);
		assert.doesNotMatch(html, /<option value="de"[^>]*selected/);
	});
});

describe('AC-4: Speichern scheitert', () => {
	for (const status of [400, 500]) {
		test(`Status ${status}: Fehlertext, Oberflaeche bleibt in der bisherigen Sprache`, async () => {
			putStatus = status;
			const r = await speichereSprache('en');
			assert.equal(r.fehler, trFor('de', 'konto.sprache.fehler'));
			assert.equal(r.meldung, '');
			assert.equal(get(locale), 'de', 'Store darf sich bei Fehler nicht aendern');
			assert.equal(await layoutLang('user-a'), 'de');
		});
	}
});
