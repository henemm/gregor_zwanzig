// TDD RED — Issue #2317 Baustein 1 (Unit-Anteil AC-1 / AC-2 / AC-3): die
// Trip-Speicherfunktion der Reiter Wertebereiche (Desktop + Mobil) und Alarme
// reicht die Fetch-Option des Speicher-Wächters an den PUT durch.
//
// Spec: docs/specs/modules/speicherung_beim_neuladen.md
//   § Implementation Details „Baustein 1 — Speichern verlässlich"
//   § Acceptance Criteria AC-1, AC-2, AC-3 (E2E-Nachweis zusätzlich in
//     frontend/e2e/speicherung-ueberlebt-neuladen.spec.ts)
//
// Befund (docs/context/fix-2317-anzeige-nach-neuladen.md): CorridorEditor.svelte,
// CorridorEditorMobile.svelte und AlarmeTab.svelte bauen ihre saveFn als
// `async () => { … api.put(url, body) … }` — OHNE `init`-Parameter. Der Wächter
// ruft beim Entladen `flush({ keepalive: true })`, die Option geht verloren, der
// PUT läuft als normale, eingereihte Anfrage mit If-Match und darf vom Browser
// abgebrochen werden. TypeScript fängt das nicht: `async () => …` erfüllt
// `SaveFn = (init?) => Promise<void>`. Deshalb dieser Verhaltensnachweis.
//
// Zielschnittstelle (existiert noch NICHT → RED per ERR_MODULE_NOT_FOUND):
//
//   frontend/src/lib/components/shared/tripSpeicherung.ts
//   baueTripSpeicherung<T>(client: PutClient, tripId, body, nachErfolg?): SaveFn
//
// Prüfstand: ECHTES `api` aus src/lib/api.ts gegen `fakeTripServer.ts` (echter
// Fingerabdruck, echte If-Match-Prüfung, zeichnet keepalive/If-Match je Anfrage
// auf) und eine ECHTE SaveStatus-Instanz (Muster `Object.create(SaveStatus.prototype)`
// aus src/lib/stores/__tests__/ausstehendeSpeicherungSichern.test.ts). Nur über
// das echte `api` ist „kein If-Match" überhaupt aussagekräftig — ein eigener
// Fake-Client setzte nie einen; der Stempel wird deshalb vorher per GET bekannt
// gemacht (Vorbedingung explizit geprüft).
//
// Ausführen:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/shared/__tests__/trip_speicherung_reicht_keepalive_durch.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../api.ts';
import { clearEtagRegistry, getKnownEtag } from '../../../etagRegistry.ts';
import { SaveStatus } from '../../../stores/saveStatusStore.svelte.ts';
import { createFakeTripServer, type FakeTripServer } from '../../../__tests__/fakeTripServer.ts';
import { baueTripSpeicherung } from '../tripSpeicherung.ts';

const TRIP_ID = 'gr20-2317';
const TRIP_PFAD = `/api/trips/${TRIP_ID}`;
const KORRIDOR_BODY = {
	corridors: [{ metric: 'wind_gust', range: [null, 55], notify: false, mark: false }],
	display_config: { metrics: [] }
};

/** Echte SaveStatus-Instanz ohne Konstruktor (Runen-Felder, s. saveStatus.test.ts). */
function createTestInstance(tripId?: string): SaveStatus {
	const inst = Object.create(SaveStatus.prototype) as SaveStatus;
	const fields = inst as unknown as Record<string, unknown>;
	fields.state = 'idle';
	fields.savedAt = null;
	fields.error = null;
	fields._timer = null;
	fields._pendingFn = null;
	fields._inflight = null;
	fields._lastFailed = null;
	fields._unresolvedError = null;
	fields._tripId = tripId;
	return inst;
}

let server: FakeTripServer;

beforeEach(() => {
	clearEtagRegistry();
	server = createFakeTripServer();
	server.install();
});

afterEach(() => server.restore());

describe('Issue #2317 Baustein 1: Trip-Speicherfunktion reicht die Entlade-Option an den PUT durch', () => {
	test('AC-1/2/3: Flush beim Entladen (keepalive) → PUT noch im selben Tick, mit keepalive, OHNE If-Match', async () => {
		// GIVEN: die Tour ist geladen (Stempel bekannt), eine Änderung wartet im 700-ms-Fenster
		await api.get(TRIP_PFAD);
		assert.ok(getKnownEtag(TRIP_ID), 'Vorbedingung: ein Stand muss bekannt sein, sonst beweist „kein If-Match" nichts');
		const ctl = createTestInstance(TRIP_ID);
		const antworten: unknown[] = [];
		ctl.schedule(baueTripSpeicherung(api, TRIP_ID, KORRIDOR_BODY, (a) => antworten.push(a)));
		assert.equal(ctl.hasPending, true, 'Vorbedingung: Änderung wartet im Speicher-Takt');
		const vorher = server.calls.length;

		// WHEN: der Wächter beim Entladen flusht — bewusst NICHT abgewartet
		const laeuft = ctl.flush({ keepalive: true });

		// THEN (synchron, vor jedem await): der PUT ist bereits beim Server
		assert.equal(
			server.calls.length,
			vorher + 1,
			'der PUT muss noch im Tick des Entladens abgesetzt sein — sonst überlebt er das Dokument nicht'
		);
		const put = server.calls[server.calls.length - 1];
		assert.equal(put.method, 'PUT');
		assert.equal(put.path, TRIP_PFAD, 'der PUT muss auf die Tour-Ressource gehen');
		assert.equal(put.keepalive, true, 'die Option keepalive:true des Wächters wurde verschluckt');
		assert.equal(put.ifMatch, null, 'ein Entlade-Flush darf keinen If-Match tragen (unsichtbarer 412, #1395 S3 AC-6)');

		await laeuft;
		assert.equal(put.status, 200);
		assert.deepEqual(server.storedBody(TRIP_ID), KORRIDOR_BODY, 'beim Server muss genau der übergebene Rumpf ankommen');
		assert.equal(ctl.hasPending, false, 'nach dem Flush steht nichts mehr aus');
		assert.equal(ctl.state, 'idle');
	});

	test('Gegenprobe: regulärer Flush (Feld verlassen) → PUT OHNE keepalive, MIT dem bekannten If-Match', async () => {
		// GIVEN
		await api.get(TRIP_PFAD);
		const bekannt = getKnownEtag(TRIP_ID);
		assert.ok(bekannt, 'Vorbedingung: ein Stand muss bekannt sein');
		const ctl = createTestInstance(TRIP_ID);
		ctl.schedule(baueTripSpeicherung(api, TRIP_ID, KORRIDOR_BODY));

		// WHEN
		await ctl.flush();

		// THEN
		const puts = server.calls.filter((c) => c.method === 'PUT');
		assert.equal(puts.length, 1, 'genau ein PUT erwartet');
		assert.equal(puts[0].keepalive, false, 'ohne Entladen darf kein keepalive gesetzt werden');
		assert.equal(puts[0].ifMatch, bekannt, 'der reguläre Weg muss den Nebenläufigkeitsschutz (If-Match) behalten');
		assert.equal(puts[0].status, 200);
		assert.equal(ctl.state, 'idle');
	});

	test('nachErfolg erhält die Server-Antwort des PUT (Übernahme in den Seitenzustand, onTripUpdate)', async () => {
		// GIVEN
		const ctl = createTestInstance(TRIP_ID);
		const antworten: unknown[] = [];
		ctl.schedule(baueTripSpeicherung(api, TRIP_ID, KORRIDOR_BODY, (a) => antworten.push(a)));

		// WHEN
		await ctl.flush({ keepalive: true });

		// THEN
		assert.equal(antworten.length, 1, 'nachErfolg muss genau einmal gerufen werden');
		assert.deepEqual(
			antworten[0],
			{ id: TRIP_ID, ...KORRIDOR_BODY },
			'nachErfolg muss die tatsächliche Server-Antwort bekommen, nicht den eigenen Rumpf'
		);
	});

	test('scheitert der PUT (412), wird nachErfolg NICHT gerufen und der Fehler erreicht den Speicher-Takt', async () => {
		// GIVEN: bekannter Stand, danach ändert „ein anderes Gerät" die Tour
		await api.get(TRIP_PFAD);
		await server.handler(TRIP_PFAD, { method: 'PUT', body: JSON.stringify({ name: 'fremd' }) });
		const ctl = createTestInstance(TRIP_ID);
		const antworten: unknown[] = [];
		ctl.schedule(baueTripSpeicherung(api, TRIP_ID, KORRIDOR_BODY, (a) => antworten.push(a)));

		// WHEN
		await ctl.flush();

		// THEN
		const letzterPut = server.calls.filter((c) => c.method === 'PUT').at(-1);
		assert.equal(letzterPut?.status, 412, 'Vorbedingung: der Server muss den veralteten Stand ablehnen');
		assert.equal(antworten.length, 0, 'nach einem gescheiterten PUT darf nachErfolg nicht laufen');
		assert.equal(
			ctl.state,
			'conflict',
			'der Fehler muss bis zum Speicher-Takt durchschlagen (Konflikt-Anzeige), nicht verschluckt werden'
		);
	});
});
