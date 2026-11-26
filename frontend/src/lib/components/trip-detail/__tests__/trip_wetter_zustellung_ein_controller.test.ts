// Issue #3020 R1, AC-2 (Ersatz für die route-Fälle des mit #3357 gelöschten
// wetter_metriken_versand_panel_speicherung, #1743): Die lebenden Reiter Wetter (samt Karte „Was steht wo“) und
// Zustellung teilen im Trip-Hub EINEN Speicher-Controller und verdrängen sich nicht — jede Eingabe landet auf dem
// Server, auch wenn die zweite vor Ablauf der Entprellung der ersten kommt, beim Verlassen der Seite und nach 412.
// Gemessen wird der SERVER-Stand (Go-Merge) über das echte `api`. Pfadregel #1409: Pfade relativ zu DIESER Datei.

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../api.ts';
import { clearEtagRegistry } from '../../../etagRegistry.ts';
import { createFakeTripServer, type FakeTripServer } from '../../../__tests__/fakeTripServer.ts';
import * as P from './tripMehrreiterPruefstand.ts';

type Rec = Record<string, unknown>;
let server: FakeTripServer;
let laufzeit = 0;
/** Fehlerinjektion vor dem Ersatz-Server (500, kein Schreibvorgang). */
let fehler: ((pfad: string, rumpf: Rec) => boolean) | null = null;
beforeEach(async () => {
	clearEtagRegistry();
	laufzeit = 0;
	server = createFakeTripServer({ merge: true, latencyMs: (m) => (m === 'PUT' ? laufzeit : 0) });
	fehler = null;
	server.install();
	const fake = globalThis.fetch;
	(globalThis as { fetch: unknown }).fetch = async (input: unknown, init?: RequestInit) =>
		init?.method === 'PUT' && fehler?.(String(input), JSON.parse(String(init.body)))
			? new Response(JSON.stringify({ error: 'boom', detail: 'Serverfehler' }), { status: 500, headers: { 'Content-Type': 'application/json' } })
			: fake(input as never, init);
	server.seed(P.TRIP_ID, P.vollerTrip());
	await api.get(P.TRIP_PFAD);
});
afterEach(() => server.restore());
const puts = () => server.calls.filter((c) => c.method === 'PUT');

/** Server-Stand der drei Eingaben: Abwahl Wind (Wetter), Etappen-Kennzahlen aus (Karte), Morgenzeit (Zustellung). */
function eingaben(): Rec {
	const t = server.stand(P.TRIP_ID);
	const rc = t.report_config as Rec;
	const wind = ((t.display_config as Rec).metrics as Rec[]).find((m) => m.metric_id === 'wind');
	return { wetter: wind?.enabled, karte: rc.show_stage_stats, zustellung: rc.morning_time };
}
const VORHER = { wetter: true, karte: true, zustellung: '07:00:00' };
const NACHHER: Rec = { wetter: false, karte: false, zustellung: '08:00:00' };

/** Alle drei Schreiber an EINEM Controller, Gesten einzeln ausführbar. */
async function hub() {
	const a = P.neuerAufbau();
	const w = await P.wetterReiter(a);
	const k = await P.karteWasStehtWo(a);
	const z = await P.zustellungReiter(a);
	return {
		a,
		wetter: w,
		zeit: (morgenZeit: string) => z.aendern({ morgenZeit }),
		geste: {
			wetter: () => w.abwaehlen('wind'),
			karte: () => k.schalten('show_stage_stats', false),
			zustellung: () => z.aendern({ morgenZeit: '08:00' })
		} as Record<string, () => void>
	};
}

describe('#3020 R1: Reiter Wetter, Karte und Zustellung an einem Controller', () => {
	for (const [erster, zweiter] of [
		['wetter', 'zustellung'],
		['zustellung', 'wetter'],
		['karte', 'zustellung'],
		['zustellung', 'karte'],
		['karte', 'wetter']
	]) {
		test(`erst ${erster}, sofort danach ${zweiter}: beide Eingaben stehen auf dem Server, ohne 412`, async () => {
			const { a, geste } = await hub();
			assert.deepEqual(eingaben(), VORHER, 'Messaufbau');
			geste[erster]();
			geste[zweiter]();
			await P.fertig(a.ctl);
			assert.deepEqual(eingaben(), { ...VORHER, [erster]: NACHHER[erster], [zweiter]: NACHHER[zweiter] });
			assert.ok(puts().every((p) => p.status === 200 && p.ifMatch !== null), JSON.stringify(puts().map((p) => [p.path, p.status])));
			assert.equal(a.ctl.state, 'idle');
		});
	}

	/** Erste Geste, kurz danach die zweite, sofort Verlassen der Seite — der erste PUT ist noch unterwegs (40 ms). */
	async function verlassen(erster: () => void, zweiter: () => void, ctl: P.Aufbau['ctl']): Promise<void> {
		laufzeit = 40;
		erster();
		await new Promise((r) => setTimeout(r, 5));
		zweiter();
		await new Promise((r) => setTimeout(r, 5)); // Geste und Verlassen sind im Browser getrennte Ereignisse
		await ctl.flush({ keepalive: true });
		await P.fertig(ctl);
		await new Promise((r) => setTimeout(r, 150));
	}
	for (const [erster, zweiter] of [
		['zustellung', 'wetter'],
		['karte', 'zustellung'],
		['zustellung', 'karte']
	]) {
		test(`erst ${erster}, dann ${zweiter}, sofort Verlassen mit keepalive: beide Eingaben stehen auf dem Server`, async () => {
			const { a, geste } = await hub();
			await verlassen(geste[erster], geste[zweiter], a.ctl);
			assert.deepEqual(eingaben(), { ...VORHER, [erster]: NACHHER[erster], [zweiter]: NACHHER[zweiter] });
			assert.equal(a.ctl.state, 'idle');
		});
	}

	// Befund R1 (#3381, eigenes Bug-Issue legt der Orchestrator an): der Reiter Wetter schreibt zwei PUTs
	// nacheinander. Kommt der keepalive-PUT der Zustellung (ohne If-Match) dazwischen, trägt der zweite Wetter-PUT
	// den überholten Stempel, der Server lehnt ihn mit 412 ab und die Seite ist schon weg.
	test('erst wetter (Tagesfenster), dann zustellung, sofort Verlassen mit keepalive: beide Eingaben stehen auf dem Server', { todo: '#3381 zweiter Wetter-PUT bekommt 412, wenn der Verlassen-Flush ihn überholt' }, async () => {
		const { a, geste, wetter } = await hub();
		await verlassen(() => wetter.aendern({ tagesfenster: { start: 6, end: 20 } }), geste.zustellung, a.ctl);
		const rc = server.stand(P.TRIP_ID).report_config as Rec;
		assert.deepEqual([rc.morning_time, rc.day_window_start_hour, rc.day_window_end_hour], ['08:00:00', 6, 20]);
	});

	test('Konflikt: Wetter und Zustellung werden abgelehnt, „Nochmal speichern“ schreibt beide, Fremdänderung bleibt', async () => {
		const { a, geste } = await hub();
		server.foreignWrite(P.TRIP_ID, { name: 'Fremder Name' });
		geste.wetter();
		geste.zustellung();
		await P.fertig(a.ctl);
		assert.equal(a.ctl.state, 'conflict');
		assert.deepEqual(eingaben(), VORHER, 'nichts geschrieben');
		await a.ctl.retryConflict();
		assert.equal(a.ctl.state, 'idle');
		assert.deepEqual(eingaben(), { ...VORHER, wetter: false, zustellung: '08:00:00' });
		assert.equal(server.stand(P.TRIP_ID).name, 'Fremder Name');
	});

	test('Konflikt: Kopf, Etappen, Alarme, Wetter und Zustellung haben je einen eigenen Eintrag, „Nochmal speichern“ schreibt alle', async () => {
		const { a, geste } = await hub();
		const kopf = await P.kopfReiter(a);
		const etappen = await P.etappenReiter(a);
		const alarme = await P.alarmeReiter(a);
		server.foreignWrite(P.TRIP_ID, { avalanche_regions: ['FREMD'] });
		const neueEtappen = [{ id: 'T1', name: 'Umbenannt', date: '2026-10-10', waypoints: [] }];
		for (const schreibt of [
			() => kopf.umbenennen('Neuer Name'),
			() => etappen.speichern(neueEtappen),
			() => alarme.empfindlichkeitAendern('wind', 'sensibel'),
			geste.wetter,
			geste.zustellung
		]) {
			await schreibt();
			await P.fertig(a.ctl);
		}
		assert.equal(a.ctl.state, 'conflict');
		assert.deepEqual(eingaben(), VORHER, 'nichts geschrieben');
		await a.ctl.retryConflict();
		assert.equal(a.ctl.state, 'idle');
		const t = server.stand(P.TRIP_ID);
		assert.deepEqual(eingaben(), { ...VORHER, wetter: false, zustellung: '08:00:00' });
		assert.equal(t.name, 'Neuer Name');
		assert.deepEqual(t.stages, neueEtappen);
		assert.equal(((t.display_config as Rec).metric_alert_levels as Rec).wind, 'sensibel');
		assert.deepEqual(t.avalanche_regions, ['FREMD']);
	});

	test('zwei Vorgänge nacheinander: der zweite trägt den Stempel der ersten Antwort', async () => {
		const { a, geste } = await hub();
		const stempel = server.etagOf(P.TRIP_ID);
		geste.zustellung();
		geste.karte();
		await P.fertig(a.ctl);
		assert.deepEqual(puts().map((p) => p.status), [200, 200]);
		assert.equal(puts()[0].ifMatch, stempel);
		assert.ok(puts()[1].ifMatch !== null && puts()[1].ifMatch !== stempel, String(puts()[1].ifMatch));
		assert.ok(puts()[0].finishedAt <= puts()[1].startedAt, 'nie zwei PUTs gleichzeitig');
	});

	for (const [erster, zweiter, trifft] of [
		['wetter', 'zustellung', (pfad: string) => pfad.endsWith('/weather-config')],
		['zustellung', 'karte', (_: string, rumpf: Rec) => 'morning_time' in ((rumpf.report_config ?? {}) as Rec)]
	] as [string, string, (pfad: string, rumpf: Rec) => boolean][]) {
		test(`AC-15: ${erster} scheitert (500), ${zweiter} klappt: Anzeige „Fehler“, nicht „Gespeichert“`, async () => {
			const { a, geste } = await hub();
			let versucht = 0;
			fehler = (pfad, rumpf) => trifft(pfad, rumpf) && ++versucht > 0;
			geste[erster]();
			geste[zweiter]();
			await P.fertig(a.ctl);
			assert.equal(versucht, 1, `${erster} wurde nie gesendet (verdrängt)`);
			assert.deepEqual(eingaben(), { ...VORHER, [zweiter]: NACHHER[zweiter] });
			assert.equal(a.ctl.state, 'error');
			assert.ok(!(a.ctl.savedAt instanceof Date), 'kein „Gespeichert HH:MM“');
		});
	}

	test('F001: Zustellzeit binnen 700 ms zurücksetzen nimmt den Wetter-Vorgang nicht mit und sendet die Zeit nie', async () => {
		const { a, geste, zeit } = await hub();
		geste.wetter();
		geste.zustellung();
		zeit('07:00');
		assert.equal(a.ctl.hasPending, false, 'der zurückgenommene Vorgang steht noch aus');
		await P.fertig(a.ctl);
		assert.deepEqual(eingaben(), { ...VORHER, wetter: false });
		assert.ok(puts().every((p) => !JSON.stringify(p.anfrage).includes('morning_time')), 'ein PUT trägt die zurückgenommene Zeit');
		assert.equal(a.ctl.state, 'idle');
	});

	test('F001: Metrik abwählen und binnen 700 ms wieder wählen: die Zustellzeit kommt an, die Auswahl bleibt', async () => {
		const { a, geste, wetter } = await hub();
		geste.zustellung();
		geste.wetter();
		wetter.hinzufuegen('wind');
		await P.fertig(a.ctl);
		assert.deepEqual(eingaben(), { ...VORHER, zustellung: '08:00:00' });
		assert.equal(a.ctl.hasPending, false);
		assert.equal(a.ctl.state, 'idle');
	});

	test('alle drei Schreiber an einem Trip: der Trip eines zweiten Nutzers bleibt unberührt', async () => {
		server.seed('t-bruno', P.vollerTrip('t-bruno'));
		const vorher = server.stand('t-bruno');
		const { a, geste } = await hub();
		for (const g of ['wetter', 'karte', 'zustellung']) geste[g]();
		await P.fertig(a.ctl);
		assert.deepEqual(server.stand('t-bruno'), vorher);
		assert.ok(server.calls.every((c) => !c.path.includes('t-bruno')));
	});
});
