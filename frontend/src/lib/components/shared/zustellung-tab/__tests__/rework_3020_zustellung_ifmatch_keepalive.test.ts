// Rework #3020 R1, AC-7: Speicherweg des Reiters „Zustellung“ beim Trip -- der regulaere PUT traegt
// If-Match und kein keepalive, der Flush beim Entladen geht mit `keepalive: true` noch im selben Tick
// hinaus, und der Stempel der Antwort gilt fuer den naechsten Schreibvorgang.
// Ersatz fuer den mit #3357 geloeschten trip_versand_reiter_ohne_dauer_keepalive.test.ts (galt dem
// geloeschten Versand-Reiter); Teilersatz fuer den Trip-Speichertakt:
// shared/__tests__/trip_speicherung_reicht_keepalive_durch.test.ts.
//
// Spec: docs/specs/modules/rework_3020_pruefungen_wiederherstellen.md (AC-7)
//
// Pruefstand: ECHTES `api` (If-Match aus der etagRegistry) gegen den Ersatz-Server, der If-Match je
// Anfrage aufzeichnet und prueft; ECHTE SaveStatus-Instanz (Muster trip_speicherung_reicht_keepalive_durch).
//
//   cd frontend && npm test -- src/lib/components/shared/zustellung-tab/__tests__/rework_3020_zustellung_ifmatch_keepalive.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../../api.ts';
import { clearEtagRegistry, getKnownEtag } from '../../../../etagRegistry.ts';
import { SaveStatus } from '../../../../stores/saveStatusStore.svelte.ts';
import { createFakeTripServer, type FakeTripServer } from '../../../../__tests__/fakeTripServer.ts';
import { standAusTrip, type ZustellungStand } from '../zustellungModell.ts';
import { erstelleZustellungSpeicherung } from '../zustellungSpeicherung.ts';
import { tripVoll } from './zustellungTabDaten.ts';
import type { Trip } from '../../../../types.ts';

const TRIP_ID = 'trip-2795';
const PFAD = `/api/trips/${TRIP_ID}`;

/** Echte SaveStatus-Instanz ohne Konstruktor (Runen-Felder), Trip-Kontext. */
function controller(): SaveStatus {
	const inst = Object.create(SaveStatus.prototype) as SaveStatus;
	const f = inst as unknown as Record<string, unknown>;
	f.state = 'idle';
	f.savedAt = null;
	f.error = null;
	f._timer = null;
	f._pendingFn = null;
	f._inflight = null;
	f._lastFailed = null;
	f._unresolvedError = null;
	f._tripId = TRIP_ID;
	return inst;
}

const puts = (server: FakeTripServer) => server.calls.filter((c) => c.method === 'PUT' && c.path === PFAD);

describe('Rework #3020 AC-7: Zustellung-Reiter (Trip) -- If-Match, keepalive, Antwort-Stempel', () => {
	let server: FakeTripServer;
	let basis: ZustellungStand;
	beforeEach(async () => {
		clearEtagRegistry();
		server = createFakeTripServer({ merge: true });
		server.seed(TRIP_ID, tripVoll());
		server.install();
		basis = standAusTrip((await api.get<Trip>(PFAD)) as Trip);
	});
	afterEach(() => server.restore());

	test('regulaeres Speichern: If-Match mit dem bekannten Stempel, kein keepalive; der Antwort-Stempel traegt den naechsten PUT', async () => {
		const geladen = getKnownEtag(TRIP_ID);
		assert.ok(geladen, 'Vorbedingung: der Stempel des geladenen Trips ist bekannt');
		const ctl = controller();
		const sp = erstelleZustellungSpeicherung({ context: 'route', id: TRIP_ID, client: api, saveController: ctl, basis });

		sp.aenderungMelden({ ...basis, morgenZeit: '08:00' });
		await ctl.flush();
		const erster = puts(server)[0];
		assert.equal(erster.status, 200, 'erster PUT angenommen');
		assert.equal(erster.ifMatch, geladen, 'der regulaere PUT muss den bekannten Stempel als If-Match tragen');
		assert.equal(erster.keepalive, false, 'ohne Entladen kein keepalive');
		const neuerStempel = server.etagOf(TRIP_ID);
		assert.notEqual(neuerStempel, geladen, 'Vorbedingung: der Server hat einen neuen Stempel vergeben');
		assert.equal(getKnownEtag(TRIP_ID), neuerStempel, 'der Stempel der Antwort muss uebernommen sein');

		sp.aenderungMelden({ ...basis, morgenZeit: '08:00', abendZeit: '19:00' });
		await ctl.flush();
		const zweiter = puts(server)[1];
		assert.equal(zweiter.ifMatch, neuerStempel, 'der naechste PUT muss den Stempel der letzten Antwort tragen');
		assert.equal(zweiter.status, 200, 'mit uebernommenem Stempel kein 412');
		assert.deepEqual(zweiter.anfrage, { report_config: { evening_time: '19:00:00' } }, 'nur der neue Unterschied geht hinaus');
		assert.equal(ctl.state, 'idle');
	});

	test('Flush beim Entladen: PUT noch im selben Tick, mit keepalive:true', async () => {
		const ctl = controller();
		const sp = erstelleZustellungSpeicherung({ context: 'route', id: TRIP_ID, client: api, saveController: ctl, basis });
		sp.aenderungMelden({ ...basis, briefing: { ...basis.briefing, sms: !basis.briefing.sms } });
		assert.equal(ctl.hasPending, true, 'Vorbedingung: Aenderung wartet im Speicher-Takt');
		const vorher = puts(server).length;

		const laeuft = ctl.flush({ keepalive: true });
		assert.equal(puts(server).length, vorher + 1, 'der PUT muss noch im Tick des Entladens abgesetzt sein');
		const put = puts(server).at(-1)!;
		assert.equal(put.keepalive, true, 'die Option keepalive:true des Waechters wurde verschluckt');
		assert.equal(put.ifMatch, null, 'ein Entlade-Flush traegt keinen If-Match (#1395 S3 AC-6)');

		await laeuft;
		assert.equal(put.status, 200);
		assert.equal((server.stand(TRIP_ID).report_config as Record<string, unknown>).send_sms, !basis.briefing.sms);
		assert.equal(ctl.hasPending, false);
	});
});
