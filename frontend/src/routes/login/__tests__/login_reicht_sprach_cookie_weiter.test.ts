// Issue #2648 (i18n S3) — AC-6: die Login-Action reicht `gz_lang` aus der
// Set-Cookie-Antwort der Go-API an den Browser weiter (wie `gz_session`).
// Kein Mock-Theater: die Action laeuft ECHT gegen einen echten HTTP-Server auf
// 127.0.0.1, der die Set-Cookie-Header so ausliefert wie die Go-API
// (Muster: login_email_unbestaetigt_verzweigung.test.ts).
// Spec: docs/specs/modules/i18n_s3_sprachumschalter_konto_2648.md
//
//   cd frontend && npm test -- src/routes/login/__tests__/login_reicht_sprach_cookie_weiter.test.ts

import { test, describe, after } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { createServer } from 'node:http';
import type { AddressInfo } from 'node:net';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../../../..');
register(
	pathToFileURL(path.join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

let setCookies: string[] = [];
const goApi = createServer((_req, res) => {
	res.writeHead(200, { 'Content-Type': 'application/json', 'Set-Cookie': setCookies });
	res.end('{}');
});
await new Promise<void>((fertig) => goApi.listen(0, '127.0.0.1', fertig));
process.env.GZ_API_BASE = `http://127.0.0.1:${(goApi.address() as AddressInfo).port}`;
after(() => goApi.close());

const { actions } = await import(
	pathToFileURL(path.join(FRONTEND, 'src/routes/login/+page.server.ts')).href
);

type Gesetzt = { name: string; wert: string; opts: Record<string, unknown> };

async function meldeAn(antwortCookies: string[]): Promise<Gesetzt[]> {
	setCookies = antwortCookies;
	const body = new FormData();
	body.set('username', 'wanderer');
	body.set('password', 'geheim-genug');
	const gesetzt: Gesetzt[] = [];
	const ereignis = {
		request: new Request('http://localhost/login?/login', { method: 'POST', body }),
		cookies: {
			set: (name: string, wert: string, opts: Record<string, unknown>) => gesetzt.push({ name, wert, opts })
		},
		url: new URL('http://localhost/login')
	};
	try {
		await actions.login(ereignis as never);
		assert.fail('Login hat nicht weitergeleitet');
	} catch (e) {
		assert.equal((e as { status?: number }).status, 302, `Login muss weiterleiten: ${e}`);
	}
	return gesetzt;
}

const SESSION = 'gz_session=u1.s1.1700000000.abc; Path=/; HttpOnly; SameSite=Lax';

describe('AC-6: Login reicht gz_lang weiter', () => {
	test('Go setzt gz_session und gz_lang=en: beide Cookies im Browser', async () => {
		const c = await meldeAn([SESSION, 'gz_lang=en; Path=/; Max-Age=31536000; SameSite=Lax']);
		assert.deepEqual(c.map((x) => x.name).sort(), ['gz_lang', 'gz_session']);
		const lang = c.find((x) => x.name === 'gz_lang')!;
		assert.equal(lang.wert, 'en');
		assert.equal(lang.opts.path, '/');
		assert.equal(lang.opts.maxAge, 31536000);
		assert.equal(lang.opts.sameSite, 'lax');
		assert.equal(lang.opts.httpOnly, false);
		assert.equal(c.find((x) => x.name === 'gz_session')!.wert, 'u1.s1.1700000000.abc');
	});

	test('gz_lang vor gz_session in der Antwort: Wert bleibt korrekt', async () => {
		const c = await meldeAn(['gz_lang=de; Path=/', SESSION]);
		assert.equal(c.find((x) => x.name === 'gz_lang')?.wert, 'de');
	});

	// F004: Secure gemaess Spec nur in Produktion (NODE_ENV=production).
	for (const [nodeEnv, soll] of [['production', true], ['development', false]] as const) {
		test(`NODE_ENV=${nodeEnv}: gz_lang secure=${soll}`, async () => {
			const vorher = process.env.NODE_ENV;
			process.env.NODE_ENV = nodeEnv;
			try {
				const c = await meldeAn([SESSION, 'gz_lang=en; Path=/']);
				assert.equal(c.find((x) => x.name === 'gz_lang')?.opts.secure, soll);
			} finally {
				if (vorher === undefined) delete process.env.NODE_ENV;
				else process.env.NODE_ENV = vorher;
			}
		});
	}

	test('ohne gz_lang in der Antwort: kein Sprach-Cookie', async () => {
		const c = await meldeAn([SESSION]);
		assert.deepEqual(
			c.map((x) => x.name),
			['gz_session']
		);
	});
});
