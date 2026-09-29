// TDD RED — Issue #2276 Scheibe S2 (Epic #2345), AC-4: ein Speicherkonflikt
// (412) beim Alarm-Speichern im Ortsvergleich führt zu „Nochmal speichern"
// (Zustand `conflict`), das Wiederholen sendet die UNVERÄNDERTE Änderung und
// endet in „Gespeichert"; die geänderten Werte bleiben sichtbar (kein Rollback
// bei 412). Bei jedem ANDEREN Fehler wird dagegen zurückgerollt (Gegenprobe).
//
// Spec: docs/specs/modules/rework_2276_s2_alarme.md — AC-4, Design Punkt 4.
//
// Zielschnittstelle (existiert noch NICHT → RED per ERR_MODULE_NOT_FOUND):
//   shared/alarmeVergleichSpeicherung.ts → erstelleAlarmeVergleichSpeicherung
//   (Vertrag s. alarme_vergleich_speichert_selbst.test.ts).
//
// Grenze dieses Prüfstands: die Kennung `{typ:'vergleich', id}` entsteht in
// routes/compare/[id]/+page.svelte (nicht mountbar). Hier wird der Controller
// MIT Kennung gebaut — geprüft wird, dass der Alarm-Speicherweg des Moduls
// bis zu `retryConflict()` trägt. Ob die Seite die Kennung wirklich übergibt,
// ist nur auf Staging (echter 412) messbar.
//
// Ausführen:
//   cd frontend && npm test -- src/lib/components/shared/__tests__/alarme_vergleich_konflikt_nochmal_speichern.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../api.ts';
import { clearEtagRegistry } from '../../../etagRegistry.ts';
import { SaveStatus } from '../../../stores/saveStatusStore.svelte.ts';
import { createFakeTripServer, type FakeTripServer } from '../../../__tests__/fakeTripServer.ts';
import type { ComparePreset } from '../../../types.ts';
import { createPutQueue } from '../../compare/compareHubPersistenz.ts';
import { hydrateAlarmFieldsFromPreset } from '../../compare/compareHubHydration.ts';
import type { PutClient } from '../tripSpeicherung.ts';
import { erstelleAlarmeVergleichSpeicherung } from '../alarmeVergleichSpeicherung.ts';
import { EIGENFELDER, schluessel } from './goMergeServerPruefstand.ts';
import { konfliktMitFremdemNamen } from './compareReiterAufbauPruefstand.ts';

const PRESET_ID = 'cp-2276-konflikt';
const PRESET_PFAD = `/api/compare/presets/${PRESET_ID}`;

function makePreset(): ComparePreset {
	return {
		id: PRESET_ID,
		name: 'Ortsvergleich Konflikt',
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
	server = createFakeTripServer();
	server.install();
});

afterEach(() => server.restore());

const puts = () => server.calls.filter((c) => c.method === 'PUT');

function aufbau(client: PutClient = api) {
	let basis = makePreset();
	const wiz: Record<string, unknown> = {};
	hydrateAlarmFieldsFromPreset(wiz, basis, []);
	const ctl = createController();
	const queue = createPutQueue();
	const speicherung = erstelleAlarmeVergleichSpeicherung({
		client,
		zustand: wiz,
		preset: () => basis,
		enqueueHubWrite: (fn) => queue.enqueue(fn),
		onCompareUpdate: (p: ComparePreset) => {
			basis = p;
		},
		saveController: ctl
	});
	return { wiz, ctl, speicherung };
}

describe('AC-4: Speicherkonflikt beim Alarm-Speichern → „Nochmal speichern" → gespeichert', () => {
	test('412 → conflict (nicht error), Werte bleiben stehen; retryConflict sendet die Änderung erneut → idle', async () => {
		// GIVEN: Seite geladen (Stand bekannt), danach ändert „ein anderes Gerät" den Vergleich
		await api.get(PRESET_PFAD);
		await server.handler(PRESET_PFAD, { method: 'PUT', body: JSON.stringify({ name: 'fremd' }) });
		const { wiz, ctl, speicherung } = aufbau();

		// WHEN: Nutzer schaltet Radar und den SMS-ALARM-Kanal an (Issue #2293 S2:
		// der Alarme-Reiter schreibt seit dieser Scheibe `wiz.channels`, nicht
		// mehr `wiz.sendSms` — dasselbe Szenario, neues Feld).
		wiz.radarAlertEnabled = true;
		wiz.channels = { ...(wiz.channels as Record<string, boolean>), sms: true };
		speicherung.aenderungMelden();
		await ctl.flush();

		// THEN (a): Konflikt, nicht generischer Fehler
		assert.equal(puts().at(-1)?.status, 412, 'Vorbedingung: der Server muss den veralteten Stand ablehnen');
		assert.equal(ctl.state, 'conflict', 'ein 412 muss „Nochmal speichern" auslösen, nicht einen generischen Fehler');
		assert.equal(wiz.radarAlertEnabled, true, 'bei 412 darf NICHT zurückgerollt werden — die Änderung bleibt sichtbar');
		assert.equal(
			(wiz.channels as Record<string, boolean>).sms,
			true,
			'bei 412 darf NICHT zurückgerollt werden — die Änderung bleibt sichtbar'
		);

		// WHEN: „Nochmal speichern"
		await ctl.retryConflict();

		// THEN (b)+(c)
		const letzter = puts().at(-1)!;
		assert.equal(letzter.status, 200, 'der Wiederholungs-PUT muss durchgehen');
		const body = server.storedBody(PRESET_ID) as Record<string, unknown>;
		assert.equal(body.radar_alert_enabled, true, 'der Wiederholungs-PUT muss den geänderten Radar-Wert tragen');
		assert.equal(
			(body.alert_channels as Record<string, boolean>).sms,
			true,
			'der Wiederholungs-PUT muss den geänderten SMS-ALARM-Kanal tragen'
		);
		assert.equal(ctl.state, 'idle', 'Endzustand „Gespeichert"');
		assert.ok(ctl.savedAt instanceof Date);
		assert.equal(wiz.radarAlertEnabled, true, 'die Oberfläche springt nicht auf den alten Stand zurück');
	});

	test('Gegenprobe: ein Nicht-412-Fehler rollt die Alarm-Änderung zurück und endet in error', async () => {
		// Gegenspieler-Client: der Server antwortet mit 500 (kein Konflikt).
		const kaputt: PutClient = {
			put: async () => {
				throw Object.assign(new Error('Serverfehler'), { status: 500, detail: 'Serverfehler' });
			}
		};
		const { wiz, ctl, speicherung } = aufbau(kaputt);

		wiz.radarAlertEnabled = true;
		speicherung.aenderungMelden();
		await ctl.flush();

		assert.equal(ctl.state, 'error', 'ein 500 ist kein Konflikt');
		assert.equal(wiz.radarAlertEnabled, false, 'bei einem Nicht-412-Fehler muss die Änderung zurückgerollt werden');
	});
});

// ── Issue #2375 (Test 6): „Nochmal speichern" sendet NUR die Eigenfelder ────
// Spec: docs/specs/bugfix/compare_konfliktschutz_teilfelder.md — Test 6, AC-2/AC-3/AC-7.
// Bis #2375 schickte der Wiederholungs-PUT den Voll-Spread der lokalen,
// veralteten Basis — der Name, den ein anderer Tab inzwischen gespeichert
// hatte, wurde still zurückgeschrieben. Der Ersatz-Server mergt hier wie Go
// (fehlende Felder bleiben), deshalb zeigt sich das am Server-Stand.
describe('Issue #2375: „Nochmal speichern" nach 412 — nur Eigenfelder, fremde Änderung überlebt', () => {
	test('Wiederholungs-PUT trägt exakt die Eigenfelder des Reiters (kein Fremdfeld)', async () => {
		const { erster, retryRumpf, zustandNach412, server } = await konfliktMitFremdemNamen('alarme', 'cp-2375-retry-alarme');
		assert.ok(erster?.ifMatch, 'Vorbedingung: der erste PUT muss If-Match tragen');
		assert.equal(erster.status, 412, 'Vorbedingung: der erste PUT muss am veralteten Stand scheitern');
		assert.equal(zustandNach412, 'conflict', 'Vorbedingung: „Nochmal speichern" wird angeboten');
		assert.equal(server.mitschnitt.filter((e) => e.method === 'PUT').at(-1)?.status, 200);
		assert.deepEqual(
			schluessel(retryRumpf),
			[...EIGENFELDER.alarme.top].sort(),
			`der Wiederholungs-PUT darf nur Eigenfelder tragen, gesendet: ${JSON.stringify(schluessel(retryRumpf))}`
		);
		assert.deepEqual(
			schluessel(retryRumpf.display_config),
			[...(EIGENFELDER.alarme.display ?? [])].sort(),
			'display_config des Wiederholungs-PUT darf nur die eigenen Schlüssel tragen'
		);
	});

	test('Fremdfeld überlebt den Retry: danach stehen der Name von A UND die Änderung von B auf dem Server', async () => {
		const { server } = await konfliktMitFremdemNamen('alarme', 'cp-2375-retry-alarme');
		const stand = server.stand('cp-2375-retry-alarme');
		assert.equal(stand.radar_alert_enabled, true, 'die Alarme-Änderung von B muss auf dem Server stehen');
		assert.equal(stand.name, 'Fremd von A', '„Nochmal speichern" hat den fremd gespeicherten Namen überschrieben');
	});
});
