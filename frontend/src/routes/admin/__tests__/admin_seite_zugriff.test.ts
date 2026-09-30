// TDD RED — Issue #2155 S4: Admin-Seite `/admin`, Zugriffsschutz und Datenform.
// Spec: docs/specs/modules/admin_ui_s4.md — AC-2 (Zwei-Nutzer-Test), AC-3 (Datenform).
//
// `load()` aus `admin/+page.server.ts` wird ECHT aufgerufen; nur die Netzgrenze
// (`fetch`) ist ersetzt und stellt das Go-Verhalten nach: Profil mit `role`, Liste
// nur fuer Admins. Vorbild: account/__tests__/premium_sms_link_code_load.test.ts.
//
// RED heute: `admin/+page.server.ts` existiert nicht — der Import scheitert.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/routes/admin/__tests__/admin_seite_zugriff.test.ts

import { test, describe, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';

register(new URL('./server-load-resolve.hooks.mjs', import.meta.url));

const { load } = (await import('../+page.server.ts')) as any;

const ADMIN_LISTE = [
	{
		id: 'u-antrag',
		email: 'antrag@example.org',
		display_name: 'Antragsteller',
		tier: 'free',
		requested_tier: 'premium',
		requested_at: '2026-09-29T10:00:00Z',
		email_verified_at: '2026-09-01T10:00:00Z',
		created_at: '2026-08-01T10:00:00Z',
		disabled: false,
		is_test_user: false,
		last_trip_report_run: { time: '2026-09-30T05:00:00Z', status: 'ok', error: '' }
	},
	{
		id: 'u-ruhig',
		email: 'ruhig@example.org',
		display_name: 'Ruhig',
		tier: 'standard',
		requested_tier: '',
		requested_at: '',
		email_verified_at: '',
		created_at: '2026-08-02T10:00:00Z',
		disabled: true,
		is_test_user: true,
		last_trip_report_run: null
	}
];

/** Sitzung -> Rolle. Zwei verschiedene Nutzer (Mandanten-Pflicht). */
const ROLLE_JE_SITZUNG: Record<string, string> = { 'sess-admin': 'admin', 'sess-user': 'user' };

let aufrufe: string[] = [];

async function fetchDouble(input: any, init?: any) {
	const url = String(input);
	const cookie: string = init?.headers?.Cookie ?? '';
	const sitzung = cookie.replace('gz_session=', '');
	aufrufe.push(`${url} [${sitzung}]`);
	const rolle = ROLLE_JE_SITZUNG[sitzung];
	if (!rolle) return { ok: false, status: 401, json: async () => ({ error: 'unauthorized' }) };
	if (url.includes('/api/auth/profile')) {
		return { ok: true, status: 200, json: async () => ({ id: sitzung, role: rolle }) };
	}
	if (url.includes('/api/admin/users')) {
		if (rolle !== 'admin') {
			return { ok: false, status: 403, json: async () => ({ error: 'forbidden' }) };
		}
		return { ok: true, status: 200, json: async () => ({ users: ADMIN_LISTE }) };
	}
	return { ok: false, status: 404, json: async () => ({}) };
}

const event = (sitzung: string) => ({
	cookies: { get: (name: string) => (name === 'gz_session' ? sitzung : undefined) }
});

let originalFetch: typeof globalThis.fetch;
before(() => {
	originalFetch = globalThis.fetch;
	globalThis.fetch = fetchDouble as unknown as typeof globalThis.fetch;
});
after(() => {
	globalThis.fetch = originalFetch;
});

describe('AC-2: Nicht-Admin wird serverseitig abgewiesen, Admin sieht die Liste', () => {
	test('Nicht-Admin: load() wirft 403 und ruft die Nutzerliste NICHT ab', async () => {
		aufrufe = [];
		let geworfen: any = null;
		try {
			await load(event('sess-user'));
		} catch (e) {
			geworfen = e;
		}
		assert.ok(geworfen, 'load() hat fuer den Nicht-Admin nichts geworfen — Seite waere offen.');
		assert.equal(geworfen.status, 403, `Status ${geworfen?.status} statt 403`);
		assert.ok(
			!aufrufe.some((a) => a.includes('/api/admin/users')),
			`Nutzerliste wurde trotz Nicht-Admin abgerufen: ${aufrufe.join(' | ')}`
		);
	});

	test('Admin: load() liefert die Nutzerliste', async () => {
		aufrufe = [];
		const result: any = await load(event('sess-admin'));
		assert.equal(result?.users?.length, 2, 'Admin erhaelt nicht beide Nutzer');
		assert.deepEqual(
			result.users.map((u: any) => u.id),
			['u-antrag', 'u-ruhig']
		);
	});

	test('ohne Sitzung: abgewiesen, keine Liste', async () => {
		let geworfen: any = null;
		try {
			await load(event('gibt-es-nicht'));
		} catch (e) {
			geworfen = e;
		}
		assert.ok(geworfen, 'Ohne Sitzung darf load() nicht durchlaufen');
		assert.ok([401, 403].includes(geworfen.status), `Status ${geworfen?.status}`);
	});
});

describe('AC-3: Datenform — nur DTO-Felder, offener Antrag bleibt erkennbar', () => {
	test('Zeilen tragen exakt die DTO-Felder, nichts darueber hinaus', async () => {
		const result: any = await load(event('sess-admin'));
		const erlaubt = new Set([
			'id', 'email', 'display_name', 'tier', 'requested_tier', 'requested_at',
			'email_verified_at', 'created_at', 'disabled', 'is_test_user', 'last_trip_report_run'
		]);
		assert.ok(result?.users?.length > 0, 'keine Zeilen geliefert');
		for (const u of result.users) {
			for (const k of Object.keys(u)) {
				assert.ok(erlaubt.has(k), `Feld ausserhalb des DTO: ${k}`);
			}
		}
	});

	test('offener Antrag (requested_tier) und `null`-Lauf kommen unveraendert an', async () => {
		const result: any = await load(event('sess-admin'));
		const antrag = result.users.find((u: any) => u.id === 'u-antrag');
		const ruhig = result.users.find((u: any) => u.id === 'u-ruhig');
		assert.equal(antrag.requested_tier, 'premium');
		assert.equal(ruhig.last_trip_report_run, null);
	});
});
