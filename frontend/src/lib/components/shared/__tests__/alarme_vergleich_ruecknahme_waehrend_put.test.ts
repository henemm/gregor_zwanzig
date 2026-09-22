// Fix-Loop F005 — Issue #2276 Scheibe S2 (Epic #2345): Rücknahme einer
// Alarm-Änderung, WÄHREND deren PUT noch unterwegs ist.
//
// Nutzersicht: Radar-Alarm an → Speichern läuft → Nutzer schaltet den Alarm
// wieder aus, bevor die Antwort da ist. Danach MUSS der Server den Stand der
// Oberfläche tragen (aus), bevor der Indikator „Gespeichert" zeigt. Vorher
// verglich die zweite Meldung gegen die noch alte Baseline, fand keinen
// Unterschied und tat nichts — Server blieb dauerhaft auf „an", UI zeigte
// „aus" und „Gespeichert".
//
// Echter Ablauf: echtes Speicher-Modul, echte Hub-Queue, echter SaveStatus,
// echter api-Client gegen den Ersatz-Server (fakeTripServer) mit Laufzeit.
//
// Ausführen:
//   cd frontend && npm test -- src/lib/components/shared/__tests__/alarme_vergleich_ruecknahme_waehrend_put.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../api.ts';
import { clearEtagRegistry } from '../../../etagRegistry.ts';
import { SaveStatus } from '../../../stores/saveStatusStore.svelte.ts';
import { createFakeTripServer, type FakeTripServer } from '../../../__tests__/fakeTripServer.ts';
import type { ComparePreset } from '../../../types.ts';
import { createPutQueue, hydrateAlarmFieldsFromPreset } from '../../compare/compareHubWizardBridge.ts';
import { erstelleAlarmeVergleichSpeicherung } from '../alarmeVergleichSpeicherung.ts';

const PRESET_ID = 'cp-2276-ruecknahme';
const PRESET_PFAD = `/api/compare/presets/${PRESET_ID}`;

function makePreset(): ComparePreset {
	return {
		id: PRESET_ID,
		name: 'Ortsvergleich Basis',
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
		send_premium_sms: false,
		morning_enabled: true,
		morning_time: '06:30:00',
		evening_enabled: false,
		evening_time: '18:00:00',
		alert_channel_thresholds: { email: 'gering', telegram: 'gering', sms: 'gering', premium_sms: 'gering' },
		corridors: [],
		display_config: { metric_alert_levels: { wind_gust: 'warn' }, telegram_style: 'rich' }
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
/** Tatsächlich abgeschickte PUT-Rümpfe (Request, nicht Server-Stand). */
let gesendet: Record<string, unknown>[];

/** Ersatz-Server installieren und die abgeschickten PUT-Rümpfe mitschreiben. */
function installiere(latencyMs = 0): void {
	if (server) server.restore();
	server = createFakeTripServer({ latencyMs });
	server.install();
	gesendet = [];
	const echterServer = globalThis.fetch;
	(globalThis as { fetch: unknown }).fetch = (input: unknown, init?: RequestInit) => {
		if ((init?.method ?? 'GET').toUpperCase() === 'PUT' && typeof init?.body === 'string') {
			gesendet.push(JSON.parse(init.body));
		}
		return echterServer(input as RequestInfo, init);
	};
}

beforeEach(() => {
	clearEtagRegistry();
	installiere(0);
});

afterEach(() => server.restore());

beforeEach(() => {
	clearEtagRegistry();
	installiere(30);
});

afterEach(() => server.restore());

describe('F005: Rücknahme einer Alarm-Änderung, während deren PUT noch unterwegs ist', () => {
	test('Radar an → PUT unterwegs → Radar wieder aus → Server trägt am Ende „aus", erst dann „Gespeichert"', async () => {
		let currentPreset = makePreset();
		const wiz: Record<string, unknown> = {};
		hydrateAlarmFieldsFromPreset(wiz, currentPreset, []);
		const ctl = createController();
		const hubPutQueue = createPutQueue();
		const speicherung = erstelleAlarmeVergleichSpeicherung({
			client: api,
			zustand: wiz,
			preset: () => currentPreset,
			enqueueHubWrite: (fn) => hubPutQueue.enqueue(fn),
			onCompareUpdate: (p: ComparePreset) => {
				currentPreset = p;
			},
			saveController: ctl
		});

		// 1) Radar an, Speichern startet, PUT ist im Netz
		wiz.radarAlertEnabled = true;
		speicherung.aenderungMelden();
		const erster = ctl.flush();
		while (gesendet.length < 1) await new Promise((r) => setImmediate(r));
		assert.equal(gesendet[0].radar_alert_enabled, true, 'Vorbedingung: der erste PUT trägt „an"');

		// 2) Nutzer nimmt die Änderung zurück, bevor die Antwort da ist
		wiz.radarAlertEnabled = false;
		speicherung.aenderungMelden();

		// 3) Alles abwarten, was der Controller noch vorhat
		await erster;
		await ctl.flush();
		while (ctl.laufendeSpeicherung) await ctl.laufendeSpeicherung;

		// THEN: Server-Stand == UI-Stand, und erst dann „Gespeichert"
		const serverStand = server.storedBody(PRESET_ID) as Record<string, unknown>;
		assert.equal(wiz.radarAlertEnabled, false, 'Vorbedingung: die Oberfläche zeigt „aus"');
		assert.equal(
			serverStand.radar_alert_enabled,
			false,
			'Server trägt den vom Nutzer verworfenen Wert „an" — Server und Oberfläche divergieren'
		);
		assert.equal(gesendet.length, 2, 'genau ein Korrektur-PUT nach dem ersten erwartet');
		assert.equal(ctl.hasPending, false, 'es darf nichts mehr ausstehen');
		assert.equal(ctl.state, 'idle', '„Gespeichert" erst, wenn der Server den UI-Stand trägt');
	});

	test('ohne Rücknahme bleibt es bei genau einem PUT (kein Folge-PUT ohne Unterschied)', async () => {
		let currentPreset = makePreset();
		const wiz: Record<string, unknown> = {};
		hydrateAlarmFieldsFromPreset(wiz, currentPreset, []);
		const ctl = createController();
		const hubPutQueue = createPutQueue();
		const speicherung = erstelleAlarmeVergleichSpeicherung({
			client: api,
			zustand: wiz,
			preset: () => currentPreset,
			enqueueHubWrite: (fn) => hubPutQueue.enqueue(fn),
			onCompareUpdate: (p: ComparePreset) => {
				currentPreset = p;
			},
			saveController: ctl
		});

		wiz.radarAlertEnabled = true;
		speicherung.aenderungMelden();
		await ctl.flush();
		await ctl.flush();

		assert.equal(gesendet.length, 1, 'ohne weitere Änderung kein zweiter PUT');
		assert.equal((server.storedBody(PRESET_ID) as Record<string, unknown>).radar_alert_enabled, true);
		assert.equal(ctl.state, 'idle');
	});
});
