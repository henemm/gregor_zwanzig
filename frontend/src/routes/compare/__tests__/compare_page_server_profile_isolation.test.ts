// TDD RED — Bugfix "Sende-Dialog nennt das tatsaechliche Versandziel".
// Spec: docs/specs/modules/fix_1471_sende_dialog_ziel.md — AC-5 (Mandantentrennung).
//
// Die exportierte `load()` aus `compare/+page.server.ts` wird ECHT aufgerufen —
// zweimal, mit je eigener Session. Nur die Netzgrenze (`fetch`) ist ersetzt; sie
// antwortet abhaengig vom durchgereichten Cookie. Keine Attrappe des Prueflings,
// kein Dateiinhalt-Grep (routes/page-server.bug395.test.ts ist ausdruecklich KEIN
// Vorbild).
//
// RED heute: `load()` laedt ueberhaupt kein Profil und gibt nur `{ presets }`
// zurueck — `ergebnis.profile` ist `undefined`.
//
// Pfadregel #1409: alle Pfade relativ zu DIESER Datei.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/routes/compare/__tests__/compare_page_server_profile_isolation.test.ts

import { test, describe, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';

register(new URL('./server-load-resolve.hooks.mjs', import.meta.url));

const { load } = (await import('../+page.server.ts')) as any;

const PROFIL: Record<string, Record<string, unknown>> = {
	'sess-anna': { mail_to: 'anna@example.org', email_verified: true, telegram_chat_id: 'A-1' },
	'sess-bodo': { mail_to: 'bodo@example.org', email_verified: true, telegram_chat_id: 'B-9' }
};
const PRESETS: Record<string, unknown[]> = {
	'sess-anna': [{ id: 'cmp-anna', name: 'Annas Vergleich', archived_at: null, location_ids: [] }],
	'sess-bodo': [{ id: 'cmp-bodo', name: 'Bodos Vergleich', archived_at: null, location_ids: [] }]
};

interface Aufruf {
	url: string;
	session: string | null;
}
let aufrufe: Aufruf[] = [];

function sessionAus(init: any): string | null {
	const kopf = init?.headers ?? {};
	const cookie = String(kopf.Cookie ?? kopf.cookie ?? '');
	return cookie.match(/gz_session=([^;]+)/)?.[1] ?? null;
}

const antwort = (body: unknown) => ({ ok: true, status: 200, json: async () => body });
const fehler = (status: number) => ({ ok: false, status, json: async () => ({}) });

async function fetchDouble(input: any, init?: any) {
	const url = String(input);
	const session = sessionAus(init);
	aufrufe.push({ url, session });
	if (!session) return fehler(401);
	if (url.includes('/api/auth/profile')) return antwort(PROFIL[session] ?? {});
	if (url.includes('/api/compare/presets')) return antwort(PRESETS[session] ?? []);
	return fehler(404);
}

const eventFuer = (session: string) => ({
	cookies: { get: (name: string) => (name === 'gz_session' ? session : undefined) },
	fetch: fetchDouble,
	url: new URL('http://localhost/compare'),
	params: {},
	route: { id: '/compare' },
	setHeaders: () => {},
	depends: () => {}
});

let originalFetch: typeof globalThis.fetch;
before(() => {
	originalFetch = globalThis.fetch;
	globalThis.fetch = fetchDouble as unknown as typeof globalThis.fetch;
});
after(() => {
	globalThis.fetch = originalFetch;
});

describe('AC-5: jeder Nutzer bekommt genau sein eigenes Konto-Profil', () => {
	test('load() liefert das Profil der jeweiligen Session', async () => {
		aufrufe = [];
		const anna: any = await load(eventFuer('sess-anna'));
		const bodo: any = await load(eventFuer('sess-bodo'));

		assert.ok(
			anna?.profile,
			'load() gibt kein `profile` zurueck — ohne Konto-Profil kann der Sende-Dialog das ' +
				'tatsaechliche Ziel gar nicht nennen (AC-5, Muster compare/new/+page.server.ts:9-26).'
		);
		assert.equal(
			anna.profile.mail_to,
			'anna@example.org',
			`Nutzer A bekommt nicht seine eigene Adresse: ${JSON.stringify(anna.profile)}`
		);
		assert.equal(
			bodo.profile.mail_to,
			'bodo@example.org',
			`Nutzer B bekommt nicht seine eigene Adresse: ${JSON.stringify(bodo.profile)} — ` +
				'Cross-User-Datenleck.'
		);
	});

	test('die Aufrufreihenfolge veraendert das Ergebnis nicht (kein geteilter Modul-Zustand)', async () => {
		aufrufe = [];
		const ersteA: any = await load(eventFuer('sess-anna'));
		await load(eventFuer('sess-bodo'));
		const zweiteA: any = await load(eventFuer('sess-anna'));

		assert.ok(ersteA?.profile && zweiteA?.profile, 'load() gibt kein `profile` zurueck (AC-5).');
		assert.deepEqual(
			zweiteA.profile,
			ersteA.profile,
			'Der Aufruf fuer Nutzer B hat das Ergebnis fuer Nutzer A veraendert — es existiert ' +
				'geteilter Modul-Zustand zwischen den Sessions (AC-5).'
		);
		assert.equal(zweiteA.profile.mail_to, 'anna@example.org');
	});

	test('der Profil-Abruf traegt die Session des Aufrufers und keinen user_id-Parameter', async () => {
		aufrufe = [];
		await load(eventFuer('sess-anna'));

		const profilAufrufe = aufrufe.filter((a) => a.url.includes('/api/auth/profile'));
		assert.ok(
			profilAufrufe.length >= 1,
			`load() hat GET /api/auth/profile gar nicht abgerufen. Abgerufen wurde: ` +
				`${JSON.stringify(aufrufe.map((a) => a.url))} (AC-5).`
		);
		for (const a of profilAufrufe) {
			assert.equal(
				a.session,
				'sess-anna',
				`Der Profil-Abruf reicht die Session nicht durch (war: ${a.session}) — der Go-Handler ` +
					'leitet die User-ID aus der Session ab (internal/handler/auth.go:512-526).'
			);
			assert.doesNotMatch(
				a.url,
				/user_id=/,
				`Der Profil-Abruf haengt eine user_id an die URL (${a.url}) — das Frontend darf die ` +
					'Nutzer-Identitaet nie selbst behaupten (CLAUDE.md Mandantentrennung).'
			);
		}
	});

	test('die Vergleichsliste bleibt unveraendert und sessiongetrennt', async () => {
		aufrufe = [];
		const anna: any = await load(eventFuer('sess-anna'));
		assert.deepEqual(
			(anna.presets ?? []).map((p: any) => p.id),
			['cmp-anna'],
			'Die bestehende Preset-Ladung hat sich veraendert — der Fix ergaenzt nur das Profil.'
		);
	});
});
