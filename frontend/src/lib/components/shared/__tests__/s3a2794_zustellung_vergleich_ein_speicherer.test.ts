// Fix-Loop Issue #2794 S3a Teil-PR 2 (Spec feat_2794_s3a_teil2_leiste.md, AC-8,
// AC-2.T1 „gleicher Request wie vor dem Umbau"): im Reiter `zustellung` des
// Ortsvergleichs sind Versand- und Alarme-Teil GLEICHZEITIG gemountet
// (ZustellungTab.svelte + Snippet `alarmeBereich`). Vorher waren es getrennte
// Reiter, nie gleichzeitig aktiv.
//
// Defekt (CI-E2E AW-4/KS-1/speicherung-ueberlebt-neuladen): der Versand-
// Schnappschuss las die drei Alarm-Zustellungsfelder (Cooldown, Stille Stunden)
// mit. Eine Cooldown-Geste im Alarme-Teil löste damit ZUSÄTZLICH den
// Versand-Speicherer (Owner 'versand') aus — zwei PUTs je Geste, und der
// Owner-Wechsel im Controller verdrängte den Alarme-Vorgang (Cooldown nach
// sofortigem Neuladen verloren).
//
// Aufbau wie im Hub: EIN gemeinsamer Feldsatz (wizardState), BEIDE echten
// Speicherer am selben echten Controller und derselben Hub-Queue, Transport
// echtes `api` gegen den Go-Merge-Prüfserver. Beide `$effect`s melden — der
// Test ruft beide `aenderungMelden()`, wie es die zwei gemounteten Reiter tun.
//
// Ausführen:
//   cd frontend && npm test -- src/lib/components/shared/__tests__/s3a2794_zustellung_vergleich_ein_speicherer.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../api.ts';
import { clearEtagRegistry } from '../../../etagRegistry.ts';
import type { ComparePreset } from '../../../types.ts';
import { createPutQueue } from '../../compare/compareHubPersistenz.ts';
import { hydrateAlarmFieldsFromPreset } from '../../compare/compareHubHydration.ts';
import { erstelleAlarmeVergleichSpeicherung } from '../alarmeVergleichSpeicherung.ts';
import {
	erstelleVersandVergleichSpeicherung,
	hydrateVersandFieldsFromPreset
} from '../versandVergleichSpeicherung.ts';
import { createController } from './versandVergleichPruefstand.ts';
import { createGoMergeServer, vollerVergleich, type GoMergeServer } from './goMergeServerPruefstand.ts';

const ID = 'cp-2794-zustellung';
const PFAD = `/api/compare/presets/${ID}`;
let server: GoMergeServer;

beforeEach(async () => {
	clearEtagRegistry();
	server = createGoMergeServer({ [ID]: vollerVergleich(ID) });
	server.install();
	await api.get(PFAD);
});
afterEach(() => server.restore());

/** Reiter `zustellung` im Vergleich: Versand- und Alarme-Teil gleichzeitig. */
function zustellungReiter() {
	let basis = vollerVergleich(ID) as unknown as ComparePreset;
	const ctl = createController(ID);
	const queue = createPutQueue();
	const wizardState: Record<string, unknown> = {};
	hydrateAlarmFieldsFromPreset(wizardState, basis, []);
	Object.assign(wizardState, hydrateVersandFieldsFromPreset(basis));
	const gemeinsam = {
		client: api,
		preset: () => basis,
		enqueueHubWrite: <T>(fn: () => Promise<T>) => queue.enqueue(fn),
		onCompareUpdate: (p: ComparePreset) => {
			basis = p;
		},
		saveController: ctl,
		zustand: wizardState
	};
	const alarme = erstelleAlarmeVergleichSpeicherung(gemeinsam);
	const versand = erstelleVersandVergleichSpeicherung(gemeinsam);
	return {
		ctl,
		wizardState,
		versand,
		/** Nutzergeste im Alarme-Teil; beide gemounteten Reiter-Effekte melden. */
		aendern(feld: string, wert: unknown) {
			wizardState[feld] = wert;
			alarme.aenderungMelden();
			versand.aenderungMelden();
		}
	};
}

const fertig = async (ctl: ReturnType<typeof createController>) => {
	await ctl.flush();
	const l = ctl.laufendeSpeicherung;
	if (l) await l;
};
const puts = () => server.putRuempfe();

describe('S3a #2794 Fix: eine Cooldown-/Stille-Stunden-Geste im Vergleich = genau EIN Speichervorgang über den Alarme-Owner', () => {
	test('Cooldown-Änderung: genau ein PUT, er trägt den Cooldown, der Server hat ihn', async () => {
		const z = zustellungReiter();
		z.aendern('alertCooldownMinutes', 30);
		await fertig(z.ctl);

		assert.equal(puts().length, 1, `genau EIN PUT je Geste erwartet, gesehen: ${JSON.stringify(puts())}`);
		assert.equal(puts()[0].alert_cooldown_minutes, 30, 'der Cooldown gehört in den (einzigen) PUT');
		assert.equal(server.stand(ID).alert_cooldown_minutes, 30);
	});

	test('Stille Stunden: genau ein PUT, beide Zeiten im Payload', async () => {
		const z = zustellungReiter();
		z.wizardState.alertQuietFrom = '21:00';
		z.aendern('alertQuietTo', '06:00');
		await fertig(z.ctl);

		assert.equal(puts().length, 1, `genau EIN PUT erwartet, gesehen: ${JSON.stringify(puts())}`);
		assert.equal(puts()[0].alert_quiet_from, '21:00');
		assert.equal(puts()[0].alert_quiet_to, '06:00');
	});

	test('der Versand-Speicherer allein meldet bei einer Alarm-Zustellungsänderung NICHTS an', () => {
		const z = zustellungReiter();
		z.wizardState.alertCooldownMinutes = 30;
		z.wizardState.alertQuietFrom = '20:00';
		z.versand.aenderungMelden();
		assert.equal(z.ctl.hasPending, false, 'Versand darf für alert_*-Felder keinen Vorgang einplanen (Feld-Besitz: Alarme)');
	});

	test('Versand-Änderung speichert weiterhin über den Versand-Speicherer (Kontrolle)', async () => {
		const z = zustellungReiter();
		z.aendern('morningTime', '07:45');
		await fertig(z.ctl);
		assert.equal(puts().length, 1);
		assert.equal(puts()[0].morning_time, '07:45:00');
		assert.equal('alert_cooldown_minutes' in puts()[0], false);
	});
});
