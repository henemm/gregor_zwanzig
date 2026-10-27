// Issue #2347 S2 (AC-6/AC-13, Fix-Loop 1 F001): scheitert ein Auto-Save der Etappen,
// fallen die Etappen sichtbar auf den zuletzt vom Server BESTAETIGTEN Stand zurueck —
// ausser bei 412 und beim „Nochmal speichern" (dort braucht der Konflikt-Weg die
// ungespeicherte Eingabe). Bestaetigt wird jeder erfolgreiche PUT: Auto-Save,
// Kaskaden-Sofortschreiben und manuelles Speichern.
//
// Gemessen am ECHTEN Instanz-Skript von EditStagesPanelNew.svelte
// (`tripMehrreiterPruefstand.ts`), echtem `api`, echter SaveStatus-Instanz und dem
// Ersatz-Server im Merge-Modus. Ein Server-Fehler 500 wird am Netz eingespeist
// (`fetch`-Huelle), die Komponente und der Speicher-Regler laufen echt.
//
// Ausfuehren:
//   cd frontend && npm test -- src/lib/components/trip-detail/__tests__/etappen_rollback_auf_bestaetigten_stand.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../api.ts';
import { clearEtagRegistry } from '../../../etagRegistry.ts';
import { createFakeTripServer, type FakeTripServer } from '../../../__tests__/fakeTripServer.ts';
import * as P from './tripMehrreiterPruefstand.ts';

type Etappe = { id: string; name: string; date: string; waypoints: unknown[] };

const ERST = ['T1:2026-10-10', 'T2:2026-10-11'];

function tripMitZweiEtappen(): Record<string, unknown> {
	const t = P.vollerTrip();
	t.stages = [
		{ id: 'T1', name: 'Etappe 1', date: '2026-10-10', waypoints: [{ id: 'G1', name: 'A', lat: 42.1, lon: 9.1, elevation_m: 100 }] },
		{ id: 'T2', name: 'Etappe 2', date: '2026-10-11', waypoints: [{ id: 'G2', name: 'B', lat: 42.2, lon: 9.2, elevation_m: 200 }] }
	];
	return t;
}

let server: FakeTripServer;
let echtesFetch: typeof globalThis.fetch;
/** true ⇒ jeder PUT antwortet 500 (Fehler-Einspeisung am Netz). */
let putScheitert = false;

beforeEach(async () => {
	clearEtagRegistry();
	putScheitert = false;
	server = createFakeTripServer({ merge: true });
	server.install();
	echtesFetch = globalThis.fetch;
	globalThis.fetch = ((input: unknown, init?: RequestInit) =>
		putScheitert && init?.method === 'PUT'
			? Promise.resolve(new Response(JSON.stringify({ error: 'stubbed failure' }), { status: 500 }))
			: echtesFetch(input as RequestInfo, init)) as typeof globalThis.fetch;
	server.seed(P.TRIP_ID, tripMitZweiEtappen());
	await api.get(P.TRIP_PFAD);
});
afterEach(() => {
	globalThis.fetch = echtesFetch;
	server.restore();
});

const puts = () => server.calls.filter((c) => c.method === 'PUT');
const stand = () => server.stand(P.TRIP_ID);
const daten = (stages: unknown) => (stages as Etappe[]).map((s) => `${s.id}:${s.date}`);

function mitDatum(stages: unknown, id: string, date: string): Etappe[] {
	return (JSON.parse(JSON.stringify(stages)) as Etappe[]).map((s) => (s.id === id ? { ...s, date } : s));
}

describe('#2347 S2: Etappen-Auto-Save scheitert ⇒ Rueckfall auf den zuletzt bestaetigten Stand', () => {
	test('(c) erster Auto-Save ok, zweiter 500 ⇒ Etappen zeigen den ERSTEN gespeicherten Stand, nicht den Oeffnungsstand', async () => {
		const a = P.neuerAufbau(tripMitZweiEtappen());
		const e = await P.etappenReiter(a);

		e.speichern(mitDatum(e.inst.u.stages, 'T1', '2026-10-20'));
		await P.fertig(a.ctl);
		assert.equal(puts().at(-1)?.status, 200, 'Vorbedingung: der erste Auto-Save geht durch');
		assert.deepEqual(daten(stand().stages), ['T1:2026-10-20', 'T2:2026-10-11']);

		putScheitert = true;
		e.speichern(mitDatum(e.inst.u.stages, 'T1', '2026-10-25'));
		await P.fertig(a.ctl);

		assert.equal(a.ctl.state, 'error', 'ein 500 endet als Fehler am Chip');
		assert.deepEqual(
			daten(e.inst.u.stages),
			['T1:2026-10-20', 'T2:2026-10-11'],
			'sichtbarer Rueckfall auf den zuletzt BESTAETIGTEN Stand (erster Auto-Save), nicht auf den Oeffnungsstand und nicht auf den Versuchswert'
		);
	});

	test('(a) 412 ⇒ KEIN Rueckfall; „Nochmal speichern" sendet die Eingabe des Nutzers', async () => {
		server.foreignWrite(P.TRIP_ID, { name: 'fremd geaendert' });
		const a = P.neuerAufbau(tripMitZweiEtappen());
		const e = await P.etappenReiter(a);

		e.speichern(mitDatum(e.inst.u.stages, 'T1', '2026-10-22'));
		await P.fertig(a.ctl);
		assert.equal(puts().at(-1)?.status, 412, 'Vorbedingung: der Server lehnt den veralteten Stand ab');
		assert.equal(a.ctl.state, 'conflict');
		assert.deepEqual(daten(e.inst.u.stages), ['T1:2026-10-22', 'T2:2026-10-11'], 'bei 412 bleibt die Eingabe sichtbar stehen');

		await a.ctl.retryConflict();

		assert.equal(puts().at(-1)?.status, 200, 'der Wiederholungs-PUT geht durch');
		assert.deepEqual(daten(stand().stages), ['T1:2026-10-22', 'T2:2026-10-11'], '„Nochmal speichern" schreibt die Eingabe des Nutzers');
		assert.equal(stand().name, 'fremd geaendert', 'die Fremdaenderung bleibt');
		assert.equal(a.ctl.state, 'idle');
	});

	test('(b) scheitert „Nochmal speichern" erneut (500) ⇒ KEIN Rueckfall, die Eingabe bleibt fuer den naechsten Versuch', async () => {
		server.foreignWrite(P.TRIP_ID, { name: 'fremd geaendert' });
		const a = P.neuerAufbau(tripMitZweiEtappen());
		const e = await P.etappenReiter(a);

		e.speichern(mitDatum(e.inst.u.stages, 'T1', '2026-10-23'));
		await P.fertig(a.ctl);
		assert.equal(a.ctl.state, 'conflict', 'Vorbedingung: Konflikt');

		putScheitert = true;
		await a.ctl.retryConflict();

		assert.equal(puts().at(-1)?.status, 412, 'Messaufbau: der 500 kam aus der Einspeisung, nicht vom Ersatz-Server');
		assert.notEqual(a.ctl.state, 'idle', 'die Wiederholung ist gescheitert');
		assert.deepEqual(
			daten(e.inst.u.stages),
			['T1:2026-10-23', 'T2:2026-10-11'],
			'beim Wiederholen wird NICHT zurueckgesetzt — sonst faende der naechste Versuch keinen Unterschied mehr'
		);
	});

	test('(d) Kaskaden-Erfolg bestaetigt den Stand: ein danach scheiternder Auto-Save faellt auf das Kaskaden-Ergebnis zurueck', async () => {
		const a = P.neuerAufbau(tripMitZweiEtappen());
		const e = await P.etappenReiter(a);
		(e.inst.u.handleDateChange as (id: string, d: string) => void)('T1', '2026-10-12');
		e.inst.u.cascadeFollowers = ['T2']; // $derived, wie Svelte es herleitet
		await (e.inst.u.applyCascade as () => Promise<void>)();
		assert.deepEqual(daten(stand().stages), ['T1:2026-10-12', 'T2:2026-10-13'], 'Vorbedingung: Kaskade gespeichert');

		putScheitert = true;
		e.speichern(mitDatum(e.inst.u.stages, 'T2', '2026-10-30'));
		await P.fertig(a.ctl);

		assert.deepEqual(
			daten(e.inst.u.stages),
			['T1:2026-10-12', 'T2:2026-10-13'],
			'Rueckfall auf das bestaetigte Kaskaden-Ergebnis, nicht auf den Oeffnungsstand'
		);
		assert.notDeepEqual(daten(e.inst.u.stages), ERST);
	});

	test('(d) manuelles Speichern (ohne Speicher-Regler) bestaetigt den Stand', async () => {
		const a = P.neuerAufbau(tripMitZweiEtappen());
		const e = await P.etappenReiter(a);
		const neu = mitDatum(e.inst.u.stages, 'T1', '2026-10-15');

		const ergebnis = await (e.inst.u.save as (s: unknown) => Promise<unknown>)(neu);
		assert.ok(ergebnis, 'Vorbedingung: manuelles Speichern geht durch');

		const stand = e.inst.u.etappenStand as { bestaetigt(): unknown };
		assert.deepEqual(daten(stand.bestaetigt()), ['T1:2026-10-15', 'T2:2026-10-11'], 'der Rueckfall-Stand ist das manuell Gespeicherte');

		putScheitert = true;
		e.speichern(mitDatum(neu, 'T1', '2026-10-31'));
		await P.fertig(a.ctl);
		assert.deepEqual(daten(e.inst.u.stages), ['T1:2026-10-15', 'T2:2026-10-11'], 'Rueckfall auf das manuell Gespeicherte');
	});

	test('Gegenprobe: ohne Fehler kein Rueckfall, Auto-Save bleibt bei der Eingabe', async () => {
		const a = P.neuerAufbau(tripMitZweiEtappen());
		const e = await P.etappenReiter(a);
		e.speichern(mitDatum(e.inst.u.stages, 'T1', '2026-10-21'));
		await P.fertig(a.ctl);
		assert.deepEqual(daten(e.inst.u.stages), ['T1:2026-10-21', 'T2:2026-10-11']);
		assert.equal(a.ctl.state, 'idle');
	});
});
