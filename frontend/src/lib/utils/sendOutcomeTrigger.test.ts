// Issue #2124 AC-3: Verdrahtung der Auslöser-Helfer `sendBriefing`
// (route/vergleich, #2280) (von Trip-Detail, Trip-Liste, Compare-Hub, -Liste und
// -Tabs genutzt) auf den geteilten Laufzustand. Verhaltenstest, kein Datei-Grep.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { beginSend, endSend, isSending, sendBriefing } from './sendOutcome.ts';

function haltendesFetch() {
	const z = { aufrufe: 0, urls: [] as string[] };
	const offen: Array<(r: Response) => void> = [];
	const fn: typeof fetch = (url) => {
		z.aufrufe += 1;
		z.urls.push(String(url));
		return new Promise<Response>((ok) => offen.push(ok));
	};
	return {
		fn,
		z,
		frei: (status = 200) => {
			for (const ok of offen.splice(0)) ok(new Response('{}', { status }));
		}
	};
}
const takt = () => new Promise<void>((ok) => setImmediate(ok));

test('Trip: zweiter Versand für denselben Trip sendet keinen zweiten Request', async () => {
	const h = haltendesFetch();
	const erster = sendBriefing('route', 'v-trip', { reportType: 'morning' }, h.fn);
	const zweiter = await sendBriefing('route', 'v-trip', { reportType: 'evening' }, h.fn);
	await takt();
	assert.equal(h.z.aufrufe, 1);
	assert.equal(zweiter.skipped, true);
	assert.equal(zweiter.kind, 'already_running');
	h.frei();
	assert.equal((await erster).kind, 'ok');
	assert.equal(isSending('trip:v-trip'), false);
});

test('Compare: zweiter Versand für dasselbe Preset sendet keinen zweiten Request, Trip-Schlüssel getrennt', async () => {
	const h = haltendesFetch();
	const erster = sendBriefing('vergleich', 'v-cmp', {}, h.fn);
	const zweiter = await sendBriefing('vergleich', 'v-cmp', {}, h.fn);
	assert.equal(zweiter.skipped, true);
	assert.equal(h.z.aufrufe, 1);
	assert.match(h.z.urls[0], /\/api\/briefings\/v-cmp\/send\?kind=vergleich$/);
	// gleicher Id-Raum, anderer Schlüssel: Trip blockiert Compare nicht
	const trip = sendBriefing('route', 'v-cmp', { reportType: 'morning' }, h.fn);
	await takt();
	assert.equal(h.z.aufrufe, 2);
	h.frei();
	await Promise.all([erster, trip]);
});

test('Auslöser sieht einen von außen laufenden Versand (z. B. aus dem Dialog) und sendet nicht', async () => {
	const h = haltendesFetch();
	assert.equal(beginSend('compare:v-extern'), true);
	try {
		const r = await sendBriefing('vergleich', 'v-extern', {}, h.fn);
		assert.equal(r.skipped, true);
		assert.equal(h.z.aufrufe, 0);
	} finally {
		endSend('compare:v-extern');
	}
});

test('endSend läuft auch bei Netzfehler (finally) und ergibt unclear', async () => {
	const kaputt: typeof fetch = () => Promise.reject(new TypeError('fetch failed'));
	const r = await sendBriefing('vergleich', 'v-netz', {}, kaputt);
	assert.equal(r.kind, 'unclear');
	assert.equal(isSending('compare:v-netz'), false);
});

test('502 vom Server: unclear und Laufzustand wieder frei', async () => {
	const h = haltendesFetch();
	const p = sendBriefing('route', 'v-502', { reportType: 'morning' }, h.fn);
	await takt();
	h.frei(502);
	const r = await p;
	assert.equal(r.kind, 'unclear');
	assert.equal(isSending('trip:v-502'), false);
});

test('Kein Client-Abbruch: fetch bekommt für Trip UND Compare kein signal (kein 60-s-Abbruch, #2124)', async () => {
	const inits: Array<RequestInit | undefined> = [];
	const fn: typeof fetch = (_url, init) => {
		inits.push(init);
		return Promise.resolve(new Response('{}', { status: 200 }));
	};
	await sendBriefing('route', 'v-signal-trip', { reportType: 'morning' }, fn);
	await sendBriefing('vergleich', 'v-signal-cmp', {}, fn);
	assert.equal(inits.length, 2);
	for (const init of inits) {
		assert.equal(init?.method, 'POST');
		assert.equal(init?.signal, undefined, 'init.signal muss fehlen: Versand darf bis zur nginx-Grenze laufen');
	}
});
