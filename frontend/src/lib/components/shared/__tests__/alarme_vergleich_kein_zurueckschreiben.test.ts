// TDD RED — Issue #2276 Scheibe S2 (Epic #2345): kein Zurückschreiben alter
// Alarmwerte durch Nachbar-Reiter (AC-2) und Basis-Lesen erst bei Ausführung in
// der Hub-Queue (AC-3).
//
// Spec: docs/specs/modules/rework_2276_s2_alarme.md — AC-2, AC-3, Design Punkt 1
//
// AC-2: Nach einem Alarm-PUT löst der Versand-Reiter einen eigenen Voll-Spread-
// PUT aus (Nachbau des bestehenden `handleVersandCommit` aus CompareTabs.svelte
// mit den ECHTEN Bridge-Funktionen, über dieselbe Queue). Geprüft wird der
// tatsächlich abgeschickte Rumpf dieses ZWEITEN PUT — nicht der Server-Stand,
// denn `fakeTripServer.ts` ersetzt den Stand komplett und nimmt jedes Feld an.
// Gewählt sind Alarmfelder, die der Versand-Snapshot NICHT selbst führt
// (Radar, Kurzstil, Kanal-Schwellen, Metrik-Stufen) — sie kommen im zweiten
// PUT ausschließlich aus der Basis `currentPreset`, also nur dann richtig, wenn
// der Alarm-Zweig die Basis über `onCompareUpdate` aufgefrischt hat.
//
// AC-3: zwei Alarm-Speichervorgänge liegen hintereinander in der Queue, die
// Basis ändert sich zwischen Einreihen und Ausführung — der zweite PUT muss
// die NEUE Basis tragen (Svelte-5-Prop-Getter statt eingefrorener Kopie).
//
// Zielschnittstelle (existiert noch NICHT → RED per ERR_MODULE_NOT_FOUND):
//   shared/alarmeVergleichSpeicherung.ts → erstelleAlarmeVergleichSpeicherung
//   (Vertrag s. alarme_vergleich_speichert_selbst.test.ts).
//
// Ausführen:
//   cd frontend && npm test -- src/lib/components/shared/__tests__/alarme_vergleich_kein_zurueckschreiben.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../api.ts';
import { clearEtagRegistry } from '../../../etagRegistry.ts';
import { SaveStatus } from '../../../stores/saveStatusStore.svelte.ts';
import { createFakeTripServer, type FakeTripServer } from '../../../__tests__/fakeTripServer.ts';
import type { ComparePreset } from '../../../types.ts';
import {
	createPutQueue,
	hydrateAlarmFieldsFromPreset,
	hydrateVersandFieldsFromPreset,
	flushPendingVersandSave
} from '../../compare/compareHubWizardBridge.ts';
import { erstelleAlarmeVergleichSpeicherung } from '../alarmeVergleichSpeicherung.ts';

const PRESET_ID = 'cp-2276-basis';
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

describe('AC-2: ein Nachbar-Reiter schreibt die gerade gespeicherten Alarmwerte NICHT zurück', () => {
	test('Alarm-PUT, danach Versand-PUT → der Rumpf des ZWEITEN PUT trägt die neuen Alarmwerte', async () => {
		let currentPreset = makePreset();
		const wiz: Record<string, unknown> = {};
		hydrateAlarmFieldsFromPreset(wiz, currentPreset, []);
		const ctl = createController();
		const hubPutQueue = createPutQueue();
		const speicherung = erstelleAlarmeVergleichSpeicherung({
			client: api,
			wiz,
			preset: () => currentPreset,
			enqueueHubWrite: (fn) => hubPutQueue.enqueue(fn),
			onCompareUpdate: (p: ComparePreset) => {
				currentPreset = p;
			},
			saveController: ctl
		});
		// Versand-Reiter hydriert beim Öffnen VOR der Alarm-Änderung (wie im Hub).
		const versandVorher = hydrateVersandFieldsFromPreset(currentPreset);

		// 1) Alarm-Änderung: Radar an, Kurzstil, Telegram-Schwelle, Metrik-Stufe
		wiz.radarAlertEnabled = true;
		wiz.telegramStyle = 'kurzform';
		wiz.channelThresholds = { email: 'gering', telegram: 'hoch', sms: 'gering', premium_sms: 'gering' };
		wiz.metricAlertLevels = { wind_gust: 'alarm' };
		speicherung.aenderungMelden();
		await ctl.flush();
		assert.equal(gesendet.length, 1, 'Vorbedingung: der Alarm-PUT ist raus');
		assert.equal(gesendet[0].radar_alert_enabled, true, 'Vorbedingung: der Alarm-PUT trägt die Änderung');

		// 2) Versand-Reiter: Morgen-Uhrzeit ändern — Nachbau handleVersandCommit
		//    (Basis wird INNERHALB der enqueueten Closure gelesen).
		const versandJetzt = { ...versandVorher, morningTime: '07:15' };
		await hubPutQueue.enqueue(async () => {
			const payload = flushPendingVersandSave(currentPreset, versandJetzt, versandVorher);
			assert.ok(payload, 'Vorbedingung: die Versand-Änderung erzeugt einen PUT');
			const result = await api.put<ComparePreset>(payload.url, payload.body);
			currentPreset = result;
		});

		// THEN: Rumpf des ZWEITEN PUT
		assert.equal(gesendet.length, 2, 'genau zwei PUTs erwartet (Alarm, dann Versand)');
		const zweiter = gesendet[1];
		assert.equal(server.calls.filter((c) => c.method === 'PUT')[1].path, PRESET_PFAD);
		assert.equal(zweiter.radar_alert_enabled, true, 'der Versand-PUT schreibt den alten Radar-Wert zurück');
		const dc = zweiter.display_config as Record<string, unknown>;
		assert.equal(dc.telegram_style, 'kurzform', 'der Versand-PUT schreibt den alten Kurzstil zurück');
		assert.deepEqual(dc.metric_alert_levels, { wind_gust: 'alarm' }, 'der Versand-PUT schreibt alte Metrik-Stufen zurück');
		assert.equal(
			(zweiter.alert_channel_thresholds as Record<string, string>).telegram,
			'hoch',
			'der Versand-PUT schreibt die alte Telegram-Schwelle zurück'
		);
	});
});

describe('AC-3: die Basis wird bei AUSFÜHRUNG in der Queue gelesen, nicht beim Einreihen', () => {
	test('zwei eingereihte Alarm-Speichervorgänge, Basis ändert sich dazwischen → zweiter PUT trägt die neue Basis', async () => {
		let basis = makePreset();
		const wiz: Record<string, unknown> = {};
		hydrateAlarmFieldsFromPreset(wiz, basis, []);
		const ctl = createController();
		const hubPutQueue = createPutQueue();
		const rueckmeldungen: ComparePreset[] = [];
		const speicherung = erstelleAlarmeVergleichSpeicherung({
			client: api,
			wiz,
			preset: () => basis,
			enqueueHubWrite: (fn) => hubPutQueue.enqueue(fn),
			// bewusst OHNE Basis-Übernahme: AC-3 prüft das Lesen, nicht die Rückmeldung
			onCompareUpdate: (p: ComparePreset) => {
				rueckmeldungen.push(p);
			},
			saveController: ctl
		});

		// Server-Laufzeit > 0: der erste Alarm-PUT ist unterwegs, während der
		// zweite eingereiht wird (sonst trüge der erste bereits beide Änderungen).
		installiere(30);

		// Erster Alarm-Vorgang: eingereiht und ausgeführt, PUT unterwegs
		wiz.radarAlertEnabled = true;
		speicherung.aenderungMelden();
		const erster = ctl.flush();
		while (gesendet.length < 1) await new Promise((r) => setImmediate(r));

		// Zweiter Alarm-Vorgang wird eingereiht, während der erste noch läuft
		wiz.sendSms = true;
		speicherung.aenderungMelden();
		const zweiter = ctl.flush();

		// Basis ändert sich NACH dem Einreihen des zweiten, VOR seiner Ausführung
		// (z. B. Rückmeldung eines Nachbar-PUT oder der Kopfzeile)
		basis = { ...basis, name: 'Neuer Name', morning_time: '08:00:00' };
		assert.equal(gesendet.length, 1, 'Vorbedingung: der zweite Vorgang wartet noch in der Queue');

		await Promise.all([erster, zweiter]);

		assert.equal(gesendet.length, 2, 'zwei Alarm-Vorgänge mit je eigener Änderung → zwei PUTs');
		assert.equal(gesendet[0].name, 'Ortsvergleich Basis', 'Vorbedingung: der erste PUT lief vor der Basis-Änderung');
		const zweiterPut = gesendet[1];
		assert.equal(zweiterPut.name, 'Neuer Name', 'der zweite PUT hat die Basis beim Einreihen eingefroren');
		assert.equal(zweiterPut.morning_time, '08:00:00', 'der zweite PUT hat die Basis beim Einreihen eingefroren');
		assert.equal(zweiterPut.radar_alert_enabled, true, 'die erste Alarm-Änderung muss erhalten bleiben');
		assert.equal(zweiterPut.send_sms, true, 'die zweite Alarm-Änderung muss im PUT stehen');
		assert.equal(ctl.state, 'idle');
	});
});
