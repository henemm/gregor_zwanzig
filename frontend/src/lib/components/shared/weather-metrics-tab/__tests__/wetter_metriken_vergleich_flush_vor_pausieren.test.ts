// TDD RED — Issue #2276 Scheibe S4 (Epic #2345), AC-8: ändert der Nutzer eine
// Wetter-Metriken/Layout-Einstellung und pausiert/aktiviert den Ortsvergleich
// sofort danach (vor Ablauf der Entprellung), ist die Änderung im
// gespeicherten Stand enthalten — nicht überschrieben durch den
// Pausier-/Aktivier-PUT.
//
// Spec: docs/specs/modules/rework_2276_s4_wetter_metriken.md — AC-8
//
// `CompareTabs.handleToggleActive()` ist in diesem Prüfstand nicht ausführbar
// (SSR, kein DOM). Nachgestellt wird deshalb GENAU seine Abfolge mit den
// echten Bausteinen: `await saveController.flush()` → Pausier-PUT über
// dieselbe Hub-Queue mit `buildToggleActivePutPayload`. Prüfort ≠ Wirkort:
// dass handleToggleActive den Flush wirklich VOR dem PUT abwartet, misst die
// E2E-Spec compare-wetter-metriken-speichert-selbst.spec.ts.
//
// Ausführen:
//   cd frontend && npm test -- src/lib/components/shared/weather-metrics-tab/__tests__/wetter_metriken_vergleich_flush_vor_pausieren.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../../api.ts';
import { clearEtagRegistry } from '../../../../etagRegistry.ts';
import { createFakeTripServer, type FakeTripServer } from '../../../../__tests__/fakeTripServer.ts';
import type { ComparePreset } from '../../../../types.ts';
import { buildToggleActivePutPayload, createPutQueue } from '../../../compare/compareHubPersistenz.ts';
import { erstelleWetterMetrikenVergleichSpeicherung } from '../weatherMetricsCompareSave.ts';
import { createController, dc, hydrierterWs, makePreset, wetterMetrikenBedienung } from './wetterMetrikenVergleichPruefstand.ts';

const PRESET_ID = 'cp-2276-s4-pause';

let server: FakeTripServer;

beforeEach(() => {
	clearEtagRegistry();
	server = createFakeTripServer({ latencyMs: 10 });
	server.install();
});

afterEach(() => server.restore());

const puts = () => server.calls.filter((c) => c.method === 'PUT');

function hub() {
	let currentPreset: ComparePreset = makePreset(PRESET_ID);
	const ws = hydrierterWs(currentPreset);
	const ctl = createController(PRESET_ID);
	const hubPutQueue = createPutQueue();
	const speicherung = erstelleWetterMetrikenVergleichSpeicherung({
		client: api,
		wiz: ws,
		preset: () => currentPreset,
		enqueueHubWrite: (fn) => hubPutQueue.enqueue(fn),
		onCompareUpdate: (p: ComparePreset) => {
			currentPreset = p;
		},
		saveController: ctl
	});
	/** Abfolge von CompareTabs.handleToggleActive() (Pausieren-Zweig). */
	async function pausieren(): Promise<void> {
		await ctl.flush();
		ctl.setSaving();
		currentPreset = await hubPutQueue.enqueue(async () => {
			const { url, body } = buildToggleActivePutPayload(currentPreset, 'manual', 'daily');
			return api.put<ComparePreset>(url, body);
		});
		ctl.setSaved();
	}
	return { ctl, speicherung, bedienung: wetterMetrikenBedienung(ws), pausieren };
}

describe('AC-8: Pausieren direkt nach einer Wetter-Metriken-Änderung verliert sie nicht', () => {
	test('Änderung im Entprell-Fenster, sofort pausieren → Wetter-Metriken-PUT zuerst, Pausier-PUT trägt die Änderung', async () => {
		const { ctl, speicherung, bedienung, pausieren } = hub();

		bedienung.toggleMetric('gust_max_kmh');
		speicherung.aenderungMelden();
		assert.equal(ctl.hasPending, true, 'Vorbedingung: Änderung wartet im Entprell-Fenster');

		await pausieren();

		assert.equal(puts().length, 2, 'erst die Wetter-Metriken-Änderung, dann das Pausieren');
		const [erster, zweiter] = puts().map((p) => p.body as Record<string, unknown>);
		assert.ok((dc(erster).active_metrics as string[]).includes('gust_max_kmh'), 'erster PUT = Wetter-Metriken-Änderung');
		assert.equal(erster.schedule, 'daily', 'erster PUT darf noch nicht pausieren');
		assert.equal(zweiter.schedule, 'manual');
		assert.ok(
			(dc(zweiter).active_metrics as string[]).includes('gust_max_kmh'),
			'der Pausier-PUT muss die bereits gespeicherte Metrikauswahl übernehmen'
		);
		const stand = server.storedBody(PRESET_ID) as Record<string, unknown>;
		assert.equal(stand.schedule, 'manual');
		assert.ok((dc(stand).active_metrics as string[]).includes('gust_max_kmh'));
		assert.equal(ctl.hasPending, false, 'nach dem Pausieren darf nichts mehr ausstehen');
	});
});
