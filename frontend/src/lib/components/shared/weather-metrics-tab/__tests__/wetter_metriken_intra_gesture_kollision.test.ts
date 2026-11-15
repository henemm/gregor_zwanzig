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
import { createController, dc, hydrierterWs, makePreset, wetterMetrikenBedienung } from './wetterMetrikenVergleichPruefstand.ts';

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
	// Reiter Wetter; die Kollision wird mit den verbleibenden Feldern dieses Speicherers gemessen
	// (Kanal-Auswahl = Wetter-Metriken-Domaene, Stundenverlauf/Ausblick = Layout-Domaene).
	// #3031: die Kanal-Auswahl (`channel_active_metrics`) schreibt dieser Speicherer nicht mehr — sie
	// gehoert der Karte „Inhalt je Kanal und Fläche“ im Reiter Wetter. Die Kollision wird deshalb
	// zwischen Stundenverlauf und Ausblick gemessen; der Rumpf traegt kein Kanal-Feld.
	test('Ausblick-Auswahl UND Stundenverlauf-Drag im selben Tick → EIN PUT, Body trägt BEIDE Änderungen', async () => {
		const { ctl, speicherung, bedienung } = aufbau();

		// Simuliert den Wrapper-Bubble: der innere Wrapper meldet zuerst, der äußere
		// unmittelbar danach — beide OHNE dazwischenliegenden Tab-Wechsel oder await.
		bedienung.outlookSelect(['wind_max_kmh']);
		speicherung.aenderungMelden();
		bedienung.hourlyDragEnd(['temp_max_c', 'wind_max_kmh', 'gust_max_kmh']);
		speicherung.aenderungMelden();

		await ctl.flush();

		assert.equal(puts().length, 1, 'eine Geste im gemeinsamen Wrapper darf nur EINEN PUT auslösen');
		const body = server.storedBody(PRESET_ID);
		assert.deepEqual(dc(body).outlook_metrics, ['wind_max_kmh'], 'die Ausblick-Änderung darf vom nachfolgenden Bubble NICHT überschrieben werden');
		assert.deepEqual(
			dc(body).hourly_metrics,
			['temp_max_c', 'wind_max_kmh', 'gust_max_kmh'],
			'die Stundenverlauf-Änderung muss im selben PUT stehen'
		);
		assert.ok(!('channel_active_metrics' in dc(body)), '#3031: Kanal-Auswahl gehoert der Karte im Reiter Wetter');
	});

	test('umgekehrte Reihenfolge (Stundenverlauf zuerst, dann Ausblick) → EIN PUT, Body trägt BEIDE Änderungen', async () => {
		const { ctl, speicherung, bedienung } = aufbau();

		bedienung.hourlyDragEnd(['temp_max_c', 'wind_max_kmh']);
		speicherung.aenderungMelden();
		bedienung.outlookSelect(['wind_max_kmh']);
		speicherung.aenderungMelden();

		await ctl.flush();

		assert.equal(puts().length, 1);
		const body = server.storedBody(PRESET_ID) as Record<string, unknown>;
		assert.deepEqual(dc(body).hourly_metrics, ['temp_max_c', 'wind_max_kmh'], 'die zuerst gemeldete Stundenverlauf-Änderung ging verloren');
		assert.deepEqual(dc(body).outlook_metrics, ['wind_max_kmh'], 'die zuletzt gemeldete Ausblick-Änderung muss ebenfalls im selben PUT stehen');
	});

	test('drei Änderungen über beide Domänen verteilt, alle vor dem ersten Flush → EIN PUT trägt alle drei', async () => {
		const { ctl, speicherung, bedienung } = aufbau();

		bedienung.outlookSelect(['wind_max_kmh', 'temp_max_c']);
		speicherung.aenderungMelden();
		bedienung.hourlyDragEnd(['temp_max_c', 'wind_max_kmh']);
		speicherung.aenderungMelden();
		bedienung.outlookFormatToggle('temp_max_c', false);
		speicherung.aenderungMelden();

		await ctl.flush();

		assert.equal(puts().length, 1, 'drei Meldungen derselben Geste — trotzdem nur ein PUT');
		const body = server.storedBody(PRESET_ID) as Record<string, unknown>;
		assert.deepEqual(dc(body).outlook_metrics, ['wind_max_kmh', 'temp_max_c']);
		assert.deepEqual(dc(body).hourly_metrics, ['temp_max_c', 'wind_max_kmh']);
		assert.equal((dc(body).outlook_metric_formats as Record<string, boolean>).temp_max_c, false);
	});
});
