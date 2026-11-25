// TDD RED — Issue #1433, Bug-Test W2 (AC-4, AC-5): ein per Telegram/SMS gesetztes
// „naechstes Briefing ueberspringen" (`report_config.skip_next`) darf beim
// Speichern in einem bereits geoeffneten Reiter nicht still zurueckgeschrieben
// werden — auch OHNE jeden 412.
//
// Spec: docs/specs/bugfix/trip_mehrreiter_konfliktschutz.md — Test Plan W2,
//       AC-4, AC-5, §1 (Befund W2), §2.3 (skip_next = Python-eigen).
//
// Der Python-Core setzt `skip_next` in derselben Datei, ohne Go-Lock und ohne
// ETag (`foreignWrite` des Ersatz-Servers). Der Versand-Reiter
// (BriefingScheduleTab) schreibt heute IMMER mit `keepalive: true` (nie
// If-Match) und schickt das ganze `report_config` seiner veralteten Kopie
// zurueck; der Wetter-Metriken-Reiter schickt ebenfalls das ganze report_config.
//
// Lehre aus dem Entwurf: der lokale Altstand der Reiter traegt `skip_next:false`
// (Seed). Fehlte der Schluessel dort, schickte auch die heutige Vollkopie ihn
// nicht, und der Test bewiese nichts.
//
// KEINE Statuscode-Zusicherung (die Spec laesst 200 oder 412 offen): geprueft wird
// nur der SERVER-Stand — `skip_next` bleibt true; und soweit der PUT durchging
// (200), steht die gespeicherte Aenderung auf dem Server.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/trip-detail/__tests__/trip_python_skip_next_ohne_412.test.ts

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
	await api.get(P.TRIP_PFAD); // der Reiter hat die Seite geladen
});
afterEach(() => server.restore());

const puts = () => server.calls.filter((c) => c.method === 'PUT');
const reportConfig = () => server.stand(P.TRIP_ID).report_config as Record<string, unknown>;

/** Telegram-/SMS-Befehl: Python setzt skip_next in der Datei (kein Go-Lock, kein ETag). */
function befehlSetztSkipNext(): void {
	server.foreignWrite(P.TRIP_ID, { report_config: { skip_next: true } });
}

/** Der Reiter steht auf einem FRISCHEN ETag (kein 412), aber sein `trip` ist veraltet. */
async function frischerEtag(): Promise<void> {
	await api.get(P.TRIP_PFAD);
}

/** Soweit ein PUT durchging, muss die Aenderung auf dem Server stehen. */
function geaenderteWerteFallsGespeichert(erwartet: Record<string, unknown>): void {
	const durchgegangen = puts().some((p) => p.status === 200);
	if (!durchgegangen) return; // 412 ist zulaessig — dann wurde nichts geschrieben
	for (const [k, v] of Object.entries(erwartet)) {
		assert.deepEqual(reportConfig()[k], v, `der durchgegangene PUT muss ${k} gespeichert haben`);
	}
}

// #3020 S1: lebender Reiter Zustellung (frueher BriefingScheduleTab).
describe('W2 / AC-4: Reiter Zustellung ueberschreibt skip_next nicht', () => {
	test('Versandzeit speichern (frischer ETag)', async () => {
		befehlSetztSkipNext();
		await frischerEtag();
		const a = P.neuerAufbau(); // veralteter lokaler Stand: skip_next=false
		const v = await P.zustellungReiter(a);
		v.aendern({ morgenZeit: '08:00' });
		await P.fertig(a.ctl);

		assert.ok(puts().length >= 1, 'Messaufbau: der Versand-Reiter muss einen PUT abgesetzt haben');
		assert.equal(reportConfig().skip_next, true, 'der Versand-Reiter hat das per Telegram gesetzte skip_next zurueckgeschrieben');
		geaenderteWerteFallsGespeichert({ morning_time: '08:00:00' });
	});

	test('Kanal speichern (frischer ETag)', async () => {
		befehlSetztSkipNext();
		await frischerEtag();
		const a = P.neuerAufbau();
		const v = await P.zustellungReiter(a);
		v.aendern({ briefing: { email: true, telegram: true, sms: true, premium_sms: false } });
		await P.fertig(a.ctl);

		assert.ok(puts().length >= 1);
		assert.equal(reportConfig().skip_next, true, 'der Versand-Reiter hat skip_next beim Kanal-Speichern zurueckgeschrieben');
		geaenderteWerteFallsGespeichert({ send_sms: true });
	});

	test('Versandzeit speichern mit VERALTETEM ETag (kein frischer GET): skip_next bleibt in beiden Ausgaengen', async () => {
		befehlSetztSkipNext(); // Registry kennt den Stand VOR dem Befehl
		const a = P.neuerAufbau();
		const v = await P.zustellungReiter(a);
		v.aendern({ morgenZeit: '08:00' });
		await P.fertig(a.ctl);

		assert.ok(puts().length >= 1);
		assert.equal(reportConfig().skip_next, true, 'weder ein 200 noch ein 412 darf skip_next loeschen');
		geaenderteWerteFallsGespeichert({ morning_time: '08:00:00' });
	});
});

// #3020 S1: lebende Schreiber statt WeatherMetricsTab. BEFUND: der Reiter Wetter (wetterTabSpeicherung.ts ->
// tripSpeicherPayload) sendet das GANZE report_config seines Seitenstands; bei frischem Stempel (z. B. nach dem
// Lesen der Karte „Was steht wo“, GET /placements) schreibt er ein inzwischen gesetztes skip_next zurueck. Die
// Zusicherung bleibt deshalb stehen und ist als `todo` sichtbar rot, bis der Speicherweg repariert ist (kein
// Produktionscode in #3020 S1). NICHT streichen, NICHT abschwaechen.
const BEFUND_VOLLKOPIE = 'Befund #3020 S1: Reiter Wetter sendet report_config als Vollkopie (#1433 AC-5/AC-13/AC-16 am lebenden Modul verletzt, Bug #3355)';

describe('W2 / AC-5: Reiter Wetter ueberschreibt skip_next nicht', () => {
	test('Tagesfenster speichern (frischer ETag): skip_next bleibt, Tagesfenster wird gespeichert', { todo: BEFUND_VOLLKOPIE }, async () => {
		befehlSetztSkipNext();
		await frischerEtag();
		const a = P.neuerAufbau();
		const wm = await P.wetterReiter(a);
		wm.aendern({ tagesfenster: { start: 6, end: 18 } });
		await P.fertig(a.ctl);

		assert.ok(puts().length >= 1, 'Messaufbau: der Reiter muss einen PUT abgesetzt haben');
		assert.equal(reportConfig().skip_next, true, 'Wetter-Metriken hat das ganze report_config samt skip_next=false zurueckgeschrieben');
		geaenderteWerteFallsGespeichert({ day_window_start_hour: 6 });
	});

	test('Anzeige-Einstellung (E-Mail-Inhalt) speichern (frischer ETag)', async () => {
		befehlSetztSkipNext();
		await frischerEtag();
		const a = P.neuerAufbau();
		const karte = await P.karteWasStehtWo(a);
		karte.schalten('show_compact_summary', false);
		await P.fertig(a.ctl);

		assert.ok(puts().length >= 1, 'Messaufbau: die Karte muss einen PUT abgesetzt haben');
		assert.equal(reportConfig().skip_next, true);
		geaenderteWerteFallsGespeichert({ show_compact_summary: false });
	});

	test('Metrik-Auswahl speichern (Trip-PUT mit report_config), frischer ETag', { todo: BEFUND_VOLLKOPIE }, async () => {
		befehlSetztSkipNext();
		await frischerEtag();
		const a = P.neuerAufbau();
		const wm = await P.wetterReiter(a);
		wm.abwaehlen('wind');
		await P.fertig(a.ctl);

		assert.ok(puts().length >= 1);
		assert.equal(reportConfig().skip_next, true, 'der zweite PUT des Reiters (report_config) hat skip_next zurueckgeschrieben');
	});
});

describe('W2: auch NACH einem 412 darf ein zweiter Versuch skip_next nicht ueberschreiben', () => {
	test('Reiter Wetter, Tagesfenster: 412, dann zweiter Versuch', async () => {
		befehlSetztSkipNext(); // Registry steht auf altem ETag ⇒ erster PUT ⇒ 412
		const a = P.neuerAufbau();
		const wm = await P.wetterReiter(a);
		wm.aendern({ tagesfenster: { start: 6, end: 18 } });
		await P.fertig(a.ctl);
		assert.ok(puts().length >= 1, 'Messaufbau: der erste Versuch hat den Server erreicht');
		// (keine Statuscode-Zusicherung — W2 laesst 200 oder 412 offen)

		// zweiter Versuch (neue Geste im selben Reiter)
		wm.aendern({ tagesfenster: { start: 7, end: 18 } });
		await P.fertig(a.ctl);

		assert.equal(reportConfig().skip_next, true, 'der zweite Versuch nach dem 412 lief ohne If-Match und hat skip_next zurueckgeschrieben');
	});
});
