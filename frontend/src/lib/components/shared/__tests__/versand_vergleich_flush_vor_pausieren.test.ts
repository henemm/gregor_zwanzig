// TDD RED — Issue #2276 Scheibe S5 (Epic #2345), AC-7: ändert der Nutzer eine
// Versand-Einstellung und pausiert/aktiviert den Ortsvergleich sofort danach
// (Aktivierungs-Karte oder Header-Kebab, vor Ablauf der Entprellung), ist die
// Änderung im gespeicherten Stand enthalten — nicht überschrieben durch den
// Pausier-/Aktivier-PUT.
//
// Spec: docs/specs/modules/rework_2276_s5_versand.md — AC-7
//
// `CompareTabs.handleToggleActive()` ist in diesem Prüfstand nicht ausführbar
// (SSR, kein DOM). Nachgestellt wird deshalb GENAU seine Abfolge mit den
// echten Bausteinen: `await saveController.flush()` → Pausier-PUT über
// dieselbe Hub-Queue mit `buildToggleActivePutPayload`. Der Flush wirkt erst,
// seit der Versand-Reiter über `schedule()` speichert — heute bedient
// `handleVersandCommit` den Controller manuell, der generische Flush findet
// dort nichts zu senden. Prüfort ≠ Wirkort: dass `handleToggleActive` den
// Flush wirklich VOR dem PUT abwartet, misst
// frontend/e2e/compare-versand-speichert-selbst.spec.ts.
//
// Mutations-Gegenprobe (Spec AC-7): den generischen `saveController.flush()`
// in `handleToggleActive` entfernen ⇒ der Pausier-PUT trägt den alten Stand,
// die Versand-Änderung fällt hinten runter ⇒ rot.
//
// Ausführen:
//   cd frontend && npm test -- src/lib/components/shared/__tests__/versand_vergleich_flush_vor_pausieren.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../api.ts';
import { clearEtagRegistry } from '../../../etagRegistry.ts';
import { createFakeTripServer, type FakeTripServer } from '../../../__tests__/fakeTripServer.ts';
import type { ComparePreset } from '../../../types.ts';
import { buildToggleActivePutPayload, createPutQueue } from '../../compare/compareHubPersistenz.ts';
import { erstelleVersandVergleichSpeicherung } from '../versandVergleichSpeicherung.ts';
import { createController, hydrierterWiz, makePreset, versandBedienung } from './versandVergleichPruefstand.ts';

const PRESET_ID = 'cp-2276-s5-pause';

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
	const wiz = hydrierterWiz(currentPreset);
	const ctl = createController(PRESET_ID);
	const hubPutQueue = createPutQueue();
	const speicherung = erstelleVersandVergleichSpeicherung({
		client: api,
		zustand: wiz,
		preset: () => currentPreset,
		enqueueHubWrite: (fn) => hubPutQueue.enqueue(fn),
		onCompareUpdate: (p: ComparePreset) => {
			currentPreset = p;
		},
		saveController: ctl
	});
	/** Nachbau von CompareTabs.handleToggleActive(): erst flushen, dann PUT. */
	async function pausieren(): Promise<void> {
		await ctl.flush();
		ctl.setSaving();
		currentPreset = await hubPutQueue.enqueue(async () => {
			const { url, body } = buildToggleActivePutPayload(currentPreset, 'manual', 'daily');
			return api.put<ComparePreset>(url, body);
		});
		ctl.setSaved();
	}
	return { ctl, speicherung, bedienung: versandBedienung(wiz), pausieren };
}

describe('AC-7: Pausieren direkt nach einer Versand-Änderung verliert sie nicht', () => {
	test('Uhrzeit ändern, sofort pausieren → Versand-PUT zuerst, Pausier-PUT trägt die Änderung', async () => {
		const { ctl, speicherung, bedienung, pausieren } = hub();

		bedienung.setMorgenZeit('07:15');
		speicherung.aenderungMelden();
		assert.equal(ctl.hasPending, true, 'Vorbedingung: Änderung wartet im Entprell-Fenster');

		await pausieren();

		assert.equal(puts().length, 2, 'erst die Versand-Änderung, dann das Pausieren');
		const [erster, zweiter] = puts().map((p) => p.body as Record<string, unknown>);
		assert.equal(erster.morning_time, '07:15:00', 'erster PUT = Versand-Änderung');
		assert.equal(erster.schedule, 'daily', 'erster PUT darf noch nicht pausieren');
		assert.equal(zweiter.schedule, 'manual');
		assert.equal(
			zweiter.morning_time,
			'07:15:00',
			'der Pausier-PUT muss die bereits gespeicherte Uhrzeit übernehmen'
		);
		const stand = server.storedBody(PRESET_ID) as Record<string, unknown>;
		assert.equal(stand.schedule, 'manual');
		assert.equal(stand.morning_time, '07:15:00', 'die Versand-Änderung überlebt das Pausieren');
		assert.equal(ctl.hasPending, false, 'nach dem Pausieren darf nichts mehr ausstehen');
	});

	test('„Bis auf Weiteres", sofort pausieren → auch die Laufzeit-Änderung überlebt', async () => {
		const { speicherung, bedienung, pausieren } = hub();

		bedienung.bisAufWeiteres();
		speicherung.aenderungMelden();
		await pausieren();

		const stand = server.storedBody(PRESET_ID) as Record<string, unknown>;
		assert.equal(stand.end_date, '', 'die Enddatum-Löschung darf der Pausier-PUT nicht zurückdrehen');
		assert.equal(stand.schedule, 'manual');
	});
});
