// Issue #2961 (FE6): jede Antwort des Frontend-Servers traegt die
// Sicherheits-Kopfzeilen — oeffentliche Seiten, angemeldete Seiten und der
// Durchreicher /api/… —, gemessen im ECHTEN `handle`
// (Muster hooks.server.hilfe_nur_eingeloggt.test.ts).
// Spec: docs/specs/modules/security_haertung_2026_11_frontend.md (AC-4)
// Die Content-Security-Policy selbst setzt SvelteKit (kit.csp); ihr Nachweis
// im Browser steht in e2e/sicherheitsrichtlinie-ohne-verletzung.spec.ts.
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/hooks.server.sicherheitskopfzeilen.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHmac } from 'node:crypto';
import { register } from 'node:module';

register('../test-env-dynamic-private-stub-hooks.mjs', import.meta.url);

const SECRET = 'a-genuinely-random-forty-char-secret-12';
process.env.GZ_SESSION_SECRET = SECRET;
delete process.env.GZ_TEST_FIXTURE_DIR;

// @ts-expect-error Cache-Busting-Query, zur Laufzeit vom Stub-Hook aufgeloest
const { handle } = await import('./hooks.server.ts?case=sicherheitskopfzeilen-2961');

function cookieFuer(userId: string): string {
	const sid = 'sess1';
	const ts = 1700000000;
	const sig = createHmac('sha256', SECRET).update(`${userId}:${sid}:${ts}`).digest('hex');
	return `${userId}.${sid}.${ts}.${sig}`;
}

async function rufe(
	pfad: string,
	cookie?: string
): Promise<{ status: number; location?: string; aufgeloest: boolean; kopf?: Headers }> {
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
		return { status: res.status, aufgeloest, kopf: res.headers };
	} catch (e) {
		const r = e as { status?: number; location?: string };
		if (typeof r.status === 'number') return { status: r.status, location: r.location, aufgeloest };
		throw e;
	}
}

const ERWARTET: Record<string, string> = {
	'x-content-type-options': 'nosniff',
	'referrer-policy': 'strict-origin-when-cross-origin',
	'x-frame-options': 'DENY'
};

function pruefeKopf(kopf: Headers | undefined, wo: string): void {
	assert.ok(kopf, `${wo}: keine Antwort`);
	for (const [name, wert] of Object.entries(ERWARTET)) {
		assert.equal(kopf!.get(name), wert, `${wo}: ${name}`);
	}
	const erlaubnis = kopf!.get('permissions-policy') ?? '';
	assert.match(erlaubnis, /(^|,\s*)geolocation=\(\)/, `${wo}: Geolocation nicht abgeschaltet`);
	assert.match(erlaubnis, /(^|,\s*)camera=\(\)/, `${wo}: Kamera nicht abgeschaltet`);
}

test('AC-4: oeffentliche Seite (Anmeldung) traegt die Kopfzeilen', async () => {
	const r = await rufe('/login');
	assert.equal(r.status, 200);
	pruefeKopf(r.kopf, '/login');
});

test('AC-4: angemeldete Seite traegt die Kopfzeilen', async () => {
	const r = await rufe('/trips', cookieFuer('nutzer-a'));
	assert.equal(r.status, 200);
	pruefeKopf(r.kopf, '/trips');
});

test('AC-4: Antwort des Durchreichers /api/… traegt die Kopfzeilen', async () => {
	const r = await rufe('/api/trips', cookieFuer('nutzer-a'));
	pruefeKopf(r.kopf, '/api/trips');
});

test('AC-4: oeffentliche Startseite ohne Sitzung traegt die Kopfzeilen', async () => {
	const r = await rufe('/');
	assert.equal(r.status, 200);
	pruefeKopf(r.kopf, '/');
});
