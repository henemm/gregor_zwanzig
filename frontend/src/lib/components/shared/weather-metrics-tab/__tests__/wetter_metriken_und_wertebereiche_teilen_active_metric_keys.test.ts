// TDD RED — Issue #2276 Scheibe S4 (Epic #2345), AC-4: `display_config.
// active_metrics` schreibt der Wertebereiche-Reiter (S3) live aus
// `ws.activeMetricKeys`. Das ist sicher, WEIL der Schreiber den Wert LIVE zum
// Ausführungszeitpunkt liest, nie aus einer beim Planen eingefrorenen Kopie —
// strukturell identisch zur bereits bekannten `metric_alert_levels`-
// Überschneidung (Alarme/Wertebereiche, S3).
//
// Issue #3389: die Fälle am toten Wetter-Metriken-Speicherer (Fälle 1 und 3)
// entfielen; der Fall am lebenden Wertebereiche-Speicherer bleibt.
//
// Spec: docs/specs/modules/rework_2276_s4_wetter_metriken.md — AC-4
// Kontext-Dokument Abschnitt 1.8 (E3-Pflicht-Prüfung).
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
import { erstelleWertebereicheVergleichSpeicherung } from '../../wetter-tab/wertebereicheVergleichSpeicherung.ts';
import { createController, hydrierterWs, makePreset } from '../../wetter-tab/__tests__/wertebereicheVergleichPruefstand.ts';

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

/** Hub-Wizard-Zustand mit der Wertebereiche-Domäne (corridors/idealRanges/metricAlertLevels/activeMetricKeys). */
function hub() {
	let basis: ComparePreset = makePreset(PRESET_ID, {
		corridors: [{ metric: 'wind_max_kmh', range: [0, 40], notify: true, mark: true }],
		display_config: {
			ideal_ranges: { wind_max_kmh: { min: 0, max: 40 } },
			metric_alert_levels: { wind_max_kmh: 'standard' },
			active_metrics: ['wind_max_kmh', 'snow_depth_cm', 'temp_max_c']
		}
	});
	const ws = hydrierterWs(basis);
	const ctl = createController(PRESET_ID);
	const queue = createPutQueue();
	const wertebereiche = erstelleWertebereicheVergleichSpeicherung({
		client: api,
		zustand: ws,
		preset: () => basis,
		enqueueHubWrite: <T>(fn: () => Promise<T>) => queue.enqueue(fn),
		onCompareUpdate: (p: ComparePreset) => {
			basis = p;
		},
		saveController: ctl
	});
	return { ws, ctl, wertebereiche };
}

describe('AC-4: activeMetricKeys live gelesen — Metrikauswahl-Änderung + Wertebereiche-Speicherung im selben Hub-Besuch', () => {
	test('Metrikauswahl geändert, aber NOCH NICHT gespeichert — Wertebereiche speichert → die neue Auswahl wird LIVE mitgenommen, nicht aus der eingefrorenen Preset-Basis', async () => {
		const { ws, ctl, wertebereiche } = hub();
		assert.ok(Array.isArray(ws.activeMetricKeys), 'Messaufbau: die Metrikauswahl ist hydriert');
		assert.equal((ws.activeMetricKeys as string[]).includes('gust_max_kmh'), false, 'Messaufbau: gust_max_kmh noch nicht gewählt');

		// Die Änderung steht nur im Wizard-Zustand, noch nicht im Speicher-Takt des Controllers.
		ws.activeMetricKeys = [...(ws.activeMetricKeys as string[]), 'gust_max_kmh'];
		ws.corridors = [{ metric: 'wind_max_kmh', range: [0, 55], notify: true, mark: true }];
		wertebereiche.aenderungMelden();
		await ctl.flush();

		assert.equal(puts().length, 1);
		const dc = (gespeichert().display_config as Record<string, unknown>) ?? {};
		assert.ok(
			(dc.active_metrics as string[]).includes('gust_max_kmh'),
			'activeMetricKeys muss live aus dem Wizard-Zustand kommen, nicht aus einer eingefrorenen Preset-Kopie'
		);
	});
});
