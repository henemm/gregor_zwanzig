// TDD RED — Issue #2276 Scheibe S5 (Epic #2345), AC-10: schließt der Nutzer
// den Tab unmittelbar nach einer Versand-Änderung, löst der Browser Keepalive
// aus — `init` muss von der SaveFn an `api.put` durchgereicht werden
// (Muster trip_speicherung_reicht_keepalive_durch.test.ts, S2/S3/S4).
//
// Spec: docs/specs/modules/rework_2276_s5_versand.md — AC-10, Design Punkt 7
//
// Mutations-Gegenprobe (Spec AC-10): `init` in der SaveFn ignorieren (fester
// `undefined`-Aufruf an `api.put`) ⇒ der PUT trägt kein keepalive ⇒ rot.
//
// Ausführen:
//   cd frontend && npm test -- src/lib/components/shared/__tests__/versand_nutzlast_reicht_keepalive_durch.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../api.ts';
import { clearEtagRegistry } from '../../../etagRegistry.ts';
import { createFakeTripServer, type FakeTripServer } from '../../../__tests__/fakeTripServer.ts';
import type { ComparePreset } from '../../../types.ts';
import { createPutQueue } from '../../compare/compareHubPersistenz.ts';
import { erstelleVersandVergleichSpeicherung } from '../versandVergleichSpeicherung.ts';
import { createController, hydrierterWiz, makePreset, versandBedienung } from './versandVergleichPruefstand.ts';

const PRESET_ID = 'cp-2276-s5-keepalive';
const PRESET_PFAD = `/api/compare/presets/${PRESET_ID}`;

let server: FakeTripServer;

beforeEach(() => {
	clearEtagRegistry();
	server = createFakeTripServer();
	server.install();
});

afterEach(() => server.restore());

const puts = () => server.calls.filter((c) => c.method === 'PUT');

function aufbau() {
	let basis = makePreset(PRESET_ID);
	const wiz = hydrierterWiz(basis);
	const ctl = createController(PRESET_ID);
	const queue = createPutQueue();
	const speicherung = erstelleVersandVergleichSpeicherung({
		client: api,
		zustand: wiz,
		preset: () => basis,
		enqueueHubWrite: (fn) => queue.enqueue(fn),
		onCompareUpdate: (p: ComparePreset) => {
			basis = p;
		},
		saveController: ctl
	});
	return { ctl, speicherung, bedienung: versandBedienung(wiz) };
}

describe('AC-10: die Entlade-Option (keepalive) erreicht den Versand-PUT', () => {
	test('Flush beim Entladen → PUT mit keepalive:true', async () => {
		const { ctl, speicherung, bedienung } = aufbau();
		await api.get(PRESET_PFAD); // Stand bekannt, wie nach dem Laden der Seite

		bedienung.setMorgenZeit('07:15');
		speicherung.aenderungMelden();
		await ctl.flush({ keepalive: true });

		assert.equal(puts().length, 1, 'genau ein PUT erwartet');
		assert.equal(puts()[0].path, PRESET_PFAD);
		assert.equal(puts()[0].keepalive, true, 'die Option keepalive:true des Wächters wurde verschluckt');
	});

	test('Gegenprobe: regulärer Flush → PUT ohne keepalive', async () => {
		const { ctl, speicherung, bedienung } = aufbau();
		await api.get(PRESET_PFAD);

		bedienung.setMorgenZeit('07:45');
		speicherung.aenderungMelden();
		await ctl.flush();

		assert.equal(puts().length, 1);
		assert.equal(puts()[0].keepalive, false, 'ohne Entladen darf kein keepalive gesetzt werden');
	});
});
