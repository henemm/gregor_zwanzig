// Issue #2961 (FE7): die Entwickler-Vorschau /email-preview-dev ist keine
// oeffentliche Seite — ohne Sitzung leitet der ECHTE `handle` auf /login, die
// Route wird gar nicht erst aufgeloest (Muster hooks.server.hilfe_nur_eingeloggt.test.ts).
// Spec: docs/specs/modules/security_haertung_2026_11_frontend.md (AC-7)
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/hooks.server.entwickler_vorschau_nicht_oeffentlich.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHmac } from 'node:crypto';
import { register } from 'node:module';

register('../test-env-dynamic-private-stub-hooks.mjs', import.meta.url);

const SECRET = 'a-genuinely-random-forty-char-secret-12';
process.env.GZ_SESSION_SECRET = SECRET;
delete process.env.GZ_TEST_FIXTURE_DIR;

// @ts-expect-error Cache-Busting-Query, zur Laufzeit vom Stub-Hook aufgeloest
const { handle } = await import('./hooks.server.ts?case=entwickler-vorschau-2961');

function cookieFuer(userId: string): string {
	const sid = 'sess1';
	const ts = 1700000000;
	const sig = createHmac('sha256', SECRET).update(`${userId}:${sid}:${ts}`).digest('hex');
	return `${userId}.${sid}.${ts}.${sig}`;
}

async function rufe(pfad: string, cookie?: string): Promise<{ status: number; location?: string; aufgeloest: boolean }> {
	let aufgeloest = false;
	const url = new URL(`http://localhost${pfad}`);
	const event = {
		url,
		locals: {},
		// Issue #2647: handle liest Accept-Language aus dem Request und gz_lang aus den Cookies.
		request: new Request(url),
		cookies: { get: (n: string) => (n === 'gz_session' ? cookie : undefined) }
	};
	const resolve = async () => {
		aufgeloest = true;
		return new Response('<html>VORSCHAU</html>', { status: 200, headers: { 'content-type': 'text/html' } });
	};
	try {
		const res: Response = await handle({ event, resolve } as unknown as Parameters<typeof handle>[0]);
		return { status: res.status, aufgeloest };
	} catch (e) {
		const r = e as { status?: number; location?: string };
		if (typeof r.status === 'number') return { status: r.status, location: r.location, aufgeloest };
		throw e;
	}
}

test('AC-7: ohne Sitzung -> Umleitung auf /login, die Vorschau wird nicht aufgeloest', async () => {
	const r = await rufe('/email-preview-dev');
	assert.equal(r.status, 302);
	assert.equal(r.location, '/login');
	assert.equal(r.aufgeloest, false, 'Entwickler-Vorschau wurde ohne Sitzung aufgeloest');
});

test('AC-7: die echten Anmeldeseiten bleiben oeffentlich (Gegenprobe)', async () => {
	const r = await rufe('/login');
	assert.equal(r.status, 200);
	assert.equal(r.aufgeloest, true);
});
