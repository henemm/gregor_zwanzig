// TDD RED — Issue #2278 (Epic #2345 P3), AC-7 (+ Wirkung der Aktionen aus AC-3/AC-4/AC-5/AC-16).
// Spec: docs/specs/modules/feat_2278_aktionsmodell.md — Implementation Details 3.
//
// Ausfuehrungs-Adapter `shared/subscriptionExec.ts`. Jede Funktion nimmt als LETZTES
// Argument eine injizierbare `fetchFn` (Muster `sendBriefing(kind, id, opts, fetchFn)` in
// lib/utils/sendOutcome.ts). Hier ist `fetchFn` ein echter Aufzeichner mit einem kleinen
// SERVER-Modell (kein Spiegel der Annahme): GET liefert den Serverstand, PATCH/PUT
// mergen den Body wie das Go-Backend (vorhandene Felder im Body ueberschreiben).
//
// Vertrag (hier festgelegt, /50 baut danach):
//   setPaused(kind, id, paused, fetchFn?)
//     trip:      PATCH /api/trips/{id}/state, Body GENAU {paused: bool}
//     vergleich: GET /api/compare/presets/{id} (frisch), danach PUT /api/compare/presets/{id}
//                mit dem Zeitplan-Wechsel. KORREKTUR ggue. Spec-Wortlaut "PUT ganzes Preset":
//                der Live-Code (#2375, buildToggleActivePutPayload) sendet bewusst NUR
//                {schedule, previous_schedule} (kein Voll-Spread, sonst Stale-Body-Race).
//                Dieser Test sichert dieselbe Zusicherung: der Wechsel entsteht aus dem
//                FRISCHEN Stand, kein anderes Feld wird mit einem veralteten Wert ueberschrieben.
//   setArchived(kind, id, archived, fetchFn?)
//     trip: PATCH /api/trips/{id}/state {archived}; vergleich: PATCH /api/compare/presets/{id}/state {archived}
//   deleteSubscription(kind, id, fetchFn?)
//     trip: DELETE /api/trips/{id}; vergleich: DELETE /api/compare/presets/{id}
//   sendSubscription(kind, id, opts: {reportType?: 'morning'|'evening'}, fetchFn?)
//     trip: POST /api/briefings/{id}/send?kind=route&report_type=<morning|evening> (Default morning, #2280)
//     vergleich: POST /api/briefings/{id}/send?kind=vergleich OHNE report_type (#2280)
//
// RED heute: Modul `shared/subscriptionExec.ts` fehlt.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/__tests__/subscriptionExec.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { pathToFileURL, fileURLToPath } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const mod: any = await import(pathToFileURL(path.join(HERE, '..', 'subscriptionExec.ts')).href).catch(() => null);
function braucheModul(): any {
	assert.ok(mod, 'Modul shared/subscriptionExec.ts fehlt (RED) — AC-7 Ausfuehrungs-Adapter.');
	return mod;
}

interface Aufruf {
	method: string;
	url: string;
	body: any;
}

/** Aufzeichnender fetch mit Server-Modell fuer EIN Objekt (`serverStand`). */
function baueServer(serverStand: Record<string, unknown>) {
	const aufrufe: Aufruf[] = [];
	const fetchFn = (async (input: any, init?: any) => {
		const method = String(init?.method ?? 'GET').toUpperCase();
		const url = String(input);
		const body = init?.body ? JSON.parse(String(init.body)) : undefined;
		aufrufe.push({ method, url, body });
		if (method === 'GET') return new Response(JSON.stringify(serverStand), { status: 200 });
		if (method === 'PUT' || method === 'PATCH') {
			Object.assign(serverStand, body);
			return new Response(JSON.stringify(serverStand), { status: 200 });
		}
		return new Response(JSON.stringify({ ok: true }), { status: 200 });
	}) as unknown as typeof fetch;
	return { aufrufe, fetchFn, serverStand };
}

describe('AC-7 Trip: Pausieren/Fortsetzen aendert NUR den Pausen-Zustand', () => {
	test('pausieren: genau ein PATCH /api/trips/{id}/state mit {paused:true}', async () => {
		const { setPaused } = braucheModul();
		const s = baueServer({ id: 't1', name: 'X', stages: [{ id: 'a' }], report_config: { send_premium_sms: true } });
		await setPaused('trip', 't1', true, s.fetchFn);
		assert.deepEqual(s.aufrufe, [{ method: 'PATCH', url: '/api/trips/t1/state', body: { paused: true } }]);
	});
	test('fortsetzen: {paused:false}; kein anderes Feld im Body', async () => {
		const { setPaused } = braucheModul();
		const s = baueServer({ id: 't1' });
		await setPaused('trip', 't1', false, s.fetchFn);
		assert.deepEqual(s.aufrufe[0].body, { paused: false });
	});
	test('HTTP-Fehler wird geworfen (kein stilles Verschlucken)', async () => {
		const { setPaused } = braucheModul();
		const fetchFn = (async () => new Response('{}', { status: 500 })) as unknown as typeof fetch;
		await assert.rejects(() => setPaused('trip', 't1', true, fetchFn));
	});
});

describe('AC-7 Ortsvergleich: Pausieren = Zeitplan-Wechsel aus FRISCHEM Stand (Read-Modify-Write)', () => {
	const frisch = () => ({
		id: 'c1',
		name: 'Frisch',
		location_ids: ['a', 'b'],
		schedule: 'daily',
		previous_schedule: 'daily',
		corridors: [{ metric: 'snow_depth_cm', range: [50, null] }],
		unbekanntes_feld: { bleibt: true }
	});

	test('pausieren: erst GET, dann PUT auf dieselbe URL; schedule=manual, previous_schedule=alter Zeitplan', async () => {
		const { setPaused } = braucheModul();
		const s = baueServer(frisch());
		await setPaused('vergleich', 'c1', true, s.fetchFn);
		assert.deepEqual(
			s.aufrufe.map((a) => [a.method, a.url]),
			[
				['GET', '/api/compare/presets/c1'],
				['PUT', '/api/compare/presets/c1']
			]
		);
		const put = s.aufrufe[1].body;
		assert.equal(put.schedule, 'manual');
		assert.equal(put.previous_schedule, 'daily');
	});

	test('Datenerhalt: Korridore und unbekannte Felder des Servers ueberleben (nichts mit Stale-Wert ueberschrieben)', async () => {
		const { setPaused } = braucheModul();
		const s = baueServer(frisch());
		await setPaused('vergleich', 'c1', true, s.fetchFn);
		const put = s.aufrufe[1].body;
		// Entweder fehlt ein Feld im Body (Teil-Payload, #2375) oder es ist der FRISCHE Wert.
		if ('corridors' in put) assert.deepEqual(put.corridors, frisch().corridors);
		if ('unbekanntes_feld' in put) assert.deepEqual(put.unbekanntes_feld, { bleibt: true });
		assert.deepEqual(s.serverStand.corridors, frisch().corridors, 'Serverstand: Korridor verloren');
		assert.deepEqual(s.serverStand.unbekanntes_feld, { bleibt: true }, 'Serverstand: unbekanntes Feld verloren');
		assert.equal(s.serverStand.name, 'Frisch');
	});

	test('fortsetzen aus "manual": stellt previous_schedule wieder her, nie "manual"', async () => {
		const { setPaused } = braucheModul();
		const s = baueServer({ ...frisch(), schedule: 'manual', previous_schedule: 'weekly' });
		await setPaused('vergleich', 'c1', false, s.fetchFn);
		assert.equal(s.serverStand.schedule, 'weekly');
		assert.notEqual(s.serverStand.previous_schedule, 'manual');
	});

	test('GET-Fehler: kein PUT, Fehler wird geworfen', async () => {
		const { setPaused } = braucheModul();
		const aufrufe: string[] = [];
		const fetchFn = (async (_u: any, init?: any) => {
			aufrufe.push(String(init?.method ?? 'GET'));
			return new Response('{}', { status: 502 });
		}) as unknown as typeof fetch;
		await assert.rejects(() => setPaused('vergleich', 'c1', true, fetchFn));
		assert.ok(!aufrufe.includes('PUT'), 'PUT ohne frischen Stand abgeschickt');
	});
});

describe('Archivieren / Loeschen / Senden — beide Arten, richtige Endpunkte', () => {
	test('setArchived: Trip und Ortsvergleich nutzen je ihren /state-Endpunkt mit {archived}', async () => {
		const { setArchived } = braucheModul();
		const t = baueServer({});
		await setArchived('trip', 't1', true, t.fetchFn);
		assert.deepEqual(t.aufrufe, [{ method: 'PATCH', url: '/api/trips/t1/state', body: { archived: true } }]);
		const c = baueServer({});
		await setArchived('vergleich', 'c1', false, c.fetchFn);
		assert.deepEqual(c.aufrufe, [{ method: 'PATCH', url: '/api/compare/presets/c1/state', body: { archived: false } }]);
	});

	test('deleteSubscription: DELETE auf den jeweiligen Endpunkt, ohne Body', async () => {
		const { deleteSubscription } = braucheModul();
		const t = baueServer({});
		await deleteSubscription('trip', 't1', t.fetchFn);
		assert.deepEqual(t.aufrufe, [{ method: 'DELETE', url: '/api/trips/t1', body: undefined }]);
		const c = baueServer({});
		await deleteSubscription('vergleich', 'c1', c.fetchFn);
		assert.deepEqual(c.aufrufe, [{ method: 'DELETE', url: '/api/compare/presets/c1', body: undefined }]);
	});

	test('sendSubscription Trip: report_type im Request (AC-4), Default morning', async () => {
		const { sendSubscription } = braucheModul();
		const a = baueServer({});
		await sendSubscription('trip', 'send-t-a', { reportType: 'evening' }, a.fetchFn);
		assert.deepEqual([a.aufrufe[0].method, a.aufrufe[0].url], ['POST', '/api/briefings/send-t-a/send?kind=route&report_type=evening']);
		const b = baueServer({});
		await sendSubscription('trip', 'send-t-b', {}, b.fetchFn);
		assert.equal(b.aufrufe[0].url, '/api/briefings/send-t-b/send?kind=route&report_type=morning');
	});

	test('sendSubscription Ortsvergleich: kein report_type, auch wenn einer uebergeben wird', async () => {
		const { sendSubscription } = braucheModul();
		const s = baueServer({});
		await sendSubscription('vergleich', 'send-c-1', { reportType: 'evening' }, s.fetchFn);
		assert.deepEqual([s.aufrufe[0].method, s.aufrufe[0].url], ['POST', '/api/briefings/send-c-1/send?kind=vergleich']);
	});
});

describe('Versand-Schutz (#2124): kein Doppelversand bei gleichzeitigem Aufruf', () => {
	test('zwei gleichzeitige sendSubscription fuer dieselbe Id: genau EIN Request, der zweite ist skipped', async () => {
		const { sendSubscription } = braucheModul();
		let freigeben!: () => void;
		const haelt = new Promise<void>((r) => (freigeben = r));
		const aufrufe: string[] = [];
		const fetchFn = (async (u: any, init?: any) => {
			aufrufe.push(`${init?.method ?? 'GET'} ${u}`);
			await haelt;
			return new Response('{"status":"ok"}', { status: 200 });
		}) as unknown as typeof fetch;
		const erster = sendSubscription('trip', 'doppel-t', { reportType: 'morning' }, fetchFn);
		const zweiter = await sendSubscription('trip', 'doppel-t', { reportType: 'morning' }, fetchFn);
		freigeben();
		const e = await erster;
		assert.equal(aufrufe.length, 1, `zwei Requests abgeschickt: ${JSON.stringify(aufrufe)}`);
		assert.equal(zweiter.skipped, true);
		assert.equal(e.skipped, false);
	});
	test('gleiches fuer den Ortsvergleich; verschiedene Ids blockieren sich nicht', async () => {
		const { sendSubscription } = braucheModul();
		let freigeben!: () => void;
		const haelt = new Promise<void>((r) => (freigeben = r));
		const aufrufe: string[] = [];
		const fetchFn = (async (u: any) => {
			aufrufe.push(String(u));
			await haelt;
			return new Response('{}', { status: 200 });
		}) as unknown as typeof fetch;
		const a = sendSubscription('vergleich', 'doppel-c1', {}, fetchFn);
		const zweiteGleiche = await sendSubscription('vergleich', 'doppel-c1', {}, fetchFn);
		const andere = sendSubscription('vergleich', 'doppel-c2', {}, fetchFn);
		await new Promise((r) => setTimeout(r, 5));
		freigeben();
		await Promise.all([a, andere]);
		assert.equal(zweiteGleiche.skipped, true);
		assert.equal(aufrufe.length, 2, `erwartet 2 (c1, c2), war: ${JSON.stringify(aufrufe)}`);
	});
});
