// Fix-Loop 3, Issue #1433 — F201: JEDER Trip-Schreiber meldet bei 412 seine gesendete
// Eigenfeld-Nutzlast an die Seite; die Seite schreibt `trip` lokal fort (Seitenstand =
// Server ⊕ ausstehende Nutzlasten). Kein Stempelwechsel, kein Neuaufbau offener Reiter.
//
// Gemessen ueber die ECHTE Trip-Seite und die ECHTEN Reiter-Skripte (alle sieben
// Schreibwege: Alarme, Versand, Wertebereiche, Wetter-Metriken (Katalog + nur Inhalt),
// Kopf, Aktivitaet, Etappen); Pruefling ist der abgelehnte PUT-Rumpf — der Seitenstand
// muss genau diese Felder tragen.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/trip-detail/__tests__/trip_konflikt_schreibt_seitenstand_fort.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../api.ts';
import { clearEtagRegistry, getKnownEtag } from '../../../etagRegistry.ts';
import { createFakeTripServer, type FakeTripServer } from '../../../__tests__/fakeTripServer.ts';
import * as P from './tripMehrreiterPruefstand.ts';

let server: FakeTripServer;

beforeEach(async () => {
	clearEtagRegistry();
	server = createFakeTripServer({ merge: true });
	server.install();
	server.seed(P.TRIP_ID, P.vollerTrip());
	await api.get(P.TRIP_PFAD);
	server.foreignWrite(P.TRIP_ID, { name: 'Fremder Name' }); // alle Schreiber laufen in 412
});
afterEach(() => server.restore());

const abgelehnt = () => server.calls.filter((c) => c.method === 'PUT' && c.status === 412);
type Rec = Record<string, unknown>;

/** Traegt `trip` jeden Schluessel des abgelehnten Rumpfes (einstufig wie der Server)? */
function traegt(trip: Rec, rumpf: Rec): void {
	const schluessel = Object.keys(rumpf);
	assert.ok(schluessel.length > 0, 'Messaufbau: der abgelehnte Rumpf ist nicht leer');
	for (const k of schluessel) {
		const w = rumpf[k];
		if (w !== null && typeof w === 'object' && !Array.isArray(w)) {
			for (const [u, v] of Object.entries(w as Rec)) assert.deepEqual((trip[k] as Rec)[u], v, `${k}.${u}`);
		} else {
			assert.deepEqual(trip[k], w, k);
		}
	}
}

async function seiteMit(): Promise<{ a: P.Aufbau; seite: Awaited<ReturnType<typeof P.tripSeite>>; neu: () => P.Aufbau }> {
	const a = P.neuerAufbau();
	const seite = await P.tripSeite(a, server);
	return { a, seite, neu: () => P.neuerAufbau(seite.trip(), a.ctl) };
}

describe('jeder Schreiber: 412 ⇒ `trip` der Seite traegt die abgelehnte Nutzlast', () => {
	test('Wertebereiche (Desktop)', async () => {
		const { a, seite, neu } = await seiteMit();
		const wb = await P.wertebereicheReiter(neu());
		wb.inst.u.rows = [{ metric: 'wind_max_kmh', label: 'Wind', min: 0, max: 55, notify: true, mark: true }];
		wb.speichern();
		await P.fertig(a.ctl);
		assert.equal(abgelehnt().length, 1, 'Vorbedingung: 412');
		assert.deepEqual(seite.trip().corridors, [{ metric: 'wind_max_kmh', range: [0, 55], notify: true, mark: true }]);
		traegt(seite.trip(), abgelehnt()[0].anfrage as Rec);
	});

	test('Wetter-Metriken (Katalog): display_config-Teil UND report_config-Teil', async () => {
		const { a, seite, neu } = await seiteMit();
		const wm = await P.wetterMetrikenReiter(neu());
		wm.inst.u.telegramKurzform = true;
		wm.inst.u.reportConfig = { ...(wm.inst.u.reportConfig as Rec), show_stage_stats: false };
		wm.metrikenSpeichern();
		await P.fertig(a.ctl);
		assert.equal(abgelehnt().length, 1, 'Vorbedingung: der erste PUT (/weather-config) wird abgelehnt');
		const t = seite.trip();
		assert.equal((t.display_config as Rec).telegram_kurzform, true, 'Wetter-Fragment (/weather-config) im Seitenstand');
		assert.equal((t.report_config as Rec).show_stage_stats, false, 'Trip-Rumpf (report_config) im Seitenstand');
		assert.equal((t.display_config as Rec).trip_id, P.TRIP_ID, 'uebrige display_config-Schluessel bleiben (einstufiger Merge)');
	});

	test('Wetter-Metriken (nur Inhalt/Tagesfenster)', async () => {
		const { a, seite, neu } = await seiteMit();
		const wm = await P.wetterMetrikenReiter(neu());
		wm.reportConfigSpeichern({ day_window_start_hour: 6 });
		await P.fertig(a.ctl);
		assert.equal(abgelehnt().length, 1);
		assert.equal((seite.trip().report_config as Rec).day_window_start_hour, 6);
		traegt(seite.trip(), abgelehnt()[0].anfrage as Rec);
	});

	test('Kopf (Name)', async () => {
		const { seite, neu } = await seiteMit();
		const k = await P.kopfReiter(neu());
		await k.umbenennen('Neuer Name');
		assert.equal(abgelehnt().length, 1);
		assert.equal(seite.trip().name, 'Neuer Name');
	});

	test('Aktivitaet', async () => {
		const { seite, neu } = await seiteMit();
		const t = await P.aktivitaetReiter(neu());
		await t.aendern('skitour');
		assert.equal(abgelehnt().length, 1);
		assert.equal(seite.trip().activity, 'skitour');
	});

	test('Etappen (Rumpf wird beim Ausloesen gelesen)', async () => {
		const { a, seite, neu } = await seiteMit();
		const e = await P.etappenReiter(neu());
		const stages = [{ id: 'T1', name: 'Umbenannt', date: '2026-10-10', waypoints: [] }];
		e.speichern(stages);
		await P.fertig(a.ctl);
		assert.equal(abgelehnt().length, 1);
		assert.deepEqual(seite.trip().stages, stages);
	});
});

describe('Fortschreiben ist lokal: kein Stempelwechsel, kein Neuaufbau, kein Fremdstand', () => {
	test('Alarme: Stempel bleibt, Reiter werden nicht neu aufgebaut, Fremdaenderung steht NICHT im Seitenstand', async () => {
		const { a, seite, neu } = await seiteMit();
		const stempel = getKnownEtag(P.TRIP_ID);
		const alarme = await P.alarmeReiter(neu());
		alarme.empfindlichkeitAendern('wind', 'sensibel');
		await P.fertig(a.ctl);
		assert.equal(a.ctl.state, 'conflict');
		assert.equal(getKnownEtag(P.TRIP_ID), stempel, 'der Stempel wird beim Fortschreiben NICHT gewechselt');
		assert.equal(seite.inst.u.uebernommeneFassung, 0, 'kein Neuaufbau');
		assert.notEqual(seite.trip().name, 'Fremder Name', 'kein stilles Ersetzen durch den Serverstand (AC-9)');
		const lv = (seite.trip().display_config as Rec).metric_alert_levels as Rec;
		assert.equal(lv.wind, 'sensibel');
	});
});
