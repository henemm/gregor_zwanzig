// TDD RED — Issue #2276 Scheibe S3 (Epic #2345): der Wertebereiche-Reiter des
// Ortsvergleichs speichert über GENAU EINEN Weg — die eigene Orchestrierung im
// Speicher-Takt des Controllers der Seite, wie Alarme (S2) und die Tour. Der
// zweite Weg (Wrapper `.hub-corridor-wrap` + `<svelte:window onpointerup>` →
// alte Hub-Commit-Funktion) entfällt.
//
// Spec: docs/specs/modules/rework_2276_s3_wertebereiche.md
//   AC-1 (einmal speichern statt zweimal), AC-10 (Keepalive erreicht den PUT)
//
// WARUM AUF MODULEBENE (wie S2, s. alarme_vergleich_speichert_selbst.test.ts):
// `svelte/server` führt weder `$effect` noch Ereignisse aus — ein Mount von
// CorridorEditor mit PUT-Zählung ist in diesem Prüfstand nicht ausführbar.
// `maybeSchedule()` darf nach S3 im vergleich-Zweig nur noch DELEGIEREN
// (`syncToWizard()` → `vergleichSpeicherung.aenderungMelden()`); Diff-Gate,
// Basis-Lesen, Queue, Rückmeldung und Rollback liegen im Modul und werden hier
// geprüft. Prüfort ≠ Wirkort: dass Editor und CompareTabs das Modul wirklich
// (und nur so) verdrahten und der Wrapper-Weg weg ist, misst die E2E-Spec
// frontend/e2e/compare-wertebereiche-speichert-selbst.spec.ts.
//
// Zielschnittstelle (existiert noch NICHT → RED per ERR_MODULE_NOT_FOUND):
//
//   frontend/src/lib/components/shared/corridor-editor/wertebereicheVergleichSpeicherung.ts
//   erstelleWertebereicheVergleichSpeicherung({
//     client,            // PutClient (echtes `api`)
//     ws,                // Wizard-Zustand (corridors/idealRanges/activeMetricKeys/metricAlertLevels)
//     preset,            // () => ComparePreset — Basis, gelesen ERST bei Ausführung
//     enqueueHubWrite,   // hubPutQueue.enqueue
//     onCompareUpdate,   // (antwort: ComparePreset) => void
//     saveController     // SaveStatus der Seite
//   }): { aenderungMelden(): void }
//
// Ausführen:
//   cd frontend && npm test -- src/lib/components/shared/corridor-editor/__tests__/wertebereiche_vergleich_speichert_einmal.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../../api.ts';
import { clearEtagRegistry } from '../../../../etagRegistry.ts';
import { createFakeTripServer, type FakeTripServer } from '../../../../__tests__/fakeTripServer.ts';
import type { ComparePreset } from '../../../../types.ts';
import { createPutQueue } from '../../../compare/compareHubWizardBridge.ts';
import { erstelleWertebereicheVergleichSpeicherung } from '../wertebereicheVergleichSpeicherung.ts';
import {
	createController,
	hydrierterWs,
	korridor,
	makePreset,
	wertebereicheBedienung
} from './wertebereicheVergleichPruefstand.ts';

const PRESET_ID = 'cp-2276-s3-einmal';
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
	const speicherung = erstelleWertebereicheVergleichSpeicherung({
		client: api,
		ws,
		preset: () => basis,
		enqueueHubWrite: (fn) => queue.enqueue(fn),
		onCompareUpdate: (p: ComparePreset) => {
			rueckmeldungen.push(p);
			basis = p;
		},
		saveController: ctl
	});
	const bedienung = wertebereicheBedienung(ws);
	return { ws, ctl, speicherung, bedienung, rueckmeldungen };
}

describe('AC-1: eine Wertebereich-Änderung speichert im Takt des Controllers — genau EIN PUT', () => {
	test('Korridor-Grenze ändern → schedule, Flush → genau EIN PUT mit dem neuen Wert, „Gespeichert"', async () => {
		const { ctl, speicherung, bedienung, rueckmeldungen } = aufbau();

		bedienung.patch('wind_max_kmh', { max: 55 });
		speicherung.aenderungMelden();

		assert.equal(ctl.hasPending, true, 'die Änderung muss im Speicher-Takt des Controllers liegen (schedule)');
		assert.equal(ctl.state, 'saving', 'während des Debounce-Fensters darf nie „Gespeichert" stehen');
		assert.equal(puts().length, 0, 'vor Ablauf der Entprellung darf nichts sofort gesendet werden');

		await ctl.flush();

		assert.equal(puts().length, 1, 'genau EIN PUT erwartet');
		assert.equal(puts()[0].path, PRESET_PFAD, 'der PUT muss auf die Ortsvergleich-Ressource gehen');
		assert.equal(puts()[0].status, 200);
		const body = server.storedBody(PRESET_ID);
		assert.deepEqual(korridor(body, 'wind_max_kmh')?.range, [0, 55], 'der geänderte Korridor muss im Rumpf stehen');
		assert.equal(ctl.state, 'idle', 'Endzustand „Gespeichert"');
		assert.ok(ctl.savedAt instanceof Date, 'savedAt muss nach echtem Erfolg gestempelt sein');
		assert.equal(rueckmeldungen.length, 1, 'onCompareUpdate genau einmal mit der Server-Antwort');
	});

	test('Slider-Ziehen: viele Zwischenwerte derselben Geste → trotzdem nur EIN PUT mit dem Endwert', async () => {
		const { ctl, speicherung, bedienung } = aufbau();

		for (const max of [41, 44, 48, 52, 57, 60]) {
			bedienung.patch('wind_max_kmh', { max });
			speicherung.aenderungMelden();
		}
		bedienung.patch('snow_depth_cm', { mark: false });
		speicherung.aenderungMelden();

		await ctl.flush();

		assert.equal(puts().length, 1, 'Letzter gewinnt: eine Geste, ein PUT');
		const body = server.storedBody(PRESET_ID) as Record<string, unknown>;
		assert.deepEqual(korridor(body, 'wind_max_kmh')?.range, [0, 60]);
		assert.equal(
			(body.corridors as Array<{ metric: string; mark: boolean }>).find((c) => c.metric === 'snow_depth_cm')?.mark,
			false,
			'die zweite Änderung derselben Geste muss im EINEN PUT enthalten sein'
		);
	});

	test('nach erfolgreichem Speichern wandert die Baseline: erneute Meldung ohne Änderung → kein zweiter PUT', async () => {
		const { ctl, speicherung, bedienung } = aufbau();

		bedienung.patch('wind_max_kmh', { max: 55 });
		speicherung.aenderungMelden();
		await ctl.flush();
		assert.equal(puts().length, 1);

		// z. B. ein Fokusverlust/Loslassen nach der schon gespeicherten Geste
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

	test('Wert hin und wieder zurück → kein PUT, Zustand idle', async () => {
		const { ctl, speicherung, bedienung } = aufbau();

		bedienung.patch('wind_max_kmh', { max: 55 });
		speicherung.aenderungMelden();
		bedienung.patch('wind_max_kmh', { max: 40 });
		speicherung.aenderungMelden();

		assert.equal(ctl.hasPending, false, 'der zurückgenommene Vorgang darf nicht mehr ausstehen');
		await ctl.flush();
		assert.equal(puts().length, 0, 'Hin-und-zurück ist keine Änderung — kein PUT');
		assert.equal(ctl.state, 'idle');
	});
});

describe('AC-10: die Entlade-Option (keepalive) erreicht den Wertebereiche-PUT', () => {
	test('Flush beim Entladen → PUT mit keepalive:true', async () => {
		const { ctl, speicherung, bedienung } = aufbau();
		await api.get(PRESET_PFAD); // Stand bekannt, wie nach dem Laden der Seite

		bedienung.patch('snow_depth_cm', { min: 50 });
		speicherung.aenderungMelden();
		await ctl.flush({ keepalive: true });

		assert.equal(puts().length, 1, 'genau ein PUT erwartet');
		assert.equal(puts()[0].path, PRESET_PFAD);
		assert.equal(puts()[0].keepalive, true, 'die Option keepalive:true des Wächters wurde verschluckt');
		assert.deepEqual(korridor(server.storedBody(PRESET_ID), 'snow_depth_cm')?.range, [50, 200]);
	});

	test('Gegenprobe: regulärer Flush → PUT ohne keepalive', async () => {
		const { ctl, speicherung, bedienung } = aufbau();

		bedienung.patch('snow_depth_cm', { min: 50 });
		speicherung.aenderungMelden();
		await ctl.flush();

		assert.equal(puts().length, 1);
		assert.equal(puts()[0].keepalive, false, 'ohne Entladen darf kein keepalive gesetzt werden');
	});
});
