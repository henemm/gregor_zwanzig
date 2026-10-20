// Fix-Loop 2 — Issue #2278, F015/F016 (AC-1, AC-3, AC-4, AC-16): die WIRKUNG der Aktionen in der Trip-Liste
// und in der Compare-Liste als Verhalten: der ECHTE Instanz-Code der Seiten (Pruefstand
// `umgebungFuer`) laeuft gegen einen Ersatz-Server, gemessen werden die Requests. Ein toter Zweig,
// ein frueher return oder ein fehlender Aufruf macht den Request unsichtbar — und den Test rot.
// (Bindung/Bedingung der Dialoge: aktionsmodell_seiten_bindung.test.ts.)
//
// Pfadregel #1409: relativ zu DIESER Datei.
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/routes/trips/__tests__/trip_liste_aktionen_verhalten.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { umgebungFuer } from '../../../lib/components/shared/__tests__/svelteInstanzPruefstand.ts';
import { clearEtagRegistry } from '../../../lib/etagRegistry.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const TRIPS_SEITE = path.join(HERE, '..', '+page.svelte');
const COMPARE_SEITE = path.join(HERE, '..', '..', 'compare', '+page.svelte');

interface Aufruf {
	method: string;
	url: string;
	body?: any;
}
let aufrufe: Aufruf[] = [];
let originalFetch: typeof fetch;
let comparePreset: Record<string, unknown>;
let putVerzoegerungMs = 0;
let putStatus = 200;
/** Reihenfolge „METHODE start|ende" aller Requests (zeigt, ob ein Folge-GET VOR der PUT-Antwort losging). */
let ereignisse: string[] = [];
let offen = 0;

beforeEach(() => {
	clearEtagRegistry();
	aufrufe = [];
	comparePreset = { id: 'c1', name: 'V', location_ids: ['a', 'b'], schedule: 'daily', previous_schedule: 'daily' };
	originalFetch = globalThis.fetch;
	putVerzoegerungMs = 0;
	putStatus = 200;
	ereignisse = [];
	offen = 0;
	globalThis.fetch = (async (url: any, init?: any) => {
		const method = String(init?.method ?? 'GET');
		const body = init?.body ? JSON.parse(init.body) : undefined;
		aufrufe.push({ method, url: String(url), body });
		const u = String(url);
		offen++;
		ereignisse.push(`${method} start`);
		try {
			if (u.includes('/api/compare/presets/')) {
				if (method === 'PUT') {
					// Ersatz-Server mit Laufzeit: die Antwort kommt erst nach der Verzoegerung.
					if (putVerzoegerungMs) await new Promise((r) => setTimeout(r, putVerzoegerungMs));
					if (putStatus !== 200) return new Response('{}', { status: putStatus });
					Object.assign(comparePreset, body);
				}
				return new Response(JSON.stringify(comparePreset), { status: 200 });
			}
			if (method === 'GET' && u.endsWith('/api/trips')) return new Response('[]', { status: 200 });
			return new Response('{}', { status: 200 });
		} finally {
			offen--;
			ereignisse.push(`${method} ende`);
		}
	}) as typeof fetch;
});
afterEach(() => {
	globalThis.fetch = originalFetch;
});

const nach = (m: string, teil: string) => aufrufe.filter((a) => a.method === m && a.url.includes(teil));
async function bis(bedingung: () => boolean, was: string): Promise<void> {
	const ende = Date.now() + 5000;
	while (!bedingung()) {
		if (Date.now() > ende) assert.fail(`Zeitueberschreitung beim Warten auf: ${was}`);
		await new Promise((r) => setTimeout(r, 5));
	}
}

/**
 * Abwesenheitspruefung (F024): erst Ruhe (alle Anfragen beantwortet), dann ein Zeitpuffer, in dem auch
 * verzoegert angestossene Handler (setTimeout) ihren Request absetzen wuerden — erst danach darf
 * „es wurde nichts gesendet/geloescht" behauptet werden.
 */
async function ruhe(): Promise<void> {
	for (let i = 0; i < 10; i++) await Promise.resolve();
	await new Promise((r) => setTimeout(r, 120));
	await bis(() => offen === 0, 'Ruhe nach der Aktion');
}

const TRIP = { id: 't1', name: 'GR20', stages: [{ id: 's', date: '2026-07-01', waypoints: [] }] };

async function tripsSeite() {
	const { u } = await umgebungFuer(TRIPS_SEITE, { data: { trips: [TRIP], profile: { mail_to: 'a@example.org' } } }, { jsAlsTs: true });
	const gotos: string[] = [];
	u.goto = (p: string) => void gotos.push(p); // $app/navigation ist unter node nicht ladbar
	return { u, gotos, aktion: (id: string) => u.onTripAction(id, TRIP) };
}
async function compareSeite() {
	const { u } = await umgebungFuer(COMPARE_SEITE, { data: { presets: [{ ...comparePreset }], profile: { mail_to: 'a@example.org' } } }, { jsAlsTs: true });
	const gotos: string[] = [];
	u.goto = (p: string) => void gotos.push(p);
	return { u, gotos, aktion: (id: string) => u.onCompareAction(id, comparePreset) };
}

describe('F016 Trip-Liste: Pausieren/Fortsetzen/Senden/Loeschen wirken', () => {
	test('"pause" -> PATCH /api/trips/t1/state {paused:true}; "resume" -> {paused:false}', async () => {
		const { aktion } = await tripsSeite();
		aktion('pause');
		await bis(() => nach('PATCH', '/state').length === 1, 'PATCH nach "pause"');
		aktion('resume');
		await bis(() => nach('PATCH', '/state').length === 2, 'PATCH nach "resume"');
		assert.deepEqual(
			nach('PATCH', '/state').map((a) => [a.url, a.body]),
			[
				['/api/trips/t1/state', { paused: true }],
				['/api/trips/t1/state', { paused: false }]
			]
		);
	});

	test('"send" merkt nur das Ziel (Dialog); gesendet wird erst mit confirmSend — mit der gewaehlten Berichtsart', async () => {
		const { u, aktion } = await tripsSeite();
		aktion('send');
		assert.equal(u.sendTarget?.id, 't1');
		await ruhe();
		assert.equal(nach('POST', '/send').length, 0, 'Senden ohne Rueckfrage');
		await u.confirmSend('evening');
		const posts = nach('POST', '/send');
		assert.equal(posts.length, 1);
		assert.match(posts[0].url, /\/api\/briefings\/t1\/send\?kind=route&report_type=evening/);
		assert.equal(u.sendTarget, null);
		assert.equal(u.sendInfo, 'Briefing wurde versendet.');
	});

	test('confirmSend() ohne Wahl sendet den Morgen-Bericht', async () => {
		const { u, aktion } = await tripsSeite();
		aktion('send');
		await u.confirmSend();
		assert.match(nach('POST', '/send')[0].url, /report_type=morning/);
	});

	test('"delete" merkt nur das Ziel; erst handleDelete loescht (DELETE /api/trips/t1)', async () => {
		const { u, aktion } = await tripsSeite();
		aktion('delete');
		assert.equal(u.deleteTarget?.id, 't1');
		await ruhe();
		assert.equal(nach('DELETE', '/api/trips/t1').length, 0, 'Loeschen ohne Rueckfrage');
		await u.handleDelete();
		assert.equal(nach('DELETE', '/api/trips/t1').length, 1);
	});

	test('Navigationsaktionen fuehren auf den Hub bzw. den Reiter', async () => {
		const { gotos, aktion } = await tripsSeite();
		for (const id of ['preview', 'alarms', 'weather', 'edit']) aktion(id);
		assert.deepEqual(gotos, [
			'/trips/t1?tab=vorschau',
			'/trips/t1?tab=alarme',
			'/trips/t1?tab=wetter-metriken',
			'/trips/t1'
		]);
	});
});

describe('F016 Compare-Liste: Pausieren/Senden/Loeschen wirken', () => {
	test('"pause" -> GET, dann PUT {schedule:"manual"}; zweites "pause" setzt NICHT fort', async () => {
		const { aktion } = await compareSeite();
		aktion('pause');
		await bis(() => nach('PUT', '/api/compare/presets/c1').length === 1, 'PUT nach "pause"');
		aktion('pause');
		await bis(() => nach('PUT', '/api/compare/presets/c1').length === 2, 'zweiter PUT');
		assert.equal(comparePreset.schedule, 'manual');
	});

	test('"resume" stellt den Zeitplan wieder her', async () => {
		const { aktion } = await compareSeite();
		aktion('pause');
		await bis(() => nach('PUT', '/c1').length === 1, 'PUT nach "pause"');
		aktion('resume');
		await bis(() => nach('PUT', '/c1').length === 2, 'PUT nach "resume"');
		assert.equal(comparePreset.schedule, 'daily');
	});

	test('"send" merkt nur das Ziel; confirmSend sendet POST /api/briefings/c1/send?kind=vergleich', async () => {
		const { u, aktion } = await compareSeite();
		aktion('send');
		assert.equal(u.sendTarget?.id, 'c1');
		await ruhe();
		assert.equal(nach('POST', '/send').length, 0, 'Senden ohne Rueckfrage');
		await u.confirmSend();
		assert.equal(nach('POST', '/api/briefings/c1/send?kind=vergleich').length, 1);
		assert.equal(u.sendInfo, 'Briefing wurde versendet.');
	});

	test('"delete" merkt nur das Ziel; erst confirmDelete loescht', async () => {
		const { u, aktion } = await compareSeite();
		aktion('delete');
		await ruhe();
		assert.equal(nach('DELETE', '/c1').length, 0, 'Loeschen ohne Rueckfrage');
		await u.confirmDelete();
		assert.equal(nach('DELETE', '/api/compare/presets/c1').length, 1);
	});

	test('F022: der Zeilen-Primaerknopf „Briefing senden" existiert fuer aktive Vergleiche und oeffnet nur den Dialog', async () => {
		const { u } = await compareSeite();
		const primaer = u.compareRowPrimary(comparePreset);
		assert.equal(primaer?.label, 'Briefing senden');
		primaer.onClick();
		assert.equal(u.sendTarget?.id, 'c1');
		await ruhe();
		assert.equal(nach('POST', '/send').length, 0, 'Primaerknopf sendet ohne Rueckfrage');
		assert.equal(u.compareRowPrimary({ ...comparePreset, schedule: 'manual' }), null, 'pausierter Vergleich hat keinen Primaerknopf');
	});

	test('F023: die Liste zeigt den neuen Stand ERST nach der PUT-Antwort (await vor setPaused)', async () => {
		putVerzoegerungMs = 80;
		const { u, aktion } = await compareSeite();
		aktion('pause');
		await bis(() => nach('PUT', '/c1').length === 1 && offen === 0 && u.presets[0].schedule === 'manual', 'neuer Stand in der Liste');
		const i0 = ereignisse.indexOf('PUT start');
		const i1 = ereignisse.indexOf('PUT ende');
		assert.ok(i0 >= 0 && i1 > i0);
		assert.ok(
			!ereignisse.slice(i0, i1).includes('GET start'),
			`der Refetch-GET startete VOR der PUT-Antwort: ${ereignisse.join(' > ')}`
		);
		assert.equal(ereignisse[i1 + 1], 'GET start', 'nach der PUT-Antwort folgt der Refetch-GET');
		assert.equal(u.error, null);
	});

	test('F023: ein PUT-Fehler landet in `error`, die Liste behaelt den alten Stand', async () => {
		putStatus = 500;
		const { u, aktion } = await compareSeite();
		aktion('pause');
		await bis(() => typeof u.error === 'string', 'Fehlermeldung in `error`');
		assert.match(u.error, /Status-Änderung fehlgeschlagen/);
		assert.equal(u.presets[0].schedule, 'daily');
		await ruhe();
		assert.equal(nach('GET', '/c1').length, 1, 'nach dem Fehler darf nicht nachgeladen werden');
	});
});
