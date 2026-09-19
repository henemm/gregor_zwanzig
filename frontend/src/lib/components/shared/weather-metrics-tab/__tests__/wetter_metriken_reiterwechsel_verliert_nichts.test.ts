// TDD RED — Issue #2276 Scheibe S4 (Epic #2345), AC-6: ändert der Nutzer eine
// Wetter-Metriken-Einstellung und wechselt sofort, vor Ablauf der
// Debounce-Zeit, in den Alarme- oder Idealwerte-Reiter, wo er ebenfalls sofort
// eine Änderung vornimmt, müssen BEIDE Änderungen gespeichert werden. Der
// Ein-Slot-Speicher-Controller (`saveStatusStore.svelte.ts`, `_pendingFn`)
// erfordert, dass `'wetter-metriken'` in die Liste der Selbst-Speicherer
// aufgenommen wird — sonst überschreibt der zweite `schedule()`-Aufruf den
// ersten kommentarlos.
//
// Spec: docs/specs/modules/rework_2276_s4_wetter_metriken.md — AC-6
//
// Zielschnittstelle (NEU an bestehender S3-Konstante, existiert noch NICHT →
// RED): `SELBST_SPEICHERNDE_VERGLEICH_REITER` (wertebereicheVergleichSpeicherung.ts)
// enthält `'wetter-metriken'`.
//
// Ausführen:
//   cd frontend && npm test -- src/lib/components/shared/weather-metrics-tab/__tests__/wetter_metriken_reiterwechsel_verliert_nichts.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../../api.ts';
import { clearEtagRegistry } from '../../../../etagRegistry.ts';
import { createFakeTripServer, type FakeTripServer } from '../../../../__tests__/fakeTripServer.ts';
import type { ComparePreset } from '../../../../types.ts';
import { createPutQueue } from '../../../compare/compareHubWizardBridge.ts';
import {
	erstelleAlarmeVergleichSpeicherung
} from '../../alarmeVergleichSpeicherung.ts';
import {
	SELBST_SPEICHERNDE_VERGLEICH_REITER,
	sichereSelbstSpeichererVorReiterwechsel
} from '../../corridor-editor/wertebereicheVergleichSpeicherung.ts';
import { erstelleWetterMetrikenVergleichSpeicherung } from '../weatherMetricsCompareSave.ts';
import { createController, dc, hydrierterWs, makePreset, wetterMetrikenBedienung } from './wetterMetrikenVergleichPruefstand.ts';

const PRESET_ID = 'cp-2276-s4-reiterwechsel';

let server: FakeTripServer;

beforeEach(() => {
	clearEtagRegistry();
	server = createFakeTripServer({ latencyMs: 15 });
	server.install();
});

afterEach(() => server.restore());

const puts = () => server.calls.filter((c) => c.method === 'PUT');

describe('die Liste der Selbst-Speicherer enthält „wetter-metriken"', () => {
	test('SELBST_SPEICHERNDE_VERGLEICH_REITER.includes("wetter-metriken")', () => {
		assert.ok(
			SELBST_SPEICHERNDE_VERGLEICH_REITER.includes('wetter-metriken'),
			'„wetter-metriken" fehlt im Flush-Guard — ein Reiterwechsel verliert dann eine ausstehende Wetter-Metriken-Änderung'
		);
	});
});

function hub() {
	let basis: ComparePreset = makePreset(PRESET_ID);
	const ws = hydrierterWs(basis);
	ws.officialAlertsEnabled = basis.official_alerts_enabled;
	ws.officialWarningsEnabled = true;
	ws.radarAlertEnabled = false;
	ws.metricAlertLevels = {};
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
	const wetterMetriken = erstelleWetterMetrikenVergleichSpeicherung({ ...gemeinsam, wiz: ws });
	const alarme = erstelleAlarmeVergleichSpeicherung({ ...gemeinsam, wiz: ws });
	return { ws, ctl, wetterMetriken, alarme, bedienung: wetterMetrikenBedienung(ws) };
}

describe('AC-6: Reiterwechsel „wetter-metriken" → „alarme" im Entprell-Fenster verliert nichts', () => {
	test('Wetter-Metriken ändern, sofort zu „alarme", dort Radar an → BEIDE Änderungen gespeichert', async () => {
		const { ws, ctl, wetterMetriken, alarme, bedienung } = hub();

		bedienung.toggleMetric('gust_max_kmh');
		wetterMetriken.aenderungMelden();
		assert.equal(ctl.hasPending, true, 'Vorbedingung: Wetter-Metriken-Änderung wartet im Entprell-Fenster');

		await sichereSelbstSpeichererVorReiterwechsel('wetter-metriken', 'alarme', ctl);

		assert.equal(puts().length, 1, 'die Wetter-Metriken-Änderung muss VOR dem Reiterwechsel gesendet sein');
		assert.equal(puts()[0].status, 200);
		assert.ok((dc(puts()[0].body as unknown).active_metrics as string[]).includes('gust_max_kmh'));

		ws.radarAlertEnabled = true;
		alarme.aenderungMelden();
		await ctl.flush();

		assert.equal(puts().length, 2, 'zwei Reiter, zwei Änderungen, zwei PUTs');
		const stand = server.storedBody(PRESET_ID) as Record<string, unknown>;
		assert.ok(
			(dc(stand).active_metrics as string[]).includes('gust_max_kmh'),
			'die Wetter-Metriken-Änderung darf vom Alarm-Speichern nicht überschrieben werden'
		);
		assert.equal(stand.radar_alert_enabled, true);
		assert.equal(ctl.state, 'idle');
	});

	test('Gegenprobe (warum der Guard nötig ist): OHNE Flush verdrängt der Alarm-Vorgang den Wetter-Metriken-Vorgang vom einen Platz', async () => {
		const { ws, ctl, wetterMetriken, alarme, bedienung } = hub();

		bedienung.toggleMetric('gust_max_kmh');
		wetterMetriken.aenderungMelden();
		ws.radarAlertEnabled = true;
		alarme.aenderungMelden();
		await ctl.flush();

		assert.equal(puts().length, 1, 'der zweite schedule() überschreibt den ersten — nur ein PUT');
		assert.ok(
			!(dc(server.storedBody(PRESET_ID)).active_metrics as string[]).includes('gust_max_kmh'),
			'ohne Guard geht die Wetter-Metriken-Änderung verloren — genau das verhindert der Flush beim Wechsel'
		);
	});

	test('kein echter Wechsel (gleicher Reiter) → nichts wird vorzeitig gesendet', async () => {
		const { ctl, wetterMetriken, bedienung } = hub();
		bedienung.toggleMetric('gust_max_kmh');
		wetterMetriken.aenderungMelden();

		await sichereSelbstSpeichererVorReiterwechsel('wetter-metriken', 'wetter-metriken', ctl);

		assert.equal(puts().length, 0);
		assert.equal(ctl.hasPending, true);
		ctl.cancel();
	});
});
