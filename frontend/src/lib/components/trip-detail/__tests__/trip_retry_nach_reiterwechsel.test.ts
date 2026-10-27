// TDD RED — Issue #1433, AC-3, AC-19: „Nochmal speichern" nach Reiterwechsel.
// Reiter A loest den Konflikt aus und ist nach dem Wechsel nicht mehr angezeigt
// (unmountet); Reiter B speichert (412, landet in derselben Liste); dann
// `retryConflict()` — es muessen BEIDE Eigenfelder-Saetze erneut gesendet werden,
// und danach stehen Fremdaenderung, A und B gemeinsam auf dem Server.
//
// Spec: docs/specs/bugfix/trip_mehrreiter_konfliktschutz.md — §4 Punkte 2/4/5,
//       AC-3, AC-19; Test Plan `trip_retry_nach_reiterwechsel`.
//
// Heute rot: `doSave` haelt nur EINEN gescheiterten Speichervorgang (`_lastFailed`
// ist ein Einzelwert), Reiter B schreibt ohne If-Match durch (Konflikt weg), und
// der Retry holt per `refreshResourceEtag` nur den Stempel, nicht den Trip.
//
// Beobachtbar gemacht, ohne neue Namen zu raten: Server-Stand (Fake, Go-Merge),
// Reihenfolge GET → PUTs, das If-Match der Wiederholung, Registry-Stand, die
// `onTripUpdate`-Meldungen der Reiter (sie tragen die Server-Antwort, aus der die
// Seite `trip` neu setzt), Controller-Zustand. NICHT geprueft: die Form der
// internen Liste (`_lastFailed`) — sie wird ueber ihre Wirkung bewiesen (beide
// Saetze werden erneut gesendet).
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/trip-detail/__tests__/trip_retry_nach_reiterwechsel.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../api.ts';
import * as registry from '../../../etagRegistry.ts';
import { clearEtagRegistry, getKnownEtag } from '../../../etagRegistry.ts';
import { createFakeTripServer, type FakeTripServer } from '../../../__tests__/fakeTripServer.ts';
import * as P from './tripMehrreiterPruefstand.ts';

let server: FakeTripServer;

const FREMDE_METRIKEN = [{ metric_id: 'cape', enabled: true, aggregations: ['max'] }];

let langsamerGet = false;

beforeEach(async () => {
	clearEtagRegistry();
	langsamerGet = false;
	server = createFakeTripServer({ merge: true, latencyMs: (m) => (m === 'GET' && langsamerGet ? 40 : 0) });
	server.install();
	server.seed(P.TRIP_ID, P.vollerTrip());
	await api.get(P.TRIP_PFAD); // beide Reiter haben die Seite mit diesem Stand geladen
});
afterEach(() => server.restore());

const puts = () => server.calls.filter((c) => c.method === 'PUT');
const gets = () => server.calls.filter((c) => c.method === 'GET');
const stand = () => server.stand(P.TRIP_ID);
const dc = () => stand().display_config as Record<string, unknown>;
const rc = () => stand().report_config as Record<string, unknown>;
const istKonflikt = (id: string): boolean => {
	const f = (registry as unknown as { istKonflikt?: (i: string) => boolean }).istKonflikt;
	assert.equal(typeof f, 'function', 'etagRegistry.ts muss `istKonflikt(id)` exportieren');
	return f!(id);
};

/** A (Alarme) loest den Konflikt aus; danach „Reiterwechsel": A wird nicht mehr referenziert. */
async function konfliktInAUndWechsel(a: P.Aufbau): Promise<void> {
	let alarme: Awaited<ReturnType<typeof P.alarmeReiter>> | null = await P.alarmeReiter(a);
	alarme.empfindlichkeitAendern('wind', 'sensibel');
	await P.fertig(a.ctl);
	assert.equal(puts()[0].status, 412, 'Vorbedingung: Reiter A scheitert am Fremdschreiber');
	assert.equal(a.ctl.state, 'conflict', 'Vorbedingung: Konflikt-Anzeige');
	alarme = null; // Reiterwechsel: nur der aktive Reiter ist gemountet (TripTabs.svelte:196)
	void alarme;
}

describe('AC-3: Fremdaenderung, A (Alarme) und B (Versand) stehen nach „Nochmal speichern" gemeinsam auf dem Server', () => {
	test('A erzeugt Konflikt, Wechsel, B speichert (412), Retry sendet beide Saetze erneut', async () => {
		server.foreignWrite(P.TRIP_ID, { display_config: { metrics: FREMDE_METRIKEN } });
		const a = P.neuerAufbau();
		await konfliktInAUndWechsel(a);

		// B (Versand) speichert bei offenem Konflikt: 412, Anzeige bleibt
		const b = await P.versandReiter(a);
		b.aendern({ morning_time: '08:00:00' });
		await P.fertig(a.ctl);
		const bPut = puts().at(-1)!;
		assert.equal(bPut.status, 412, 'Vorbedingung: der Versand-PUT bei offenem Konflikt wird abgelehnt (Server traegt die Sperre)');
		assert.equal(a.ctl.state, 'conflict', 'AC-2: die Anzeige bleibt nach dem Speichern in B');
		assert.notEqual(rc().morning_time, '08:00:00', 'Vorbedingung: B hat noch nichts geschrieben');

		// WHEN: „Nochmal speichern"
		const etagVorRetry = server.etagOf(P.TRIP_ID);
		const putsVorRetry = puts().length;
		const getsVorRetry = gets().length;
		await a.ctl.retryConflict();

		// THEN: GET zuerst, danach beide Saetze erneut, mit dem frischen Stempel
		assert.equal(gets().length, getsVorRetry + 1, 'der Retry holt den Trip per GET (AC-19)');
		const retryGet = gets().at(-1)!;
		const retryPuts = puts().slice(putsVorRetry);
		assert.ok(retryPuts.length >= 2, `beide Eigenfelder-Saetze (A und B) muessen erneut gesendet werden, gesehen: ${retryPuts.length}`);
		for (const p of retryPuts) {
			assert.ok(p.startedAt >= retryGet.finishedAt, 'AC-19: erst GET, DANN die eigenen Aenderungen');
			assert.equal(p.status, 200, `Wiederholung ${p.path} muss durchgehen`);
		}
		assert.equal(retryPuts[0].ifMatch, etagVorRetry, 'die erste Wiederholung traegt den frisch geholten Stempel');

		// Server-Stand: Fremdaenderung + A + B
		assert.deepEqual(dc().metrics, FREMDE_METRIKEN, 'die Fremdaenderung muss erhalten bleiben');
		assert.equal(
			(dc().metric_alert_levels as Record<string, unknown>).wind,
			'sensibel',
			'die Alarm-Aenderung aus Reiter A muss gespeichert sein (A ist nicht mehr angezeigt!)'
		);
		assert.equal(rc().morning_time, '08:00:00', 'die Versand-Aenderung aus Reiter B muss gespeichert sein');
		assert.equal(rc().skip_next, false, 'Seed unveraendert');

		// Konfliktanzeige weg, Markierung weg
		assert.equal(a.ctl.state, 'idle', 'nach erfolgreichem Retry verschwindet die Konfliktanzeige');
		assert.equal(istKonflikt(P.TRIP_ID), false, 'die Konflikt-Markierung der Registry ist geloescht');
		assert.equal(getKnownEtag(P.TRIP_ID), server.etagOf(P.TRIP_ID), 'ETag und Server-Stand sind wieder synchron');
	});

	// GRENZE dieses Tests (AC-19): gemessen wird nur, dass die nach dem Retry an die Seite
	// gemeldete Fassung (`onTripUpdate`, = Antwort des Wiederholungs-PUT, die der Go-Handler
	// als Gesamtdokument liefert) die Fremdaenderung enthaelt und der Stempel zum Serverstand
	// passt. Die Zusicherung „der Retry-GET ersetzt `trip` UND ETag GEMEINSAM (nie der Stempel
	// allein)" ist ohne einen in der Spec offen gelassenen Mechanismus nicht beobachtbar — ein
	// Retry, der nur den Stempel adoptiert (heutiges `refreshResourceEtag`), wuerde diesen Test
	// bei Teilfeld-Nutzlasten ebenfalls bestehen. Abgedeckt ist AC-19 daher nur ueber die
	// REIHENFOLGE (GET vor den PUTs, If-Match = Stempel des GET) im Test oben.
	test('AC-19 (nur Wirkung): die nach dem Retry gemeldete Fassung enthaelt die Fremdaenderung, Stempel = Serverstand', async () => {
		server.foreignWrite(P.TRIP_ID, { name: 'Fremder Name', display_config: { metrics: FREMDE_METRIKEN } });
		const a = P.neuerAufbau();
		await konfliktInAUndWechsel(a);
		await a.ctl.retryConflict();

		const letzte = a.updates.at(-1);
		assert.ok(letzte, 'der Retry muss die Server-Antwort an die Seite melden (onTripUpdate)');
		assert.equal(letzte!.name, 'Fremder Name', 'die gemeldete Fassung muss die Fremdaenderung enthalten');
		assert.deepEqual((letzte!.display_config as Record<string, unknown>).metrics, FREMDE_METRIKEN);
		assert.equal(getKnownEtag(P.TRIP_ID), server.etagOf(P.TRIP_ID));
	});
});

describe('AC-3 mit Wertebereiche als zweitem Reiter (anderes Top-Level-Feld)', () => {
	test('Fremd: Name; A: Alarme; B: Wertebereiche — nach dem Retry stehen alle drei auf dem Server', async () => {
		server.foreignWrite(P.TRIP_ID, { name: 'Fremder Name' });
		const a = P.neuerAufbau();
		await konfliktInAUndWechsel(a);

		const b = await P.wertebereicheReiter(a);
		b.inst.u.rows = [{ metric: 'wind_max_kmh', label: 'Wind', min: 0, max: 55, notify: true, mark: true }];
		b.speichern();
		await P.fertig(a.ctl);
		assert.equal(puts().at(-1)!.status, 412, 'Vorbedingung: B wird bei offenem Konflikt abgelehnt');

		await a.ctl.retryConflict();

		assert.equal(stand().name, 'Fremder Name', 'Fremdaenderung bleibt');
		assert.equal((dc().metric_alert_levels as Record<string, unknown>).wind, 'sensibel', 'A steht auf dem Server');
		assert.deepEqual(stand().corridors, [{ metric: 'wind_max_kmh', range: [0, 55], notify: true, mark: true }], 'B steht auf dem Server');
		assert.equal(a.ctl.state, 'idle');
	});
});

describe('Retry bei erneutem Konflikt: nichts geht verloren', () => {
	test('ein weiterer Fremdschreiber waehrend des Retry ⇒ Konflikt bleibt, ein zweiter Retry sendet weiterhin BEIDE Saetze', async () => {
		server.foreignWrite(P.TRIP_ID, { name: 'Fremd 1' });
		const a = P.neuerAufbau();
		await konfliktInAUndWechsel(a);
		const b = await P.versandReiter(a);
		b.aendern({ morning_time: '08:00:00' });
		await P.fertig(a.ctl);

		// zweiter Fremdschreiber, waehrend der Retry-GET unterwegs ist: der Server hat den
		// GET bei Ankunft beantwortet (alter Stempel), die Antwort kommt verzoegert an.
		langsamerGet = true;
		const retry = a.ctl.retryConflict();
		await new Promise((r) => setTimeout(r, 10));
		server.foreignWrite(P.TRIP_ID, { name: 'Fremd 2' });
		await retry;
		langsamerGet = false;

		assert.equal(a.ctl.state, 'conflict', 'der Retry trifft auf den neuen Fremdschreiber ⇒ weiter Konflikt');
		assert.equal(stand().name, 'Fremd 2', 'nichts wurde ueberschrieben');

		// zweiter Versuch: jetzt ohne Stoerung
		await a.ctl.retryConflict();
		assert.equal(a.ctl.state, 'idle');
		assert.equal(stand().name, 'Fremd 2');
		assert.equal((dc().metric_alert_levels as Record<string, unknown>).wind, 'sensibel', 'A ging nicht verloren');
		assert.equal(rc().morning_time, '08:00:00', 'B ging nicht verloren');
	});
});
