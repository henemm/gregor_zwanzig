// Issue #1969 Fix-Loop 1 (Adversary F002) — Startseite: der nächste Versand
// kommt aus GET /api/next-briefings (Loader) und erscheint dort, wo er WIRKT:
// Trip-Hero „Was geht raus", Vergleichs-Hero (Stat + Timeline) und die Zeile
// „Außerdem beobachtet" (seit #2346 S2 die gemeinsame SubscriptionKachel).
// Spec: docs/specs/modules/feat_1969_naechstes_briefing.md (AC-23)
//
// (d) echter Loader (+page.server.ts) mit aufzeichnendem fetch-Stub;
// (e) echte Startseite (svelte/server) mit `data.nextBriefings`.
//
// Ausführen:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/routes/__tests__/startseite_naechstes_briefing.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { pathToFileURL } from 'node:url';
import path from 'node:path';
import { FRONTEND, ROUTES, renderStartseite, aktiverVergleich, sichtbar } from './onboardingSsr.ts';

register(pathToFileURL(path.join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
const { load } = await import(pathToFileURL(path.join(ROUTES, '+page.server.ts')).href);

const NB = (local_time: string, slot = 'morning') => ({
	at: `2026-10-22T${local_time}:00+02:00`,
	local_date: '2026-10-22',
	local_time,
	tz: 'Europe/Paris',
	tz_abbr: 'CEST',
	slot
});

const cookies = { get: (n: string) => (n === 'gz_session' ? 'S' : undefined) };

async function ladeMit(antwort: (url: string) => Response | Promise<Response>) {
	const echt = globalThis.fetch;
	const urls: string[] = [];
	globalThis.fetch = (async (u: string) => (urls.push(String(u)), antwort(String(u)))) as unknown as typeof fetch;
	try {
		const data = (await load({ locals: { userId: 'u1' }, cookies } as never)) as Record<string, any>;
		return { data, urls };
	} finally {
		globalThis.fetch = echt;
	}
}
const json = (b: unknown, status = 200) => new Response(JSON.stringify(b), { status });

describe('(d) Loader: /api/next-briefings → data.nextBriefings', () => {
	const NBS = { trips: { t1: NB('08:00') }, compare: { p1: NB('07:00') } };

	test('ruft /api/next-briefings auf und reicht das Ergebnis durch', async () => {
		const { data, urls } = await ladeMit((u) =>
			u.endsWith('/api/next-briefings') ? json(NBS) : u.endsWith('/api/trips') ? json([{ id: 't1' }]) : json([])
		);
		assert.ok(urls.some((u) => new URL(u).pathname === '/api/next-briefings'), `kein Abruf: ${urls.join(', ')}`);
		assert.deepEqual(data.nextBriefings, NBS);
		assert.deepEqual(data.trips, [{ id: 't1' }]);
	});

	test('Fehler (500 / Netz) → null, Seite bleibt intakt', async () => {
		for (const fehler of [() => json({}, 500), () => Promise.reject(new Error('down'))]) {
			const { data } = await ladeMit((u) =>
				u.endsWith('/api/next-briefings') ? fehler() : u.endsWith('/api/trips') ? json([{ id: 't1' }]) : json([])
			);
			assert.equal(data.nextBriefings, null);
			assert.equal(data.oeffentlich, false);
			assert.deepEqual(data.trips, [{ id: 't1' }]);
		}
	});
});

// Trip mit heutiger Etappe ⇒ Hero-Modus „trip"; Morgen 08:00 laut report_config.
function heuteTrip() {
	const heute = new Date();
	const iso = `${heute.getFullYear()}-${String(heute.getMonth() + 1).padStart(2, '0')}-${String(heute.getDate()).padStart(2, '0')}`;
	return {
		id: 't1',
		name: 'Testtrip',
		stages: [{ id: 's1', name: 'E1', date: iso, waypoints: [] }],
		report_config: { enabled: true, morning_enabled: true, evening_enabled: false, morning_time: '08:00:00', send_email: true },
		display_config: {}
	};
}

describe('(e) Startseite zeigt den Wert aus data.nextBriefings', () => {
	test('Trip-Hero „Was geht raus" + „Außerdem beobachtet" (Vergleichs-Kachel, #2346 S2)', () => {
		const html = renderStartseite({
			trips: [heuteTrip()],
			presets: [aktiverVergleich('p1')],
			nextBriefings: { trips: { t1: NB('08:00') }, compare: { p1: NB('07:00') } }
		});
		const t = sichtbar(html);
		assert.ok(t.includes('Was geht raus'), 'Messaufbau: Trip-Hero fehlt');
		assert.ok(t.includes('08:00 (CEST)'), `Trip-Wert aus dem Backend fehlt: ${t}`);
		assert.ok(t.includes('Do 07:00 (CEST)'), `Vergleichs-Kachel zeigt den Backend-Wert nicht: ${t}`);
	});

	test('Vergleichs-Hero: Stat „Nächster Versand" und Timeline „Nächster · …"', () => {
		const html = renderStartseite({
			trips: [],
			presets: [aktiverVergleich('p1')],
			nextBriefings: { trips: {}, compare: { p1: NB('07:00') } }
		});
		const t = sichtbar(html);
		assert.ok(t.includes('Nächster · Do 07:00 (CEST)'), `Timeline-Zeile fehlt: ${t}`);
		assert.ok(/Nächster Versand\s+Do 07:00 \(CEST\)/.test(t), `Hero-Stat zeigt den Backend-Wert nicht: ${t}`);
	});

	test('ohne Backend-Wert: „—", keine erfundene Zeit', () => {
		const html = renderStartseite({ trips: [], presets: [aktiverVergleich('p1')], nextBriefings: null });
		const t = sichtbar(html);
		assert.ok(/Nächster Versand\s+—/.test(t), t);
		assert.ok(!t.includes('Nächster ·'), t);
	});
});
