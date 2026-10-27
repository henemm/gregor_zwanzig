// Fix-Loop 3, Issue #1433 — F201: nach einem Konflikt zeigt jeder (wieder) gemountete
// Reiter die ungesicherte Eingabe des Nutzers (EINE Wahrheit).
//
// Wurzel: ungesicherte Eingaben lagen nur in der Controller-Liste (Closures); der
// Seitenstand `trip`, aus dem Reiter beim Mount lesen, wusste davon nichts. Invariante:
// Seitenstand = letzter Serverstand ⊕ ausstehende Eigenfeld-Nutzlasten der Liste.
//
// Gemessen ueber die ECHTE Trip-Seite (`tripSeite`, Skript der +page.svelte mit ihrem
// echten Callback am Controller) und die echten Reiter-Skripte: der neue Reiter wird aus
// dem `trip` der SEITE gebaut, nicht aus einer Testkopie. Server: Fake im Go-Merge-Modus.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/trip-detail/__tests__/trip_retry_reiterwechsel_eingabe_bleibt.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../api.ts';
import { clearEtagRegistry } from '../../../etagRegistry.ts';
import { createFakeTripServer, type FakeTripServer } from '../../../__tests__/fakeTripServer.ts';
import * as P from './tripMehrreiterPruefstand.ts';

let server: FakeTripServer;

beforeEach(async () => {
	clearEtagRegistry();
	server = createFakeTripServer({ merge: true });
	server.install();
	server.seed(P.TRIP_ID, P.vollerTrip());
	await api.get(P.TRIP_PFAD);
});
afterEach(() => server.restore());

const stand = () => server.stand(P.TRIP_ID);
const dc = () => stand().display_config as Record<string, unknown>;
const rc = () => stand().report_config as Record<string, unknown>;
const levels = () => dc().metric_alert_levels as Record<string, unknown>;

/** Aufbau fuer einen NEUEN Reiter: Trip aus der Seite, gleicher Controller (Reiterwechsel/Rueckkehr). */
const ausSeite = (a: P.Aufbau, seite: { trip(): Record<string, unknown> }): P.Aufbau => P.neuerAufbau(seite.trip(), a.ctl);

describe('F201 (Trip): Reiter verlassen und zurueckkehren nach einem Konflikt', () => {
	test('Alarme: der zurueckgekehrte Reiter zeigt die erste Eingabe; zweite Aenderung + Nochmal speichern ⇒ BEIDE auf dem Server', async () => {
		server.foreignWrite(P.TRIP_ID, { name: 'Fremder Name' });
		const a = P.neuerAufbau();
		const seite = await P.tripSeite(a, server);

		const erster = await P.alarmeReiter(ausSeite(a, seite));
		erster.empfindlichkeitAendern('wind', 'sensibel');
		await P.fertig(a.ctl);
		assert.equal(a.ctl.state, 'conflict', 'Vorbedingung: 412');

		// Reiterwechsel Versand und zurueck: der Alarme-Reiter wird NEU aus dem Seitenstand gebaut
		await P.versandReiter(ausSeite(a, seite));
		const zurueck = await P.alarmeReiter(ausSeite(a, seite));
		assert.equal(
			(zurueck.inst.u.routeMetricLevels as Record<string, unknown>).wind,
			'sensibel',
			'der neu gemountete Reiter zeigt die ungesicherte Eingabe, nicht den Serverstand von vorher'
		);

		zurueck.empfindlichkeitAendern('precipitation', 'ruhig');
		await P.fertig(a.ctl);
		assert.equal(a.ctl.state, 'conflict', 'Vorbedingung: weiter Konflikt (kein „Gespeichert")');

		await a.ctl.retryConflict();
		assert.equal(a.ctl.state, 'idle');
		assert.equal(stand().name, 'Fremder Name', 'die Fremdaenderung bleibt');
		assert.equal(levels().wind, 'sensibel', 'die ERSTE Eingabe ging nicht verloren');
		assert.equal(levels().precipitation, 'ruhig', 'und die zweite steht auch auf dem Server');
	});

	test('Alarme ohne zweite Aenderung: Nochmal speichern schreibt genau das, was der Reiter zeigt', async () => {
		server.foreignWrite(P.TRIP_ID, { name: 'Fremder Name' });
		const a = P.neuerAufbau();
		const seite = await P.tripSeite(a, server);

		const erster = await P.alarmeReiter(ausSeite(a, seite));
		erster.empfindlichkeitAendern('wind', 'sensibel');
		await P.fertig(a.ctl);
		const zurueck = await P.alarmeReiter(ausSeite(a, seite));
		const angezeigt = (zurueck.inst.u.routeMetricLevels as Record<string, unknown>).wind;

		await a.ctl.retryConflict();
		assert.equal(a.ctl.state, 'idle');
		assert.equal(levels().wind, angezeigt, 'Server und Anzeige tragen denselben Wert (keine zwei Wahrheiten)');
		assert.equal(angezeigt, 'sensibel');
	});

	test('Versand: der zurueckgekehrte Reiter zeigt die erste Eingabe; zweite Aenderung ⇒ beide auf dem Server', async () => {
		server.foreignWrite(P.TRIP_ID, { name: 'Fremder Name' });
		const a = P.neuerAufbau();
		const seite = await P.tripSeite(a, server);

		const erster = await P.versandReiter(ausSeite(a, seite));
		erster.aendern({ morning_time: '08:00:00' });
		await P.fertig(a.ctl);
		assert.equal(a.ctl.state, 'conflict', 'Vorbedingung: 412');

		const zurueck = await P.versandReiter(ausSeite(a, seite));
		assert.equal(
			(zurueck.inst.u.reportConfig as Record<string, unknown>).morning_time,
			'08:00:00',
			'der neu gemountete Versand-Reiter zeigt die ungesicherte Eingabe'
		);
		zurueck.aendern({ evening_time: '20:00:00' });
		await P.fertig(a.ctl);

		await a.ctl.retryConflict();
		assert.equal(a.ctl.state, 'idle');
		assert.equal(stand().name, 'Fremder Name');
		assert.equal(rc().morning_time, '08:00:00', 'die erste Eingabe ging nicht verloren');
		assert.equal(rc().evening_time, '20:00:00', 'die zweite steht auch auf dem Server');
	});

	test("bei 'geholt' (Retry-GET) enthaelt der Seitenstand GET-Stand ⊕ ausstehende Eingaben (kein Stand ohne Eingabe)", async () => {
		server.foreignWrite(P.TRIP_ID, { name: 'Fremder Name' });
		const a = P.neuerAufbau();
		const seite = await P.tripSeite(a, server);
		const erster = await P.alarmeReiter(ausSeite(a, seite));
		erster.empfindlichkeitAendern('wind', 'sensibel');
		await P.fertig(a.ctl);

		// der Retry scheitert an den PUTs (500) — nach dem GET steht `trip` auf GET ⊕ Eingabe
		const basis = globalThis.fetch;
		(globalThis as { fetch: unknown }).fetch = async (input: unknown, init?: RequestInit) =>
			(init?.method ?? 'GET').toUpperCase() === 'PUT'
				? new Response(JSON.stringify({ error: 'boom' }), { status: 500, headers: { 'Content-Type': 'application/json' } })
				: basis(input as never, init);
		await a.ctl.retryConflict();
		(globalThis as { fetch: unknown }).fetch = basis;

		assert.equal(a.ctl.state, 'conflict');
		assert.equal(seite.trip().name, 'Fremder Name', 'GET-Stand (Fremdaenderung)');
		const lv = (seite.trip().display_config as Record<string, unknown>).metric_alert_levels as Record<string, unknown>;
		assert.equal(lv.wind, 'sensibel', 'ausstehende Eingabe ueberlagert den GET-Stand');
	});
});
