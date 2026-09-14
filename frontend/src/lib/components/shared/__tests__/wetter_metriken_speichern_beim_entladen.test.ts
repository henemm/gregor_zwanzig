// TDD RED — Issue #2317 Baustein 1 (AC-17 + Unit-Anteil AC-4): die Speicherung
// des Reiters Wetter-Metriken schickt zwei PUTs — regulär strikt nacheinander,
// beim Entladen beide sofort und unabhängig voneinander.
//
// Spec: docs/specs/modules/speicherung_beim_neuladen.md
//   § Implementation Details „Baustein 1 — Speichern verlässlich"
//   § Acceptance Criteria AC-4 (E2E-Nachweis in
//     frontend/e2e/speicherung-ueberlebt-neuladen.spec.ts), AC-17
//
// Befund: WeatherMetricsTab.svelte `scheduleAutoSave()` baut
//   async () => { await api.put(`…/weather-config`, payload); const updated = await api.put(`…/trips/{id}`, …); … }
// OHNE `init`. Beim Entladen kommt die Antwort des ersten PUT nie an — der
// zweite (report_config) startet also nie, selbst wenn init durchgereicht würde.
// Die Reihenfolge im Normalfall bleibt Pflicht: die lokale Übernahme von
// alert_rules hängt an der Trip-Antwort NACH der Wetter-Konfiguration (#850).
//
// Zielschnittstelle (existiert noch NICHT → RED per ERR_MODULE_NOT_FOUND):
//
//   frontend/src/lib/components/shared/tripSpeicherung.ts
//   baueWetterMetrikenSpeicherung<T>(client: PutClient, tripId, wetterPayload, tripBody, nachErfolg?): SaveFn
//
// 🔴 Warum hier ein AUFZEICHNENDER PutClient statt `api` + fakeTripServer (Abweichung
// vom bevorzugten Prüfstand, bewusst): `/api/trips/{id}/weather-config` und
// `/api/trips/{id}` liegen in `etagRegistry.extractTripId` auf DERSELBEN
// Kennung; ein regulärer PUT läuft durch `enqueueTripWrite` in dieselbe
// Warteschlange. Über das echte `api` wäre „der zweite PUT startet erst nach dem
// ersten" also auch dann grün, wenn `baueWetterMetrikenSpeicherung` beide
// gleichzeitig abfeuerte — die Warteschlange, nicht das Modul, sorgte für die
// Reihenfolge. Die Zusicherung wird deshalb dort gemessen, wo das Modul
// entscheidet: an seinen Aufrufen des Clients, mit von außen steuerbarer
// Auflösung. Das ist kein Mock-Theater: der Fake gibt keine Annahme zurück,
// sondern hält jede Antwort fest, bis der Test sie freigibt. Ein zusätzlicher
// Fall prüft den Entlade-Weg Ende-zu-Ende über das echte `api` (keepalive +
// kein If-Match am Fetch).
//
// Ausführen:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/shared/__tests__/wetter_metriken_speichern_beim_entladen.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../api.ts';
import { clearEtagRegistry, getKnownEtag } from '../../../etagRegistry.ts';
import { SaveStatus } from '../../../stores/saveStatusStore.svelte.ts';
import { createFakeTripServer, type FakeTripServer } from '../../../__tests__/fakeTripServer.ts';
import { baueWetterMetrikenSpeicherung, type PutClient } from '../tripSpeicherung.ts';

const TRIP_ID = 'khw-2317';
const WETTER_PFAD = `/api/trips/${TRIP_ID}/weather-config`;
const TRIP_PFAD = `/api/trips/${TRIP_ID}`;
const WETTER_PAYLOAD = { metrics: [{ metric_id: 'gust', enabled: false, bucket: 'off', order: 0 }] };
const TRIP_BODY = { report_config: { day_window_start_hour: 6 }, official_alerts_enabled: true };

/** Echte SaveStatus-Instanz ohne Konstruktor (Runen-Felder, s. saveStatus.test.ts). */
function createTestInstance(): SaveStatus {
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
	return inst;
}

interface PutAufruf {
	path: string;
	body: unknown;
	init: RequestInit | undefined;
	aufloesen: (antwort: unknown) => void;
	ablehnen: (fehler: unknown) => void;
}

/**
 * Aufzeichnender Client: jeder `put` wird BEI AUFRUF festgehalten (Promise-
 * Executor läuft synchron) und bleibt offen, bis der Test ihn auflöst.
 */
function erzeugeHaltenderClient(): { client: PutClient; aufrufe: PutAufruf[] } {
	const aufrufe: PutAufruf[] = [];
	const client: PutClient = {
		put<T>(path: string, body: unknown, init?: RequestInit): Promise<T> {
			return new Promise<T>((resolve, reject) => {
				aufrufe.push({
					path,
					body,
					init,
					aufloesen: (a) => resolve(a as T),
					ablehnen: reject
				});
			});
		}
	};
	return { client, aufrufe };
}

const tick = () => new Promise<void>((r) => setImmediate(r));
const TRIP_ANTWORT = { id: TRIP_ID, alert_rules: [{ id: 'r1', metric: 'wind_gust' }], ...TRIP_BODY };

describe('Issue #2317 AC-17: reguläres Speichern — Wetter-Konfiguration, DANN Trip, nie gleichzeitig', () => {
	test('zweiter PUT (Trip) startet NICHT, solange der erste (weather-config) offen ist; danach genau einer', async () => {
		// GIVEN
		const { client, aufrufe } = erzeugeHaltenderClient();
		const ctl = createTestInstance();
		const antworten: unknown[] = [];
		ctl.schedule(baueWetterMetrikenSpeicherung(client, TRIP_ID, WETTER_PAYLOAD, TRIP_BODY, (a) => antworten.push(a)));

		// WHEN: regulärer Flush (Feld verlassen), erster PUT bleibt offen
		const laeuft = ctl.flush();
		await tick();
		await tick();

		// THEN: nur die Wetter-Konfiguration ist unterwegs
		assert.equal(aufrufe.length, 1, 'solange der erste PUT offen ist, darf der zweite nicht starten (#850)');
		assert.equal(aufrufe[0].path, WETTER_PFAD, 'zuerst muss die Wetter-Konfiguration geschrieben werden');
		assert.deepEqual(aufrufe[0].body, WETTER_PAYLOAD);
		assert.notEqual(aufrufe[0].init?.keepalive, true, 'regulär darf kein keepalive gesetzt sein');

		// WHEN: erster PUT kommt zurück
		aufrufe[0].aufloesen({ metrics: WETTER_PAYLOAD.metrics });
		await tick();
		await tick();

		// THEN: genau ein weiterer PUT, auf den Trip
		assert.equal(aufrufe.length, 2, 'nach Auflösung des ersten PUT muss genau ein zweiter folgen');
		assert.equal(aufrufe[1].path, TRIP_PFAD, 'der zweite PUT muss auf die Tour gehen');
		assert.deepEqual(aufrufe[1].body, TRIP_BODY);
		assert.notEqual(aufrufe[1].init?.keepalive, true, 'regulär darf kein keepalive gesetzt sein');
		assert.equal(antworten.length, 0, 'nachErfolg darf erst nach dem Trip-PUT laufen');

		// WHEN: Trip-PUT kommt zurück
		aufrufe[1].aufloesen(TRIP_ANTWORT);
		await laeuft;

		// THEN
		assert.equal(aufrufe.length, 2, 'es darf kein dritter PUT entstehen');
		assert.deepEqual(antworten, [TRIP_ANTWORT], 'nachErfolg muss genau einmal die TRIP-Antwort bekommen (alert_rules, #850)');
		assert.equal(ctl.state, 'idle');
	});

	test('scheitert der erste PUT regulär, startet der Trip-PUT nicht und nachErfolg läuft nicht', async () => {
		// GIVEN
		const { client, aufrufe } = erzeugeHaltenderClient();
		const ctl = createTestInstance();
		const antworten: unknown[] = [];
		ctl.schedule(baueWetterMetrikenSpeicherung(client, TRIP_ID, WETTER_PAYLOAD, TRIP_BODY, (a) => antworten.push(a)));

		// WHEN
		const laeuft = ctl.flush();
		await tick();
		aufrufe[0].ablehnen({ error: 'Serverfehler', status: 500 });
		await laeuft;

		// THEN
		assert.equal(aufrufe.length, 1, 'nach gescheiterter Wetter-Konfiguration darf der Trip-PUT regulär nicht folgen');
		assert.equal(antworten.length, 0, 'nach einem Fehlschlag darf nachErfolg nicht laufen');
		assert.equal(ctl.state, 'error', 'der Fehler muss den Speicher-Takt erreichen, nicht verschluckt werden');
	});
});

describe('Issue #2317 AC-4 (Unit-Anteil): Speichern beim Entladen — beide PUTs sofort, unabhängig, mit keepalive', () => {
	test('beide PUTs im selben synchronen Tick, beide keepalive:true — auch wenn der erste nie antwortet', async () => {
		// GIVEN
		const { client, aufrufe } = erzeugeHaltenderClient();
		const ctl = createTestInstance();
		const antworten: unknown[] = [];
		ctl.schedule(baueWetterMetrikenSpeicherung(client, TRIP_ID, WETTER_PAYLOAD, TRIP_BODY, (a) => antworten.push(a)));

		// WHEN: der Wächter flusht beim Entladen — nicht abgewartet, keine Antwort freigegeben
		const laeuft = ctl.flush({ keepalive: true });

		// THEN (synchron): beide sind raus
		assert.equal(
			aufrufe.length,
			2,
			'beim Entladen müssen BEIDE PUTs noch im selben Tick abgesetzt werden — die Antwort des ersten kommt nie an'
		);
		const pfade = aufrufe.map((a) => a.path).sort();
		assert.deepEqual(pfade, [TRIP_PFAD, WETTER_PFAD].sort(), 'je ein PUT auf Wetter-Konfiguration und Tour erwartet');
		for (const a of aufrufe) {
			assert.equal(a.init?.keepalive, true, `PUT ${a.path}: die Option keepalive:true des Wächters wurde verschluckt`);
		}
		assert.deepEqual(aufrufe.find((a) => a.path === WETTER_PFAD)?.body, WETTER_PAYLOAD);
		assert.deepEqual(aufrufe.find((a) => a.path === TRIP_PFAD)?.body, TRIP_BODY);

		// WHEN: nur der Trip-PUT antwortet — die Wetter-Konfiguration bleibt offen
		aufrufe.find((a) => a.path === TRIP_PFAD)!.aufloesen(TRIP_ANTWORT);
		await tick();
		await tick();

		// THEN: nachErfolg wartet auf beide
		assert.equal(antworten.length, 0, 'nachErfolg darf erst nach BEIDEN PUTs laufen');

		// WHEN: jetzt auch die Wetter-Konfiguration
		aufrufe.find((a) => a.path === WETTER_PFAD)!.aufloesen({ metrics: WETTER_PAYLOAD.metrics });
		await laeuft;

		// THEN
		assert.equal(aufrufe.length, 2, 'es darf kein weiterer PUT entstehen');
		assert.deepEqual(antworten, [TRIP_ANTWORT], 'nachErfolg muss genau einmal die TRIP-Antwort bekommen');
		assert.equal(ctl.hasPending, false);
	});
});

describe('Issue #2317 AC-4 (Unit-Anteil): Entlade-Weg Ende-zu-Ende über das echte api', () => {
	let server: FakeTripServer;

	beforeEach(() => {
		clearEtagRegistry();
		server = createFakeTripServer();
		server.install();
	});

	afterEach(() => server.restore());

	test('beide Fetches sind synchron beim Server, beide keepalive, keiner mit If-Match', async () => {
		// GIVEN: Stand bekannt
		await api.get(TRIP_PFAD);
		assert.ok(getKnownEtag(TRIP_ID), 'Vorbedingung: ein Stand muss bekannt sein, sonst beweist „kein If-Match" nichts');
		const ctl = createTestInstance();
		ctl.schedule(baueWetterMetrikenSpeicherung(api, TRIP_ID, WETTER_PAYLOAD, TRIP_BODY));
		const vorher = server.calls.length;

		// WHEN
		const laeuft = ctl.flush({ keepalive: true });

		// THEN (synchron)
		const puts = server.calls.slice(vorher);
		assert.equal(puts.length, 2, 'beide PUTs müssen noch im Tick des Entladens beim Server angekommen sein');
		assert.deepEqual(puts.map((p) => p.path).sort(), [TRIP_PFAD, WETTER_PFAD].sort());
		for (const p of puts) {
			assert.equal(p.method, 'PUT');
			assert.equal(p.keepalive, true, `Fetch ${p.path}: keepalive fehlt`);
			assert.equal(p.ifMatch, null, `Fetch ${p.path}: ein Entlade-Flush darf keinen If-Match tragen`);
		}

		await laeuft;
		assert.ok(puts.every((p) => p.status === 200), 'beide PUTs müssen angenommen werden');
		assert.equal(ctl.state, 'idle');
	});
});
