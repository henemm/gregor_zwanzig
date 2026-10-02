// TDD RED — Issue #1433, Bug-Test W1 (AC-1, AC-2, AC-18):
// Nach einem Speicherkonflikt (412) in Reiter A darf ein Speichern aus Reiter B
// die FREMDE Aenderung auf dem Server nicht ueberschreiben, und die
// Konfliktanzeige „Nochmal speichern" muss stehen bleiben.
//
// Spec: docs/specs/bugfix/trip_mehrreiter_konfliktschutz.md — Test Plan W1,
//       AC-1, AC-2, AC-18.
//
// Heute rot, weil (a) `api.ts:136` den ETag nach 412 verwirft — Reiter B
// schreibt danach OHNE If-Match mit der veralteten Vollkopie von display_config
// (Fremdaenderung weg), und (b) `schedule()`/`doSave()` den Zustand `conflict`
// ueber `setSaving()` verlassen (Anzeige verschwindet).
//
// Wo die Zusicherung wirkt: gelesen wird der SERVER-STAND im Ersatz-Server
// (Go-Merge) NACH dem Zusammenspiel zweier echter Reiter (Alarme, Wetter-
// Metriken/Wertebereiche) ueber EINEN gemeinsamen Controller — nicht die Form
// einer Nutzlast. Die Reiter laufen mit ihren echten Instanz-Skripten.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/trip-detail/__tests__/trip_mehrreiter_nach_412_kein_verlust.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../api.ts';
import { clearEtagRegistry } from '../../../etagRegistry.ts';
import { createFakeTripServer, type FakeTripServer } from '../../../__tests__/fakeTripServer.ts';
import * as P from './tripMehrreiterPruefstand.ts';

let server: FakeTripServer;

/** Die Fremdaenderung: ein anderer Tab / der Python-Core setzt `metrics` neu. */
const FREMDE_METRIKEN = [{ metric_id: 'cape', enabled: true, aggregations: ['max'] }];

beforeEach(async () => {
	clearEtagRegistry();
	server = createFakeTripServer({ merge: true });
	server.install();
	server.seed(P.TRIP_ID, P.vollerTrip());
	// Reiter A und B haben die Seite mit diesem Stand geladen (ETag bekannt) ...
	await api.get(P.TRIP_PFAD);
	// ... danach aendert jemand anderes die Metriken.
	server.foreignWrite(P.TRIP_ID, { display_config: { metrics: FREMDE_METRIKEN } });
});
afterEach(() => server.restore());

const puts = () => server.calls.filter((c) => c.method === 'PUT');
const metrikenAufServer = () => (server.stand(P.TRIP_ID).display_config as Record<string, unknown>).metrics;

/** Reiter A: Alarm-Empfindlichkeit speichern ⇒ 412 ⇒ Konflikt. */
async function konfliktInReiterA(a: P.Aufbau): Promise<void> {
	const alarme = await P.alarmeReiter(a);
	alarme.empfindlichkeitAendern('wind', 'sensibel');
	await P.fertig(a.ctl);
	assert.equal(puts().length, 1, 'Messaufbau: Reiter A hat genau einen PUT abgesetzt');
	assert.equal(puts()[0].status, 412, 'Vorbedingung: der Server lehnt den veralteten Stand ab');
	assert.equal(a.ctl.state, 'conflict', 'Vorbedingung: „Nochmal speichern" wird angeboten');
}

describe('W1 / AC-1: Fremdaenderung ueberlebt ein Speichern aus Reiter B nach dem Konflikt in Reiter A', () => {
	test('B = Wetter-Metriken: Server-`metrics` bleibt die Fremdaenderung, B-PUT traegt If-Match und bekommt 412', async () => {
		const a = P.neuerAufbau();
		await konfliktInReiterA(a);
		const ifMatchA = puts()[0].ifMatch;
		assert.ok(ifMatchA, 'Vorbedingung: der PUT von A trug If-Match');

		// Reiterwechsel: A ist ausgehaengt, B (Wetter-Metriken) speichert ueber denselben Controller.
		const wm = await P.wetterMetrikenReiter(a);
		wm.metrikenSpeichern();
		await P.fertig(a.ctl);

		assert.deepEqual(
			metrikenAufServer(),
			FREMDE_METRIKEN,
			'Reiter B hat die fremde Aenderung an display_config.metrics ueberschrieben (veralteter Spread ohne If-Match)'
		);
		const bPuts = puts().slice(1);
		assert.ok(bPuts.length >= 1, 'Messaufbau: Reiter B muss mindestens einen PUT abgesetzt haben');
		for (const p of bPuts) {
			assert.equal(p.ifMatch, ifMatchA, `B-PUT ${p.path} muss das ALTE If-Match tragen (kein unbedingtes Schreiben nach 412)`);
			assert.equal(p.status, 412, `B-PUT ${p.path} muss abgelehnt werden`);
		}
		assert.equal(a.ctl.state, 'conflict', 'AC-2: „Nochmal speichern" bleibt nach dem Speichern in Reiter B sichtbar');
	});

	test('B = Wertebereiche: dieselbe Zusicherung (sendet heute die GANZE display_config zurueck)', async () => {
		const a = P.neuerAufbau();
		await konfliktInReiterA(a);

		const wb = await P.wertebereicheReiter(a);
		wb.speichern();
		await P.fertig(a.ctl);

		assert.deepEqual(metrikenAufServer(), FREMDE_METRIKEN, 'Wertebereiche hat display_config.metrics zurueckgeschrieben');
		const letzter = puts().at(-1)!;
		assert.equal(letzter.status, 412, 'der Wertebereiche-PUT muss abgelehnt werden');
		assert.ok(letzter.ifMatch, 'der Wertebereiche-PUT muss If-Match tragen');
		assert.equal(a.ctl.state, 'conflict');
	});

	test('B = Alarme (derselbe Reiter noch einmal): auch das aendert nichts am Server', async () => {
		const a = P.neuerAufbau();
		await konfliktInReiterA(a);
		const alarme = await P.alarmeReiter(a);
		alarme.kanalUmschalten('sms');
		await P.fertig(a.ctl);

		assert.deepEqual(metrikenAufServer(), FREMDE_METRIKEN);
		assert.equal(puts().at(-1)!.status, 412);
		assert.equal(a.ctl.state, 'conflict');
	});

	test('Server-Stand nach dem Konflikt: weder A noch B haben etwas geschrieben', async () => {
		const a = P.neuerAufbau();
		await konfliktInReiterA(a);
		const wm = await P.wetterMetrikenReiter(a);
		wm.metrikenSpeichern();
		await P.fertig(a.ctl);

		const dc = server.stand(P.TRIP_ID).display_config as Record<string, unknown>;
		const seed = P.vollerTrip().display_config as Record<string, unknown>;
		assert.deepEqual(
			dc,
			{ ...seed, metrics: FREMDE_METRIKEN },
			'auf dem Server darf nur die Fremdaenderung stehen: weder die abgelehnte Alarm-Aenderung von A noch ein Rueckschreiben durch B'
		);
	});
});

describe('Gegenprobe: ohne Konflikt schreibt Reiter B normal (der Test ist nicht vakuum-gruen)', () => {
	test('frischer Stand: Wetter-Metriken-Reiter speichert, der Server-Stand aendert sich', async () => {
		// frischen Stand holen: Registry kennt den aktuellen ETag
		await api.get(P.TRIP_PFAD);
		const a = P.neuerAufbau(P.vollerTrip());
		const wm = await P.wetterMetrikenReiter(a);
		wm.inst.u.telegramKurzform = true;
		wm.metrikenSpeichern();
		await P.fertig(a.ctl);

		assert.equal(puts().at(-1)!.status, 200, 'ohne Konflikt muss der PUT durchgehen');
		assert.equal((server.stand(P.TRIP_ID).display_config as Record<string, unknown>).telegram_kurzform, true);
		assert.equal(a.ctl.state, 'idle');
	});
});
