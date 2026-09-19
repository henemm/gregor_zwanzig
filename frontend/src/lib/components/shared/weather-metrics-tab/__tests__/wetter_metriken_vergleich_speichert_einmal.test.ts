// TDD RED — Issue #2276 Scheibe S4 (Epic #2345), AC-1: eine Änderung im
// Wetter-Metriken-Reiter des Ortsvergleichs speichert über GENAU EINEN Weg —
// die neue kombinierte Orchestrierung im Speicher-Takt des Seiten-Controllers
// (schedule/flush/retryConflict), wie Alarme (S2) und Wertebereiche (S3). Der
// alte Doppel-Weg (zwei Commit-Funktionen `handleWetterMetrikenCommit`/
// `handleLayoutCommit`, ein Wrapper-Div-Paar) entfällt.
//
// Spec: docs/specs/modules/rework_2276_s4_wetter_metriken.md — AC-1
//
// WARUM AUF MODULEBENE (wie S2/S3): `svelte/server` führt weder `$effect`
// noch Ereignisse aus — ein Mount von WeatherMetricsTab mit PUT-Zählung ist in
// diesem Prüfstand nicht ausführbar. Der neue reaktive `$effect` darf nach S4
// nur DELEGIEREN (`vergleichSpeicherung.aenderungMelden()`); Diff-Gate,
// Basis-Lesen, Queue, Rückmeldung und Rollback liegen im Modul und werden
// hier geprüft. Prüfort ≠ Wirkort: dass WeatherMetricsTab/CompareTabs das
// Modul wirklich (und nur so) verdrahten, misst die E2E-Spec
// frontend/e2e/compare-wetter-metriken-speichert-selbst.spec.ts.
//
// Zielschnittstelle (existiert noch NICHT → RED):
//
//   frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsCompareSave.ts
//   erstelleWetterMetrikenVergleichSpeicherung({
//     client, wiz, preset: () => ComparePreset, enqueueHubWrite,
//     onCompareUpdate, saveController
//   }): { aenderungMelden(): void }
//
// Ausführen:
//   cd frontend && npm test -- src/lib/components/shared/weather-metrics-tab/__tests__/wetter_metriken_vergleich_speichert_einmal.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../../api.ts';
import { clearEtagRegistry } from '../../../../etagRegistry.ts';
import { createFakeTripServer, type FakeTripServer } from '../../../../__tests__/fakeTripServer.ts';
import type { ComparePreset } from '../../../../types.ts';
import { createPutQueue } from '../../../compare/compareHubWizardBridge.ts';
import { erstelleWetterMetrikenVergleichSpeicherung } from '../weatherMetricsCompareSave.ts';
import { createController, dc, hydrierterWs, makePreset, wetterMetrikenBedienung } from './wetterMetrikenVergleichPruefstand.ts';

const PRESET_ID = 'cp-2276-s4-einmal';
const PRESET_PFAD = `/api/compare/presets/${PRESET_ID}`;

let server: FakeTripServer;

beforeEach(() => {
	clearEtagRegistry();
	server = createFakeTripServer();
	server.install();
});

afterEach(() => server.restore());

const puts = () => server.calls.filter((c) => c.method === 'PUT');

function aufbau(preset = makePreset(PRESET_ID)) {
	let basis = preset;
	const ws = hydrierterWs(basis);
	const ctl = createController(PRESET_ID);
	const queue = createPutQueue();
	const rueckmeldungen: ComparePreset[] = [];
	const speicherung = erstelleWetterMetrikenVergleichSpeicherung({
		client: api,
		wiz: ws,
		preset: () => basis,
		enqueueHubWrite: (fn) => queue.enqueue(fn),
		onCompareUpdate: (p: ComparePreset) => {
			rueckmeldungen.push(p);
			basis = p;
		},
		saveController: ctl
	});
	const bedienung = wetterMetrikenBedienung(ws);
	return { ws, ctl, speicherung, bedienung, rueckmeldungen };
}

describe('AC-1: eine Wetter-Metriken-Änderung speichert im Takt des Controllers — genau EIN PUT', () => {
	test('Metrik-Checkbox an → schedule, Flush → genau EIN PUT mit der neuen Auswahl, „Gespeichert"', async () => {
		const { ctl, speicherung, bedienung, rueckmeldungen } = aufbau();

		bedienung.toggleMetric('gust_max_kmh');
		speicherung.aenderungMelden();

		assert.equal(ctl.hasPending, true, 'die Änderung muss im Speicher-Takt des Controllers liegen (schedule)');
		assert.equal(ctl.state, 'saving', 'während des Debounce-Fensters darf nie „Gespeichert" stehen');
		assert.equal(puts().length, 0, 'vor Ablauf der Entprellung darf nichts sofort gesendet werden');

		await ctl.flush();

		assert.equal(puts().length, 1, 'genau EIN PUT erwartet — historisch bis zu zwei (Wetter-Metriken + Layout)');
		assert.equal(puts()[0].path, PRESET_PFAD, 'der PUT muss auf die Ortsvergleich-Ressource gehen');
		assert.equal(puts()[0].status, 200);
		const body = server.storedBody(PRESET_ID);
		assert.ok(
			(dc(body).active_metrics as string[]).includes('gust_max_kmh'),
			'die neu aktivierte Metrik muss im Rumpf stehen'
		);
		assert.equal(ctl.state, 'idle', 'Endzustand „Gespeichert"');
		assert.ok(ctl.savedAt instanceof Date, 'savedAt muss nach echtem Erfolg gestempelt sein');
		assert.equal(rueckmeldungen.length, 1, 'onCompareUpdate genau einmal mit der Server-Antwort');
	});

	test('mehrere Zwischenwerte derselben Geste (Kanal-Reihenfolge-Drag) → trotzdem nur EIN PUT mit dem Endwert', async () => {
		const { ctl, speicherung, bedienung } = aufbau();

		for (const order of [
			['snow_depth_cm', 'wind_max_kmh', 'temp_max_c'],
			['temp_max_c', 'snow_depth_cm', 'wind_max_kmh'],
			['temp_max_c', 'wind_max_kmh', 'snow_depth_cm']
		]) {
			bedienung.reorderMetrics(order);
			speicherung.aenderungMelden();
		}

		await ctl.flush();

		assert.equal(puts().length, 1, 'Letzter gewinnt: eine Geste, ein PUT');
		const body = server.storedBody(PRESET_ID);
		assert.deepEqual(dc(body).active_metrics, ['temp_max_c', 'wind_max_kmh', 'snow_depth_cm']);
	});

	test('nach erfolgreichem Speichern wandert die Baseline: erneute Meldung ohne Änderung → kein zweiter PUT', async () => {
		const { ctl, speicherung, bedienung } = aufbau();

		bedienung.toggleOfficialAlerts();
		speicherung.aenderungMelden();
		await ctl.flush();
		assert.equal(puts().length, 1);

		speicherung.aenderungMelden();
		await ctl.flush();

		assert.equal(puts().length, 1, 'der bereits gespeicherte Stand darf nicht erneut gesendet werden');
		assert.equal(ctl.hasPending, false);
	});

	test('Reiter öffnen ohne Änderung → kein PUT, kein „Speichert…", savedAt unverändert', async () => {
		const { ctl, speicherung } = aufbau();
		const alterStempel = new Date('2026-09-01T10:00:00Z');
		(ctl as unknown as { savedAt: Date }).savedAt = alterStempel;

		speicherung.aenderungMelden();

		assert.equal(ctl.hasPending, false, 'ohne Unterschied zur Baseline darf nichts eingeplant werden');
		assert.notEqual(ctl.state, 'saving');
		await ctl.flush();
		assert.equal(puts().length, 0, 'kein PUT ohne inhaltliche Änderung');
		assert.equal(ctl.savedAt, alterStempel);
	});

	test('Tagesfenster hin und wieder zurück → kein PUT, Zustand idle', async () => {
		const { ctl, speicherung, bedienung } = aufbau();

		bedienung.setDayWindow(5, 20);
		speicherung.aenderungMelden();
		bedienung.setDayWindow(4, 19);
		speicherung.aenderungMelden();

		assert.equal(ctl.hasPending, false, 'der zurückgenommene Vorgang darf nicht mehr ausstehen');
		await ctl.flush();
		assert.equal(puts().length, 0, 'Hin-und-zurück ist keine Änderung — kein PUT');
		assert.equal(ctl.state, 'idle');
	});
});
