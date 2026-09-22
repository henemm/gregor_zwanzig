// TDD RED — Issue #2276 Scheibe S5 (Epic #2345), AC-4: ändert der Nutzer eine
// Versand-Einstellung und wechselt sofort — vor Ablauf der Entprellung — in
// den Alarme- oder Idealwerte-Reiter, wo er ebenfalls sofort etwas ändert,
// sind BEIDE Änderungen gespeichert. Der Controller hat genau EINEN Platz für
// einen geplanten Speichervorgang (`_pendingFn`); ohne vorherigen Flush
// verdrängt die zweite Änderung die erste lautlos.
//
// Spec: docs/specs/modules/rework_2276_s5_versand.md — AC-4
//
// Der Guard ist listenbasiert: `sichereSelbstSpeichererVorReiterwechsel`
// (shared/corridor-editor/wertebereicheVergleichSpeicherung.ts) flusht nur,
// wenn der VERLASSENE Reiter in `SELBST_SPEICHERNDE_VERGLEICH_REITER` steht —
// 'versand' fehlt dort heute (RED).
//
// Mutations-Gegenprobe (Spec AC-4): `'versand'` nicht in die Liste aufnehmen
// ⇒ der Wechsel flusht nicht ⇒ der Alarm-Vorgang verdrängt die
// Versand-Änderung vom einen Platz ⇒ rot.
//
// Grenze: dass CompareTabs.handleValueChange den Helfer wirklich aufruft,
// prüft dieser Test nicht (Prüfort ≠ Wirkort) — das misst
// frontend/e2e/compare-versand-speichert-selbst.spec.ts im Browser.
//
// Ausführen:
//   cd frontend && npm test -- src/lib/components/shared/__tests__/versand_vergleich_reiterwechsel_verliert_nichts.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../api.ts';
import { clearEtagRegistry } from '../../../etagRegistry.ts';
import { createFakeTripServer, type FakeTripServer } from '../../../__tests__/fakeTripServer.ts';
import type { ComparePreset } from '../../../types.ts';
import { createPutQueue, hydrateAlarmFieldsFromPreset } from '../../compare/compareHubWizardBridge.ts';
import { erstelleAlarmeVergleichSpeicherung } from '../alarmeVergleichSpeicherung.ts';
import {
	SELBST_SPEICHERNDE_VERGLEICH_REITER,
	sichereSelbstSpeichererVorReiterwechsel
} from '../corridor-editor/wertebereicheVergleichSpeicherung.ts';
import { erstelleVersandVergleichSpeicherung } from '../versandVergleichSpeicherung.ts';
import { createController, hydrierterWiz, makePreset, versandBedienung } from './versandVergleichPruefstand.ts';

const PRESET_ID = 'cp-2276-s5-reiter';

let server: FakeTripServer;

beforeEach(() => {
	clearEtagRegistry();
	// Server-Laufzeit > 0: „vor dem Wechsel" heißt, der PUT ist ABGESCHLOSSEN,
	// wenn der Helfer zurückkehrt — nicht nur losgeschickt.
	server = createFakeTripServer({ latencyMs: 20 });
	server.install();
});

afterEach(() => server.restore());

const puts = () => server.calls.filter((c) => c.method === 'PUT');

/** EIN Wizard-Zustand, EIN Controller, EINE Queue — wie im Hub: beide Reiter
 *  teilen sich denselben Speicher-Platz des Controllers. */
function hub() {
	let basis = makePreset(PRESET_ID);
	const wiz = hydrierterWiz(basis);
	hydrateAlarmFieldsFromPreset(wiz, basis, []);
	const ctl = createController(PRESET_ID);
	const queue = createPutQueue();
	const gemeinsam = {
		client: api,
		wiz,
		preset: () => basis,
		enqueueHubWrite: <T>(fn: () => Promise<T>) => queue.enqueue(fn),
		onCompareUpdate: (p: ComparePreset) => {
			basis = p;
		},
		saveController: ctl
	};
	return {
		wiz,
		ctl,
		versand: erstelleVersandVergleichSpeicherung(gemeinsam),
		alarme: erstelleAlarmeVergleichSpeicherung({ ...gemeinsam, zustand: wiz }),
		bedienung: versandBedienung(wiz)
	};
}

describe('AC-4: Reiterwechsel weg von „versand" sendet die ausstehende Änderung vorher', () => {
	test('„versand" steht in der Liste der selbst speichernden Reiter', () => {
		assert.ok(
			SELBST_SPEICHERNDE_VERGLEICH_REITER.includes('versand'),
			'ohne den Eintrag flusht der Reiterwechsel-Guard den Versand-Reiter nicht — Datenverlust-Pfad'
		);
	});

	test('Versand-Änderung im Entprell-Fenster, Wechsel zu „alarme" mit sofortiger Radar-Änderung → BEIDE gespeichert', async () => {
		const { wiz, ctl, versand, alarme, bedienung } = hub();

		bedienung.setMorgenZeit('07:15');
		versand.aenderungMelden();
		assert.equal(ctl.hasPending, true, 'Vorbedingung: die Versand-Änderung wartet');
		assert.equal(puts().length, 0, 'Vorbedingung: noch nichts gesendet');

		await sichereSelbstSpeichererVorReiterwechsel('versand', 'alarme', ctl);

		assert.equal(puts().length, 1, 'die Versand-Änderung muss vor dem Reiterwechsel gesendet werden');
		assert.equal(puts()[0].status, 200, 'der PUT muss abgeschlossen sein, bevor der Wechsel weiterläuft');

		// Im Alarme-Reiter sofort Radar anschalten
		wiz.radarAlertEnabled = true;
		alarme.aenderungMelden();
		await ctl.flush();

		assert.equal(puts().length, 2, 'zwei unabhängige Änderungen → zwei PUTs');
		const stand = server.storedBody(PRESET_ID) as Record<string, unknown>;
		assert.equal(stand.morning_time, '07:15:00', 'die Versand-Änderung ging beim Reiterwechsel verloren');
		assert.equal(stand.radar_alert_enabled, true, 'die Alarm-Änderung muss ebenfalls gespeichert sein');
		assert.equal(ctl.state, 'idle');
	});

	test('Gegenprobe: „Wechsel" auf denselben Reiter → nichts wird vorzeitig gesendet', async () => {
		const { ctl, versand, bedienung } = hub();
		bedienung.setMorgenZeit('07:15');
		versand.aenderungMelden();

		await sichereSelbstSpeichererVorReiterwechsel('versand', 'versand', ctl);

		assert.equal(puts().length, 0, 'ohne echten Wechsel bleibt die Entprellung unangetastet');
		assert.equal(ctl.hasPending, true);
		ctl.cancel();
	});
});
