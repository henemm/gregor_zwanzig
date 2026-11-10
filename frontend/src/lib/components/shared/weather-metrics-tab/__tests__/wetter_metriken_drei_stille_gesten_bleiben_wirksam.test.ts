// Issue #2276 Scheibe S4 (Epic #2345), AC-5 — UMGESTELLT durch Issue #2794 S3a Teil-PR 3
// (Fix-Loop 1, Adversary-Finding F006, AC-38 woertlich):
//
// Frueher: die drei „stillen" Gesten Metrik-Checkbox, Amtliche-Warnungen-Schalter und
// Tagesfenster Von/Bis hatten keinen eigenen Commit-Call und mussten ueber den
// Wetter-Metriken-Speicherer gespeichert werden.
// Jetzt: diese drei Felder gehoeren dem Reiter Wetter (WetterTab, wetterTabSpeicherung.ts).
// WeatherMetricsTab steht nur noch im Reiter Zustellung, und sein Speicherer darf KEINES
// dieser Felder schreiben — auch nicht, wenn sie sich in seiner Kopie aendern (z. B. nach
// der Neu-Hydration aus der WetterTab-Antwort). Je Geste ein eigener Testfall
// (Isolationsnachweis wie bisher): jede der drei loest allein keinen PUT aus.
//
// Ausführen:
//   cd frontend && npm test -- src/lib/components/shared/weather-metrics-tab/__tests__/wetter_metriken_drei_stille_gesten_bleiben_wirksam.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../../api.ts';
import { clearEtagRegistry } from '../../../../etagRegistry.ts';
import { createFakeTripServer, type FakeTripServer } from '../../../../__tests__/fakeTripServer.ts';
import type { ComparePreset } from '../../../../types.ts';
import { createPutQueue } from '../../../compare/compareHubPersistenz.ts';
import { erstelleWetterMetrikenVergleichSpeicherung } from '../weatherMetricsCompareSave.ts';
import { createController, hydrierterWs, makePreset, wetterMetrikenBedienung } from './wetterMetrikenVergleichPruefstand.ts';

const PRESET_ID = 'cp-2276-s4-stille-gesten';

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
		zustand: ws,
		preset: () => basis,
		enqueueHubWrite: (fn) => queue.enqueue(fn),
		onCompareUpdate: (p: ComparePreset) => {
			basis = p;
		},
		saveController: ctl
	});
	return { ws, ctl, speicherung, bedienung: wetterMetrikenBedienung(ws) };
}

const FAELLE: Array<[string, (b: ReturnType<typeof wetterMetrikenBedienung>) => void]> = [
	['AC-5a → #2794 F006: Metrik-Checkbox', (b) => b.toggleMetric('wind_max_kmh')],
	['AC-5b → #2794 F006: Amtliche-Warnungen-Schalter', (b) => b.toggleOfficialAlerts()],
	['AC-5c → #2794 F006: Tagesfenster Von/Bis', (b) => b.setDayWindow(6, 21)]
];

describe('#2794 F006: Felder des Reiters Wetter speichert der Zustellungs-Speicherer nicht', () => {
	for (const [was, geste] of FAELLE) {
		test(`${was} — allein ⇒ kein PUT, kein Vorgang beim Controller`, async () => {
			const { ctl, speicherung, bedienung } = aufbau();
			geste(bedienung);
			speicherung.aenderungMelden();
			assert.equal(ctl.hasPending, false, `${was}: der Zustellungs-Speicherer plant einen Vorgang ein`);
			await ctl.flush();
			assert.equal(puts().length, 0, `${was}: der Zustellungs-Speicherer schreibt ein Feld des Reiters Wetter`);
		});
	}
});
