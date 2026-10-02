// Fix-Loop 3, Issue #1433 — F203 und F206: Schutzbedingungen, die bisher ohne Wache wirkten.
//
// F203: „Nochmal speichern" baut die Reiter nach vollem Erfolg nur neu auf ('wiederholt'),
//       wenn nichts Neues ansteht. Tippt der Nutzer waehrend der Wiederholung (ausstehender
//       Speichervorgang), darf KEIN Neuaufbau ueber die Eingabe laufen; beide Eingaben
//       landen auf dem Server. (Die Teilbedingung `state === 'idle'` ist nach dem Schleifen-
//       ende durch Konstruktion erfuellt, sobald Liste leer und nichts aussteht — aequivalent,
//       s. Rueckmeldung; die Bedingung `Liste leer` ist durch trip_retry_fehlerpfade bewacht.)
// F206: bei offenem Konflikt wird der neue Pausen-/Archiv-Status angezeigt (AC-9: Konfliktanzeige
//       bleibt, lokaler Stand wird nicht still ersetzt — der Status selbst ist kein Fremdstand,
//       sondern das Ergebnis der eigenen Aktion).
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/trip-detail/__tests__/trip_retry_adoption_schutz.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../api.ts';
import { clearEtagRegistry, istKonflikt } from '../../../etagRegistry.ts';
import { createFakeTripServer, type FakeTripServer } from '../../../__tests__/fakeTripServer.ts';
import * as P from './tripMehrreiterPruefstand.ts';

let server: FakeTripServer;
let langsamePuts = false;

beforeEach(async () => {
	clearEtagRegistry();
	langsamePuts = false;
	server = createFakeTripServer({ merge: true, latencyMs: (m) => (m === 'PUT' && langsamePuts ? 60 : 0) });
	server.install();
	server.seed(P.TRIP_ID, P.vollerTrip());
	await api.get(P.TRIP_PFAD);
});
afterEach(() => server.restore());

const stand = () => server.stand(P.TRIP_ID);

describe('F203: Eingabe waehrend der Wiederholung ⇒ kein Neuaufbau ueber die Eingabe', () => {
	test("Nutzer tippt im Versand-Reiter, waehrend 'Nochmal speichern' laeuft ⇒ kein 'wiederholt', beide Eingaben landen auf dem Server", async () => {
		server.foreignWrite(P.TRIP_ID, { name: 'Fremder Name' });
		const a = P.neuerAufbau();
		const seite = await P.tripSeite(a, server);
		const alarme = await P.alarmeReiter(P.neuerAufbau(seite.trip(), a.ctl));
		alarme.empfindlichkeitAendern('wind', 'sensibel');
		await P.fertig(a.ctl);
		assert.equal(a.ctl.state, 'conflict', 'Vorbedingung: 412');
		const versand = await P.versandReiter(P.neuerAufbau(seite.trip(), a.ctl));

		langsamePuts = true;
		const retry = a.ctl.retryConflict();
		await new Promise((r) => setTimeout(r, 20)); // der Wiederholungs-PUT ist unterwegs
		versand.aendern({ morning_time: '08:00:00' }); // Nutzer tippt: ausstehender Speichervorgang
		await retry;
		langsamePuts = false;

		assert.equal(a.ctl.hasPending, true, 'Vorbedingung: die Eingabe steht aus');
		assert.equal(seite.inst.u.uebernommeneFassung, 0, 'KEIN Neuaufbau der Reiter ueber die ausstehende Eingabe');

		await P.fertig(a.ctl);
		const rc = stand().report_config as Record<string, unknown>;
		const dc = stand().display_config as Record<string, unknown>;
		assert.equal((dc.metric_alert_levels as Record<string, unknown>).wind, 'sensibel', 'die Eingabe aus der Wiederholung steht auf dem Server');
		assert.equal(rc.morning_time, '08:00:00', 'und die waehrenddessen getippte auch');
		assert.equal(a.ctl.state, 'idle');
	});

	test("Gegenprobe: ohne Eingabe waehrend der Wiederholung baut die Seite nach vollem Erfolg einmal neu auf", async () => {
		server.foreignWrite(P.TRIP_ID, { name: 'Fremder Name' });
		const a = P.neuerAufbau();
		const seite = await P.tripSeite(a, server);
		const alarme = await P.alarmeReiter(P.neuerAufbau(seite.trip(), a.ctl));
		alarme.empfindlichkeitAendern('wind', 'sensibel');
		await P.fertig(a.ctl);
		await a.ctl.retryConflict();
		assert.equal(seite.inst.u.uebernommeneFassung, 1);
	});
});

describe('F206: Pausieren/Archivieren bei offenem Konflikt zeigt den neuen Status', () => {
	async function konfliktUndSeite() {
		server.foreignWrite(P.TRIP_ID, { name: 'Fremder Name' });
		const a = P.neuerAufbau();
		const alarme = await P.alarmeReiter(a);
		alarme.empfindlichkeitAendern('wind', 'sensibel');
		await P.fertig(a.ctl);
		assert.equal(a.ctl.state, 'conflict', 'Vorbedingung: Konflikt offen');
		return { a, seite: await P.tripSeite(a, server) };
	}

	test('Pausieren: `trip.paused_at` ist gesetzt, die Konfliktanzeige bleibt, der lokale Stand wird nicht durch den Serverstand ersetzt', async () => {
		const { a, seite } = await konfliktUndSeite();
		await seite.pausieren();
		assert.ok(seite.trip().paused_at, 'der neue Pausen-Status wird angezeigt');
		assert.equal(a.ctl.state, 'conflict', 'AC-9: Konfliktanzeige bleibt');
		assert.equal(istKonflikt(P.TRIP_ID), true);
		assert.notEqual(seite.trip().name, 'Fremder Name', 'AC-9: kein stilles Ersetzen des lokalen Stands');
	});

	test('Archivieren: `trip.archived_at` ist gesetzt, die Konfliktanzeige bleibt', async () => {
		const { a, seite } = await konfliktUndSeite();
		await seite.archivieren();
		assert.ok(seite.trip().archived_at, 'der neue Archiv-Status wird angezeigt');
		assert.equal(a.ctl.state, 'conflict');
		assert.notEqual(seite.trip().name, 'Fremder Name');
	});
});
