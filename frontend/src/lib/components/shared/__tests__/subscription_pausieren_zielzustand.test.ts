// Fix-Loop 1 — Issue #2278, F009 (AC-7): setPaused(kind, id, paused) setzt den ZIELZUSTAND und
// schaltet nicht um. Der Ortsvergleich-Zweig kehrte bisher den frischen Stand um: zeigte die Liste
// „Pausieren", der Server war aber schon pausiert (zweiter Tab / Auto-Pause), wurde FORTGESETZT.
//
// Echtes Verhalten gegen einen In-Memory-Server (GET liefert den Stand, PUT fuehrt den JSON-Body
// per Merge ein — wie der Go-Store). Die Assertions lesen den Serverzustand.
//
// Pfadregel #1409: relativ zu DIESER Datei.
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/__tests__/subscription_pausieren_zielzustand.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const { setPaused } = (await import(pathToFileURL(path.join(HERE, '..', 'subscriptionExec.ts')).href)) as any;

type Aufruf = { method: string; url: string; body?: Record<string, unknown> };

function baueServer(start: Record<string, unknown>) {
	const stand: Record<string, unknown> = { ...start };
	const aufrufe: Aufruf[] = [];
	const fetchFn = (async (url: string, init?: any) => {
		const method = String(init?.method ?? 'GET');
		const body = init?.body ? JSON.parse(init.body) : undefined;
		aufrufe.push({ method, url, body });
		if (method === 'PUT') Object.assign(stand, body);
		return new Response(JSON.stringify(stand), { status: 200 });
	}) as unknown as typeof fetch;
	return { stand, aufrufe, fetchFn };
}

const aktiv = () => ({
	id: 'c1',
	name: 'Frisch',
	schedule: 'daily',
	previous_schedule: 'daily',
	corridors: [{ metric: 'snow_depth_cm', range: [50, null] }],
	unbekanntes_feld: { bleibt: true }
});

describe('F009: Ortsvergleich-setPaused setzt den Zielzustand, schaltet nicht um', () => {
	test('zweimal setPaused(true): danach pausiert', async () => {
		const s = baueServer(aktiv());
		await setPaused('vergleich', 'c1', true, s.fetchFn);
		assert.equal(s.stand.schedule, 'manual');
		await setPaused('vergleich', 'c1', true, s.fetchFn);
		assert.equal(s.stand.schedule, 'manual', 'zweites Pausieren hat fortgesetzt');
	});

	test('zweites Pausieren zerstoert den gemerkten Zeitplan nicht: Fortsetzen stellt ihn wieder her', async () => {
		const s = baueServer({ ...aktiv(), schedule: 'weekly', previous_schedule: 'weekly' });
		await setPaused('vergleich', 'c1', true, s.fetchFn);
		await setPaused('vergleich', 'c1', true, s.fetchFn);
		assert.equal(s.stand.previous_schedule, 'weekly');
		await setPaused('vergleich', 'c1', false, s.fetchFn);
		assert.equal(s.stand.schedule, 'weekly');
	});

	test('zweimal setPaused(false) auf laufendem Vergleich: bleibt laufend', async () => {
		const s = baueServer(aktiv());
		await setPaused('vergleich', 'c1', false, s.fetchFn);
		await setPaused('vergleich', 'c1', false, s.fetchFn);
		assert.equal(s.stand.schedule, 'daily');
	});

	test('Pausieren und Fortsetzen: Rundreise liefert den Ausgangszustand', async () => {
		const s = baueServer(aktiv());
		await setPaused('vergleich', 'c1', true, s.fetchFn);
		await setPaused('vergleich', 'c1', false, s.fetchFn);
		assert.equal(s.stand.schedule, 'daily');
		assert.equal(s.stand.previous_schedule, 'daily');
	});

	test('Read-Modify-Write: PUT-Body hat NUR { schedule, previous_schedule }, Fremdfelder bleiben', async () => {
		const s = baueServer(aktiv());
		await setPaused('vergleich', 'c1', true, s.fetchFn);
		const put = s.aufrufe.find((a) => a.method === 'PUT')!;
		assert.deepEqual(Object.keys(put.body!).sort(), ['previous_schedule', 'schedule']);
		assert.deepEqual(s.stand.corridors, aktiv().corridors);
		assert.deepEqual(s.stand.unbekanntes_feld, { bleibt: true });
		assert.equal(s.stand.name, 'Frisch');
	});

	test('der PUT folgt einem GET desselben Vergleichs (frischer Stand)', async () => {
		const s = baueServer(aktiv());
		await setPaused('vergleich', 'c1', true, s.fetchFn);
		assert.deepEqual(
			s.aufrufe.map((a) => [a.method, a.url]),
			[
				['GET', '/api/compare/presets/c1'],
				['PUT', '/api/compare/presets/c1']
			]
		);
	});
});

describe('F009: Trip-setPaused ist bereits Zielzustand — Gegenprobe', () => {
	test('zweimal setPaused(true) schickt zweimal {paused:true}', async () => {
		const s = baueServer({ id: 't1' });
		await setPaused('trip', 't1', true, s.fetchFn);
		await setPaused('trip', 't1', true, s.fetchFn);
		assert.deepEqual(
			s.aufrufe.map((a) => a.body),
			[{ paused: true }, { paused: true }]
		);
	});
});
