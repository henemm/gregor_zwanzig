// Onboarding S3 (Issue #2521), AC-20: /hilfe ist nur fuer Eingeloggte erreichbar —
// gemessen im ECHTEN `handle` (Muster hooks.server.oeffentliche_startseite.test.ts).
// Spec: docs/specs/modules/onboarding_standardwerte_hilfe.md
//
// BEWUSST GRUEN schon vor der Umsetzung: `/hilfe` darf nie in `publicPaths`
// landen. Der Test sichert genau das ab (Mutation „/hilfe in publicPaths"
// muss ihn rot machen). Die Seite selbst existiert erst nach der Umsetzung —
// `resolve` ist hier die SvelteKit-Grenze und liefert immer 200.
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/hooks.server.hilfe_nur_eingeloggt.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHmac } from 'node:crypto';
import { register } from 'node:module';

register('../test-env-dynamic-private-stub-hooks.mjs', import.meta.url);

const SECRET = 'a-genuinely-random-forty-char-secret-12';
process.env.GZ_SESSION_SECRET = SECRET;
delete process.env.GZ_TEST_FIXTURE_DIR;

// @ts-expect-error Cache-Busting-Query, zur Laufzeit vom Stub-Hook aufgeloest
const { handle } = await import('./hooks.server.ts?case=hilfe-2521');

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
		return new Response('<html>HILFE</html>', { status: 200, headers: { 'content-type': 'text/html' } });
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

test('AC-20: ohne Sitzung -> Umleitung auf /login, Hilfeinhalt wird nicht ausgeliefert', async () => {
	const r = await rufe('/hilfe');
	assert.equal(r.status, 302);
	assert.equal(r.location, '/login');
	assert.equal(r.aufgeloest, false, 'Seite wurde ohne Sitzung aufgeloest');
});

test('AC-20: ungueltige Sitzung wird wie ausgeloggt behandelt', async () => {
	const r = await rufe('/hilfe', 'x.y.1.deadbeef');
	assert.equal(r.status, 302);
	assert.equal(r.aufgeloest, false);
});

test('AC-20: eingeloggt -> Seite wird ausgeliefert', async () => {
	const r = await rufe('/hilfe', cookieFuer('nutzer-a'));
	assert.equal(r.status, 200);
	assert.equal(r.aufgeloest, true);
});
