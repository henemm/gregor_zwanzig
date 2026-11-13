// Issue #2961 (FE-U2) — die Code-Anmeldung setzt das Sitzungs-Cookie mit
// `Secure`, sobald NODE_ENV=production gilt ODER die Seite ueber HTTPS laeuft.
//
// Spec: docs/specs/modules/security_haertung_2026_11_frontend.md (AC-6)
// Kein Mock: die echte Action laeuft gegen einen lokalen HTTP-Server, der wie
// die Go-API ein Sitzungs-Cookie ausliefert (Muster:
// routes/login/__tests__/login_reicht_sprach_cookie_weiter.test.ts).
//
//   cd frontend && npm test -- src/routes/magic-link/verify/__tests__/anmelde_cookie_secure.test.ts

import { test, describe, after } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { createServer } from 'node:http';
import type { AddressInfo } from 'node:net';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> verify -> magic-link -> routes -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../../..');
register(
	pathToFileURL(path.join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

const goApi = createServer((_req, res) => {
	res.writeHead(200, {
		'Content-Type': 'application/json',
		'Set-Cookie': 'gz_session=u1.s1.1700000000.abc; Path=/; HttpOnly; SameSite=Lax'
	});
	res.end('{}');
});
await new Promise<void>((fertig) => goApi.listen(0, '127.0.0.1', fertig));
process.env.GZ_API_BASE = `http://127.0.0.1:${(goApi.address() as AddressInfo).port}`;
after(() => goApi.close());

const { actions } = await import(
	pathToFileURL(path.join(FRONTEND, 'src/routes/magic-link/verify/+page.server.ts')).href
);

async function secureBeiAnmeldung(nodeEnv: string, adresse: string): Promise<unknown> {
	const vorher = process.env.NODE_ENV;
	process.env.NODE_ENV = nodeEnv;
	try {
		const body = new FormData();
		body.set('email', 'wanderer@example.com');
		body.set('code', '12345678');
		const gesetzt: Record<string, unknown>[] = [];
		const ereignis = {
			request: new Request(adresse, { method: 'POST', body }),
			cookies: { set: (_n: string, _w: string, opts: Record<string, unknown>) => gesetzt.push(opts) },
			locals: { lang: 'de' },
			url: new URL(adresse)
		};
		try {
			await actions.default(ereignis as never);
			assert.fail('Anmeldung hat nicht weitergeleitet');
		} catch (e) {
			assert.equal((e as { status?: number }).status, 302, `Anmeldung muss weiterleiten: ${e}`);
		}
		assert.equal(gesetzt.length, 1, 'kein Sitzungs-Cookie gesetzt');
		return gesetzt[0].secure;
	} finally {
		if (vorher === undefined) delete process.env.NODE_ENV;
		else process.env.NODE_ENV = vorher;
	}
}

describe('AC-6: Secure-Flag des Sitzungs-Cookies bei der Code-Anmeldung', () => {
	test('HTTPS ohne NODE_ENV=production: secure', async () => {
		assert.equal(await secureBeiAnmeldung('development', 'https://gregor.invalid/magic-link/verify'), true);
	});

	test('NODE_ENV=production auch ueber HTTP (hinter dem Proxy): secure', async () => {
		assert.equal(await secureBeiAnmeldung('production', 'http://localhost/magic-link/verify'), true);
	});

	test('lokale Entwicklung ueber HTTP: nicht secure (sonst keine Anmeldung moeglich)', async () => {
		assert.equal(await secureBeiAnmeldung('development', 'http://localhost/magic-link/verify'), false);
	});
});
