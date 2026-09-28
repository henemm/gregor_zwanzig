// TDD RED — Issue #2155 Scheibe S2 (Admin-Rolle), AC-8 + Frontend-Umstellung
// der Konto-Karte auf GET /api/scheduler/status/me.
// Spec: docs/specs/modules/admin_rolle_s2_status_token.md, Abschnitt 8.
//
// Teil 1 — reine Funktion `lastRunDot` (neu, frontend/src/routes/account/
// schedulerLastRun.ts): leitet den Farbpunkt der Konto-Karte aus `last_run`
// ab. Vertrag:
//   null / undefined / ohne time      -> 'none'    (grau, "Zuletzt: —")
//   status 'ok'                       -> 'ok'      (gruen)
//   status 'error'                    -> 'error'   (rot)
//   jeder andere Status (partial, budget, skipped_in_flight, not_reached,
//   kuenftige Werte)                  -> 'neutral' (weder gruen noch rot)
// RED heute: die Datei existiert nicht (Import scheitert).
//
// Teil 2 — `load()` aus account/+page.server.ts wird ECHT aufgerufen, nur die
// Netzgrenze (`fetch`) ist ersetzt. Der Stub unterscheidet EXAKT zwischen
// `/api/scheduler/status/me` und dem nackten `/api/scheduler/status` (ein
// `includes('/api/scheduler/status')` traefe beide und bewiese nichts).
// RED heute: load() ruft den nackten Pfad ab.
//
// Bekannter Punkt fuer die Adversary-Mutationsprobe in /50: ob +page.svelte
// die Funktion `lastRunDot` tatsaechlich fuer den Punkt benutzt, prueft
// dieser Test NICHT (keine Svelte-Render-Umgebung, kein Dateiinhalt-Grep).
//
// Pfadregel #1409: alle Pfade relativ zu DIESER Datei.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/routes/account/__tests__/scheduler-status-me-render.test.ts

import { test, describe, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

register(new URL('./server-load-resolve.hooks.mjs', import.meta.url));

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ACCOUNT = path.resolve(HERE, '..');

type Dot = 'ok' | 'error' | 'neutral' | 'none';

describe('#2155 S2 AC-8 — Farbpunkt der Konto-Karte aus last_run', async () => {
	const { lastRunDot } = (await import(
		pathToFileURL(path.join(ACCOUNT, 'schedulerLastRun.ts')).href
	)) as { lastRunDot: (lastRun: unknown) => Dot };

	test('last_run: null -> none (kein Absturz, "Zuletzt: —")', () => {
		assert.equal(lastRunDot(null), 'none');
		assert.equal(lastRunDot(undefined), 'none');
	});

	test('ok -> gruen, error -> rot', () => {
		assert.equal(lastRunDot({ time: '2026-09-27T10:00:00Z', status: 'ok', error: '' }), 'ok');
		assert.equal(lastRunDot({ time: '2026-09-27T10:00:00Z', status: 'error', error: 'x' }), 'error');
	});

	for (const status of ['partial', 'budget', 'skipped_in_flight', 'not_reached', 'kuenftig_neu']) {
		test(`${status} -> neutral (weder gruen noch rot, nicht "kein Lauf")`, () => {
			assert.equal(
				lastRunDot({ time: '2026-09-27T10:00:00Z', status, error: '' }),
				'neutral'
			);
		});
	}
});

describe('#2155 S2 — load() liest den eigenen Status ueber /api/scheduler/status/me', () => {
	const ME_PAYLOAD = { jobs: [{ id: 'trip_reports_hourly', name: 'me', next_run: 'n', last_run: null }] };
	const VOLL_PAYLOAD = { jobs: [{ id: 'trip_reports_hourly', name: 'VOLLSTATUS' }], running: true };
	const aufgerufen: string[] = [];

	let originalFetch: typeof globalThis.fetch;
	before(() => {
		originalFetch = globalThis.fetch;
		globalThis.fetch = (async (input: any) => {
			const url = new URL(String(input), 'http://localhost');
			aufgerufen.push(url.pathname);
			if (url.pathname === '/api/scheduler/status/me') {
				return { ok: true, status: 200, json: async () => ME_PAYLOAD };
			}
			if (url.pathname === '/api/scheduler/status') {
				return { ok: true, status: 200, json: async () => VOLL_PAYLOAD };
			}
			return { ok: false, status: 404, json: async () => ({}) };
		}) as unknown as typeof globalThis.fetch;
	});
	after(() => {
		globalThis.fetch = originalFetch;
	});

	test('scheduler kommt aus /status/me, der nackte /status-Pfad wird nie abgerufen', async () => {
		const { load } = (await import('../+page.server.ts')) as any;
		const result: any = await load({
			cookies: { get: (n: string) => (n === 'gz_session' ? 'sess-1' : undefined) }
		});
		assert.deepEqual(result?.scheduler, ME_PAYLOAD, 'data.scheduler muss die /status/me-Antwort sein');
		assert.ok(
			!aufgerufen.includes('/api/scheduler/status'),
			`load() darf den tokengeschuetzten Vollstatus nicht abrufen, aufgerufen: ${aufgerufen.join(', ')}`
		);
	});
});
