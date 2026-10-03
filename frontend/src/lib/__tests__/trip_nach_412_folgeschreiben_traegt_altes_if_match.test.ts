// TDD RED — Issue #1433, AC-18 (+ Vorbedingung von AC-1/AC-2/AC-10): nach einem
// 412 wird der ETag NICHT mehr verworfen. Die Registry markiert die Ressource als
// `konflikt` und behaelt den alten Stempel — jeder weitere Schreibvorgang (Reiter
// B, Kopf, Aktivitaet, auch ein erneuter Versuch desselben Reiters) traegt das
// ALTE If-Match, bekommt wieder 412, und der Server schreibt nichts.
//
// Spec: docs/specs/bugfix/trip_mehrreiter_konfliktschutz.md — §4 Punkt 1 und 5,
//       §1 (Befund `api.ts:136`), AC-18.
//
// Heute rot: `api.ts:136` ruft bei 412 `discardEtag` — der naechste Schreibvorgang
// laeuft OHNE If-Match durch und schreibt unbedingt.
//
// Zielschnittstelle in etagRegistry.ts (neu): `markiereKonflikt(id)`,
// `istKonflikt(id)` — dynamischer Import je Test (der Modul-Import schlaegt nicht
// fehl, nur der Zugriff).
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/__tests__/trip_nach_412_folgeschreiben_traegt_altes_if_match.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../api.ts';
import * as registry from '../etagRegistry.ts';
import { clearEtagRegistry, getKnownEtag } from '../etagRegistry.ts';
import { createFakeTripServer, type FakeTripServer } from './fakeTripServer.ts';
import * as P from '../components/trip-detail/__tests__/tripMehrreiterPruefstand.ts';

let server: FakeTripServer;

beforeEach(() => {
	clearEtagRegistry();
	server = createFakeTripServer({ merge: true });
	server.install();
	server.seed(P.TRIP_ID, P.vollerTrip());
});
afterEach(() => server.restore());

const puts = () => server.calls.filter((c) => c.method === 'PUT');

type KonfliktApi = { markiereKonflikt?: (id: string) => void; istKonflikt?: (id: string) => boolean };
const konfliktApi = (): Required<KonfliktApi> => {
	const m = registry as unknown as KonfliktApi;
	assert.equal(typeof m.istKonflikt, 'function', 'etagRegistry.ts muss `istKonflikt(id)` exportieren');
	assert.equal(typeof m.markiereKonflikt, 'function', 'etagRegistry.ts muss `markiereKonflikt(id)` exportieren');
	return m as Required<KonfliktApi>;
};

/** Konflikt herstellen: Reiter A kennt E1, ein Fremdschreiber aendert, A schreibt ⇒ 412. */
async function konfliktHerstellen(): Promise<{ alterEtag: string }> {
	await api.get(P.TRIP_PFAD);
	const alterEtag = getKnownEtag(P.TRIP_ID)!;
	assert.ok(alterEtag, 'Messaufbau: die Registry kennt den Stand');
	server.foreignWrite(P.TRIP_ID, { display_config: { metrics: [{ metric_id: 'cape', enabled: true }] } });
	await assert.rejects(api.put(P.TRIP_PFAD, { activity: 'mtb' }), (e: { status?: number }) => e.status === 412);
	return { alterEtag };
}

describe('AC-18 / §4.1: nach 412 bleibt der alte ETag, die Ressource ist als Konflikt markiert', () => {
	test('der ETag wird nicht verworfen und die Ressource ist `konflikt`', async () => {
		const { alterEtag } = await konfliktHerstellen();
		assert.equal(getKnownEtag(P.TRIP_ID), alterEtag, 'api.ts:136 darf den ETag nach 412 nicht mehr verwerfen');
		assert.equal(konfliktApi().istKonflikt(P.TRIP_ID), true, 'die Registry muss den Zustand `konflikt` fuehren');
	});

	test('ein weiterer api.put traegt das ALTE If-Match, bekommt 412, der Server schreibt nichts', async () => {
		const { alterEtag } = await konfliktHerstellen();
		const vorher = JSON.stringify(server.stand(P.TRIP_ID));
		await assert.rejects(api.put(P.TRIP_PFAD, { name: 'zweiter Versuch' }), (e: { status?: number }) => e.status === 412);
		const letzter = puts().at(-1)!;
		assert.equal(letzter.ifMatch, alterEtag, 'kein unbedingtes Schreiben nach 412: der Folge-PUT muss das alte If-Match tragen');
		assert.equal(letzter.status, 412);
		assert.equal(JSON.stringify(server.stand(P.TRIP_ID)), vorher, 'der Server darf nichts geschrieben haben');
	});

	test('der Konflikt gilt je Ressource: ein anderer Trip ist nicht betroffen', async () => {
		await konfliktHerstellen();
		const m = konfliktApi();
		assert.equal(m.istKonflikt('anderer-trip'), false);
		server.seed('anderer-trip', { name: 'x' });
		await api.get('/api/trips/anderer-trip');
		await api.put('/api/trips/anderer-trip', { name: 'y' });
		assert.equal(puts().at(-1)!.status, 200, 'ein unbeteiligter Trip schreibt weiter normal');
	});

	test('Ortsvergleich teilt den Mechanismus (gleiche Registry): 412 auf dem Preset-Pfad markiert ebenfalls', async () => {
		const id = 'cp-1433-paritaet';
		await api.get(`/api/compare/presets/${id}`);
		const alt = getKnownEtag(id)!;
		server.foreignWrite(id, { name: 'fremd' });
		await assert.rejects(api.put(`/api/compare/presets/${id}`, { name: 'lokal' }), (e: { status?: number }) => e.status === 412);
		assert.equal(getKnownEtag(id), alt, 'auch beim Ortsvergleich bleibt der alte ETag');
		assert.equal(konfliktApi().istKonflikt(id), true);
		await assert.rejects(api.put(`/api/compare/presets/${id}`, { name: 'nochmal' }), (e: { status?: number }) => e.status === 412);
		assert.equal(puts().at(-1)!.ifMatch, alt);
	});

	test('clearEtagRegistry (Testisolation) setzt auch die Konflikt-Markierung zurueck', async () => {
		await konfliktHerstellen();
		clearEtagRegistry();
		assert.equal(konfliktApi().istKonflikt(P.TRIP_ID), false, 'sonst verseucht ein Konflikt die Folgetests');
	});

	test('markiereKonflikt/istKonflikt: Direktaufruf', () => {
		const m = konfliktApi();
		assert.equal(m.istKonflikt('x1'), false);
		m.markiereKonflikt('x1');
		assert.equal(m.istKonflikt('x1'), true);
		assert.equal(m.istKonflikt('x2'), false);
	});
});

describe('AC-18: jeder weitere Schreiber traegt das alte If-Match (Reiter B, Kopf, Aktivitaet)', () => {
	test('Reiter B (Wetter-Metriken): beide PUTs bzw. der erste tragen das alte If-Match, der Server schreibt nichts', async () => {
		const { alterEtag } = await konfliktHerstellen();
		const vorher = JSON.stringify(server.stand(P.TRIP_ID));
		const a = P.neuerAufbau();
		const w = await P.wetterMetrikenReiter(a);
		w.metrikenSpeichern();
		await P.fertig(a.ctl);
		const neue = puts().slice(1);
		assert.ok(neue.length >= 1, 'Messaufbau: Reiter B hat geschrieben');
		for (const p of neue) {
			assert.equal(p.ifMatch, alterEtag, `${p.path}: altes If-Match erwartet`);
			assert.equal(p.status, 412);
		}
		assert.equal(JSON.stringify(server.stand(P.TRIP_ID)), vorher);
	});

	test('Kopf (Umbenennen): altes If-Match, 412, Name auf dem Server unveraendert, lokaler trip wird nicht ersetzt', async () => {
		const { alterEtag } = await konfliktHerstellen();
		const a = P.neuerAufbau();
		const k = await P.kopfReiter(a);
		await k.umbenennen('Neuer Name');
		const p = puts().at(-1)!;
		assert.equal(p.ifMatch, alterEtag);
		assert.equal(p.status, 412);
		assert.notEqual(server.stand(P.TRIP_ID).name, 'Neuer Name');
		assert.equal(a.updates.length, 0, '§4.1: bei 412 darf `trip` im lokalen Zustand nicht ersetzt werden');
	});

	test('Aktivitaet: altes If-Match, 412, nichts geschrieben, lokaler trip nicht ersetzt', async () => {
		const { alterEtag } = await konfliktHerstellen();
		const a = P.neuerAufbau();
		const t = await P.aktivitaetReiter(a);
		await t.aendern('skitour');
		const p = puts().at(-1)!;
		assert.equal(p.ifMatch, alterEtag);
		assert.equal(p.status, 412);
		assert.notEqual(server.stand(P.TRIP_ID).activity, 'skitour');
		assert.equal(a.updates.length, 0);
	});

	test('Etappen: altes If-Match, 412, nichts geschrieben', async () => {
		const { alterEtag } = await konfliktHerstellen();
		const a = P.neuerAufbau();
		const e = await P.etappenReiter(a);
		e.speichern([{ id: 'T1', name: 'Umbenannt', date: '2026-10-10', waypoints: [] }]);
		await P.fertig(a.ctl);
		const p = puts().at(-1)!;
		assert.equal(p.ifMatch, alterEtag);
		assert.equal(p.status, 412);
		assert.notEqual((server.stand(P.TRIP_ID).stages as Array<{ name: string }>)[0].name, 'Umbenannt');
	});
});
