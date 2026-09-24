// TDD RED — Issue #2276 Scheibe S3 (Epic #2345), AC-6: ändert der Nutzer einen
// Wertebereich und pausiert/aktiviert den Ortsvergleich sofort danach (vor
// Ablauf der Entprellung), ist die Wertebereich-Änderung im gespeicherten Stand
// enthalten — nicht überschrieben durch den Pausier-/Aktivier-PUT.
//
// Spec: docs/specs/modules/rework_2276_s3_wertebereiche.md — AC-6
//
// `CompareTabs.handleToggleActive()` ist in diesem Prüfstand nicht ausführbar
// (SSR, kein DOM). Nachgestellt wird deshalb GENAU seine Abfolge mit den echten
// Bausteinen: `await saveController.flush()` (vorhanden seit S2) → Pausier-PUT
// über dieselbe Hub-Queue mit `buildToggleActivePutPayload(currentPreset, …)`,
// `currentPreset` = die über `onCompareUpdate` zurückgemeldete Basis. Geprüft
// wird, dass die Wertebereiche-Orchestrierung so in diesen Takt passt, dass der
// Pausier-PUT die Änderung trägt. Prüfort ≠ Wirkort: dass handleToggleActive
// den Flush wirklich VOR dem PUT abwartet, misst die E2E-Spec
// compare-wertebereiche-speichert-selbst.spec.ts (Mutation „flush entfernen").
//
// Ausführen:
//   cd frontend && npm test -- src/lib/components/shared/corridor-editor/__tests__/wertebereiche_vergleich_flush_vor_pausieren.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../../api.ts';
import { clearEtagRegistry } from '../../../../etagRegistry.ts';
import { createFakeTripServer, type FakeTripServer } from '../../../../__tests__/fakeTripServer.ts';
import type { ComparePreset } from '../../../../types.ts';
import { buildToggleActivePutPayload, createPutQueue } from '../../../compare/compareHubPersistenz.ts';
import { erstelleWertebereicheVergleichSpeicherung } from '../wertebereicheVergleichSpeicherung.ts';
import {
	createController,
	hydrierterWs,
	korridor,
	makePreset,
	wertebereicheBedienung
} from './wertebereicheVergleichPruefstand.ts';

const PRESET_ID = 'cp-2276-s3-pause';

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
	const speicherung = erstelleWertebereicheVergleichSpeicherung({
		client: api,
		zustand: ws,
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
	return { ctl, speicherung, bedienung: wertebereicheBedienung(ws), pausieren };
}

describe('AC-6: Pausieren direkt nach einer Wertebereich-Änderung verliert sie nicht', () => {
	test('Änderung im Entprell-Fenster, sofort pausieren → Wertebereich-PUT zuerst, Pausier-PUT trägt die Änderung', async () => {
		const { ctl, speicherung, bedienung, pausieren } = hub();

		bedienung.patch('snow_depth_cm', { min: 80 });
		speicherung.aenderungMelden();
		assert.equal(ctl.hasPending, true, 'Vorbedingung: Änderung wartet im Entprell-Fenster');

		await pausieren();

		assert.equal(puts().length, 2, 'erst die Wertebereich-Änderung, dann das Pausieren');
		const [erster, zweiter] = puts().map((p) => p.body as Record<string, unknown>);
		assert.deepEqual(korridor(erster, 'snow_depth_cm')?.range, [80, 200], 'erster PUT = Wertebereich-Änderung');
		assert.equal(erster.schedule, 'daily', 'erster PUT darf noch nicht pausieren');
		assert.equal(zweiter.schedule, 'manual');
		assert.deepEqual(
			korridor(zweiter, 'snow_depth_cm')?.range,
			[80, 200],
			'der Pausier-PUT schreibt den alten Korridor zurück'
		);
		const stand = server.storedBody(PRESET_ID) as Record<string, unknown>;
		assert.equal(stand.schedule, 'manual');
		assert.deepEqual(korridor(stand, 'snow_depth_cm')?.range, [80, 200]);
		assert.equal(ctl.hasPending, false, 'nach dem Pausieren darf nichts mehr ausstehen');
	});
});
