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

// Issue #2124 AC-2: 409 ist auf POST /api/trips/<id>/send ausschliesslich
// „Versand läuft bereits" (#1756-Lock) — das geteilte Modul sendOutcome.ts
// zeigt dafür die feste Meldung statt des Backend-detail (Spec-Tabelle §4).
test('AC-11/#2124: 409 zeigt „Versand läuft bereits"', async () => {
	antwort = { status: 409, body: JSON.stringify({ detail: 'Versand für morning läuft bereits — bitte warten' }) };

	const r = await sendTripTestReport('t1', 7, fetchAmServer);

	assert.equal(r.result, null);
	assert.match(r.error ?? '', /Versand läuft bereits/);
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

// ---------------------------------------------------------------------------
// Issue #2124 AC-2/AC-3 — Verdrahtung der Trip-Liste auf das geteilte Modul
// `$lib/utils/sendOutcome.ts` (Spec fix_2124_versand_nginx_timeout.md §4).
// Schlüssel-Konvention `trip:<id>` (geteilt mit Trip-Detail und Dialog).
// tripListSend.ts MUSS `from '$lib/utils/sendOutcome'` (OHNE Endung) importieren:
// test-lib-hooks.mjs löst das auf dieselbe Datei-URL auf wie der relative Import
// unten — nur dann teilen Test und Helfer EINE Modulinstanz (`.js` bräche hier).
// RED heute: kein Laufzustand, 502 ergibt „fehlgeschlagen".
// ---------------------------------------------------------------------------

/** fetch, das bis zur manuellen Freigabe offen bleibt und Aufrufe zählt. */
function haltendesFetch() {
	const zaehler = { aufrufe: 0 };
	const offen: Array<(r: Response) => void> = [];
	const fn: typeof fetch = () => {
		zaehler.aufrufe += 1;
		return new Promise<Response>((ok) => {
			offen.push(ok);
		});
	};
	return {
		fn,
		zaehler,
		// Gibt ALLE offenen Requests frei — heute (ohne Laufzustand) hängen zwei.
		freigabe: () => {
			for (const ok of offen.splice(0)) ok(new Response('{"status":"ok"}', { status: 200 }));
		}
	};
}

const naechsterTakt = () => new Promise<void>((ok) => setImmediate(ok));

test('#2124 AC-3: zweiter Versand für denselben Trip während des ersten schickt keinen zweiten Request', async () => {
	const h = haltendesFetch();
	const erster = sendTripTestReport('t-2124-inflight', 7, h.fn);
	const zweiterP = sendTripTestReport('t-2124-inflight', 7, h.fn);
	await naechsterTakt();
	const aufrufeWaehrendLauf = h.zaehler.aufrufe;

	// Erst freigeben, dann prüfen — damit der Test nie an einem hängenden Request stehen bleibt.
	h.freigabe();
	const [r1, zweiter] = await Promise.all([erster, zweiterP]);

	assert.equal(aufrufeWaehrendLauf, 1, 'während der erste läuft, darf kein zweiter Request abgehen');
	assert.equal(zweiter.result, null);
	assert.match(zweiter.error ?? '', /Versand läuft bereits/);
	assert.equal(r1.error, null);

	// Nach Abschluss ist ein bewusster neuer Versand wieder möglich.
	const dritter = await sendTripTestReport('t-2124-inflight', 7, fetchAmServer);
	assert.equal(dritter.error, null);
	assert.equal(aufrufe.length, 1);
});

test('#2124 AC-3: Trip-Liste nutzt den geteilten Laufzustand (Schlüssel trip:<id>)', async () => {
	const { beginSend, endSend } = await import('../../lib/utils/sendOutcome.ts');
	assert.equal(beginSend('trip:t-2124-geteilt'), true);
	try {
		const r = await sendTripTestReport('t-2124-geteilt', 18, fetchAmServer);
		assert.equal(aufrufe.length, 0, 'läuft der Versand bereits (z. B. aus dem Trip-Detail), geht kein Request ab');
		assert.match(r.error ?? '', /Versand läuft bereits/);
	} finally {
		endSend('trip:t-2124-geteilt');
	}
});

test('#2124 AC-2: 502 zeigt „Ergebnis unklar" statt „fehlgeschlagen"', async () => {
	antwort = { status: 502, body: JSON.stringify({ error: 'upstream unreachable' }) };

	const r = await sendTripTestReport('t-2124-502', 18, fetchAmServer);

	assert.equal(r.result, null);
	assert.equal(r.error, 'Ergebnis unklar — Versand kann noch laufen, nicht erneut senden');
});

test('AC-11: Netzwerkfehler ergibt einen Fehlertext statt einer Ausnahme', async () => {
	const kaputt: typeof fetch = () => Promise.reject(new TypeError('fetch failed'));

	const r = await sendTripTestReport('t1', 7, kaputt);

	assert.equal(r.result, null);
	assert.ok(r.error && r.error.length > 0);
});
