// TDD RED — Issue #1433 Fix-Loop (CI-Befund PR #2486, Klasse-b-Inventar): das
// Kaskaden-Sofortschreiben der Etappen (`EditStagesPanelNew.applyCascade`) schreibt per
// `api.put` mit Registry-If-Match am Controller vorbei. Bei 412 meldete es nur
// `setError` + `deferSave()` — kein „Nochmal speichern", und jeder weitere Versuch
// trug das alte If-Match (#1433 §4.1) und scheiterte wieder: Sackgasse.
//
// Spec: docs/specs/bugfix/trip_mehrreiter_konfliktschutz.md — §4 (2/3/4), AC-15,
//       AC-18, AC-19.
//
// Gemessen am ECHTEN Instanz-Skript (`tripMehrreiterPruefstand.ts`), echtem `api`,
// echtem SaveStatus und dem Ersatz-Server im Merge-Modus — gelesen wird der SERVER-STAND.
// `cascadeFollowers` ist im Komponenten-Code ein `$derived` (im Pruefstand nicht
// reaktiv) und wird hier so gesetzt, wie Svelte es nach `handleDateChange` herleitet.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/trip-detail/__tests__/trip_etappen_kaskade_412_nochmal_speichern.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../api.ts';
import { clearEtagRegistry } from '../../../etagRegistry.ts';
import { createFakeTripServer, type FakeTripServer } from '../../../__tests__/fakeTripServer.ts';
import * as P from './tripMehrreiterPruefstand.ts';

const FREMDE_METRIKEN = [{ metric_id: 'cape', enabled: true, aggregations: ['max'] }];

function tripMitZweiEtappen(): Record<string, unknown> {
	const t = P.vollerTrip();
	t.stages = [
		{ id: 'T1', name: 'Etappe 1', date: '2026-10-10', waypoints: [{ id: 'G1', name: 'A', lat: 42.1, lon: 9.1, elevation_m: 100 }] },
		{ id: 'T2', name: 'Etappe 2', date: '2026-10-11', waypoints: [{ id: 'G2', name: 'B', lat: 42.2, lon: 9.2, elevation_m: 200 }] }
	];
	return t;
}

let server: FakeTripServer;

beforeEach(async () => {
	clearEtagRegistry();
	server = createFakeTripServer({ merge: true });
	server.install();
	server.seed(P.TRIP_ID, tripMitZweiEtappen());
	await api.get(P.TRIP_PFAD);
});
afterEach(() => server.restore());

const puts = () => server.calls.filter((c) => c.method === 'PUT');
const stand = () => server.stand(P.TRIP_ID);
const daten = (stages: unknown) => (stages as Array<{ id: string; date: string }>).map((s) => `${s.id}:${s.date}`);

/** Etappe 1 umdatieren (+2 Tage) und „Folgende Etappen mitverschieben" waehlen. */
async function kaskade(a: P.Aufbau) {
	const e = await P.etappenReiter(a);
	(e.inst.u.handleDateChange as (id: string, d: string) => void)('T1', '2026-10-12');
	assert.ok(e.inst.u.cascade && !(e.inst.u.cascade as { done: boolean }).done, 'Messaufbau: Rueckfrage zur Kaskade steht');
	e.inst.u.cascadeFollowers = ['T2']; // $derived, wie Svelte es herleitet
	await (e.inst.u.applyCascade as () => Promise<void>)();
	return e;
}

describe('Etappen-Kaskade: 412 ⇒ „Nochmal speichern" statt Sackgasse', () => {
	test('412 mit If-Match ⇒ Controller `conflict`, nichts geschrieben, Fremdaenderung bleibt', async () => {
		server.foreignWrite(P.TRIP_ID, { display_config: { metrics: FREMDE_METRIKEN } });
		const a = P.neuerAufbau(tripMitZweiEtappen());
		const stand0 = JSON.stringify(stand());

		await kaskade(a);

		assert.equal(puts().length, 1, 'Messaufbau: genau EIN PUT (das Kaskaden-Sofortschreiben)');
		assert.ok(puts()[0].ifMatch, 'AC-18: If-Match');
		assert.equal(puts()[0].status, 412, 'Vorbedingung');
		assert.equal(a.ctl.state, 'conflict', '„Nochmal speichern" muss erscheinen — heute nur `error`');
		assert.equal(JSON.stringify(stand()), stand0);
	});

	test('„Nochmal speichern" ⇒ Kaskade (beide Etappen umdatiert) UND Fremdaenderung auf dem Server, Nutzlast nur { stages }', async () => {
		server.foreignWrite(P.TRIP_ID, { display_config: { metrics: FREMDE_METRIKEN } });
		const a = P.neuerAufbau(tripMitZweiEtappen());
		await kaskade(a);
		assert.equal(a.ctl.state, 'conflict', 'Vorbedingung');

		await a.ctl.retryConflict();

		const retry = puts().at(-1)!;
		assert.equal(retry.status, 200);
		assert.deepEqual(Object.keys(retry.anfrage as object), ['stages'], 'AC-15: nur das Eigenfeld `stages`');
		assert.deepEqual(daten(stand().stages), ['T1:2026-10-12', 'T2:2026-10-13'], 'die Kaskade (Eingabe des Nutzers) steht auf dem Server');
		assert.deepEqual((stand().display_config as Record<string, unknown>).metrics, FREMDE_METRIKEN, 'die Fremdaenderung bleibt');
		assert.equal(a.ctl.state, 'idle');
	});

	test('nach dem 412 haengt kein zurueckgestellter Altstand ohne Kaskade an, der den Retry-Eintrag ueberschreiben koennte', async () => {
		server.foreignWrite(P.TRIP_ID, { display_config: { metrics: FREMDE_METRIKEN } });
		const a = P.neuerAufbau(tripMitZweiEtappen());
		const e = await kaskade(a);
		// Reiterwechsel: flush des Controllers
		await a.ctl.flush();
		await a.ctl.retryConflict();
		assert.deepEqual(daten(stand().stages), ['T1:2026-10-12', 'T2:2026-10-13'], 'die Kaskade darf beim Retry nicht verloren gehen');
		assert.deepEqual(daten(e.inst.u.stages), ['T1:2026-10-12', 'T2:2026-10-13'], 'der Reiter zeigt, was gesendet wird');
	});

	test('Gegenprobe ohne Fremdschreiber: Kaskade speichert sofort, Controller `idle`', async () => {
		const a = P.neuerAufbau(tripMitZweiEtappen());
		await kaskade(a);
		assert.equal(puts().at(-1)!.status, 200);
		assert.deepEqual(daten(stand().stages), ['T1:2026-10-12', 'T2:2026-10-13']);
		assert.equal(a.ctl.state, 'idle');
	});
});
