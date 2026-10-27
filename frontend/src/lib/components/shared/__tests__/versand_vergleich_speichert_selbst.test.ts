// TDD RED — Issue #2276 Scheibe S5 (Epic #2345), AC-1: der Versand-Reiter des
// Ortsvergleichs speichert SELBST über den Speicher-Controller der Seite
// (`schedule()` → `idle → saving → saved`), nicht mehr über den Wrapper-Div
// `.hub-versand-wrap` + `handleVersandCommit` in CompareTabs.svelte.
//
// Spec: docs/specs/modules/rework_2276_s5_versand.md — AC-1
//
// WARUM AUF MODULEBENE: `svelte/server` führt weder `$effect` noch Ereignisse
// aus, ein DOM gibt es in diesem Prüfstand nicht. Der `$effect` des
// Versand-Reiters darf deshalb nur noch DELEGIEREN: an
// `erstelleVersandVergleichSpeicherung(...).aenderungMelden()`. Diff-Gate,
// Basis-Lesen, Queue, Rückmeldung und Rollback liegen im Modul — genau dort
// werden sie hier geprüft. Dass das Markup keinen Wrapper-Div mehr trägt,
// prüft compare/__tests__/versand_panel_ohne_wrapper_div.test.ts; dass die
// Verdrahtung im Browser greift, die E2E-Spec
// compare-versand-speichert-selbst.spec.ts.
//
// Zielschnittstelle (existiert noch NICHT → RED per ERR_MODULE_NOT_FOUND):
//
//   frontend/src/lib/components/shared/versandVergleichSpeicherung.ts
//   erstelleVersandVergleichSpeicherung({
//     client,            // PutClient (echtes `api`)
//     wiz,               // Wizard-Zustand (Versandfelder, bei Nicht-412 zurückgerollt)
//     preset,            // () => ComparePreset — Basis, gelesen ERST bei Ausführung
//     enqueueHubWrite,   // hubPutQueue.enqueue — Serialisierung mit den Nachbar-Reitern
//     onCompareUpdate,   // (antwort: ComparePreset) => void — Basis-Rückmeldung
//     saveController     // SaveStatus der Seite
//   }): { aenderungMelden(): void }
//
//   Anfangs-Baseline = Versandstand von `wiz` beim Erzeugen (nach der
//   Hydration). `aenderungMelden()` vergleicht den aktuellen Stand damit:
//   ohne Unterschied → kein schedule(), ein eigener ausstehender Vorgang wird
//   verworfen (cancel + markPristine); mit Unterschied → schedule(SaveFn).
//
// Mutations-Gegenprobe (Spec AC-1): `aenderungMelden()` durch einen No-Op
// ersetzen ⇒ kein PUT, kein Zustandswechsel ⇒ rot.
//
// Ausführen:
//   cd frontend && npm test -- src/lib/components/shared/__tests__/versand_vergleich_speichert_selbst.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../api.ts';
import { clearEtagRegistry } from '../../../etagRegistry.ts';
import { createFakeTripServer, type FakeTripServer } from '../../../__tests__/fakeTripServer.ts';
import type { ComparePreset } from '../../../types.ts';
import { createPutQueue } from '../../compare/compareHubPersistenz.ts';
import { erstelleVersandVergleichSpeicherung } from '../versandVergleichSpeicherung.ts';
import { createController, hydrierterWiz, makePreset, versandBedienung } from './versandVergleichPruefstand.ts';

const PRESET_ID = 'cp-2276-s5';
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
	const wiz = hydrierterWiz(basis);
	const ctl = createController(PRESET_ID);
	const queue = createPutQueue();
	const rueckmeldungen: ComparePreset[] = [];
	const speicherung = erstelleVersandVergleichSpeicherung({
		client: api,
		zustand: wiz,
		preset: () => basis,
		enqueueHubWrite: (fn) => queue.enqueue(fn),
		onCompareUpdate: (p: ComparePreset) => {
			rueckmeldungen.push(p);
			basis = p;
		},
		saveController: ctl
	});
	return { wiz, ctl, speicherung, rueckmeldungen, bedienung: versandBedienung(wiz), basis: () => basis };
}

describe('AC-1: eine Versand-Änderung speichert über den Controller — genau ein PUT, Endzustand gespeichert', () => {
	test('Telegram-Schalter umlegen → schedule, Flush → EIN PUT mit dem neuen Wert, state idle, savedAt gesetzt', async () => {
		const { ctl, speicherung, bedienung, rueckmeldungen } = aufbau();

		bedienung.toggleTelegram();
		speicherung.aenderungMelden();

		assert.equal(ctl.hasPending, true, 'die Änderung muss über schedule() im Speicher-Platz des Controllers liegen');
		assert.equal(ctl.state, 'saving', 'der Controller muss beim Planen in „Speichern…" wechseln');
		assert.equal(puts().length, 0, 'vor dem Flush darf noch nichts gesendet sein (Entprellung)');

		await ctl.flush();

		assert.equal(puts().length, 1, 'genau EIN PUT für eine Versand-Änderung');
		assert.equal(puts()[0].path, PRESET_PFAD);
		assert.equal(
			(server.storedBody(PRESET_ID) as Record<string, unknown>).send_telegram,
			false,
			'der gespeicherte Stand muss den umgelegten Kanal-Schalter tragen'
		);
		assert.equal(ctl.state, 'idle', 'Endzustand „Gespeichert"');
		assert.ok(ctl.savedAt instanceof Date, 'savedAt muss gesetzt sein');
		assert.equal(rueckmeldungen.length, 1, 'die aktualisierte Basis muss über onCompareUpdate zurückfließen');
		assert.equal(rueckmeldungen[0].send_telegram, false);
	});

	test('Morgen-Uhrzeit ändern → PUT trägt HH:MM:SS, die übrigen Versandfelder unverändert', async () => {
		const { ctl, speicherung, bedienung } = aufbau();

		bedienung.setMorgenZeit('07:15');
		speicherung.aenderungMelden();
		await ctl.flush();

		const stand = server.storedBody(PRESET_ID) as Record<string, unknown>;
		assert.equal(stand.morning_time, '07:15:00', 'die Uhrzeit muss als HH:MM:SS persistiert werden');
		assert.equal(stand.evening_time, '18:00:00', 'die Abendzeit darf sich nicht mitverändern');
		assert.equal(stand.send_telegram, true, 'der Kanal-Schalter darf sich nicht mitverändern');
	});

	test('zwei Änderungen im selben Entprell-Fenster → EIN PUT mit beiden Werten', async () => {
		const { ctl, speicherung, bedienung } = aufbau();

		bedienung.setMorgenZeit('07:15');
		speicherung.aenderungMelden();
		bedienung.toggleSms();
		speicherung.aenderungMelden();
		await ctl.flush();

		assert.equal(puts().length, 1, 'zwei Gesten im Entprell-Fenster dürfen nur EINEN PUT auslösen');
		const stand = server.storedBody(PRESET_ID) as Record<string, unknown>;
		assert.equal(stand.morning_time, '07:15:00');
		assert.equal(stand.send_sms, true);
	});

	test('Rücknahme auf den Ausgangswert vor dem Flush → gar kein PUT, kein „Gespeichert"-Stempel', async () => {
		const { ctl, speicherung, bedienung } = aufbau();

		bedienung.toggleSms();
		speicherung.aenderungMelden();
		assert.equal(ctl.hasPending, true, 'Vorbedingung: die Änderung wartet');
		bedienung.toggleSms(); // zurück auf den Ausgangswert
		speicherung.aenderungMelden();

		assert.equal(ctl.hasPending, false, 'ein eigener ausstehender Vorgang ohne Unterschied muss verworfen werden');
		await ctl.flush();
		assert.equal(puts().length, 0, 'ohne Unterschied zur Basis darf kein PUT entstehen');
		assert.equal(ctl.savedAt, null, 'ein No-Op darf kein „Gespeichert" stempeln');
	});

	test('ohne Änderung meldet der reaktive Effect ins Leere → kein PUT, Controller bleibt unberührt', async () => {
		const { ctl, speicherung } = aufbau();

		speicherung.aenderungMelden();

		assert.equal(ctl.hasPending, false);
		assert.equal(ctl.state, 'idle');
		await ctl.flush();
		assert.equal(puts().length, 0);
	});
});
