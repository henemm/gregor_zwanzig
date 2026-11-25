// TDD RED — Issue #2276 Scheibe S4 (Epic #2345), AC-2: die kritische,
// gegenüber S2/S3 NEUE Anforderung dieser Scheibe. Der Nutzer ändert eine
// Metrikauswahl UND — innerhalb desselben Debounce-Fensters, ausgelöst durch
// denselben Wrapper-Bubble — eine Stundenverlauf-/Ausblick-Einstellung. Weil
// heute beide Domänen an EINEM Wrapper-Paar hängen, feuern beide historischen
// Commit-Funktionen im selben synchronen Tick. Würde S4 das 1:1 auf zwei
// unabhängige Selbst-Speicherer übertragen, überschriebe der zweite
// `schedule()`-Aufruf den `_pendingFn`-Einzel-Slot des ersten NOCH VOR Ablauf
// des Debounce-Fensters — die zuerst geplante Änderung ginge beim einzigen
// tatsächlich ausgeführten PUT verloren (Spec Design-Entscheidung 1,
// Kontext-Dokument Abschnitt 1.7).
//
// Spec: docs/specs/modules/rework_2276_s4_wetter_metriken.md — AC-2
//
// Deshalb baut S4 EINE kombinierte Orchestrierung mit EINEM Snapshot-Typ über
// BEIDE Domänen: `aenderungMelden()` liest bei JEDEM Aufruf den VOLLSTÄNDIGEN,
// aktuell LIVE im Wizard-Zustand stehenden Stand — unabhängig davon, welches
// Feld die Geste zuletzt geändert hat. Ein zweiter `aenderungMelden()`-Aufruf
// in derselben Millisekunde (Wetter-Metriken-Wrapper, dann Layout-Wrapper)
// überschreibt daher NICHT die zuerst gemeldete Änderung — er bestätigt sie.
//
// Zielschnittstelle: s. wetter_metriken_vergleich_speichert_einmal.test.ts
//
// Ausführen:
//   cd frontend && npm test -- src/lib/components/shared/weather-metrics-tab/__tests__/wetter_metriken_intra_gesture_kollision.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../../api.ts';
import { clearEtagRegistry } from '../../../../etagRegistry.ts';
import { createFakeTripServer, type FakeTripServer } from '../../../../__tests__/fakeTripServer.ts';
import type { ComparePreset } from '../../../../types.ts';
import { createPutQueue } from '../../../compare/compareHubPersistenz.ts';
import { erstelleWetterMetrikenVergleichSpeicherung } from '../weatherMetricsCompareSave.ts';
import { createController, hydrierterWs, makePreset, wetterMetrikenBedienung } from './wetterMetrikenVergleichPruefstand.ts';

const PRESET_ID = 'cp-2276-s4-kollision';

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

describe('AC-2: eine Geste löst historisch BEIDE Wrapper aus — beide Domänen überleben EINEN PUT', () => {
	// #2794 S3a Teil 3 (F006): Metrikauswahl, Amtliche Warnungen und Tagesfenster gehoeren dem
	// Reiter Wetter. Issue #3276: Kanal-Auswahl, Stundenverlauf- und Ausblick-Listen/-Formate sind
	// Altschluessel und werden nicht mehr gesendet. Issue #3298: auch der Ausblick-Schalter
	// entfaellt; die Kollision wird mit dem verbliebenen eigenen Feld (Stundenverlauf-Schalter)
	// und einer Kanal-Aenderung derselben Geste gemessen, die NICHT im Rumpf auftauchen darf.
	test('Stundenverlauf-Schalter und Kanal-Aenderung im selben Tick → EIN PUT, nur der Schalter reist', async () => {
		const { ws, ctl, speicherung, bedienung } = aufbau();

		bedienung.hourlyEnabledToggle();
		speicherung.aenderungMelden();
		ws.channelActiveMetricKeys = { email: ['wind_max_kmh'], telegram: null, sms: null };
		speicherung.aenderungMelden();

		await ctl.flush();

		assert.equal(puts().length, 1, 'eine Geste im gemeinsamen Wrapper darf nur EINEN PUT auslösen');
		const body = server.storedBody(PRESET_ID) as Record<string, unknown>;
		assert.equal(body.hourly_enabled, false, 'die zuerst gemeldete Änderung darf nicht überschrieben werden');
		assert.ok(!('outlook_enabled' in body), '#3298: kein Ausblick-Schalter im Rumpf');
		assert.equal(body.display_config, undefined, '#3276: Kanal-Aenderungen reisen nicht mit');
	});

	test('drei Meldungen derselben Geste vor dem ersten Flush → EIN PUT trägt den Endstand', async () => {
		const { ws, ctl, speicherung, bedienung } = aufbau();

		bedienung.hourlyEnabledToggle();
		speicherung.aenderungMelden();
		ws.channelActiveMetricKeys = { email: null, telegram: ['temp_max_c'], sms: null };
		speicherung.aenderungMelden();
		speicherung.aenderungMelden();

		await ctl.flush();

		assert.equal(puts().length, 1, 'drei Meldungen derselben Geste — trotzdem nur ein PUT');
		const body = server.storedBody(PRESET_ID) as Record<string, unknown>;
		assert.equal(body.hourly_enabled, false);
		assert.equal(body.display_config, undefined, '#3276: Kanal-Aenderungen sind Altschluessel');
	});
});
