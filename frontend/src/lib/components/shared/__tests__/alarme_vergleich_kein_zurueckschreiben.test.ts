// TDD — Alarme-Reiter des Ortsvergleichs: die Basis wird erst bei Ausführung
// in der Hub-Queue gelesen.
//
// Issue #2276 Scheibe S2 (Epic #2345): S2-AC-3 (Basis erst bei Ausführung
//   in der Hub-Queue lesen).
//
// Issue #3389: die Blöcke S2-AC-2, S5-AC-2, S5-AC-11 und S5-AC-3 nutzten den
// toten Versand-Speicherer als Nachbar-Reiter und entfielen mit ihm. Den
// Feld-Besitz der Zustellung (Versand sendet nie Alarmfelder) belegt
// zustellungSpeicherung.test.ts (NIE-Liste, Eigenfeld-Whitelist).
//
// Spec: docs/specs/modules/rework_2276_s2_alarme.md — AC-3
//
// Geprüft wird jeweils der tatsächlich abgeschickte PUT-Rumpf (Request), nicht
// der Server-Stand — `fakeTripServer.ts` ersetzt den Stand komplett und nimmt
// jedes Feld an.
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
import { createPutQueue } from '../../compare/compareHubPersistenz.ts';
import { hydrateAlarmFieldsFromPreset } from '../../compare/compareHubHydration.ts';
import { erstelleAlarmeVergleichSpeicherung } from '../alarmeVergleichSpeicherung.ts';

const PRESET_ID = 'cp-2276-basis';

function makePreset(overrides: Partial<ComparePreset> = {}): ComparePreset {
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
		display_config: { metric_alert_levels: { wind_gust: 'warn' }, telegram_style: 'rich' },
		...overrides
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

describe('S2-AC-3: die Basis wird bei AUSFÜHRUNG in der Queue gelesen, nicht beim Einreihen', () => {
	test('zwei eingereihte Alarm-Speichervorgänge, Basis ändert sich dazwischen → zweiter PUT trägt die neue Basis', async () => {
		let basis = makePreset();
		const wiz: Record<string, unknown> = {};
		hydrateAlarmFieldsFromPreset(wiz, basis, []);
		const ctl = createController();
		const hubPutQueue = createPutQueue();
		const rueckmeldungen: ComparePreset[] = [];
		const speicherung = erstelleAlarmeVergleichSpeicherung({
			client: api,
			zustand: wiz,
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

		// Zweiter Alarm-Vorgang wird eingereiht, während der erste noch läuft.
		// Issue #2293 S2 (AC-9 Entkopplung): der Alarme-Reiter schreibt seit
		// dieser Scheibe `wiz.channels` statt der Briefing-Felder
		// sendTelegram/sendSms/sendPremiumSms — dieselbe Zusicherung (zweite
		// Alarm-Änderung erreicht den zweiten PUT), nur am neuen Feld gemessen.
		wiz.channels = { ...(wiz.channels as Record<string, boolean>), sms: true };
		speicherung.aenderungMelden();
		const zweiter = ctl.flush();

		// Basis ändert sich NACH dem Einreihen des zweiten, VOR seiner Ausführung
		// (z. B. Rückmeldung eines Nachbar-PUT oder der Kopfzeile)
		basis = { ...basis, name: 'Neuer Name', morning_time: '08:00:00' };
		assert.equal(gesendet.length, 1, 'Vorbedingung: der zweite Vorgang wartet noch in der Queue');

		await Promise.all([erster, zweiter]);

		assert.equal(gesendet.length, 2, 'zwei Alarm-Vorgänge mit je eigener Änderung → zwei PUTs');
		assert.equal(gesendet[0].radar_alert_enabled, true, 'Vorbedingung: der erste PUT trägt die erste Alarm-Änderung');
		const zweiterPut = gesendet[1];
		// Seit #2375 fließt die Basis gar nicht mehr in die Alarm-Nutzlast — weder
		// eine eingefrorene noch eine frische: Name und Uhrzeit stehen nicht im Body.
		assert.ok(!('name' in zweiterPut), 'die Alarm-Nutzlast darf den Namen der Basis nicht senden');
		assert.ok(!('morning_time' in zweiterPut), 'die Alarm-Nutzlast darf die Versandzeit der Basis nicht senden');
		assert.equal(zweiterPut.radar_alert_enabled, true, 'die erste Alarm-Änderung muss erhalten bleiben');
		assert.equal(
			(zweiterPut.alert_channels as Record<string, boolean>).sms,
			true,
			'die zweite Alarm-Änderung muss im PUT stehen'
		);
		assert.equal(ctl.state, 'idle');
	});
});
