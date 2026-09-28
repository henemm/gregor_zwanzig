// TDD RED — Issue #2155 Scheibe S1 (Admin-Rolle), AC-10 + AC-11.
//
// Spec: docs/specs/modules/admin_rolle_s1.md § "6. Frontend-Umstellung"
//
// Der Knopf „Briefing senden" der Trip-Liste stiess bisher über
// POST /api/scheduler/trip-reports?hour=… ALLE Trips des Nutzers an. Künftig
// geht genau EIN Aufruf POST /api/trips/<id>/send?report_type=morning|evening
// an den gewählten Trip. Die Umstellung liegt in einem kleinen, reinen Helfer
// `tripListSend.ts` (Nachbar der +page.svelte), damit sie testbar ist:
//
//   reportTypeForHour(hour: 7 | 18): 'morning' | 'evening'
//   sendTripTestReport(tripId, hour, fetchFn = fetch)
//       : Promise<{ result: string | null; error: string | null }>
//
// Geprüft wird Verhalten gegen einen ECHTEN lokalen HTTP-Server (node:http),
// der jede eingehende Anfrage (Methode + Pfad + Query) aufzeichnet — kein
// Quelltext-Grep. Die Verdrahtung der +page.svelte auf diesen Helfer bewacht
// zusätzlich das Playwright-Staging-E2E (siehe unten „Hinweis").
//
// Scheitert heute, weil ./tripListSend.ts nicht existiert.
//
// Ausführung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/routes/trips/trips-list-send.test.ts
//
// Hinweis (kein Teil dieser Datei): Staging-E2E — Trip-Liste „Briefing senden"
// ⇒ Request-URL `/api/trips/<id>/send?report_type=…`, KEIN Request an
// `/api/scheduler/trip-reports`.

import { test, before, after, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import type { AddressInfo } from 'node:net';

import { reportTypeForHour, sendTripTestReport } from './tripListSend.ts';

type Aufruf = { method: string; url: string };

let server: http.Server;
let basis = '';
let aufrufe: Aufruf[] = [];
// Antwort, die der Server für den nächsten Aufruf liefert.
let antwort: { status: number; body: string } = { status: 200, body: '{"status":"ok"}' };

before(async () => {
	server = http.createServer((req, res) => {
		aufrufe.push({ method: req.method ?? '', url: req.url ?? '' });
		res.writeHead(antwort.status, { 'Content-Type': 'application/json' });
		res.end(antwort.body);
	});
	await new Promise<void>((ok) => server.listen(0, '127.0.0.1', ok));
	basis = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});

after(async () => {
	await new Promise<void>((ok) => server.close(() => ok()));
});

beforeEach(() => {
	aufrufe = [];
	antwort = { status: 200, body: '{"status":"ok"}' };
});

// Echtes fetch, nur die relative URL wird auf den lokalen Server gelegt —
// so verhält sich der Helfer wie im Browser (relative /api/…-Pfade).
const fetchAmServer: typeof fetch = (input, init) => fetch(basis + String(input), init);

// ---------------------------------------------------------------------------
// AC-10: Abbildung hour -> report_type
// ---------------------------------------------------------------------------

test('AC-10: 7 Uhr -> morning, 18 Uhr -> evening', () => {
	assert.equal(reportTypeForHour(7), 'morning');
	assert.equal(reportTypeForHour(18), 'evening');
});

// ---------------------------------------------------------------------------
// AC-10: genau EIN Aufruf an /api/trips/<id>/send, keiner an den Sammel-Trigger
// ---------------------------------------------------------------------------

test('AC-10: 7 Uhr sendet genau POST /api/trips/t1/send?report_type=morning', async () => {
	await sendTripTestReport('t1', 7, fetchAmServer);

	assert.equal(aufrufe.length, 1, `erwartet genau 1 Aufruf, aufgezeichnet: ${JSON.stringify(aufrufe)}`);
	assert.deepEqual(aufrufe[0], { method: 'POST', url: '/api/trips/t1/send?report_type=morning' });
});

test('AC-10: 18 Uhr sendet genau POST /api/trips/t1/send?report_type=evening', async () => {
	await sendTripTestReport('t1', 18, fetchAmServer);

	assert.equal(aufrufe.length, 1, `erwartet genau 1 Aufruf, aufgezeichnet: ${JSON.stringify(aufrufe)}`);
	assert.deepEqual(aufrufe[0], { method: 'POST', url: '/api/trips/t1/send?report_type=evening' });
});

test('AC-10: kein Aufruf an /api/scheduler/trip-reports (Sammel-Trigger)', async () => {
	await sendTripTestReport('t1', 7, fetchAmServer);
	await sendTripTestReport('t2', 18, fetchAmServer);

	assert.equal(aufrufe.length, 2);
	for (const a of aufrufe) {
		assert.ok(!a.url.includes('/api/scheduler/'), `Sammel-Trigger aufgerufen: ${a.url}`);
	}
	// Der gewählte Trip landet im Pfad — nicht ein fester oder der erste.
	assert.equal(aufrufe[0].url.split('?')[0], '/api/trips/t1/send');
	assert.equal(aufrufe[1].url.split('?')[0], '/api/trips/t2/send');
});

// ---------------------------------------------------------------------------
// AC-11: Ergebnis-/Fehlertext je Antwort
// ---------------------------------------------------------------------------

test('AC-11: Erfolg (200) nennt „diesen Trip", nicht „Alle aktiven Trips"', async () => {
	antwort = { status: 200, body: '{"status":"ok"}' };

	const r = await sendTripTestReport('t1', 7, fetchAmServer);

	assert.equal(r.error, null);
	assert.ok(r.result, 'bei Erfolg muss ein Ergebnistext vorliegen');
	assert.match(r.result!, /diesen Trip/);
	assert.doesNotMatch(r.result!, /Alle aktiven Trips/);
	assert.match(r.result!, /Morning/, 'der Text nennt die gewählte Meldung (7 Uhr = Morning)');
});

test('AC-11: Erfolgstext für 18 Uhr nennt Evening', async () => {
	const r = await sendTripTestReport('t1', 18, fetchAmServer);

	assert.ok(r.result);
	assert.match(r.result!, /Evening/);
	assert.match(r.result!, /diesen Trip/);
});

test('AC-11: 409 zeigt den detail-Text der Antwort', async () => {
	antwort = { status: 409, body: JSON.stringify({ detail: 'Trip ist pausiert — kein Versand.' }) };

	const r = await sendTripTestReport('t1', 7, fetchAmServer);

	assert.equal(r.result, null);
	assert.equal(r.error, 'Trip ist pausiert — kein Versand.');
});

test('AC-11: 422 zeigt den detail-Text der Antwort', async () => {
	antwort = { status: 422, body: JSON.stringify({ detail: 'report_type ungültig' }) };

	const r = await sendTripTestReport('t1', 18, fetchAmServer);

	assert.equal(r.result, null);
	assert.equal(r.error, 'report_type ungültig');
});

test('AC-11: 404 mit detail zeigt den detail-Text', async () => {
	antwort = { status: 404, body: JSON.stringify({ detail: 'Trip nicht gefunden' }) };

	const r = await sendTripTestReport('t1', 7, fetchAmServer);

	assert.equal(r.error, 'Trip nicht gefunden');
});

test('AC-11: 4xx ohne detail nutzt error, sonst einen allgemeinen Text', async () => {
	antwort = { status: 400, body: JSON.stringify({ error: 'bad_request' }) };
	const mitError = await sendTripTestReport('t1', 7, fetchAmServer);
	assert.equal(mitError.result, null);
	assert.equal(mitError.error, 'bad_request');

	antwort = { status: 400, body: 'kein json' };
	const ohneAlles = await sendTripTestReport('t1', 7, fetchAmServer);
	assert.equal(ohneAlles.result, null);
	assert.ok(ohneAlles.error && ohneAlles.error.length > 0, 'allgemeiner Fehlertext erwartet');
});

test('AC-11: 5xx zeigt eine handlungsleitende Meldung OHNE Rohtext', async () => {
	antwort = { status: 500, body: JSON.stringify({ detail: 'Traceback: KeyError internal secret' }) };

	const r = await sendTripTestReport('t1', 7, fetchAmServer);

	assert.equal(r.result, null);
	assert.ok(r.error, 'Fehlertext erwartet');
	assert.doesNotMatch(r.error!, /Traceback|KeyError|secret/);
	assert.match(r.error!, /später erneut versuchen/);
});

test('AC-11: Netzwerkfehler ergibt einen Fehlertext statt einer Ausnahme', async () => {
	const kaputt: typeof fetch = () => Promise.reject(new TypeError('fetch failed'));

	const r = await sendTripTestReport('t1', 7, kaputt);

	assert.equal(r.result, null);
	assert.ok(r.error && r.error.length > 0);
});
