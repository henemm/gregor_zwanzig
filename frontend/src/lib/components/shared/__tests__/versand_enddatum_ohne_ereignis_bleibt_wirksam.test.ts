// TDD RED — Issue #2276 Scheibe S5 (Epic #2345), AC-5: „Bis auf Weiteres" im
// Laufzeit-Control (`VTLaufzeitVergleich`) löscht das Enddatum durch einen
// REINEN Button-Klick — ohne `change`, ohne garantiertes `focusout` (WebKit
// fokussiert Buttons nicht per Klick). Der bisherige Weg dafür war ein drittes
// Wrapper-Ereignis (`onclick` an `.hub-versand-wrap`, Fix-Loop 1 / F001). Mit
// dem Wrapper fällt dieser Auslöser weg; der Ersatz ist der reaktive
// `$effect`, der ALLE 10 Versandfelder beobachtet — `endDate` eingeschlossen.
//
// Spec: docs/specs/modules/rework_2276_s5_versand.md — AC-5, Design Punkt 1
//
// Auf Modulebene geprüft (wie AC-1): der Snapshot muss `endDate` führen, damit
// ein reiner Feldwechsel ohne begleitendes DOM-Ereignis als Diff erkannt wird
// und einen PUT auslöst. Prüfort ≠ Wirkort für die `$effect`-Verdrahtung
// selbst — die misst frontend/e2e/compare-versand-speichert-selbst.spec.ts.
//
// Mutations-Gegenprobe (Spec AC-5): `endDate` aus dem beobachteten Snapshot
// nehmen ⇒ kein Diff ⇒ kein PUT ⇒ rot.
//
// Ausführen:
//   cd frontend && npm test -- src/lib/components/shared/__tests__/versand_enddatum_ohne_ereignis_bleibt_wirksam.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../api.ts';
import { clearEtagRegistry } from '../../../etagRegistry.ts';
import { createFakeTripServer, type FakeTripServer } from '../../../__tests__/fakeTripServer.ts';
import type { ComparePreset } from '../../../types.ts';
import { createPutQueue } from '../../compare/compareHubPersistenz.ts';
import {
	erstelleVersandVergleichSpeicherung,
	versandSnapshotAus
} from '../versandVergleichSpeicherung.ts';
import { createController, hydrierterWiz, makePreset, versandBedienung } from './versandVergleichPruefstand.ts';

const PRESET_ID = 'cp-2276-s5-laufzeit';

let server: FakeTripServer;

beforeEach(() => {
	clearEtagRegistry();
	server = createFakeTripServer();
	server.install();
});

afterEach(() => server.restore());

const puts = () => server.calls.filter((c) => c.method === 'PUT');

function aufbau() {
	let basis = makePreset(PRESET_ID);
	const wiz = hydrierterWiz(basis);
	const ctl = createController(PRESET_ID);
	const queue = createPutQueue();
	const speicherung = erstelleVersandVergleichSpeicherung({
		client: api,
		zustand: wiz,
		preset: () => basis,
		enqueueHubWrite: (fn) => queue.enqueue(fn),
		onCompareUpdate: (p: ComparePreset) => {
			basis = p;
		},
		saveController: ctl
	});
	return { wiz, ctl, speicherung, bedienung: versandBedienung(wiz) };
}

describe('AC-5: „Bis auf Weiteres" wirkt ohne begleitendes DOM-Ereignis', () => {
	test('endDate → null (reiner Klick) → PUT mit dem Lösch-Sentinel end_date=""', async () => {
		const { ctl, speicherung, bedienung } = aufbau();

		bedienung.bisAufWeiteres(); // kein change, kein focusout — nur die Mutation
		speicherung.aenderungMelden();

		assert.equal(ctl.hasPending, true, 'der reine Feldwechsel muss als Änderung erkannt werden');
		await ctl.flush();

		assert.equal(puts().length, 1, 'die Enddatum-Löschung muss genau einen PUT auslösen');
		assert.equal(
			(server.storedBody(PRESET_ID) as Record<string, unknown>).end_date,
			'',
			'„Bis auf Weiteres" persistiert den Lösch-Sentinel end_date="" (#1232)'
		);
	});

	test('ein gesetztes Enddatum wird als YYYY-MM-DD gespeichert', async () => {
		const { ctl, speicherung, bedienung } = aufbau();

		bedienung.setEnddatum('2026-09-30');
		speicherung.aenderungMelden();
		await ctl.flush();

		assert.equal((server.storedBody(PRESET_ID) as Record<string, unknown>).end_date, '2026-09-30');
	});

	test('der Snapshot führt endDate — ein Wechsel allein erzeugt einen Unterschied', () => {
		const { wiz, bedienung } = aufbau();
		const vorher = versandSnapshotAus(wiz);
		bedienung.bisAufWeiteres();
		const nachher = versandSnapshotAus(wiz);

		assert.equal(vorher.endDate, '2026-08-01');
		assert.equal(nachher.endDate, null);
		assert.notEqual(
			JSON.stringify(vorher),
			JSON.stringify(nachher),
			'ohne endDate im Snapshot bliebe die Laufzeit-Änderung unsichtbar (Wrapper-onclick entfällt ersatzlos)'
		);
	});
});
