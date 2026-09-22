// TDD RED — Issue #2276 Scheibe S5 (Epic #2345), AC-6: ein Speicherkonflikt
// (412) beim Versand-Speichern im Ortsvergleich führt zu „Nochmal speichern"
// (Zustand `conflict`), das Wiederholen sendet die UNVERÄNDERTE Änderung und
// endet in „Gespeichert"; die geänderten Werte bleiben sichtbar (kein Rollback
// bei 412). Bei jedem ANDEREN Fehler wird dagegen zurückgerollt (Gegenprobe).
//
// Spec: docs/specs/modules/rework_2276_s5_versand.md — AC-6
//
// Heute zeigt dieser Pfad einen generischen Fehler: `handleVersandCommit`
// (CompareTabs.svelte:422-468) fängt den Fehler selbst ab und ruft
// `setError()` — der Controller sieht den 412 nie und kann deshalb kein
// „Nochmal speichern" anbieten. Die neue SaveFn wirft weiter.
//
// Grenze dieses Prüfstands: die Kennung `{typ:'vergleich', id}` entsteht in
// routes/compare/[id]/+page.svelte (nicht mountbar). Hier wird der Controller
// MIT Kennung gebaut; ob die Seite sie übergibt, ist nur gegen Staging messbar
// (frontend/e2e/compare-versand-speichert-selbst.spec.ts, echter 412).
//
// Mutations-Gegenprobe (Spec AC-6): Rollback auch bei 412 auslösen ⇒ die
// Werte springen zurück ⇒ rot.
//
// Ausführen:
//   cd frontend && npm test -- src/lib/components/shared/__tests__/versand_vergleich_konflikt_nochmal_speichern.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../api.ts';
import { clearEtagRegistry } from '../../../etagRegistry.ts';
import { createFakeTripServer, type FakeTripServer } from '../../../__tests__/fakeTripServer.ts';
import type { ComparePreset } from '../../../types.ts';
import { createPutQueue } from '../../compare/compareHubWizardBridge.ts';
import type { PutClient } from '../tripSpeicherung.ts';
import { erstelleVersandVergleichSpeicherung } from '../versandVergleichSpeicherung.ts';
import { createController, hydrierterWiz, makePreset, versandBedienung } from './versandVergleichPruefstand.ts';

const PRESET_ID = 'cp-2276-s5-konflikt';
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
	const wiz = hydrierterWiz(basis);
	const ctl = createController(PRESET_ID);
	const queue = createPutQueue();
	const speicherung = erstelleVersandVergleichSpeicherung({
		client,
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

describe('AC-6: Speicherkonflikt beim Versand-Speichern → „Nochmal speichern" → gespeichert', () => {
	test('412 → conflict (nicht error), Werte bleiben stehen; retryConflict sendet erneut → idle', async () => {
		// GIVEN: Seite geladen (Stand bekannt), danach ändert „ein anderes Gerät" den Vergleich
		await api.get(PRESET_PFAD);
		await server.handler(PRESET_PFAD, { method: 'PUT', body: JSON.stringify({ name: 'fremd' }) });
		const { wiz, ctl, speicherung, bedienung } = aufbau();

		// WHEN: Nutzer ändert die Morgen-Uhrzeit und schaltet den SMS-Kanal an
		bedienung.setMorgenZeit('07:15');
		bedienung.toggleSms();
		speicherung.aenderungMelden();
		await ctl.flush();

		// THEN (a): Konflikt, nicht generischer Fehler
		assert.equal(puts().at(-1)?.status, 412, 'Vorbedingung: der Server muss den veralteten Stand ablehnen');
		assert.equal(ctl.state, 'conflict', 'ein 412 muss „Nochmal speichern" auslösen, nicht einen generischen Fehler');
		assert.equal(wiz.morningTime, '07:15', 'bei 412 darf NICHT zurückgerollt werden — die Änderung bleibt sichtbar');
		assert.equal(wiz.sendSms, true, 'bei 412 darf NICHT zurückgerollt werden — die Änderung bleibt sichtbar');

		// WHEN: „Nochmal speichern"
		await ctl.retryConflict();

		// THEN (b)+(c)
		assert.equal(puts().at(-1)?.status, 200, 'der Wiederholungs-PUT muss durchgehen');
		const body = server.storedBody(PRESET_ID) as Record<string, unknown>;
		assert.equal(body.morning_time, '07:15:00', 'der Wiederholungs-PUT muss die geänderte Uhrzeit tragen');
		assert.equal(body.send_sms, true, 'der Wiederholungs-PUT muss den geänderten SMS-Kanal tragen');
		assert.equal(ctl.state, 'idle', 'Endzustand „Gespeichert"');
		assert.ok(ctl.savedAt instanceof Date);
		assert.equal(wiz.morningTime, '07:15', 'die Oberfläche springt nicht auf den alten Stand zurück');
	});

	test('Gegenprobe: ein Nicht-412-Fehler rollt die Versand-Änderung zurück und endet in error', async () => {
		const kaputt: PutClient = {
			put: async () => {
				throw Object.assign(new Error('Serverfehler'), { status: 500, detail: 'Serverfehler' });
			}
		};
		const { wiz, ctl, speicherung, bedienung } = aufbau(kaputt);

		bedienung.setMorgenZeit('07:15');
		speicherung.aenderungMelden();
		await ctl.flush();

		assert.equal(ctl.state, 'error', 'ein 500 ist kein Konflikt');
		assert.equal(wiz.morningTime, '06:30', 'bei einem Nicht-412-Fehler muss die Änderung zurückgerollt werden');
	});
});
