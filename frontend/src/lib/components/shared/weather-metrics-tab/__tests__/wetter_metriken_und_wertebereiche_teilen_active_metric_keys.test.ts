// TDD RED — Issue #2276 Scheibe S4 (Epic #2345), AC-4: `display_config.
// active_metrics` wird von ZWEI Reitern geschrieben — dem Wertebereiche-Reiter
// (S3, live aus `ws.activeMetricKeys`) UND der neuen Wetter-Metriken-
// Orchestrierung (S4). Das ist sicher, WEIL beide Schreiber den Wert LIVE zum
// Ausführungszeitpunkt lesen, nie aus einer beim Planen eingefrorenen Kopie —
// strukturell identisch zur bereits bekannten `metric_alert_levels`-
// Überschneidung (Alarme/Wertebereiche, S3).
//
// Spec: docs/specs/modules/rework_2276_s4_wetter_metriken.md — AC-4
// Kontext-Dokument Abschnitt 1.8 (E3-Pflicht-Prüfung).
//
// Zielschnittstelle: s. wetter_metriken_vergleich_speichert_einmal.test.ts
//
// Ausführen:
//   cd frontend && npm test -- src/lib/components/shared/weather-metrics-tab/__tests__/wetter_metriken_und_wertebereiche_teilen_active_metric_keys.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../../api.ts';
import { clearEtagRegistry } from '../../../../etagRegistry.ts';
import { createFakeTripServer, type FakeTripServer } from '../../../../__tests__/fakeTripServer.ts';
import type { ComparePreset } from '../../../../types.ts';
import { createPutQueue } from '../../../compare/compareHubPersistenz.ts';
import {
	erstelleWertebereicheVergleichSpeicherung,
	sichereSelbstSpeichererVorReiterwechsel
} from '../../corridor-editor/wertebereicheVergleichSpeicherung.ts';
import { erstelleWetterMetrikenVergleichSpeicherung } from '../weatherMetricsCompareSave.ts';
import { createController, dc, hydrierterWs, makePreset, wetterMetrikenBedienung } from './wetterMetrikenVergleichPruefstand.ts';

const PRESET_ID = 'cp-2276-s4-active-metrics';

let server: FakeTripServer;

beforeEach(() => {
	clearEtagRegistry();
	server = createFakeTripServer();
	server.install();
});

afterEach(() => server.restore());

const puts = () => server.calls.filter((c) => c.method === 'PUT');
const gespeichert = () => server.storedBody(PRESET_ID) as Record<string, unknown>;

/** EIN Hub-Wizard-Zustand mit BEIDEN Domänen: Wertebereiche (corridors/
 *  idealRanges/metricAlertLevels) und Wetter-Metriken/Layout. */
function hub() {
	let basis: ComparePreset = makePreset(PRESET_ID, {
		corridors: [{ metric: 'wind_max_kmh', range: [0, 40], notify: true, mark: true }],
		display_config: {
			ideal_ranges: { wind_max_kmh: { min: 0, max: 40 } },
			metric_alert_levels: { wind_max_kmh: 'standard' },
			active_metrics: ['wind_max_kmh', 'snow_depth_cm', 'temp_max_c'],
			channel_active_metrics: {},
			hourly_metrics: ['wind_max_kmh'],
			outlook_metrics: ['temp_max_c'],
			outlook_metric_formats: { temp_max_c: true }
		}
	});
	const ws = hydrierterWs(basis);
	ws.corridors = basis.corridors;
	ws.idealRanges = (basis.display_config as Record<string, unknown>).ideal_ranges;
	ws.metricAlertLevels = (basis.display_config as Record<string, unknown>).metric_alert_levels;
	const ctl = createController(PRESET_ID);
	const queue = createPutQueue();
	const gemeinsam = {
		client: api,
		preset: () => basis,
		enqueueHubWrite: <T>(fn: () => Promise<T>) => queue.enqueue(fn),
		onCompareUpdate: (p: ComparePreset) => {
			basis = p;
		},
		saveController: ctl
	};
	const wertebereiche = erstelleWertebereicheVergleichSpeicherung({ ...gemeinsam, zustand: ws });
	const wetterMetriken = erstelleWetterMetrikenVergleichSpeicherung({ ...gemeinsam, wiz: ws });
	return { ws, ctl, wertebereiche, wetterMetriken, bedienung: wetterMetrikenBedienung(ws) };
}

describe('AC-4: activeMetricKeys live gelesen — Wetter-Metriken-Änderung + Wertebereiche-Speicherung im selben Hub-Besuch', () => {
	test('Metrikauswahl ZUERST geändert, Wertebereiche-Reiter speichert ZULETZT → gespeicherter Stand trägt die AKTUELLE Auswahl', async () => {
		const { ws, ctl, wetterMetriken, wertebereiche, bedienung } = hub();

		bedienung.toggleMetric('gust_max_kmh');
		wetterMetriken.aenderungMelden();
		assert.equal(ctl.hasPending, true, 'Vorbedingung: Wetter-Metriken-Änderung wartet im Entprell-Fenster');

		await sichereSelbstSpeichererVorReiterwechsel('wetter-metriken', 'idealwerte', ctl);
		assert.equal(puts().length, 1, 'die Wetter-Metriken-Änderung muss VOR dem Reiterwechsel gesendet sein');
		assert.ok((dc(gespeichert()).active_metrics as string[]).includes('gust_max_kmh'));

		// Idealwerte-Reiter ändert einen Korridor — berührt activeMetricKeys NICHT.
		ws.corridors = [{ metric: 'wind_max_kmh', range: [0, 55], notify: true, mark: true }];
		wertebereiche.aenderungMelden();
		await ctl.flush();

		assert.equal(puts().length, 2);
		assert.ok(
			(dc(gespeichert()).active_metrics as string[]).includes('gust_max_kmh'),
			'der Wertebereiche-PUT darf die aktuelle Metrikauswahl nicht auf einen alten Stand zurücksetzen'
		);
	});

	test('Metrikauswahl geändert, aber NOCH NICHT gespeichert — Wertebereiche speichert → die neue Auswahl wird LIVE mitgenommen, nicht aus der eingefrorenen Preset-Basis', async () => {
		const { ws, ctl, wertebereiche, bedienung } = hub();

		bedienung.toggleMetric('gust_max_kmh');
		// KEIN wetterMetriken.aenderungMelden() hier — die Änderung steht nur im
		// Wizard-Zustand, noch nicht im Speicher-Takt des Controllers.
		ws.corridors = [{ metric: 'wind_max_kmh', range: [0, 55], notify: true, mark: true }];
		wertebereiche.aenderungMelden();
		await ctl.flush();

		assert.equal(puts().length, 1);
		assert.ok(
			(dc(gespeichert()).active_metrics as string[]).includes('gust_max_kmh'),
			'activeMetricKeys muss live aus dem Wizard-Zustand kommen, nicht aus einer eingefrorenen Preset-Kopie'
		);
	});

	test('Wetter-Metriken-SaveFn liest activeMetricKeys ERST bei Ausführung: eine Live-Änderung NACH aenderungMelden(), VOR dem Flush, landet trotzdem im PUT', async () => {
		const { ws, ctl, wetterMetriken, bedienung } = hub();

		bedienung.toggleMetric('gust_max_kmh');
		wetterMetriken.aenderungMelden();
		// Weitere Live-Mutation VOR dem Flush (z. B. durch eine zweite, schnelle Geste):
		ws.activeMetricKeys = [...(ws.activeMetricKeys as string[]), 'wind_direction_deg'];

		await ctl.flush();

		assert.equal(puts().length, 1);
		const aktiv = dc(gespeichert()).active_metrics as string[];
		assert.ok(aktiv.includes('gust_max_kmh'), 'erste Meldung muss ankommen');
		assert.ok(
			aktiv.includes('wind_direction_deg'),
			'die SaveFn muss activeMetricKeys ERST bei Ausführung lesen — sonst geht eine spätere Live-Änderung verloren'
		);
	});
});
