// TDD RED — Issue #2278 (Epic #2345 P3), AC-10 (+ AC-11: Archiv-Ausblendung der Trip-Liste).
// Spec: docs/specs/modules/feat_2278_aktionsmodell.md — Implementation Details 6.
//
// Der Sende-Dialog nennt das Ziel des ANGEMELDETEN Nutzers. Dafuer braucht jede der drei
// Seiten das Konto-Profil. Geprueft wird dort, wo es WIRKT: die ECHTEN `load()`-Funktionen
// von routes/trips/+page.server.ts, routes/trips/[id]/+page.server.ts und
// routes/compare/[id]/+page.server.ts werden aufgerufen — mit zwei Sessions (A und B) und
// ohne Session. Der geteilte Helfer in lib/server/ ist Implementierungsdetail und hier
// bewusst NICHT importiert (sonst koennte /50 ihn bauen und nie einbinden).
// Muster: routes/compare/__tests__/compare_page_server_profile_isolation.test.ts
// Nur die Netzgrenze (`fetch`) ist ersetzt und antwortet abhaengig vom Cookie.
//
// RED heute: alle drei `load()` liefern kein `profile`.
//
// Pfadregel #1409: alle Pfade relativ zu DIESER Datei.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/server/__tests__/profileLoader.test.ts

import { test, describe, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';

register(new URL('../../../routes/compare/__tests__/server-load-resolve.hooks.mjs', import.meta.url));

const tripsListe: any = await import('../../../routes/trips/+page.server.ts');
const tripHub: any = await import('../../../routes/trips/[id]/+page.server.ts');
const compareHub: any = await import('../../../routes/compare/[id]/+page.server.ts');

const PROFIL: Record<string, Record<string, unknown>> = {
	'sess-anna': { mail_to: 'anna@example.org', email_verified: true, telegram_chat_id: 'A-1' },
	'sess-bodo': { mail_to: 'bodo@example.org', email_verified: true, telegram_chat_id: 'B-9' }
};

const TRIPS = [
	{ id: 'aktiv', name: 'Aktiv', stages: [], archived_at: null },
	{ id: 'archiviert', name: 'Archiviert', stages: [], archived_at: '2026-09-01T00:00:00Z' }
];

interface Aufruf {
	url: string;
	session: string | null;
}
let aufrufe: Aufruf[] = [];
let profilFaellt = false;

function sessionAus(init: any): string | null {
	const kopf = init?.headers ?? {};
	const cookie = String(kopf.Cookie ?? kopf.cookie ?? '');
	return cookie.match(/gz_session=([^;]+)/)?.[1] ?? null;
}
const antwort = (body: unknown) =>
	new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } });
const fehler = (status: number) => new Response('{}', { status });

async function fetchDouble(input: any, init?: any) {
	const url = String(input);
	const session = sessionAus(init);
	aufrufe.push({ url, session });
	if (url.includes('/api/auth/profile')) {
		if (!session) return fehler(401);
		if (profilFaellt) throw new TypeError('fetch failed');
		return antwort(PROFIL[session] ?? {});
	}
	// Fachdaten antworten bewusst auch ohne Session: das Profil ist die einzige Variable dieses Tests.
	if (/\/api\/trips\/[^/?]+/.test(url)) return antwort({ id: 'aktiv', name: 'Aktiv', stages: [] });
	if (url.includes('/api/trips')) return antwort(TRIPS);
	if (url.includes('/api/metrics')) return antwort([]);
	if (url.includes('/api/compare/presets/')) return antwort({ id: 'cmp', name: 'V', location_ids: [], schedule: 'daily' });
	if (url.includes('/api/locations')) return antwort([]);
	return fehler(404);
}

const event = (session: string | null, params: Record<string, string> = {}) => ({
	cookies: { get: (name: string) => (name === 'gz_session' && session ? session : undefined) },
	fetch: fetchDouble,
	url: new URL('http://localhost/x'),
	params,
	route: { id: '/x' },
	setHeaders: () => {},
	depends: () => {}
});

const LOADER: Array<[string, () => any, Record<string, string>]> = [
	['routes/trips/+page.server.ts', () => tripsListe.load, {}],
	['routes/trips/[id]/+page.server.ts', () => tripHub.load, { id: 'aktiv' }],
	['routes/compare/[id]/+page.server.ts', () => compareHub.load, { id: 'cmp' }]
];

let originalFetch: typeof globalThis.fetch;
before(() => {
	originalFetch = globalThis.fetch;
	globalThis.fetch = fetchDouble as unknown as typeof globalThis.fetch;
});
after(() => {
	globalThis.fetch = originalFetch;
});

for (const [name, getLoad, params] of LOADER) {
	describe(`AC-10: ${name}`, () => {
		test('zwei Sessions: jeder Nutzer bekommt genau SEIN Profil, nie das des anderen', async () => {
			const anna: any = await getLoad()(event('sess-anna', params));
			const bodo: any = await getLoad()(event('sess-bodo', params));
			assert.equal(anna?.profile?.mail_to, 'anna@example.org', `Nutzer A: ${JSON.stringify(anna?.profile)}`);
			assert.equal(bodo?.profile?.mail_to, 'bodo@example.org', `Nutzer B: ${JSON.stringify(bodo?.profile)}`);
			assert.equal(bodo.profile.telegram_chat_id, 'B-9');
		});

		test('Aufrufreihenfolge aendert nichts (kein geteilter Modul-Zustand)', async () => {
			const erste: any = await getLoad()(event('sess-anna', params));
			await getLoad()(event('sess-bodo', params));
			const zweite: any = await getLoad()(event('sess-anna', params));
			assert.ok(erste?.profile && zweite?.profile, 'load() liefert kein profile');
			assert.deepEqual(zweite.profile, erste.profile);
		});

		test('ohne Session: profile = null, nie ein Rueckfall auf einen anderen/Default-Nutzer', async () => {
			aufrufe = [];
			const ohne: any = await getLoad()(event(null, params));
			assert.ok('profile' in (ohne ?? {}), 'load() liefert das Feld `profile` gar nicht (erwartet: null)');
			assert.equal(ohne.profile, null);
		});

		test('Profil-Abruf traegt die Session des Aufrufers und KEINEN user_id-Parameter', async () => {
			aufrufe = [];
			await getLoad()(event('sess-bodo', params));
			const profilAufrufe = aufrufe.filter((a) => a.url.includes('/api/auth/profile'));
			assert.ok(profilAufrufe.length >= 1, `GET /api/auth/profile wurde nie abgerufen: ${JSON.stringify(aufrufe)}`);
			for (const a of profilAufrufe) {
				assert.equal(a.session, 'sess-bodo');
				assert.doesNotMatch(a.url, /user_id=/);
			}
		});

		test('fail-soft: faellt der Profil-Abruf aus, laedt die Seite trotzdem (profile = null)', async () => {
			profilFaellt = true;
			try {
				const r: any = await getLoad()(event('sess-anna', params));
				assert.ok(r && 'profile' in r, 'load() liefert `profile` nicht');
				assert.equal(r.profile, null);
			} finally {
				profilFaellt = false;
			}
		});
	});
}

describe('AC-11: archivierte Trips erscheinen nicht in der Trip-Liste (wie bei Ortsvergleichen)', () => {
	test('load() von routes/trips/+page.server.ts filtert archived_at != null heraus', async () => {
		const r: any = await tripsListe.load(event('sess-anna'));
		assert.deepEqual(
			(r.trips ?? []).map((t: any) => t.id),
			['aktiv'],
			'archivierter Trip taucht in der Liste auf'
		);
	});
});
