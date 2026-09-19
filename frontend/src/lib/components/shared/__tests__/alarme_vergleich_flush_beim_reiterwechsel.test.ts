// TDD RED — Issue #2276 Scheibe S2 (Epic #2345), AC-6: wechselt der Nutzer
// direkt nach einer Alarm-Änderung (vor Ablauf der 700-ms-Debounce-Zeit) den
// Reiter, wird die Änderung VOR dem Wechsel gesendet, nicht verloren.
//
// Spec: docs/specs/modules/rework_2276_s2_alarme.md — AC-6, Design Punkt 5
// Vorbild: TripTabs.svelte `handleValueChange` (flush() beim Verlassen).
//
// Warum ein Modul-Helfer: `CompareTabs.handleValueChange` ist in diesem
// Prüfstand nicht ausführbar (kein DOM, SSR führt keine Ereignisse aus).
// Die Entscheidung „wann wird vor dem Wechsel gesichert" liegt deshalb in
//
//   shared/corridor-editor/wertebereicheVergleichSpeicherung.ts (seit #2276 S3
//   generisch fuer alle selbst speichernden Reiter, vorher reiter-spezifisch)
//   sichereSelbstSpeichererVorReiterwechsel(aktiverReiter: string, zielReiter: string,
//                                           saveController?: SaveStatus): Promise<void>
//
// und `handleValueChange` wartet sie ab, BEVOR `activeTab` umgestellt wird.
// (existiert noch NICHT → RED per ERR_MODULE_NOT_FOUND)
//
// Grenze: dass CompareTabs den Helfer wirklich aufruft, prüft dieser Test
// nicht (Prüfort ≠ Wirkort) — das ist nur im Browser (Staging) messbar.
//
// Ausführen:
//   cd frontend && npm test -- src/lib/components/shared/__tests__/alarme_vergleich_flush_beim_reiterwechsel.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../api.ts';
import { clearEtagRegistry } from '../../../etagRegistry.ts';
import { SaveStatus } from '../../../stores/saveStatusStore.svelte.ts';
import { createFakeTripServer, type FakeTripServer } from '../../../__tests__/fakeTripServer.ts';
import type { ComparePreset } from '../../../types.ts';
import { createPutQueue, hydrateAlarmFieldsFromPreset } from '../../compare/compareHubWizardBridge.ts';
import { erstelleAlarmeVergleichSpeicherung } from '../alarmeVergleichSpeicherung.ts';
// Issue #2276 S3: der reiter-spezifische Guard ist im generischen, listenbasierten
// Flush-Guard aufgegangen — die S2-Zusicherungen gelten fuer ihn unveraendert.
import { sichereSelbstSpeichererVorReiterwechsel } from '../corridor-editor/wertebereicheVergleichSpeicherung.ts';

const PRESET_ID = 'cp-2276-reiter';

function makePreset(): ComparePreset {
	return {
		id: PRESET_ID,
		name: 'Ortsvergleich Reiter',
		location_ids: ['loc-a', 'loc-b', 'loc-c'],
		schedule: 'daily',
		profil: 'wandern',
		hour_from: 6,
		hour_to: 9,
		forecast_hours: 48,
		empfaenger: ['a@example.com'],
		created_at: '2026-01-01T00:00:00Z',
		official_warnings: { enabled: true },
		radar_alert_enabled: false,
		send_telegram: true,
		send_sms: false,
		corridors: [],
		display_config: { metric_alert_levels: {}, telegram_style: 'rich' }
	};
}

function createController(): SaveStatus {
	const inst = Object.create(SaveStatus.prototype) as SaveStatus;
	const f = inst as unknown as Record<string, unknown>;
	f.state = 'idle';
	f.savedAt = null;
	f.error = null;
	f._timer = null;
	f._pendingFn = null;
	f._inflight = null;
	f._lastFailed = null;
	f._unresolvedError = null;
	f._tripId = PRESET_ID;
	f._resourceKind = 'vergleich';
	return inst;
}

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

function aufbau() {
	let basis = makePreset();
	const wiz: Record<string, unknown> = {};
	hydrateAlarmFieldsFromPreset(wiz, basis, []);
	const ctl = createController();
	const queue = createPutQueue();
	const speicherung = erstelleAlarmeVergleichSpeicherung({
		client: api,
		wiz,
		preset: () => basis,
		enqueueHubWrite: (fn) => queue.enqueue(fn),
		onCompareUpdate: (p: ComparePreset) => {
			basis = p;
		},
		saveController: ctl
	});
	return { wiz, ctl, speicherung };
}

describe('AC-6: Reiterwechsel weg von „alarme" sendet die ausstehende Alarm-Änderung vorher', () => {
	test('Änderung im Debounce-Fenster, Wechsel zu „versand" → PUT abgeschlossen, bevor der Wechsel freigegeben wird', async () => {
		const { wiz, ctl, speicherung } = aufbau();
		wiz.radarAlertEnabled = true;
		speicherung.aenderungMelden();
		assert.equal(ctl.hasPending, true, 'Vorbedingung: Änderung wartet im Debounce-Fenster');
		assert.equal(puts().length, 0, 'Vorbedingung: noch nichts gesendet');

		await sichereSelbstSpeichererVorReiterwechsel('alarme', 'versand', ctl);

		assert.equal(puts().length, 1, 'die Alarm-Änderung muss vor dem Reiterwechsel gesendet werden');
		assert.equal(puts()[0].status, 200, 'der PUT muss abgeschlossen sein, bevor der Wechsel weiterläuft');
		assert.equal(
			(server.storedBody(PRESET_ID) as Record<string, unknown>).radar_alert_enabled,
			true,
			'der gesendete Stand muss die Änderung tragen'
		);
		assert.equal(ctl.hasPending, false);
		assert.equal(ctl.state, 'idle');
	});

	test('Gegenprobe: „Wechsel" auf denselben Reiter → nichts wird vorzeitig gesendet', async () => {
		const { wiz, ctl, speicherung } = aufbau();
		wiz.radarAlertEnabled = true;
		speicherung.aenderungMelden();

		await sichereSelbstSpeichererVorReiterwechsel('alarme', 'alarme', ctl);

		assert.equal(puts().length, 0, 'ohne echten Wechsel bleibt der Debounce unangetastet');
		assert.equal(ctl.hasPending, true);
		ctl.cancel();
	});

	test('ohne Controller (Anlege-Seite) → kein Fehler, kein PUT', async () => {
		await sichereSelbstSpeichererVorReiterwechsel('alarme', 'versand', undefined);
		assert.equal(puts().length, 0);
	});
});
