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
// (shared/wetter-tab/wertebereicheVergleichSpeicherung.ts) flusht nur,
// wenn der VERLASSENE Reiter in `SELBST_SPEICHERNDE_VERGLEICH_REITER` steht —
// 'versand' fehlt dort heute (RED).
//
// Mutations-Gegenprobe (Spec AC-4): `'versand'` nicht in die Liste aufnehmen
// ⇒ der Wechsel flusht nicht ⇒ der Alarm-Vorgang verdrängt die
// Versand-Änderung vom einen Platz ⇒ rot.
//
// Grenze: dass CompareTabs.handleValueChange den Helfer wirklich aufruft,
// prüft dieser Test nicht (Prüfort ≠ Wirkort) — das misst
// frontend/e2e/hub-versand-speichert-selbst.spec.ts (VS-1, #2347 S3b) im Browser.
//
// #1743 (Spec feat_1743_reiter_aufraeumen §10, AC-26): der Reiter „versand" entfällt; der
// Versand-Abschnitt liegt im Reiter „wetter-metriken". Der Guard flusht deshalb beim Verlassen
// von „wetter-metriken" (beide Besitzer); 'versand' gehört nicht mehr in die Liste.
//
// Ausführen:
//   cd frontend && npm test -- src/lib/components/shared/__tests__/versand_vergleich_reiterwechsel_verliert_nichts.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../api.ts';
import { clearEtagRegistry } from '../../../etagRegistry.ts';
import { createGoMergeServer, type GoMergeServer } from './goMergeServerPruefstand.ts';
import type { ComparePreset } from '../../../types.ts';
import { createPutQueue } from '../../compare/compareHubPersistenz.ts';
import { hydrateAlarmFieldsFromPreset } from '../../compare/compareHubHydration.ts';
import { erstelleAlarmeVergleichSpeicherung } from '../alarmeVergleichSpeicherung.ts';
import {
	SELBST_SPEICHERNDE_VERGLEICH_REITER,
	sichereSelbstSpeichererVorReiterwechsel
} from '../wetter-tab/wertebereicheVergleichSpeicherung.ts';
import { erstelleVersandVergleichSpeicherung } from '../versandVergleichSpeicherung.ts';
import { createController, hydrierterWiz, makePreset, versandBedienung } from './versandVergleichPruefstand.ts';

const PRESET_ID = 'cp-2276-s5-reiter';

// Seit #2375 sendet jeder Reiter nur seine Eigenfelder — dass BEIDE Änderungen
// auf dem Server stehen, entscheidet der Server-Abgleich; darum der Ersatz-Server,
// der wie der Go-Handler zusammenführt (der fakeTripServer ersetzt den Rumpf komplett).
let server: GoMergeServer;

beforeEach(() => {
	clearEtagRegistry();
	server = createGoMergeServer({ [PRESET_ID]: makePreset(PRESET_ID) as unknown as Record<string, unknown> });
	server.install();
});

afterEach(() => server.restore());

const puts = () =>
	server.mitschnitt.filter((e) => e.method === 'PUT').map((e) => ({ status: e.status, body: e.anfrage }));

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
		zustand: wiz,
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

// Issue #2794 S3a (Spec feat_2794_s3a_teil2_leiste.md AC-2): der Versand-Abschnitt liegt im Reiter
// „zustellung" (zusammen mit den Alarmen). Der Guard flusht beim Verlassen von „zustellung"; die
// Alarm-Aenderung danach kommt ebenfalls an (zwei unabhaengige Aenderungen, zwei PUTs).
describe('AC-4 (#1743/#2794): Reiterwechsel weg von „zustellung" sendet die ausstehende Versand-Änderung vorher', () => {
	test('#1743 AC-26 / #2794: „zustellung" steht in der Liste, „versand"/„vorschau"/„wetter-metriken" nicht mehr', () => {
		assert.ok(
			SELBST_SPEICHERNDE_VERGLEICH_REITER.includes('zustellung'),
			'ohne den Eintrag flusht der Reiterwechsel-Guard den Versand-Abschnitt nicht — Datenverlust-Pfad'
		);
		for (const alt of ['versand', 'vorschau', 'wetter-metriken']) {
			assert.ok(!SELBST_SPEICHERNDE_VERGLEICH_REITER.includes(alt), `'${alt}' ist kein Reiter mehr`);
		}
	});

	test('Versand-Änderung im Entprell-Fenster, Wechsel zu „wetter", danach sofortige Radar-Änderung → BEIDE gespeichert', async () => {
		const { wiz, ctl, versand, alarme, bedienung } = hub();

		bedienung.setMorgenZeit('07:15');
		versand.aenderungMelden();
		assert.equal(ctl.hasPending, true, 'Vorbedingung: die Versand-Änderung wartet');
		assert.equal(puts().length, 0, 'Vorbedingung: noch nichts gesendet');

		await sichereSelbstSpeichererVorReiterwechsel('zustellung', 'wetter', ctl);

		assert.equal(puts().length, 1, 'die Versand-Änderung muss vor dem Reiterwechsel gesendet werden');
		assert.equal(puts()[0].status, 200, 'der PUT muss abgeschlossen sein, bevor der Wechsel weiterläuft');

		// Danach sofort Radar anschalten (Alarm-Besitzer)
		wiz.radarAlertEnabled = true;
		alarme.aenderungMelden();
		await ctl.flush();

		assert.equal(puts().length, 2, 'zwei unabhängige Änderungen → zwei PUTs');
		const stand = server.stand(PRESET_ID);
		assert.equal(stand.morning_time, '07:15:00', 'die Versand-Änderung ging beim Reiterwechsel verloren');
		assert.equal(stand.radar_alert_enabled, true, 'die Alarm-Änderung muss ebenfalls gespeichert sein');
		assert.equal(ctl.state, 'idle');
	});

	test('Gegenprobe: „Wechsel" auf denselben Reiter → nichts wird vorzeitig gesendet', async () => {
		const { ctl, versand, bedienung } = hub();
		bedienung.setMorgenZeit('07:15');
		versand.aenderungMelden();

		await sichereSelbstSpeichererVorReiterwechsel('zustellung', 'zustellung', ctl);

		assert.equal(puts().length, 0, 'ohne echten Wechsel bleibt die Entprellung unangetastet');
		assert.equal(ctl.hasPending, true);
		ctl.cancel();
	});
});
