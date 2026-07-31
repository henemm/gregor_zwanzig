// Issue #1395 S3 — Registry (Stand je Tour) + Schreib-Warteschlange.
// Spec: docs/specs/modules/issue_1395_s3_etag_registry.md — AC-9,
//   § "extractTripId(path) — welche Pfade zaehlen".

import { test, describe, beforeEach } from 'node:test';
import assert from 'node:assert/strict';

import {
	getKnownEtag,
	setKnownEtag,
	setKnownEtagIfUnchanged,
	adoptEtagFromPageLoad,
	etagVersion,
	discardEtag,
	clearEtagRegistry,
	extractTripId,
	enqueueTripWrite
} from '../etagRegistry.ts';

/** Laesst alle bereits geplanten Microtasks/Timer-Ticks durchlaufen. */
const tick = () => new Promise<void>((r) => setTimeout(r, 0));

describe('etagRegistry — Stand je Tour', () => {
	beforeEach(() => clearEtagRegistry());

	test('test_getSetDiscard_roundtrip', () => {
		// GIVEN: fuer eine Tour ist noch nichts bekannt
		assert.equal(getKnownEtag('gr20'), undefined);

		// WHEN: ein Stand gemerkt wird
		setKnownEtag('gr20', '"abc123"');

		// THEN: liefert die Registry genau diesen Wert zurueck — und nur fuer
		// diese Tour (der Stempel gehoert zur Tour, nicht zur Adresse).
		assert.equal(getKnownEtag('gr20'), '"abc123"');
		assert.equal(getKnownEtag('jakobsweg'), undefined);

		// WHEN: der Stand verworfen wird
		discardEtag('gr20');

		// THEN: ist er weg — der naechste Schreibvorgang laeuft ohne Vorbedingung
		assert.equal(getKnownEtag('gr20'), undefined);
	});

	test('test_extractTripId_matchesOnlyTripAndWeatherConfigPaths', () => {
		// GIVEN/WHEN/THEN: drei Pfadformen tragen einen ETag — die Tour und ihre
		// Wetter-Konfiguration (S2), seit S6 zusaetzlich der Ortsvergleich.
		assert.equal(extractTripId('/api/trips/gr20'), 'gr20');
		assert.equal(extractTripId('/api/trips/gr20/weather-config'), 'gr20');
		assert.equal(extractTripId('/api/trips/gr20?force=1'), 'gr20');
		assert.equal(extractTripId('/api/trips/gr20/weather-config?x=1'), 'gr20');
		assert.equal(extractTripId('/api/compare/presets/cp-abc'), 'cp-abc');
		assert.equal(extractTripId('/api/compare/presets/cp-abc?x=1'), 'cp-abc');

		// Alle uebrigen Unterpfade duerfen NICHT matchen — der Server prueft dort
		// kein If-Match (S2 AC-15) und liefert keinen ETag.
		assert.equal(extractTripId('/api/trips/gr20/state'), null);
		assert.equal(extractTripId('/api/trips/gr20/waypoints/wp1/confirm'), null);
		assert.equal(extractTripId('/api/trips/gr20/preview'), null);
		assert.equal(extractTripId('/api/trips'), null);
		assert.equal(extractTripId('/api/trips/'), null);
		assert.equal(extractTripId('/api/compare/presets'), null);
		assert.equal(extractTripId('/api/compare/presets/cp-abc/state'), null);
		assert.equal(extractTripId('/api/compare/presets/cp-abc/send'), null);

		// Fremde Ressourcen bleiben unberuehrt (Orte). Der zweite Server-seitige
		// Schreibweg /api/briefings/{id}?kind=vergleich ist zwar ebenfalls
		// abgesichert (S6 AC-9), wird vom Frontend aber nicht benutzt und bleibt
		// darum bewusst ausserhalb des Trichters.
		assert.equal(extractTripId('/api/locations/korsika'), null);
		assert.equal(extractTripId('/api/briefings/abc?kind=vergleich'), null);
	});

	test('test_setKnownEtagIfUnchanged_rejectsStampFromOutdatedView', () => {
		// GIVEN: ein Vorgang hat den Zaehler beim Losschicken gesehen, nichts ist
		// passiert → sein Stempel wird uebernommen
		assert.equal(setKnownEtagIfUnchanged('gr20', '"fp-1"', etagVersion('gr20')), true);
		assert.equal(getKnownEtag('gr20'), '"fp-1"');

		// WHEN: inzwischen ein juengerer Stand hinterlegt wurde und ein
		// Nachzuegler mit dem alten Blick ankommt
		const gesehen = etagVersion('gr20');
		setKnownEtag('gr20', '"fp-2"');
		assert.equal(setKnownEtagIfUnchanged('gr20', '"fp-1"', gesehen), false);

		// THEN: bleibt der juengere Stand stehen
		assert.equal(getKnownEtag('gr20'), '"fp-2"');

		// UND: auch das VERWERFEN zaehlt als Veraenderung — ein `PATCH /state`
		// hat die Tourdatei angefasst, jeder vorher erfasste Stempel ist veraltet.
		const gesehen2 = etagVersion('gr20');
		discardEtag('gr20');
		assert.equal(setKnownEtagIfUnchanged('gr20', '"fp-2"', gesehen2), false);
		assert.equal(getKnownEtag('gr20'), undefined);
	});

	test('test_adoptEtagFromPageLoad_neverOverwritesAnExistingStamp', () => {
		// GIVEN: fuer die Tour ist noch nichts bekannt → der Seitenaufbau darf setzen
		assert.equal(adoptEtagFromPageLoad('gr20', '"fp-1"'), true);
		assert.equal(getKnownEtag('gr20'), '"fp-1"');

		// WHEN: ein Speichervorgang hat inzwischen einen juengeren Stand gesetzt
		// und `load()` laeuft erneut (Invalidierung) mit seinem alten Stempel
		setKnownEtag('gr20', '"fp-2"');
		assert.equal(adoptEtagFromPageLoad('gr20', '"fp-1"'), false);

		// THEN: bleibt der juengere Stand stehen
		assert.equal(getKnownEtag('gr20'), '"fp-2"');
	});
});

describe('enqueueTripWrite — Schreib-Warteschlange je Tour (AC-9)', () => {
	beforeEach(() => clearEtagRegistry());

	test('test_enqueueTripWrite_serializesSameTripId', async () => {
		// GIVEN: zwei Schreibvorgaenge auf DIESELBE Tour, der erste haengt
		let firstStarted = false;
		let secondStarted = false;
		let releaseFirst!: () => void;
		const gate = new Promise<void>((r) => {
			releaseFirst = r;
		});

		// WHEN: beide ohne Wartezeit dazwischen eingereiht werden
		const p1 = enqueueTripWrite('gr20', async () => {
			firstStarted = true;
			await gate;
			return 'erster';
		});
		const p2 = enqueueTripWrite('gr20', async () => {
			secondStarted = true;
			return 'zweiter';
		});
		await tick();

		// THEN: laeuft der erste, der zweite hat noch NICHT begonnen
		assert.equal(firstStarted, true, 'der erste Vorgang muss sofort starten');
		assert.equal(
			secondStarted,
			false,
			'der zweite Vorgang darf nicht starten, solange der erste laeuft — sonst ist die Warteschlange eine Attrappe'
		);

		releaseFirst();
		assert.deepEqual(await Promise.all([p1, p2]), ['erster', 'zweiter']);
		assert.equal(secondStarted, true);
	});

	test('test_enqueueTripWrite_differentTripIds_runConcurrently', async () => {
		// GIVEN: ein haengender Schreibvorgang auf Tour A
		let bStarted = false;
		let releaseA!: () => void;
		const gate = new Promise<void>((r) => {
			releaseA = r;
		});
		const pA = enqueueTripWrite('gr20', async () => {
			await gate;
			return 'a';
		});

		// WHEN: ein Schreibvorgang auf Tour B eingereiht wird
		const pB = enqueueTripWrite('jakobsweg', async () => {
			bStarted = true;
			return 'b';
		});
		await tick();

		// THEN: laeuft B sofort — die Warteschlange trennt nach Tour
		assert.equal(bStarted, true, 'Warteschlange darf nicht ueber Tour-Grenzen hinweg blockieren');
		assert.equal(await pB, 'b');

		releaseA();
		assert.equal(await pA, 'a');
	});

	test('test_enqueueTripWrite_continuesAfterRejectedPredecessor', async () => {
		// GIVEN: ein Vorgaenger, der fehlschlaegt (z. B. 412 oder Netzfehler)
		const failing = enqueueTripWrite('gr20', async () => {
			throw new Error('vorgaenger kaputt');
		});
		await assert.rejects(failing, /vorgaenger kaputt/);

		// WHEN: danach ein weiterer Schreibvorgang eingereiht wird
		const ok = await enqueueTripWrite('gr20', async () => 'laeuft trotzdem');

		// THEN: laeuft er — kein Domino-Abbruch der Kette
		assert.equal(ok, 'laeuft trotzdem');
	});

	test('test_enqueueTripWrite_rejectedPredecessorDoesNotBlockAlreadyQueuedSuccessor', async () => {
		// GIVEN: ein Vorgaenger, der fehlschlaegt, und ein bereits dahinter
		// eingereihter Nachfolger (der haeufigere Fall: beide sind schon in der
		// Schlange, wenn der erste scheitert)
		let releaseFirst!: () => void;
		const gate = new Promise<void>((r) => {
			releaseFirst = r;
		});
		const failing = enqueueTripWrite('gr20', async () => {
			await gate;
			throw new Error('vorgaenger kaputt');
		});
		const successor = enqueueTripWrite('gr20', async () => 'nachfolger laeuft');

		releaseFirst();

		// THEN: der Nachfolger laeuft trotzdem
		await assert.rejects(failing, /vorgaenger kaputt/);
		assert.equal(await successor, 'nachfolger laeuft');
	});
});
