// TDD RED — Issue #2276 Scheibe S4 (Epic #2345), AC-11: schließt der Nutzer
// den Tab unmittelbar nach einer Wetter-Metriken/Layout-Änderung, löst der
// Browser Keepalive aus — `init` muss an den PUT durchgereicht werden (analog
// `trip_speicherung_reicht_keepalive_durch.test.ts`, S2/S3-Muster).
//
// Spec: docs/specs/modules/rework_2276_s4_wetter_metriken.md — AC-11
//
// Ausführen:
//   cd frontend && npm test -- src/lib/components/shared/weather-metrics-tab/__tests__/wetter_metriken_nutzlast_reicht_keepalive_durch.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../../api.ts';
import { clearEtagRegistry } from '../../../../etagRegistry.ts';
import { createFakeTripServer, type FakeTripServer } from '../../../../__tests__/fakeTripServer.ts';
import type { ComparePreset } from '../../../../types.ts';
import { createPutQueue } from '../../../compare/compareHubWizardBridge.ts';
import { erstelleWetterMetrikenVergleichSpeicherung } from '../weatherMetricsCompareSave.ts';
import { createController, hydrierterWs, makePreset, wetterMetrikenBedienung } from './wetterMetrikenVergleichPruefstand.ts';

const PRESET_ID = 'cp-2276-s4-keepalive';
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
	const ws = hydrierterWs(basis);
	const ctl = createController(PRESET_ID);
	const queue = createPutQueue();
	const speicherung = erstelleWetterMetrikenVergleichSpeicherung({
		client: api,
		wiz: ws,
		preset: () => basis,
		enqueueHubWrite: (fn) => queue.enqueue(fn),
		onCompareUpdate: (p: ComparePreset) => {
			basis = p;
		},
		saveController: ctl
	});
	return { ws, ctl, speicherung, bedienung: wetterMetrikenBedienung(ws) };
}

describe('AC-11: die Entlade-Option (keepalive) erreicht den Wetter-Metriken-PUT', () => {
	test('Flush beim Entladen → PUT mit keepalive:true', async () => {
		const { ctl, speicherung, bedienung } = aufbau();
		await api.get(PRESET_PFAD); // Stand bekannt, wie nach dem Laden der Seite

		bedienung.toggleMetric('gust_max_kmh');
		speicherung.aenderungMelden();
		await ctl.flush({ keepalive: true });

		assert.equal(puts().length, 1, 'genau ein PUT erwartet');
		assert.equal(puts()[0].path, PRESET_PFAD);
		assert.equal(puts()[0].keepalive, true, 'die Option keepalive:true des Wächters wurde verschluckt');
	});

	test('Gegenprobe: regulärer Flush → PUT ohne keepalive', async () => {
		const { ctl, speicherung, bedienung } = aufbau();

		bedienung.toggleMetric('gust_max_kmh');
		speicherung.aenderungMelden();
		await ctl.flush();

		assert.equal(puts().length, 1);
		assert.equal(puts()[0].keepalive, false, 'ohne Entladen darf kein keepalive gesetzt werden');
	});
});
