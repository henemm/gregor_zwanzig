// Admin-Einladungslinks (Spec admin_einladungslinks_2519), AC-11 + Weiterreichen
// in der Register-Action. load/Action laufen ECHT; nur die globale fetch-Funktion
// (Netzgrenze zur Go-API) ist ersetzt. Die Seite wird echt SSR-gerendert.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/routes/register/__tests__/register_einladung.test.ts

import { test, describe, after } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../../../..');
const base = pathToFileURL(FRONTEND + '/').href;

register(pathToFileURL(path.join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href, base);
register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, base);

const { render } = await import('svelte/server');
const Seite = (await import(pathToFileURL(path.join(FRONTEND, 'src/routes/register/+page.svelte')).href)).default;
const { load, actions } = (await import(
	pathToFileURL(path.join(FRONTEND, 'src/routes/register/+page.server.ts')).href
)) as any;

type Aufruf = { url: string; init?: any };
let aufrufe: Aufruf[] = [];
let antwort: { status: number; koerper: string } = { status: 404, koerper: '{"error":"invite_invalid"}' };
const echterFetch = globalThis.fetch;
globalThis.fetch = (async (url: any, init: any) => {
	aufrufe.push({ url: String(url), init });
	return new Response(antwort.koerper, { status: antwort.status, headers: { 'Content-Type': 'application/json' } });
}) as unknown as typeof fetch;
after(() => {
	globalThis.fetch = echterFetch;
});

const strip = (html: string) => html.replace(/<!--[\s\S]*?-->/g, '');
const loadEvent = (query: string) => ({
	url: new URL('http://localhost/register' + query),
	request: new Request('http://localhost/register' + query)
});
function seite(data: Record<string, unknown>): string {
	return strip(render(Seite, { props: { form: null, data } }).body);
}

describe('register load: Vorab-Check der Einladung', () => {
	test('ohne invite-Parameter: kein Check, Status none', async () => {
		aufrufe = [];
		const d = await load(loadEvent(''));
		assert.equal(d.invite.status, 'none');
		assert.equal(aufrufe.length, 0, 'ohne Parameter darf kein Check abgesetzt werden');
	});

	test('gueltige Einladung: Status valid mit Level und Token', async () => {
		aufrufe = [];
		antwort = { status: 200, koerper: '{"tier":"premium"}' };
		const d = await load(loadEvent('?invite=tok%2F1'));
		assert.equal(d.invite.status, 'valid');
		assert.equal(d.invite.tier, 'premium');
		assert.equal(d.invite.token, 'tok/1');
		// Token nie in der URL (Access-Log), sondern im POST-Body.
		assert.ok(aufrufe[0].url.endsWith('/api/auth/invite/check'), aufrufe[0].url);
		assert.ok(!aufrufe[0].url.includes('tok'), 'Token in der URL');
		assert.equal(aufrufe[0].init.method, 'POST');
		assert.deepEqual(JSON.parse(aufrufe[0].init.body), { token: 'tok/1' });
	});

	for (const [name, status] of [['429 (Limit)', 429], ['500', 500], ['502', 502]] as const) {
		test(`${name}: Status unknown, Token bleibt erhalten (kein stilles Free-Konto)`, async () => {
			antwort = { status, koerper: '{}' };
			const d = await load(loadEvent('?invite=tok-9'));
			assert.equal(d.invite.status, 'unknown');
			assert.equal(d.invite.token, 'tok-9');
		});
	}

	test('Netzfehler beim Check: Status unknown mit Token', async () => {
		const f = globalThis.fetch;
		globalThis.fetch = (async () => {
			throw new Error('Netz weg');
		}) as unknown as typeof fetch;
		try {
			const d = await load(loadEvent('?invite=tok-n'));
			assert.equal(d.invite.status, 'unknown');
			assert.equal(d.invite.token, 'tok-n');
		} finally {
			globalThis.fetch = f;
		}
	});

	test('ungueltige Einladung (404): Status invalid', async () => {
		antwort = { status: 404, koerper: '{"error":"invite_invalid"}' };
		const d = await load(loadEvent('?invite=weg'));
		assert.equal(d.invite.status, 'invalid');
	});
});

describe('register Seite: Einladungs-Hinweis und Google-Knopf (AC-11)', () => {
	test('gueltig: Hinweis mit Level, Hidden-Field invite, Google-Knopf weg', () => {
		const html = seite({ googleEnabled: true, invite: { status: 'valid', tier: 'premium', token: 'abc' } });
		assert.ok(html.includes('Du wurdest eingeladen'), 'Hinweis fehlt');
		assert.ok(html.includes('Level: Premium'), 'Level fehlt');
		assert.match(html, /<input[^>]*name="invite"[^>]*value="abc"|<input[^>]*value="abc"[^>]*name="invite"/);
		assert.ok(!html.includes('Mit Google registrieren'));
	});

	test('ungueltig: klarer Hinweis, normale Registrierung bleibt, kein Hidden-Field, Google weg', () => {
		const html = seite({ googleEnabled: true, invite: { status: 'invalid', token: 'x' } });
		assert.ok(html.includes('Einladung nicht (mehr) gültig'), 'Hinweis fehlt');
		assert.ok(html.includes('name="username"'), 'Formular muss bleiben');
		assert.ok(!/name="invite"/.test(html), 'ungueltiges Token darf nicht mitgesendet werden');
		assert.ok(!html.includes('Mit Google registrieren'));
	});

	test('unknown: Hinweis "nicht geprueft", Hidden-Field BLEIBT, Google weg', () => {
		const html = seite({ googleEnabled: true, invite: { status: 'unknown', token: 'abc' } });
		assert.ok(html.includes('Einladung konnte gerade nicht geprüft werden'), 'Hinweis fehlt');
		assert.ok(html.includes('beim Absenden geprüft'));
		assert.match(html, /<input[^>]*name="invite"[^>]*value="abc"|<input[^>]*value="abc"[^>]*name="invite"/);
		assert.ok(!html.includes('Mit Google registrieren'));
		assert.ok(!html.includes('nicht (mehr) gültig'));
	});

	test('ohne invite: Seite unveraendert, Google-Knopf sichtbar', () => {
		const html = seite({ googleEnabled: true, invite: { status: 'none' } });
		assert.ok(html.includes('Mit Google registrieren'));
		assert.ok(!html.includes('eingeladen'));
		assert.ok(!/name="invite"/.test(html));
	});
});

describe('register Action: invite weiterreichen', () => {
	async function absenden(felder: Record<string, string>) {
		const body = new FormData();
		for (const [k, v] of Object.entries(felder)) body.set(k, v);
		body.set('username', 'neuling');
		body.set('email', 'neuling@example.org');
		body.set('password', 'geheim1234');
		body.set('confirmPassword', 'geheim1234');
		return actions.default({ request: new Request('http://localhost/register', { method: 'POST', body }) });
	}

	test('invite landet im JSON-Body an /api/auth/register', async () => {
		aufrufe = [];
		antwort = { status: 400, koerper: '{}' };
		await absenden({ invite: 'tok-1' });
		assert.equal(JSON.parse(aufrufe[0].init.body).invite, 'tok-1');
	});

	test('ohne invite kein invite-Feld im Body', async () => {
		aufrufe = [];
		antwort = { status: 400, koerper: '{}' };
		await absenden({});
		assert.ok(!('invite' in JSON.parse(aufrufe[0].init.body)));
	});

	test('400 invite_invalid: eigene Meldung statt Pflichtfeld-Text', async () => {
		antwort = { status: 400, koerper: '{"error":"invite_invalid"}' };
		const r = (await absenden({ invite: 'tok-1' })) as { status: number; data: { error: string } };
		assert.equal(r.status, 400);
		assert.match(r.data.error, /Einladung/);
		assert.ok(!/Passwort \(mind/.test(r.data.error));
	});
});
