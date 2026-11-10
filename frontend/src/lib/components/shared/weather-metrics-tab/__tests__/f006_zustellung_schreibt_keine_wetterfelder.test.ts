// Fix-Loop 1 Issue #2794 S3a Teil-PR 3, Adversary-Finding F006 (AC-38 woertlich):
// Der Zustellungs-Speicherer des Ortsvergleichs (WeatherMetricsTab, bereich="zustellung",
// `erstelleWetterMetrikenVergleichSpeicherung` → `baueWetterMetrikenNutzlast`) schreibt
// KEINES der Felder des Reiters Wetter mehr: `active_metrics`, `ampel`,
// `official_alerts_enabled`, `official_warnings`, `radar_alert_enabled`, `day_window_*`.
// Allein der WetterTab-Speicherer (wetterTabSpeicherung.ts) besitzt sie.
//
// Gemessen am gesendeten Rumpf (echter Speicherer, echte Hub-Schlange, echter Controller,
// echtes `api` gegen den Go-Merge-Pruefserver) — eine Wetter-Feld-Aenderung in der
// Kopie des Zustellungs-Reiters (z. B. nach der Neu-Hydration aus der WetterTab-Antwort)
// loest dort keinen PUT aus, und eine Zustellungs-Geste traegt die Wetter-Felder nicht mit.
//
//   cd frontend && npm test -- src/lib/components/shared/weather-metrics-tab/__tests__/f006_zustellung_schreibt_keine_wetterfelder.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../../api.ts';
import { clearEtagRegistry } from '../../../../etagRegistry.ts';
import { createGoMergeServer, type GoMergeServer } from '../../__tests__/goMergeServerPruefstand.ts';
import type { ComparePreset } from '../../../../types.ts';
import { createPutQueue } from '../../../compare/compareHubPersistenz.ts';
import {
	baueWetterMetrikenNutzlast,
	erstelleWetterMetrikenVergleichSpeicherung,
	wetterMetrikenSnapshotAus
} from '../weatherMetricsCompareSave.ts';
import { createController, hydrierterWs, makePreset, wetterMetrikenBedienung } from './wetterMetrikenVergleichPruefstand.ts';

const ID = 'cp-2794-f006';
const WETTER_TOP = ['official_alerts_enabled', 'official_warnings', 'radar_alert_enabled', 'day_window_start_hour', 'day_window_end_hour'];
const WETTER_DC = ['active_metrics', 'ampel'];

function preset(): ComparePreset {
	const p = makePreset(ID);
	(p.display_config as Record<string, unknown>).ampel = { template: 'wandern', metrics: { gust: { alarm_ab: 'red' } } };
	return p;
}

function keineWetterFelder(body: unknown, wo: string): void {
	const b = body as Record<string, unknown>;
	for (const k of WETTER_TOP) assert.ok(!(k in b), `${wo}: Zustellung schreibt Wetter-Feld ${k}`);
	const dc = (b.display_config as Record<string, unknown>) ?? {};
	for (const k of WETTER_DC) assert.ok(!(k in dc), `${wo}: Zustellung schreibt display_config.${k}`);
}

describe('F006/AC-38: Nutzlast des Zustellungs-Speicherers ohne Felder des Reiters Wetter', () => {
	const gesten: Array<[string, (ws: Record<string, unknown>) => void]> = [
		['Stundenverlauf-Reihenfolge', (ws) => wetterMetrikenBedienung(ws).hourlyDragEnd(['temp_max_c', 'wind_max_kmh'])],
		['Kanal-Auswahl', (ws) => (ws.channelActiveMetricKeys = { email: ['wind_max_kmh'], telegram: null, sms: null })],
		['Metrik-Auswahl in der Kopie', (ws) => wetterMetrikenBedienung(ws).toggleMetric('gust_max_kmh')],
		['Tagesfenster in der Kopie', (ws) => wetterMetrikenBedienung(ws).setDayWindow(6, 21)],
		['Amtliche Warnungen in der Kopie', (ws) => wetterMetrikenBedienung(ws).toggleOfficialAlerts()]
	];
	for (const [was, geste] of gesten) {
		test(`${was}: baueWetterMetrikenNutzlast traegt kein Wetter-Feld`, () => {
			const p = preset();
			const ws = hydrierterWs(p);
			geste(ws);
			keineWetterFelder(baueWetterMetrikenNutzlast(p, wetterMetrikenSnapshotAus(ws)).body, was);
		});
	}
});

describe('F006/AC-38: echter Speicherweg (Hub-Schlange, Go-Merge-Server)', () => {
	let server: GoMergeServer;
	beforeEach(() => {
		clearEtagRegistry();
		server = createGoMergeServer({ [ID]: preset() as unknown as Record<string, unknown> });
		server.install();
	});
	afterEach(() => server.restore());

	function reiter() {
		let basis = preset();
		const ws = hydrierterWs(basis);
		const ctl = createController(ID);
		const queue = createPutQueue();
		const sp = erstelleWetterMetrikenVergleichSpeicherung({
			client: api,
			zustand: ws,
			preset: () => basis,
			enqueueHubWrite: (fn) => queue.enqueue(fn),
			onCompareUpdate: (p: ComparePreset) => {
				basis = p;
			},
			saveController: ctl
		});
		return { ws, ctl, sp };
	}

	test('nur Wetter-Felder in der Kopie geaendert ⇒ KEIN PUT des Zustellungs-Speicherers', async () => {
		const { ws, ctl, sp } = reiter();
		wetterMetrikenBedienung(ws).toggleMetric('gust_max_kmh');
		wetterMetrikenBedienung(ws).setDayWindow(6, 21);
		wetterMetrikenBedienung(ws).toggleOfficialAlerts();
		sp.aenderungMelden();
		await ctl.flush();
		assert.deepEqual(server.putRuempfe(), [], 'der Zustellungs-Speicherer schreibt Felder des Reiters Wetter');
	});

	test('Zustellungs-Geste nach Wetter-Abweichung in der Kopie: ein PUT, ohne Wetter-Felder; Server-Stand der Wetter-Felder unveraendert', async () => {
		const { ws, ctl, sp } = reiter();
		const vorher = server.stand(ID);
		wetterMetrikenBedienung(ws).toggleMetric('gust_max_kmh');
		wetterMetrikenBedienung(ws).setDayWindow(6, 21);
		wetterMetrikenBedienung(ws).hourlyDragEnd(['temp_max_c', 'wind_max_kmh']);
		sp.aenderungMelden();
		await ctl.flush();
		const puts = server.putRuempfe();
		assert.equal(puts.length, 1);
		keineWetterFelder(puts[0], 'PUT');
		const nachher = server.stand(ID);
		for (const k of WETTER_TOP) assert.deepEqual(nachher[k], vorher[k], `${k} veraendert`);
		const dcV = vorher.display_config as Record<string, unknown>;
		const dcN = nachher.display_config as Record<string, unknown>;
		for (const k of WETTER_DC) assert.deepEqual(dcN[k], dcV[k], `display_config.${k} veraendert`);
		assert.deepEqual(dcN.hourly_metrics, ['temp_max_c', 'wind_max_kmh'], 'die Zustellungs-Geste selbst wurde nicht gespeichert');
	});
});
