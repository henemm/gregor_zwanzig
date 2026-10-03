// TDD RED — Issue #1433, AC-10 (§4 Punkt 3): ein 412 beim Aendern von Name (Kopf,
// `TripHeader.svelte:45`) oder Aktivitaet (`TripTabs.svelte:188`
// `handleActivityChange`, heute ohne try/catch) fuehrt zur Konfliktanzeige „Nochmal
// speichern" am gemeinsamen Controller — kein stilles Scheitern. Die Fremdaenderung
// bleibt erhalten. Beide schreiben heute an den Controller vorbei (`api.put`
// direkt) und melden deshalb nichts.
//
// Spec: docs/specs/bugfix/trip_mehrreiter_konfliktschutz.md — §4 Punkt 3, AC-10;
//       Test Plan `trip_kopf_aktivitaet_melden_konflikt` (neuer Controller-Weg
//       `meldeKonflikt`; hier ueber die WIRKUNG gemessen: Controller-Zustand,
//       Retry, Server-Stand — nicht ueber die Signatur).
//
// Die Schreiber laufen mit ihren ECHTEN Instanz-Skripten (`makeNameSaveHandler`,
// `handleActivityChange`) ueber das echte `api` und eine echte SaveStatus-Instanz.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/trip-detail/__tests__/trip_kopf_aktivitaet_melden_konflikt.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../api.ts';
import { clearEtagRegistry } from '../../../etagRegistry.ts';
import { createFakeTripServer, type FakeTripServer } from '../../../__tests__/fakeTripServer.ts';
import * as P from './tripMehrreiterPruefstand.ts';

let server: FakeTripServer;
const FREMDE_METRIKEN = [{ metric_id: 'cape', enabled: true, aggregations: ['max'] }];

beforeEach(async () => {
	clearEtagRegistry();
	server = createFakeTripServer({ merge: true });
	server.install();
	server.seed(P.TRIP_ID, P.vollerTrip());
	await api.get(P.TRIP_PFAD);
	// ein anderer Tab / der Python-Core hat den Trip inzwischen geaendert
	server.foreignWrite(P.TRIP_ID, { display_config: { metrics: FREMDE_METRIKEN } });
});
afterEach(() => server.restore());

const puts = () => server.calls.filter((c) => c.method === 'PUT');
const stand = () => server.stand(P.TRIP_ID);

describe('AC-10: Kopf (Name) — 412 zeigt „Nochmal speichern"', () => {
	test('412 beim Umbenennen: Controller steht auf `conflict`, Name und Fremdaenderung auf dem Server unveraendert', async () => {
		const a = P.neuerAufbau();
		assert.equal(a.ctl.state, 'idle');
		const k = await P.kopfReiter(a);
		await k.umbenennen('Neuer Name');

		assert.equal(puts().at(-1)!.status, 412, 'Vorbedingung: der Server lehnt den veralteten Stand ab');
		assert.equal(a.ctl.state, 'conflict', 'AC-10: die Oberflaeche muss „Nochmal speichern" zeigen (heute: Kopf meldet nichts an den Controller)');
		assert.notEqual(stand().name, 'Neuer Name');
		assert.deepEqual((stand().display_config as Record<string, unknown>).metrics, FREMDE_METRIKEN, 'die Fremdaenderung bleibt erhalten');
		assert.equal(a.updates.length, 0, 'bei 412 wird `trip` nicht durch die lokale Fassung ersetzt');
	});

	test('„Nochmal speichern" wiederholt die Namensaenderung gegen den frischen Stand; Fremdaenderung bleibt', async () => {
		const a = P.neuerAufbau();
		const k = await P.kopfReiter(a);
		await k.umbenennen('Neuer Name');
		assert.equal(a.ctl.state, 'conflict', 'Vorbedingung');

		await a.ctl.retryConflict();

		assert.equal(stand().name, 'Neuer Name', 'der Retry muss die Eingabe des Nutzers speichern — sonst ist der Knopf eine Attrappe');
		assert.deepEqual((stand().display_config as Record<string, unknown>).metrics, FREMDE_METRIKEN);
		assert.equal(a.ctl.state, 'idle');
	});
});

describe('AC-10: Aktivitaet — 412 zeigt „Nochmal speichern"', () => {
	test('412 beim Aendern der Aktivitaet: Controller `conflict`, nichts geschrieben', async () => {
		const a = P.neuerAufbau();
		const t = await P.aktivitaetReiter(a);
		await t.aendern('skitour');

		assert.equal(puts().at(-1)!.status, 412);
		assert.equal(a.ctl.state, 'conflict', 'AC-10: Konfliktanzeige statt stillem Scheitern (heute: kein try/catch, Controller unbeteiligt)');
		assert.notEqual(stand().activity, 'skitour');
		assert.deepEqual((stand().display_config as Record<string, unknown>).metrics, FREMDE_METRIKEN);
		assert.equal(a.updates.length, 0);
	});

	test('der Handler wirft bei 412 nicht (kein unbehandelter Promise-Fehler im Klick-Handler)', async () => {
		const a = P.neuerAufbau();
		const t = await P.aktivitaetReiter(a);
		const handler = t.inst.u.handleActivityChange as (e: unknown) => Promise<void>;
		await assert.doesNotReject(handler({ target: { value: 'skitour' } }), '412 muss am Controller gemeldet, nicht als Ausnahme durchgereicht werden');
	});

	test('„Nochmal speichern" wiederholt die Aktivitaetsaenderung; Fremdaenderung bleibt', async () => {
		const a = P.neuerAufbau();
		const t = await P.aktivitaetReiter(a);
		await t.aendern('skitour');
		assert.equal(a.ctl.state, 'conflict', 'Vorbedingung');

		await a.ctl.retryConflict();

		assert.equal(stand().activity, 'skitour');
		assert.deepEqual((stand().display_config as Record<string, unknown>).metrics, FREMDE_METRIKEN);
		assert.equal(a.ctl.state, 'idle');
	});
});

describe('Kopf und Reiter teilen EINE Konfliktanzeige', () => {
	test('Kopf-412 und Alarme-412 landen in derselben Anzeige; ein Retry schreibt beide', async () => {
		const a = P.neuerAufbau();
		const k = await P.kopfReiter(a);
		await k.umbenennen('Neuer Name');
		const alarme = await P.alarmeReiter(a);
		alarme.empfindlichkeitAendern('wind', 'sensibel');
		await P.fertig(a.ctl);
		assert.equal(a.ctl.state, 'conflict');

		await a.ctl.retryConflict();

		assert.equal(stand().name, 'Neuer Name');
		assert.equal(((stand().display_config as Record<string, unknown>).metric_alert_levels as Record<string, unknown>).wind, 'sensibel');
		assert.deepEqual((stand().display_config as Record<string, unknown>).metrics, FREMDE_METRIKEN);
	});
});
