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
import { createGoMergeServer, type GoMergeServer } from '../../__tests__/goMergeServerPruefstand.ts';
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

// Seit #2375 sendet der Pausier-PUT nur { schedule, previous_schedule } — dass die
// Wertebereich-Änderung überlebt, entscheidet der Server-Abgleich; darum der
// Ersatz-Server, der wie der Go-Handler zusammenführt und die ANFRAGE-Rümpfe mitschneidet.
let server: GoMergeServer;

beforeEach(() => {
	clearEtagRegistry();
	server = createGoMergeServer({ [PRESET_ID]: makePreset(PRESET_ID) as unknown as Record<string, unknown> });
	server.install();
});

afterEach(() => server.restore());

const puts = () => server.putRuempfe();

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
		const [erster, zweiter] = puts();
		assert.deepEqual(korridor(erster, 'snow_depth_cm')?.range, [80, 200], 'erster PUT = Wertebereich-Änderung');
		assert.ok(!('schedule' in erster), 'erster PUT darf den Zeitplan nicht senden (also auch nicht pausieren)');
		assert.deepEqual(
			zweiter,
			{ schedule: 'manual', previous_schedule: 'daily' },
			'der Pausier-PUT trägt keine Korridore — er kann den Korridor nicht zurückschreiben'
		);
		const stand = server.stand(PRESET_ID);
		assert.equal(stand.schedule, 'manual');
		assert.deepEqual(korridor(stand, 'snow_depth_cm')?.range, [80, 200]);
		assert.equal(ctl.hasPending, false, 'nach dem Pausieren darf nichts mehr ausstehen');
	});
});
