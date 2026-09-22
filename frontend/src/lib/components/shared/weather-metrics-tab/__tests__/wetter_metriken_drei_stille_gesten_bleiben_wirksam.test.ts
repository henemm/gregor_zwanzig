// TDD RED — Issue #2276 Scheibe S4 (Epic #2345), AC-5: drei Gesten hatten
// historisch KEINEN expliziten Commit-Call und verließen sich vollständig auf
// den Wrapper-Bubble (Kontext-Dokument Abschnitt 1.5): Metrik-Checkbox
// (`toggleCompareMetric`), Amtliche-Warnungen-Schalter
// (`onToggleVergleichOfficialAlerts`) und Tagesfenster Von/Bis
// (`DayWindowCard`-Handler). Fällt der Wrapper weg, müssen genau diese drei
// Stellen einen Ersatzweg bekommen (reaktiver `$effect`, der alle acht
// persistenzrelevanten Felder beobachtet) — sonst verstummt die Persistenz
// für genau diese drei Gesten lautlos.
//
// Spec: docs/specs/modules/rework_2276_s4_wetter_metriken.md — AC-5
//
// Je Geste ein eigener Testfall (Isolationsnachweis: fällt der Ersatzweg für
// GENAU eine Geste weg, wird GENAU dieser Test rot, die anderen beiden bleiben
// grün). Auf Modulebene geprüft (wie AC-1): der kombinierte Snapshot muss ALLE
// drei Felder tragen, damit ein reiner Feldwechsel — ohne Ziehgeste — als
// Diff erkannt wird. Prüfort ≠ Wirkort für die tatsächliche `$effect`-
// Verdrahtung: E2E-Spec compare-wetter-metriken-speichert-selbst.spec.ts.
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
import { createController, dc, hydrierterWs, makePreset, wetterMetrikenBedienung } from './wetterMetrikenVergleichPruefstand.ts';

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

describe('AC-5a: Metrik-Checkbox (toggleCompareMetric) — kein Drag, trotzdem gespeichert', () => {
	test('Checkbox aus (Metrik entfernen) → gemeldet, gespeichert', async () => {
		const { ctl, speicherung, bedienung } = aufbau();
		bedienung.toggleMetric('wind_max_kmh'); // in makePreset aktiv → wird entfernt
		speicherung.aenderungMelden();
		await ctl.flush();
		assert.equal(puts().length, 1, 'die Checkbox-Geste (ohne Ziehgeste) muss gespeichert werden');
		assert.ok(!(dc(server.storedBody(PRESET_ID)).active_metrics as string[]).includes('wind_max_kmh'));
	});
});

describe('AC-5b: Amtliche-Warnungen-Schalter (onToggleVergleichOfficialAlerts) — kein Drag, trotzdem gespeichert', () => {
	test('Schalter umgelegt → gemeldet, gespeichert', async () => {
		const { ctl, speicherung, bedienung } = aufbau();
		bedienung.toggleOfficialAlerts();
		speicherung.aenderungMelden();
		await ctl.flush();
		assert.equal(puts().length, 1, 'der Amtliche-Warnungen-Schalter (ohne Ziehgeste) muss gespeichert werden');
		assert.equal((server.storedBody(PRESET_ID) as Record<string, unknown>).official_alerts_enabled, false);
	});
});

describe('AC-5c: Tagesfenster Von/Bis (DayWindowCard-Handler) — kein Drag, trotzdem gespeichert', () => {
	test('Von/Bis geändert → gemeldet, gespeichert', async () => {
		const { ctl, speicherung, bedienung } = aufbau();
		bedienung.setDayWindow(6, 21);
		speicherung.aenderungMelden();
		await ctl.flush();
		assert.equal(puts().length, 1, 'das Tagesfenster (ohne Ziehgeste) muss gespeichert werden');
		const stand = server.storedBody(PRESET_ID) as Record<string, unknown>;
		assert.equal(stand.day_window_start_hour, 6);
		assert.equal(stand.day_window_end_hour, 21);
	});
});

describe('Isolationsnachweis: die drei Gesten sind unabhängig voneinander erkennbar', () => {
	test('nur EINE der drei Gesten ausgelöst → genau diese eine steht im Diff, die anderen beiden bleiben beim Ausgangswert', async () => {
		const { ctl, speicherung, bedienung } = aufbau();
		bedienung.toggleOfficialAlerts();
		speicherung.aenderungMelden();
		await ctl.flush();

		const stand = server.storedBody(PRESET_ID) as Record<string, unknown>;
		assert.equal(stand.official_alerts_enabled, false, 'die ausgelöste Geste muss stehen');
		assert.equal(stand.day_window_start_hour, 4, 'Tagesfenster-Start unangetastet (Default)');
		assert.equal(stand.day_window_end_hour, 19, 'Tagesfenster-Ende unangetastet (Default)');
		assert.deepEqual(
			dc(stand).active_metrics,
			['wind_max_kmh', 'snow_depth_cm', 'temp_max_c'],
			'Metrikauswahl unangetastet (Ausgangsstand aus makePreset)'
		);
	});
});
