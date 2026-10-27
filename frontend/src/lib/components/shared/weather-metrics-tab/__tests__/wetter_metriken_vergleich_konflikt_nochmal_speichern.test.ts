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
import { createPutQueue } from '../../../compare/compareHubPersistenz.ts';
import type { PutClient } from '../../tripSpeicherung.ts';
import { erstelleWetterMetrikenVergleichSpeicherung } from '../weatherMetricsCompareSave.ts';
import { createController, dc, hydrierterWs, makePreset, wetterMetrikenBedienung } from './wetterMetrikenVergleichPruefstand.ts';
import { EIGENFELDER, schluessel } from '../../__tests__/goMergeServerPruefstand.ts';
import { konfliktMitFremdemNamen } from '../../__tests__/compareReiterAufbauPruefstand.ts';

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

// ── Issue #2375 (Test 6): „Nochmal speichern" sendet NUR die Eigenfelder ────
// Spec: docs/specs/bugfix/compare_konfliktschutz_teilfelder.md — Test 6, AC-2/AC-3/AC-7.
// Bis #2375 schickte der Wiederholungs-PUT den Voll-Spread der lokalen,
// veralteten Basis — der Name, den ein anderer Tab inzwischen gespeichert
// hatte, wurde still zurückgeschrieben. Der Ersatz-Server mergt hier wie Go
// (fehlende Felder bleiben), deshalb zeigt sich das am Server-Stand.
describe('Issue #2375: „Nochmal speichern" nach 412 — nur Eigenfelder, fremde Änderung überlebt', () => {
	test('Wiederholungs-PUT trägt exakt die Eigenfelder des Reiters (kein Fremdfeld)', async () => {
		const { erster, retryRumpf, zustandNach412, server } = await konfliktMitFremdemNamen('wetterMetriken', 'cp-2375-retry-wettermetriken');
		assert.ok(erster?.ifMatch, 'Vorbedingung: der erste PUT muss If-Match tragen');
		assert.equal(erster.status, 412, 'Vorbedingung: der erste PUT muss am veralteten Stand scheitern');
		assert.equal(zustandNach412, 'conflict', 'Vorbedingung: „Nochmal speichern" wird angeboten');
		assert.equal(server.mitschnitt.filter((e) => e.method === 'PUT').at(-1)?.status, 200);
		assert.deepEqual(
			schluessel(retryRumpf),
			[...EIGENFELDER.wetterMetriken.top].sort(),
			`der Wiederholungs-PUT darf nur Eigenfelder tragen, gesendet: ${JSON.stringify(schluessel(retryRumpf))}`
		);
		assert.deepEqual(
			schluessel(retryRumpf.display_config),
			[...(EIGENFELDER.wetterMetriken.display ?? [])].sort(),
			'display_config des Wiederholungs-PUT darf nur die eigenen Schlüssel tragen'
		);
	});

	test('Fremdfeld überlebt den Retry: danach stehen der Name von A UND die Änderung von B auf dem Server', async () => {
		const { server } = await konfliktMitFremdemNamen('wetterMetriken', 'cp-2375-retry-wettermetriken');
		const stand = server.stand('cp-2375-retry-wettermetriken');
		assert.ok(
			JSON.stringify((stand.display_config as Record<string, unknown>).active_metrics).includes('gust_max_kmh'),
			'die Wetter-Metriken-Änderung von B muss auf dem Server stehen'
		);
		assert.equal(stand.name, 'Fremd von A', '„Nochmal speichern" hat den fremd gespeicherten Namen überschrieben');
	});
});
