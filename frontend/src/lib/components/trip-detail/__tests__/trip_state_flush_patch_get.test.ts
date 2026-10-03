// TDD RED — Issue #1433, AC-8, AC-9 (Lieferstufe 3, §5 „Pausieren/Archivieren"):
// Pausieren/Archivieren (PATCH /state, bewusst ohne If-Match — S2 AC-15) verwirft
// heute den ETag (`discardEtag`, +page.svelte:137) und ersetzt `trip` durch die
// PATCH-Antwort. Der naechste Schreibvorgang laeuft damit unbedingt. Neu:
//   (a) offene Speichervorgaenge des Controllers flushen,
//   (b) PATCH /state,
//   (c) GET des Trips — die GET-Antwort ersetzt `trip` UND den ETag gemeinsam.
// Bei offenem Konflikt wird NICHTS adoptiert, der Konflikt bleibt bestehen.
//
// Spec: docs/specs/bugfix/trip_mehrreiter_konfliktschutz.md — §5, AC-8, AC-9,
//       Test Plan `trip_state_flush_patch_get`; Known Limitation „PATCH /state".
//
// Ersetzt die Quelltext-Zusicherung „sendStateUpdate verwirft den ETag" aus
// `tripStateDiscardsEtag.test.ts` (dort bewusst umgeschrieben) durch eine
// VERHALTENS-Zusicherung: der ECHTE Klick-Handler der Seite
// (`handlePauseClick`/`handleArchiveConfirm`, Instanz-Skript von +page.svelte)
// laeuft gegen den Ersatz-Server; gemessen wird Reihenfolge, Registry und `trip`.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/trip-detail/__tests__/trip_state_flush_patch_get.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../api.ts';
import * as registry from '../../../etagRegistry.ts';
import { clearEtagRegistry, getKnownEtag } from '../../../etagRegistry.ts';
import { createFakeTripServer, type FakeTripServer } from '../../../__tests__/fakeTripServer.ts';
import * as P from './tripMehrreiterPruefstand.ts';

let server: FakeTripServer;
const FREMDE_METRIKEN = [{ metric_id: 'cape', enabled: true, aggregations: ['max'] }];

beforeEach(async () => {
	clearEtagRegistry();
	server = createFakeTripServer({ merge: true });
	server.install();
	server.seed(P.TRIP_ID, P.vollerTrip());
	await api.get(P.TRIP_PFAD); // die Seite wurde mit diesem Stand geladen
});
afterEach(() => server.restore());

const stand = () => server.stand(P.TRIP_ID);
/** Reihenfolge der Anfragen auf die Trip-Ressource als „METHODE pfad-ende". */
const ablauf = (): string[] =>
	server.calls.map((c) => `${c.method} ${c.path.replace(P.TRIP_PFAD, '') || '/'}`);

describe('AC-8: Pausieren — Flush, PATCH, GET; trip und ETag gemeinsam aus der GET-Antwort', () => {
	test('mit offenem Speichervorgang: erst PUT (Flush), dann PATCH /state, dann GET', async () => {
		const a = P.neuerAufbau();
		const alarme = await P.alarmeReiter(a);
		alarme.kanalUmschalten('sms'); // Debounce-Fenster offen: schedule() hat gespeichert-Anzeige gesetzt
		assert.equal(a.ctl.hasPending, true, 'Messaufbau: ein Speichervorgang steht aus');
		server.calls.length = 0;

		const seite = await P.tripSeite(a, server);
		await seite.pausieren();
		a.ctl.cancel(); // Aufraeumen: kein Timer ueber das Testende hinaus

		const folge = ablauf();
		const iPut = folge.findIndex((x) => x.startsWith('PUT'));
		const iPatch = folge.indexOf('PATCH /state');
		const iGet = folge.findIndex((x, i) => x === 'GET /' && i > iPatch);
		assert.ok(iPut >= 0, `der ausstehende Speichervorgang muss VOR dem PATCH geflusht werden, Ablauf: ${folge.join(' → ')}`);
		assert.ok(iPatch > iPut, `PATCH /state muss NACH dem Flush kommen, Ablauf: ${folge.join(' → ')}`);
		assert.ok(iGet > iPatch, `nach dem PATCH muss ein GET des Trips folgen, Ablauf: ${folge.join(' → ')}`);
		assert.equal(
			(stand().alert_channels as Record<string, unknown>).sms,
			true,
			'der geflushte Speichervorgang steht auf dem Server (nicht durch das Pausieren verloren)'
		);
	});

	test('trip und ETag kommen gemeinsam aus der GET-Antwort (Fremdaenderung sichtbar, ETag aktuell)', async () => {
		server.foreignWrite(P.TRIP_ID, { name: 'Fremder Name', display_config: { metrics: FREMDE_METRIKEN } });
		const a = P.neuerAufbau(); // lokaler trip ist veraltet
		const seite = await P.tripSeite(a, server);
		await seite.pausieren();

		const t = seite.trip();
		assert.equal(t.name, 'Fremder Name', '`trip` muss aus der GET-Antwort kommen (enthaelt die Fremdaenderung)');
		assert.ok(t.paused_at, '… und den neuen Pausen-Status tragen');
		assert.deepEqual((t.display_config as Record<string, unknown>).metrics, FREMDE_METRIKEN);
		assert.ok(getKnownEtag(P.TRIP_ID), 'der ETag darf nach dem Pausieren nicht verworfen sein (discardEtag entfaellt)');
		assert.equal(
			getKnownEtag(P.TRIP_ID),
			server.etagOf(P.TRIP_ID),
			'der ETag muss zum Stand der GET-Antwort passen — gemeinsam mit `trip` uebernommen'
		);
	});

	test('ein folgendes Speichern traegt If-Match und gelingt; die Fremdaenderung bleibt', async () => {
		server.foreignWrite(P.TRIP_ID, { display_config: { metrics: FREMDE_METRIKEN } });
		const a = P.neuerAufbau();
		const seite = await P.tripSeite(a, server);
		await seite.pausieren();
		server.calls.length = 0;
		const etagNachPausieren = server.etagOf(P.TRIP_ID);

		const alarme = await P.alarmeReiter(a);
		alarme.kanalUmschalten('sms');
		await P.fertig(a.ctl);

		const put = server.calls.find((c) => c.method === 'PUT')!;
		assert.ok(put.ifMatch, 'AC-8: nach dem Pausieren schreibt der naechste Vorgang NICHT unbedingt (kein discardEtag)');
		assert.equal(put.ifMatch, etagNachPausieren, 'das If-Match ist der Stempel der GET-Antwort nach dem Pausieren');
		assert.equal(put.status, 200, 'mit dem frischen Stempel aus der GET-Antwort geht das Speichern durch');
		assert.deepEqual(
			(stand().display_config as Record<string, unknown>).metrics,
			FREMDE_METRIKEN,
			'das folgende Speichern ueberschreibt keine fremde Aenderung'
		);
		assert.equal((stand().alert_channels as Record<string, unknown>).sms, true);
	});

	test('Archivieren: derselbe Ablauf (PATCH, dann GET, ETag bleibt)', async () => {
		const a = P.neuerAufbau();
		const seite = await P.tripSeite(a, server);
		server.calls.length = 0;
		await seite.archivieren();

		const folge = ablauf();
		const iPatch = folge.indexOf('PATCH /state');
		assert.ok(iPatch >= 0, `Messaufbau: PATCH /state erwartet, Ablauf: ${folge.join(' → ')}`);
		assert.ok(folge.some((x, i) => x === 'GET /' && i > iPatch), `nach dem Archivieren muss ein GET folgen, Ablauf: ${folge.join(' → ')}`);
		assert.equal(getKnownEtag(P.TRIP_ID), server.etagOf(P.TRIP_ID));
		assert.ok(seite.trip().archived_at, '`trip` traegt den neuen Status aus der Server-Antwort');
	});
});

describe('AC-9: offener Konflikt — nichts wird adoptiert, die Konfliktanzeige bleibt', () => {
	test('Pausieren bei Konflikt: Anzeige bleibt, ETag bleibt der alte, trip wird nicht still durch den Serverstand ersetzt', async () => {
		server.foreignWrite(P.TRIP_ID, { name: 'Fremder Name', display_config: { metrics: FREMDE_METRIKEN } });
		const a = P.neuerAufbau();
		const alarme = await P.alarmeReiter(a);
		alarme.empfindlichkeitAendern('wind', 'sensibel');
		await P.fertig(a.ctl);
		assert.equal(a.ctl.state, 'conflict', 'Vorbedingung: Konflikt offen');
		const alt = getKnownEtag(P.TRIP_ID);
		const f = (registry as unknown as { istKonflikt?: (i: string) => boolean }).istKonflikt;
		assert.equal(typeof f, 'function', 'etagRegistry.ts muss `istKonflikt(id)` exportieren');

		const seite = await P.tripSeite(a, server);
		await seite.pausieren();

		assert.equal(a.ctl.state, 'conflict', 'AC-9: die Konfliktanzeige bleibt bestehen');
		assert.equal(f!(P.TRIP_ID), true, 'die Konflikt-Markierung bleibt');
		assert.equal(getKnownEtag(P.TRIP_ID), alt, 'bei offenem Konflikt wird der ETag NICHT adoptiert');
		assert.notEqual(
			seite.trip().name,
			'Fremder Name',
			'der lokale Stand darf nicht still durch den Serverstand ersetzt werden (sonst ginge die abgelehnte Eingabe verloren)'
		);
		assert.deepEqual(
			(stand().display_config as Record<string, unknown>).metrics,
			FREMDE_METRIKEN,
			'die Fremdaenderung auf dem Server bleibt unveraendert'
		);
	});

	test('Archivieren bei Konflikt: dieselbe Zusicherung', async () => {
		server.foreignWrite(P.TRIP_ID, { name: 'Fremder Name' });
		const a = P.neuerAufbau();
		const alarme = await P.alarmeReiter(a);
		alarme.empfindlichkeitAendern('wind', 'sensibel');
		await P.fertig(a.ctl);
		const alt = getKnownEtag(P.TRIP_ID);

		const seite = await P.tripSeite(a, server);
		await seite.archivieren();

		assert.equal(a.ctl.state, 'conflict');
		assert.equal(getKnownEtag(P.TRIP_ID), alt);
		assert.notEqual(seite.trip().name, 'Fremder Name');
	});
});
