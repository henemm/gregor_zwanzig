// Issue #1395 S3 — der Anfrage-Trichter (`$lib/api.ts`) fuehrt den Stempel.
// Spec: docs/specs/modules/issue_1395_s3_etag_registry.md — AC-1/2/7/8,
//   § "Ablauf in api.ts::request()".
// Der Trichter war bis hierher vollstaendig ungetestet — dies ist die erste
// Abdeckung ueberhaupt. Zum Ersatz-fetch siehe fakeTripServer.ts.

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../api.ts';
import { clearEtagRegistry, getKnownEtag, setKnownEtag } from '../etagRegistry.ts';
import { extractMessage } from '../stores/saveStatusStore.svelte.ts';
import {
	createFakeTripServer,
	PRECONDITION_FAILED_DETAIL,
	type FakeTripServer
} from './fakeTripServer.ts';

let server: FakeTripServer;

beforeEach(() => {
	clearEtagRegistry();
	server = createFakeTripServer();
	server.install();
});

afterEach(() => server.restore());

const lastCall = () => server.calls[server.calls.length - 1];

describe('Trichter: Stempel aufnehmen und mitschicken', () => {
	test('test_get_capturesEtagFromResponse', async () => {
		// GIVEN: der Server liefert bei GET einen ETag (S2 AC-1)
		// WHEN: die Tour ueber den Trichter geladen wird
		await api.get('/api/trips/gr20');

		// THEN: hat sich das Frontend den Stand gemerkt — genau den, den der
		// Server geschickt hat, unveraendert inklusive Anfuehrungszeichen.
		assert.equal(getKnownEtag('gr20'), server.etagOf('gr20'));
	});

	test('test_put_attachesIfMatch_whenStampKnown', async () => {
		// GIVEN: eine Tour wurde geladen, der Stand ist bekannt
		await api.get('/api/trips/gr20');
		const stampFromGet = getKnownEtag('gr20');
		assert.ok(stampFromGet, 'Vorbedingung: GET muss einen Stand hinterlassen');

		// WHEN: danach gespeichert wird
		await api.put('/api/trips/gr20', { name: 'GR20' });

		// THEN: traegt die Anfrage diesen Stand als If-Match — ohne dass die
		// aufrufende Komponente davon etwas wissen muss (AC-2).
		assert.equal(lastCall().method, 'PUT');
		assert.equal(lastCall().ifMatch, stampFromGet);
		assert.equal(lastCall().status, 200);
	});

	test('test_put_omitsIfMatch_whenStampUnknown', async () => {
		// GIVEN: fuer diese Tour ist in dieser Sitzung kein Stand bekannt
		assert.equal(getKnownEtag('unbekannt'), undefined);

		// WHEN: gespeichert wird
		await api.put('/api/trips/unbekannt', { name: 'X' });

		// THEN: geht die Anfrage OHNE Vorbedingung raus und wird angenommen —
		// exakt das Verhalten vor dieser Scheibe (AC-7).
		assert.equal(lastCall().ifMatch, null);
		assert.equal(lastCall().status, 200);
	});

	test('test_put_capturesNewEtagFromWriteResponse', async () => {
		// GIVEN: eine geladene Tour
		await api.get('/api/trips/gr20');
		const stampFromGet = getKnownEtag('gr20');

		// WHEN: gespeichert wird
		await api.put('/api/trips/gr20', { name: 'GR20' });

		// THEN: hat der Trichter den NEUEN Stempel aus der Schreib-Antwort
		// uebernommen (ADR-0036: der alte aus dem GET ist ab dem ersten
		// Speichern veraltet).
		const stampAfterPut = getKnownEtag('gr20');
		assert.ok(stampAfterPut, 'nach dem PUT muss ein Stand bekannt sein');
		assert.notEqual(stampAfterPut, stampFromGet);
		assert.equal(stampAfterPut, server.etagOf('gr20'));
	});

	test('test_weatherConfigPath_sharesStampWithTripPath', async () => {
		// GIVEN: der Stempel gehoert zur TOUR, nicht zur Adresse — beide Pfade
		// beschreiben dieselbe Datei.
		await api.get('/api/trips/gr20');

		// WHEN: ueber den weather-config-Pfad geschrieben wird
		await api.put('/api/trips/gr20/weather-config', { buckets: [] });

		// THEN: wurde derselbe Registry-Eintrag benutzt und fortgeschrieben
		assert.equal(lastCall().path, '/api/trips/gr20/weather-config');
		assert.ok(lastCall().ifMatch, 'auch der weather-config-PUT traegt den Stand der Tour');
		assert.equal(getKnownEtag('gr20'), server.etagOf('gr20'));
	});
});

describe('Trichter: Header-Zusammenfuehrung', () => {
	test('test_put_mergesHeadersFieldwise_contentTypeSurvives', async () => {
		// GIVEN: ein Aufruf mit eigenen Zusatz-Headern und bekanntem Stand
		await api.get('/api/trips/gr20');
		const stamp = getKnownEtag('gr20');

		// WHEN: gespeichert wird
		await api.put('/api/trips/gr20', { a: 1 }, { headers: { 'X-Test': 'ja' } });

		// THEN: bleibt Content-Type erhalten (der Server verschluckt sich sonst am
		// Rumpf), der eigene Header kommt an, und If-Match ist zusaetzlich da.
		assert.equal(lastCall().contentType, 'application/json');
		assert.equal(lastCall().ifMatch, stamp);
		assert.equal(lastCall().status, 200);
	});
});

describe('Trichter: Pfadfilter', () => {
	test('test_put_neverAttachesIfMatch_onStateOrWaypointPaths', async () => {
		// GIVEN: der Stand der Tour ist bekannt
		await api.get('/api/trips/gr20');
		assert.ok(getKnownEtag('gr20'));

		// WHEN: Unterpfade angesprochen werden, die der Server nicht prueft (S2 AC-15)
		await api.put('/api/trips/gr20/state', { paused: true });
		assert.equal(lastCall().ifMatch, null);

		await api.put('/api/trips/gr20/waypoints/wp1/confirm', {});

		// THEN: geht dort nie ein If-Match raus
		assert.equal(lastCall().ifMatch, null);
	});

	test('test_nonTripPaths_completelyUnaffected', async () => {
		// GIVEN: irgendein Stand ist bekannt
		setKnownEtag('gr20', '"irgendwas"');

		// WHEN: eine echt fremde Ressource angesprochen wird (Orte — Issue #1395
		// betrifft sie nie). Orts-Vergleiche sind seit S6 KEIN Fremdpfad mehr
		// (siehe Block "Trichter: Ortsvergleich (S6)" unten) — hier wird nur
		// noch geprueft, dass ein UNBEKANNTER Compare-Preset-Stand (kein
		// vorheriges GET fuer 'abc') ebenfalls kein If-Match traegt, exakt wie
		// bei einer unbekannten Tour (AC-7-Analogon).
		await api.put('/api/locations/korsika', { name: 'Korsika' });
		assert.equal(lastCall().ifMatch, null);

		await api.put('/api/compare/presets/abc', { name: 'Vergleich' });

		// THEN: kein If-Match, und die Eintraege fremder Ressourcen bleiben
		// unberuehrt. Der Orts-Vergleich selbst fuehrt seit S6 einen Eintrag —
		// aus der Schreib-Antwort, exakt wie eine Tour (siehe
		// test_put_capturesNewEtagFromWriteResponse oben).
		assert.equal(lastCall().ifMatch, null);
		assert.equal(getKnownEtag('gr20'), '"irgendwas"');
		assert.equal(getKnownEtag('korsika'), undefined);
		assert.equal(getKnownEtag('abc'), server.etagOf('abc'));
	});
});

// TDD RED — Issue #1395 S6: Der Trichter (`api.ts`/`etagRegistry.ts`) muss
// Compare-Preset-Pfade (`/api/compare/presets/{id}`) genauso behandeln wie
// Trip-Pfade — GET nimmt den Stempel auf, PUT traegt ihn automatisch mit.
// `fakeTripServer.ts` bildet den ZIEL-Serververtrag bereits ab (S6 generalisiert
// dort `TRIP_PATH_RE` mit); diese Tests beweisen die noch fehlende FRONTEND-Seite
// (`etagRegistry.ts`s `TRIP_PATH_RE`/`extractTripId` matchen Compare-Preset-Pfade
// noch nicht) — MUESSEN jetzt rot sein, werden nach der Implementierung gruen.
//
// Spec: docs/specs/modules/issue_1395_s6_ortsvergleich_etag.md § AC-17
describe('Trichter: Ortsvergleich (S6)', () => {
	test('test_get_capturesEtagFromComparePresetResponse', async () => {
		// GIVEN: der (Ziel-)Server liefert bei GET auf ein Compare-Preset einen ETag
		// WHEN: das Preset ueber den Trichter geladen wird
		await api.get('/api/compare/presets/cp-abc');

		// THEN: hat sich das Frontend den Stand gemerkt — exakt wie bei einer Tour
		assert.equal(getKnownEtag('cp-abc'), server.etagOf('cp-abc'));
	});

	test('test_put_attachesIfMatch_whenComparePresetStampKnown', async () => {
		// GIVEN: ein Compare-Preset wurde geladen, der Stand ist bekannt
		await api.get('/api/compare/presets/cp-abc');
		const stampFromGet = getKnownEtag('cp-abc');
		assert.ok(stampFromGet, 'Vorbedingung: GET muss einen Stand hinterlassen');

		// WHEN: danach gespeichert wird
		await api.put('/api/compare/presets/cp-abc', { name: 'Vergleich' });

		// THEN: traegt die Anfrage diesen Stand als If-Match — ohne dass der
		// Compare-Editor davon etwas wissen muss (AC-17)
		assert.equal(lastCall().method, 'PUT');
		assert.equal(lastCall().ifMatch, stampFromGet);
		assert.equal(lastCall().status, 200);
	});

	test('test_put_omitsIfMatch_whenComparePresetStampUnknown', async () => {
		// GIVEN: fuer dieses Preset ist in dieser Sitzung kein Stand bekannt
		assert.equal(getKnownEtag('cp-unbekannt'), undefined);

		// WHEN: gespeichert wird (z. B. direkt nach dem Anlegen)
		await api.put('/api/compare/presets/cp-unbekannt', { name: 'X' });

		// THEN: geht die Anfrage OHNE Vorbedingung raus und wird angenommen
		assert.equal(lastCall().ifMatch, null);
		assert.equal(lastCall().status, 200);
	});

	test('test_tripAndComparePresetStamps_doNotCollide_evenWithSameSuffix', async () => {
		// GIVEN: eine Tour und ein Compare-Preset, deren IDs sich nur im
		// `cp-`-Praefix unterscheiden (echter Namensraum, kein Test-Artefakt —
		// `newComparePresetID()` erzeugt IDs immer mit diesem Praefix)
		await api.get('/api/trips/abc');
		await api.get('/api/compare/presets/cp-abc');
		const tripStamp = getKnownEtag('abc');
		const presetStamp = getKnownEtag('cp-abc');

		// THEN: getrennte Registry-Eintraege, kein gegenseitiges Ueberschreiben
		assert.ok(tripStamp, 'Vorbedingung: Trip-Stand bekannt');
		assert.ok(presetStamp, 'Vorbedingung: Preset-Stand bekannt');

		// WHEN: beide gespeichert werden
		await api.put('/api/trips/abc', { name: 'Trip' });
		await api.put('/api/compare/presets/cp-abc', { name: 'Preset' });

		// THEN: jede Schreibanfrage traegt AUSSCHLIESSLICH ihren eigenen Stand
		const tripCall = server.calls[server.calls.length - 2];
		const presetCall = lastCall();
		assert.equal(tripCall.ifMatch, tripStamp);
		assert.equal(presetCall.ifMatch, presetStamp);
		assert.notEqual(tripStamp, presetStamp);
	});
});

/** Erzeugt eine echte 412-Ablehnung: Stand bekannt, aber veraltet. */
async function rejectedWithStaleStamp(): Promise<unknown> {
	await api.get('/api/trips/gr20');
	setKnownEtag('gr20', '"veraltet"');
	try {
		await api.put('/api/trips/gr20', { name: 'X' });
		assert.fail('der Schreibvorgang haette mit 412 abgelehnt werden muessen');
	} catch (e) {
		return e;
	}
}

describe('Trichter: Fehlerobjekt (AC-8)', () => {
	test('test_thrownError_carriesStatusAlongsideExistingFields', async () => {
		// GIVEN/WHEN: ein Schreibvorgang wird wegen veraltetem Stand abgelehnt
		const thrown = await rejectedWithStaleStamp();

		// THEN: traegt das geworfene Objekt den Statuscode ZUSAETZLICH zu den
		// bisherigen Feldern — `error` und `detail` bleiben unveraendert.
		// Wortgleich mit `preconditionFailedDetail` in internal/handler/etag.go:26-28
		// — kein Teilwort-Treffer, sonst koennte der Pruefstand von der
		// Wirklichkeit abweichen, ohne dass es auffaellt.
		const err = thrown as { status?: number; error?: string; detail?: string };
		assert.equal(err.status, 412);
		assert.equal(err.error, 'precondition_failed');
		assert.equal(err.detail, PRECONDITION_FAILED_DETAIL);
	});

	test('test_extractMessage_unaffectedByNewStatusField', async () => {
		// GIVEN: dieselbe 412-Ablehnung
		const thrown = await rejectedWithStaleStamp();

		// WHEN: der Speicher-Anzeiger die Meldung ableitet
		const message = extractMessage(thrown);

		// THEN: erscheint die deutsche Servermeldung — nicht "Fehler beim
		// Speichern", nicht der rohe Statuscode. Das neue `status`-Feld aendert
		// daran nichts.
		assert.equal(message, (thrown as { detail: string }).detail);
		assert.notEqual(message, 'Fehler beim Speichern');
		assert.ok(!/412/.test(message), 'der rohe Statuscode darf nicht in der Meldung landen');
	});

	test('test_412_discardsStampSoNextAttemptGoesThrough', async () => {
		// GIVEN: eine Ablehnung wegen veraltetem Stand
		await rejectedWithStaleStamp();

		// THEN: ist der gemerkte Stand verworfen — sonst scheiterte jeder weitere
		// Versuch endlos am selben Wert und der Nutzer kaeme ohne Neuladen nicht
		// mehr heraus.
		assert.equal(getKnownEtag('gr20'), undefined);

		// WHEN: erneut gespeichert wird
		await api.put('/api/trips/gr20', { name: 'X' });

		// THEN: geht der Versuch ohne Vorbedingung durch (einmal melden, dann
		// nicht mehr im Weg stehen).
		assert.equal(lastCall().ifMatch, null);
		assert.equal(lastCall().status, 200);
	});

	test('test_nonPreconditionError_keepsStamp', async () => {
		// GIVEN: ein bekannter Stand und ein Server, der mit 400 antwortet
		await api.get('/api/trips/gr20');
		const stamp = getKnownEtag('gr20');
		const realFetch = globalThis.fetch;
		(globalThis as { fetch: unknown }).fetch = async () =>
			new Response(JSON.stringify({ error: 'validation_error', detail: 'Ungültige Etappe' }), {
				status: 400,
				headers: { 'Content-Type': 'application/json' }
			});

		// WHEN: der Schreibvorgang aus einem anderen Grund scheitert
		let thrown: unknown;
		try {
			await api.put('/api/trips/gr20', { name: 'X' });
		} catch (e) {
			thrown = e;
		} finally {
			(globalThis as { fetch: unknown }).fetch = realFetch;
		}

		// THEN: bleibt der Stand erhalten — nur 412 belegt, dass er veraltet ist.
		assert.equal((thrown as { status?: number }).status, 400);
		assert.equal(getKnownEtag('gr20'), stamp);
	});
});
