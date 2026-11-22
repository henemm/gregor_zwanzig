// Issue #3281 (MCP-Konnektor, Nacharbeit) — nach erfolgreicher Passkey-Anmeldung
// (Knopf und Autofill) geht es auf den per `safeRedirectPath` erlaubten
// Ruecksprung der Anmeldeseite (`/login?redirect=…`), per Vollnavigation
// (`location.assign`, das Ziel kann unter `/api/` liegen); sonst wie bisher auf `/`.
//
// Ersetzt sind nur die Browser-Grenzen, die es unter Node nicht gibt: `fetch`
// (Go-API), `navigator.credentials.get` (Betriebssystem-Dialog) und
// `window.location` (Seitenadresse und Navigation).
//
//   cd frontend && npm test -- src/lib/passkey_ruecksprung.test.ts

import { test, afterEach } from 'node:test';
import assert from 'node:assert/strict';

const { loginWithPasskey, loginWithDiscoverablePasskey } = await import('./passkey.ts');

const AUTHORIZE = '/api/mcp/oauth/authorize?response_type=code&client_id=c_x&state=z';
const leer = new Uint8Array([1, 2, 3]).buffer;
const echt = { fetch: globalThis.fetch, navigator: globalThis.navigator, window: (globalThis as { window?: unknown }).window };

function browser(search: string): string[] {
	const ziele: string[] = [];
	globalThis.fetch = (async (input: RequestInfo | URL) => {
		const pfad = String(input);
		if (pfad.endsWith('/login/begin')) {
			return new Response(JSON.stringify({ publicKey: { challenge: 'AQID', allowCredentials: [] } }), { status: 200 });
		}
		if (pfad.endsWith('/discoverable/begin')) {
			return new Response(JSON.stringify({ publicKey: { challenge: 'AQID' } }), { status: 200 });
		}
		return new Response('{}', { status: 200 });
	}) as typeof fetch;
	const credential = {
		id: 'AQID', rawId: leer, type: 'public-key', authenticatorAttachment: null,
		response: { clientDataJSON: leer, authenticatorData: leer, signature: leer, userHandle: null },
		getClientExtensionResults: () => ({})
	};
	Object.defineProperty(globalThis, 'navigator', {
		value: { credentials: { get: async () => credential } },
		configurable: true
	});
	(globalThis as { window?: unknown }).window = { location: { search, assign: (z: string) => ziele.push(z) } };
	return ziele;
}

afterEach(() => {
	globalThis.fetch = echt.fetch;
	Object.defineProperty(globalThis, 'navigator', { value: echt.navigator, configurable: true });
	(globalThis as { window?: unknown }).window = echt.window;
});

for (const [name, anmelden] of [
	['Knopf', () => loginWithPasskey('anna@beispiel.de')],
	['Autofill', () => loginWithDiscoverablePasskey()]
] as const) {
	test(`${name}: nach der Anmeldung zum Ruecksprung`, async () => {
		const ziele = browser(`?redirect=${encodeURIComponent(AUTHORIZE)}`);
		await anmelden();
		assert.deepEqual(ziele, [AUTHORIZE]);
	});

	test(`${name}: ohne oder mit fremdem Ruecksprung auf /`, async () => {
		for (const search of ['', `?redirect=${encodeURIComponent('https://evil.example')}`, '?redirect=%2F%2Fevil']) {
			const ziele = browser(search);
			await anmelden();
			assert.deepEqual(ziele, ['/'], search);
		}
	});
}
