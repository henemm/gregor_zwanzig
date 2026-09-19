// TDD RED — Issue #2276 Scheibe S4 (Epic #2345), AC-7: scheitert ein
// Wetter-Metriken/Layout-Speichervorgang mit einem Speicherkonflikt (412),
// zeigt der Ortsvergleich „Nochmal speichern" (Controller-Zustand `conflict`)
// statt eines generischen Fehlers; „Nochmal speichern" sendet die Änderung
// erneut, endet in „Gespeichert", der geänderte Stand bleibt sichtbar (kein
// Rollback bei 412 — Design-Entscheidung 7).
//
// Spec: docs/specs/modules/rework_2276_s4_wetter_metriken.md — AC-7
// Nachweisschicht: Kern (hier) + E2E (compare-wetter-metriken-speichert-selbst.spec.ts).
//
// Ausführen:
//   cd frontend && npm test -- src/lib/components/shared/weather-metrics-tab/__tests__/wetter_metriken_vergleich_konflikt_nochmal_speichern.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../../api.ts';
import { clearEtagRegistry } from '../../../../etagRegistry.ts';
import { createFakeTripServer, type FakeTripServer } from '../../../../__tests__/fakeTripServer.ts';
import type { ComparePreset } from '../../../../types.ts';
import { createPutQueue } from '../../../compare/compareHubWizardBridge.ts';
import type { PutClient } from '../../tripSpeicherung.ts';
import { erstelleWetterMetrikenVergleichSpeicherung } from '../weatherMetricsCompareSave.ts';
import { createController, dc, hydrierterWs, makePreset, wetterMetrikenBedienung } from './wetterMetrikenVergleichPruefstand.ts';

const PRESET_ID = 'cp-2276-s4-konflikt';
const PRESET_PFAD = `/api/compare/presets/${PRESET_ID}`;

let server: FakeTripServer;

beforeEach(() => {
	clearEtagRegistry();
	server = createFakeTripServer();
	server.install();
});

afterEach(() => server.restore());

const puts = () => server.calls.filter((c) => c.method === 'PUT');

function aufbau(client: PutClient = api) {
	let basis = makePreset(PRESET_ID);
	const ws = hydrierterWs(basis);
	const ctl = createController(PRESET_ID);
	const queue = createPutQueue();
	const speicherung = erstelleWetterMetrikenVergleichSpeicherung({
		client,
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

describe('AC-7: Speicherkonflikt beim Wetter-Metriken-Speichern → „Nochmal speichern" → gespeichert', () => {
	test('412 → conflict (nicht error), Wert bleibt stehen; retryConflict sendet erneut → idle, Wert bleibt', async () => {
		await api.get(PRESET_PFAD);
		await server.handler(PRESET_PFAD, { method: 'PUT', body: JSON.stringify({ name: 'fremd' }) });
		const { ws, ctl, speicherung, bedienung } = aufbau();

		bedienung.toggleMetric('gust_max_kmh');
		speicherung.aenderungMelden();
		await ctl.flush();

		assert.equal(puts().at(-1)?.status, 412, 'Vorbedingung: der Server muss den veralteten Stand ablehnen');
		assert.equal(ctl.state, 'conflict', 'ein 412 muss „Nochmal speichern" auslösen, nicht einen generischen Fehler');
		assert.ok(
			(ws.activeMetricKeys as string[]).includes('gust_max_kmh'),
			'bei 412 darf NICHT zurückgerollt werden — die Änderung bleibt sichtbar'
		);

		await ctl.retryConflict();

		const letzter = puts().at(-1)!;
		assert.equal(letzter.status, 200, 'der Wiederholungs-PUT muss durchgehen');
		assert.ok((dc(server.storedBody(PRESET_ID)).active_metrics as string[]).includes('gust_max_kmh'));
		assert.equal(ctl.state, 'idle', 'Endzustand „Gespeichert"');
		assert.ok(ctl.savedAt instanceof Date);
	});

	test('Gegenprobe: ein Nicht-412-Fehler rollt die Änderung zurück und endet in error', async () => {
		const kaputt: PutClient = {
			put: async () => {
				throw Object.assign(new Error('Serverfehler'), { status: 500, detail: 'Serverfehler' });
			}
		};
		const { ws, ctl, speicherung, bedienung } = aufbau(kaputt);

		bedienung.toggleMetric('gust_max_kmh');
		speicherung.aenderungMelden();
		await ctl.flush();

		assert.equal(ctl.state, 'error', 'ein 500 ist kein Konflikt');
		assert.ok(
			!(ws.activeMetricKeys as string[]).includes('gust_max_kmh'),
			'bei einem Nicht-412-Fehler muss die Änderung zurückgerollt werden'
		);
	});

	test('Konflikt beim Stundenverlauf (Layout-Domäne) verhält sich identisch — kein zweiter, abweichender Fehlerpfad', async () => {
		await api.get(PRESET_PFAD);
		await server.handler(PRESET_PFAD, { method: 'PUT', body: JSON.stringify({ name: 'fremd2' }) });
		const { ws, ctl, speicherung, bedienung } = aufbau();

		bedienung.hourlyDragEnd(['temp_max_c', 'gust_max_kmh']);
		speicherung.aenderungMelden();
		await ctl.flush();

		assert.equal(ctl.state, 'conflict');
		assert.deepEqual(ws.hourlyMetricKeys, ['temp_max_c', 'gust_max_kmh'], 'kein Rollback bei 412');

		await ctl.retryConflict();
		assert.equal(ctl.state, 'idle');
		assert.deepEqual(dc(server.storedBody(PRESET_ID)).hourly_metrics, ['temp_max_c', 'gust_max_kmh']);
	});
});
