// Issue #1395 S3 — Kernfall (Doppel-PUT), Zwei-Fenster-Fall, Serialisierung.
// Spec: docs/specs/modules/issue_1395_s3_etag_registry.md — AC-3/4/7/9.
// Der Ersatz-Server (fakeTripServer.ts) verhaelt sich wie der S2-Go-Server:
// passender/fehlender If-Match → 200 + NEUER ETag, falscher → 412 ohne ETag;
// die zuletzt geschriebenen Daten bleiben abfragbar.

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../api.ts';
import { clearEtagRegistry, discardEtag, getKnownEtag } from '../etagRegistry.ts';
import { createFakeTripServer, type FakeTripServer } from './fakeTripServer.ts';

let server: FakeTripServer;

function boot(latencyMs: number | ((method: string, path: string) => number) = 0) {
	if (server) server.restore();
	server = createFakeTripServer({ latencyMs });
	server.install();
}

beforeEach(() => {
	clearEtagRegistry();
	boot(0);
});

afterEach(() => server.restore());

const putCalls = () => server.calls.filter((c) => c.method === 'PUT');

describe('AC-3 (Kernfall): der Doppel-PUT des Wetter-Reiters', () => {
	test('test_weatherMetricsTab_sequentialDoublePut_bothSucceed', async () => {
		// GIVEN: die Tour-Seite wurde geladen, der Stand ist bekannt
		await api.get('/api/trips/gr20');
		const stampFromGet = getKnownEtag('gr20');

		// WHEN: handleSave() laeuft — erst /weather-config, dann /api/trips/{id},
		// sequenziell mit await, ohne Neulesen dazwischen (WeatherMetricsTab.svelte)
		await api.put('/api/trips/gr20/weather-config', { buckets: [] });
		await api.put<{ id: string }>('/api/trips/gr20', {
			report_config: { start_hour: 6 },
			official_alerts_enabled: true
		});

		// THEN: beide gelingen, und der zweite hat NICHT den alten Stand aus dem
		// GET benutzt, sondern den vom ersten PUT zurueckgelieferten neuen.
		const puts = putCalls();
		assert.equal(puts.length, 2);
		assert.equal(puts[0].status, 200, 'erster PUT (/weather-config) muss gelingen');
		assert.equal(puts[1].status, 200, 'zweiter PUT (/api/trips/{id}) muss gelingen');
		assert.equal(puts[0].ifMatch, stampFromGet);
		assert.notEqual(
			puts[1].ifMatch,
			stampFromGet,
			'der zweite PUT darf nicht mit dem veralteten Stand aus dem GET fahren'
		);
		assert.ok(puts[1].ifMatch, 'der zweite PUT muss einen Stand mitfuehren');
	});

	test('test_weatherMetricsTab_doublePut_withoutAwaitBetween_secondUsesFreshStamp', async () => {
		// Dies ist der Test, der die REIHENFOLGE im Trichter festnagelt:
		// einreihen ZUERST, Stand nachschlagen DANACH (innerhalb der Warteschlange).
		//
		// GIVEN: die Tour ist geladen
		await api.get('/api/trips/gr20');
		const stampFromGet = getKnownEtag('gr20');

		// WHEN: beide Schreibvorgaenge losgetreten werden, OHNE dass der erste
		// abgewartet wird (zwei Reiter derselben Seite, je eigener Debounce)
		const first = api.put('/api/trips/gr20/weather-config', { buckets: [] });
		const second = api.put('/api/trips/gr20', { report_config: { start_hour: 6 } });
		await Promise.all([first, second]);

		// THEN: beide gelingen. Wuerde der Stand VOR dem Einreihen gelesen,
		// haetten beide denselben (alten) Wert eingefroren und der zweite
		// scheiterte mit 412, obwohl er ordentlich gewartet hat.
		const puts = putCalls();
		assert.equal(puts.length, 2);
		assert.equal(puts[0].ifMatch, stampFromGet);
		assert.equal(puts[0].status, 200);
		assert.notEqual(
			puts[1].ifMatch,
			stampFromGet,
			'der zweite Schreibvorgang muss den Stand ERST beim Losgehen nachschlagen, nicht beim Einreihen'
		);
		assert.equal(puts[1].status, 200, 'der zweite Schreibvorgang darf nicht mit 412 scheitern');
	});
});

describe('AC-4: zwei Browser-Fenster auf derselben Tour', () => {
	test('test_twoRealms_secondArrivalRejected_notOverwritten', async () => {
		// GIVEN: dieses Fenster hat die Tour geladen und kennt den Stand
		await api.get('/api/trips/gr20');
		const stampHier = getKnownEtag('gr20');
		assert.ok(stampHier);

		// WHEN: ein anderes Fenster (eigener JS-Realm, eigene Registry) zuerst
		// schreibt — hier als roher fetch am Trichter vorbei nachgestellt
		const fremd = await server.handler('/api/trips/gr20', {
			method: 'PUT',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ name: 'vom anderen Fenster' })
		});
		assert.equal(fremd.status, 200);
		assert.equal((server.storedBody('gr20') as { name?: string })?.name, 'vom anderen Fenster');

		// ... und dieses Fenster danach mit seinem inzwischen veralteten Stand
		let thrown: unknown;
		try {
			await api.put('/api/trips/gr20', { name: 'von hier' });
			assert.fail('der veraltete Schreibvorgang haette abgelehnt werden muessen');
		} catch (e) {
			thrown = e;
		}

		// THEN: wird der zeitlich zweite abgelehnt statt die bereits gespeicherte
		// Aenderung zu ueberschreiben.
		assert.equal((thrown as { status?: number }).status, 412);
		assert.equal(
			(server.storedBody('gr20') as { name?: string })?.name,
			'vom anderen Fenster',
			'die Aenderung des anderen Fensters darf nicht ueberschrieben worden sein'
		);
	});
});

describe('AC-9: gleichzeitig ausgeloeste Schreibvorgaenge laufen serialisiert', () => {
	test('test_concurrentAutoSaveAcrossTabs_sameTripId_bothSucceedSerialized', async () => {
		// GIVEN: ein Server mit messbarer Laufzeit und eine geladene Tour
		boot(15);
		await api.get('/api/trips/gr20');

		// WHEN: zwei Editor-Reiter gleichzeitig speichern (kein await dazwischen)
		await Promise.all([
			api.put('/api/trips/gr20', { report_config: { start_hour: 6 } }),
			api.put('/api/trips/gr20/weather-config', { buckets: [] })
		]);

		// THEN: beide gelingen, und ihre Zeitfenster beim Server ueberschneiden
		// sich NICHT — sie kamen nacheinander an.
		const puts = putCalls();
		assert.equal(puts.length, 2);
		assert.equal(puts[0].status, 200);
		assert.equal(puts[1].status, 200);
		assert.ok(
			puts[1].startedAt >= puts[0].finishedAt,
			`Zeitfenster ueberschneiden sich: erster [${puts[0].startedAt}, ${puts[0].finishedAt}], ` +
				`zweiter startete bei ${puts[1].startedAt}`
		);
	});

	test('test_concurrentWrites_differentTrips_notSerializedAgainstEachOther', async () => {
		// GIVEN: zwei verschiedene Touren
		boot(15);

		// WHEN: beide gleichzeitig gespeichert werden
		await Promise.all([
			api.put('/api/trips/gr20', { a: 1 }),
			api.put('/api/trips/jakobsweg', { a: 1 })
		]);

		// THEN: laufen sie ueberlappend — die Warteschlange trennt nach Tour und
		// bremst nicht die ganze Anwendung aus.
		const puts = putCalls();
		assert.equal(puts.length, 2);
		assert.ok(
			puts[1].startedAt < puts[0].finishedAt,
			'Schreibvorgaenge auf verschiedene Touren duerfen sich nicht gegenseitig blockieren'
		);
	});
});

describe('F001: ein Lesevorgang darf einen juengeren Stempel nie ueberschreiben', () => {
	test('test_slowRead_doesNotOverwriteFresherStampFromCompletedWrite', async () => {
		// Lesevorgaenge laufen bewusst NICHT durch die Warteschlange (sie
		// veraendern nichts), setzen aber den Stempel. Kommt eine Leseantwort
		// verspaetet an, traegt sie den Stand von IHREM Anfragezeitpunkt.
		//
		// GIVEN: ein Lesevorgang ist unterwegs und hat serverseitig den damals
		// aktuellen Fingerabdruck erfasst
		boot((method) => (method === 'GET' ? 60 : 0));
		const langsamerLesevorgang = api.get('/api/trips/gr20');
		assert.ok(
			server.calls.some((c) => c.method === 'GET'),
			'Vorbedingung: der Lesevorgang muss beim Server angekommen sein'
		);

		// WHEN: waehrenddessen ein Schreibvorgang KOMPLETT durchlaeuft und einen
		// neuen Stempel setzt ...
		await api.put('/api/trips/gr20', { name: 'frisch gespeichert' });
		const stempelNachSchreiben = getKnownEtag('gr20');
		assert.equal(stempelNachSchreiben, server.etagOf('gr20'));

		// ... und der Lesevorgang erst DANACH zurueckkommt
		await langsamerLesevorgang;

		// THEN: gilt weiterhin der juengere Stempel. Sonst schickte der naechste
		// Schreibvorgang den alten Wert und bekaeme 412 — obwohl niemand sonst
		// etwas geaendert hat.
		assert.equal(
			getKnownEtag('gr20'),
			stempelNachSchreiben,
			'die verspaetete Leseantwort hat den frischeren Stempel ueberschrieben'
		);

		// UND: der naechste Schreibvorgang gelingt ohne Umweg ueber einen 412.
		await api.put('/api/trips/gr20', { name: 'noch eine Aenderung' });
		const letzter = putCalls()[putCalls().length - 1];
		assert.equal(letzter.status, 200, 'kein Konflikt ohne echten Konflikt');
	});

	test('test_slowRead_afterStateDiscard_doesNotResurrectStaleStamp', async () => {
		// Derselbe Mechanismus deckt einen zweiten Weg ab: `PATCH /state`
		// veraendert die Tourdatei und verwirft deshalb den Stempel. Kommt eine
		// vorher gestartete Leseantwort danach an, darf sie den verworfenen Stand
		// nicht wieder ablegen — er beschreibt die Datei VOR dem PATCH.
		boot((method) => (method === 'GET' ? 60 : 0));
		await api.get('/api/trips/gr20');
		const langsamerLesevorgang = api.get('/api/trips/gr20');

		// WHEN: die Tour zwischenzeitlich pausiert/archiviert wird
		await server.handler('/api/trips/gr20/state', {
			method: 'PATCH',
			body: JSON.stringify({ paused: true })
		});
		discardEtag('gr20');
		await langsamerLesevorgang;

		// THEN: bleibt der Stand verworfen — der naechste Schreibvorgang laeuft
		// ohne Vorbedingung durch (Verhalten wie vor S3), statt an einem
		// veralteten Stempel zu scheitern.
		assert.equal(getKnownEtag('gr20'), undefined);
		await api.put('/api/trips/gr20', { name: 'X' });
		const letzter = putCalls()[putCalls().length - 1];
		assert.equal(letzter.ifMatch, null);
		assert.equal(letzter.status, 200);
	});
});

describe('AC-7: ohne bekannten Stand verhaelt sich alles wie vor S3', () => {
	test('test_withoutKnownStamp_writeSucceeds_asBefore', async () => {
		// GIVEN: die Tour wurde nie ueber die Detailseite geladen
		assert.equal(getKnownEtag('nie-geladen'), undefined);

		// WHEN: geschrieben wird — auch wenn sich die Datei serverseitig laengst
		// geaendert hat (hier: eine fremde Schreibaktion vorweg)
		await server.handler('/api/trips/nie-geladen', {
			method: 'PUT',
			body: JSON.stringify({ name: 'fremd' })
		});
		const updated = await api.put<{ id: string }>('/api/trips/nie-geladen', { name: 'von hier' });

		// THEN: wird der Schreibvorgang angenommen (S2-Rollout-Politik:
		// fehlender Header = angenommen)
		assert.equal(updated.id, 'nie-geladen');
		const puts = putCalls();
		assert.equal(puts[puts.length - 1].ifMatch, null);
		assert.equal(puts[puts.length - 1].status, 200);
	});

	test('test_afterDiscard_writeGoesThroughWithoutPrecondition', async () => {
		// GIVEN: ein Stand ist bekannt, wird aber verworfen (z. B. nach einem
		// PATCH /state, der die Datei veraendert hat)
		await api.get('/api/trips/gr20');
		assert.ok(getKnownEtag('gr20'));
		discardEtag('gr20');

		// WHEN: geschrieben wird
		await api.put('/api/trips/gr20', { name: 'X' });

		// THEN: geht es ohne Vorbedingung durch
		const puts = putCalls();
		assert.equal(puts[puts.length - 1].ifMatch, null);
		assert.equal(puts[puts.length - 1].status, 200);
	});
});
