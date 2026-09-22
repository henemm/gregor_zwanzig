// TDD RED — Issue #2276 Scheibe S2 (Epic #2345): der Alarme-Reiter des
// Ortsvergleichs speichert SELBST über den Speicher-Controller der Seite, wie
// bei der Tour — nicht mehr über Wrapper + `handleAlarmeCommit` in CompareTabs.
//
// Spec: docs/specs/modules/rework_2276_s2_alarme.md
//   AC-1 (genau ein PUT, Endzustand gespeichert), AC-5 (No-Op stempelt kein
//   „Gespeichert"), AC-10 (Keepalive-Option erreicht den PUT)
//
// WARUM AUF MODULEBENE: `svelte/server` führt weder `$effect` noch Ereignisse
// aus, ein DOM gibt es in diesem Prüfstand nicht (s. telegram_kurzstil_shared_
// toggle.test.ts:20). Der `$effect` des Alarme-Reiters darf deshalb nur noch
// DELEGIEREN: an `erstelleAlarmeVergleichSpeicherung(...).aenderungMelden()`.
// Diff-Gate, Basis-Lesen, Queue, Rückmeldung und Rollback liegen im Modul —
// genau dort werden sie hier geprüft.
//
// Zielschnittstelle (existiert noch NICHT → RED per ERR_MODULE_NOT_FOUND):
//
//   frontend/src/lib/components/shared/alarmeVergleichSpeicherung.ts
//   erstelleAlarmeVergleichSpeicherung({
//     client,            // PutClient (echtes `api`)
//     wiz,               // Wizard-Zustand (Alarmfelder, wird bei Nicht-412 zurückgerollt)
//     preset,            // () => ComparePreset — Basis, gelesen ERST bei Ausführung
//     enqueueHubWrite,   // hubPutQueue.enqueue — Serialisierung mit den Nachbar-Reitern
//     onCompareUpdate,   // (antwort: ComparePreset) => void — Basis-Rückmeldung
//     saveController     // SaveStatus der Seite
//   }): { aenderungMelden(): void }
//
//   Anfangs-Baseline (lastPersistedAlarmSnapshot) = Alarmstand von `wiz` beim
//   Erzeugen (nach der Hydration). `aenderungMelden()` vergleicht den aktuellen
//   Stand damit: ohne Unterschied → kein schedule(), ein evtl. ausstehender
//   Vorgang wird verworfen, markPristine(); mit Unterschied → schedule(SaveFn).
//
// Prüfstand: ECHTES `api` gegen `fakeTripServer.ts` (Compare-Preset-Pfad mit
// ETag), ECHTE `createPutQueue`, ECHTE SaveStatus-Instanz.
//
// Ausführen:
//   cd frontend && npm test -- src/lib/components/shared/__tests__/alarme_vergleich_speichert_selbst.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../api.ts';
import { clearEtagRegistry } from '../../../etagRegistry.ts';
import { SaveStatus } from '../../../stores/saveStatusStore.svelte.ts';
import { createFakeTripServer, type FakeTripServer } from '../../../__tests__/fakeTripServer.ts';
import type { ComparePreset } from '../../../types.ts';
import { createPutQueue, hydrateAlarmFieldsFromPreset } from '../../compare/compareHubWizardBridge.ts';
import { erstelleAlarmeVergleichSpeicherung } from '../alarmeVergleichSpeicherung.ts';

const PRESET_ID = 'cp-2276-s2';
const PRESET_PFAD = `/api/compare/presets/${PRESET_ID}`;

function makePreset(overrides: Partial<ComparePreset> = {}): ComparePreset {
	return {
		id: PRESET_ID,
		name: 'Ortsvergleich Alarme',
		location_ids: ['loc-a', 'loc-b', 'loc-c'],
		schedule: 'daily',
		profil: 'wandern',
		hour_from: 6,
		hour_to: 9,
		forecast_hours: 48,
		empfaenger: ['a@example.com'],
		created_at: '2026-01-01T00:00:00Z',
		official_alerts_enabled: true,
		official_warnings: { enabled: true },
		radar_alert_enabled: false,
		send_telegram: true,
		send_sms: false,
		send_premium_sms: false,
		alert_cooldown_minutes: 30,
		alert_quiet_from: '22:00',
		alert_quiet_to: '07:00',
		corridors: [],
		display_config: { metric_alert_levels: { wind_gust: 'warn' }, telegram_style: 'rich' },
		...overrides
	};
}

/** Echte SaveStatus-Instanz ohne Konstruktor (Runen-Felder, s. saveStatus.test.ts),
 *  MIT Kennung {typ:'vergleich', id} wie künftig in routes/compare/[id]/+page.svelte. */
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

/** Wizard-Stand, hydriert mit der ECHTEN Hydration des Hubs. */
function hydratedWiz(preset: ComparePreset): Record<string, unknown> {
	const wiz: Record<string, unknown> = {};
	hydrateAlarmFieldsFromPreset(wiz, preset, []);
	return wiz;
}

let server: FakeTripServer;

beforeEach(() => {
	clearEtagRegistry();
	server = createFakeTripServer();
	server.install();
});

afterEach(() => server.restore());

const puts = () => server.calls.filter((c) => c.method === 'PUT');

function aufbau(preset = makePreset()) {
	let basis = preset;
	const wiz = hydratedWiz(basis);
	const ctl = createController();
	const queue = createPutQueue();
	const rueckmeldungen: ComparePreset[] = [];
	const speicherung = erstelleAlarmeVergleichSpeicherung({
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
	return { wiz, ctl, queue, speicherung, rueckmeldungen, basis: () => basis };
}

describe('AC-1: eine Alarm-Änderung speichert über den Controller — genau ein PUT, Endzustand gespeichert', () => {
	test('Radar-Schalter an → schedule, Flush → genau EIN PUT mit dem neuen Wert, state idle, savedAt gesetzt', async () => {
		const { wiz, ctl, speicherung, rueckmeldungen } = aufbau();

		wiz.radarAlertEnabled = true;
		speicherung.aenderungMelden();

		assert.equal(ctl.hasPending, true, 'die Änderung muss im Speicher-Takt des Controllers liegen (schedule)');
		assert.equal(ctl.state, 'saving', 'während des Debounce-Fensters darf nie „Gespeichert" stehen');

		await ctl.flush();

		assert.equal(puts().length, 1, 'genau EIN PUT erwartet');
		const put = puts()[0];
		assert.equal(put.path, PRESET_PFAD, 'der PUT muss auf die Ortsvergleich-Ressource gehen');
		assert.equal(put.status, 200);
		const body = server.storedBody(PRESET_ID) as Record<string, unknown>;
		assert.equal(body.radar_alert_enabled, true, 'der geänderte Radar-Schalter muss im Rumpf stehen');
		assert.equal(body.name, 'Ortsvergleich Alarme', 'Voll-Spread: Nicht-Alarmfelder bleiben im Rumpf erhalten');
		assert.equal(ctl.state, 'idle', 'Endzustand „Gespeichert"');
		assert.ok(ctl.savedAt instanceof Date, 'savedAt muss nach echtem Erfolg gestempelt sein');
		assert.equal(rueckmeldungen.length, 1, 'onCompareUpdate genau einmal mit der Server-Antwort');
		assert.equal(rueckmeldungen[0].radar_alert_enabled, true);
	});

	test('mehrere Meldungen derselben Geste innerhalb des Debounce-Fensters → trotzdem nur EIN PUT', async () => {
		const { wiz, ctl, speicherung } = aufbau();

		wiz.radarAlertEnabled = true;
		speicherung.aenderungMelden();
		wiz.channelThresholds = { telegram: 'hoch', sms: 'gering', premium_sms: 'gering', email: 'gering' };
		speicherung.aenderungMelden();
		speicherung.aenderungMelden();

		await ctl.flush();

		assert.equal(puts().length, 1, 'Letzter gewinnt: drei Meldungen, ein PUT');
		const body = server.storedBody(PRESET_ID) as Record<string, unknown>;
		assert.equal(body.radar_alert_enabled, true);
		assert.deepEqual(
			(body.alert_channel_thresholds as Record<string, string>).telegram,
			'hoch',
			'die zweite Änderung derselben Geste muss im EINEN PUT enthalten sein'
		);
	});

	test('nach erfolgreichem Speichern wandert die Baseline: erneute Meldung ohne Änderung → kein zweiter PUT', async () => {
		const { wiz, ctl, speicherung } = aufbau();

		wiz.radarAlertEnabled = true;
		speicherung.aenderungMelden();
		await ctl.flush();
		assert.equal(puts().length, 1);

		speicherung.aenderungMelden();
		await ctl.flush();

		assert.equal(puts().length, 1, 'der bereits gespeicherte Stand darf nicht erneut gesendet werden');
		assert.equal(ctl.hasPending, false);
	});
});

describe('AC-5: No-Op stempelt kein „Gespeichert"', () => {
	test('Reiter öffnen ohne Änderung → kein PUT, kein schedule, savedAt unverändert', async () => {
		const { ctl, speicherung } = aufbau();
		const alterStempel = new Date('2026-09-01T10:00:00Z');
		(ctl as unknown as { savedAt: Date }).savedAt = alterStempel;

		speicherung.aenderungMelden();

		assert.equal(ctl.hasPending, false, 'ohne Unterschied zur Baseline darf nichts eingeplant werden');
		assert.notEqual(ctl.state, 'saving', 'ohne Änderung darf kein „Speichert…" erscheinen');
		await ctl.flush();
		assert.equal(puts().length, 0, 'kein PUT ohne inhaltliche Änderung');
		assert.equal(ctl.savedAt, alterStempel, 'savedAt darf ohne echten Speichervorgang nicht neu gestempelt werden');
	});

	test('Wert hin und wieder zurück → kein PUT, savedAt unverändert, Zustand idle', async () => {
		const { wiz, ctl, speicherung } = aufbau();
		const alterStempel = new Date('2026-09-01T10:00:00Z');
		(ctl as unknown as { savedAt: Date }).savedAt = alterStempel;

		wiz.radarAlertEnabled = true;
		speicherung.aenderungMelden();
		wiz.radarAlertEnabled = false;
		speicherung.aenderungMelden();

		assert.equal(ctl.hasPending, false, 'der zurückgenommene Vorgang darf nicht mehr ausstehen');
		await ctl.flush();

		assert.equal(puts().length, 0, 'Hin-und-zurück ist keine Änderung — kein PUT');
		assert.equal(ctl.savedAt, alterStempel, 'kein frischer „Gespeichert HH:MM"-Stempel ohne echten Speichervorgang');
		assert.equal(ctl.state, 'idle');
	});
});

describe('AC-10: die Entlade-Option (keepalive) erreicht den PUT', () => {
	test('Flush beim Entladen → PUT mit keepalive:true', async () => {
		const { wiz, ctl, speicherung } = aufbau();
		await api.get(PRESET_PFAD); // Stand bekannt, wie nach dem Laden der Seite

		wiz.sendSms = true;
		speicherung.aenderungMelden();
		await ctl.flush({ keepalive: true });

		assert.equal(puts().length, 1, 'genau ein PUT erwartet');
		assert.equal(puts()[0].path, PRESET_PFAD);
		assert.equal(puts()[0].keepalive, true, 'die Option keepalive:true des Wächters wurde verschluckt');
		assert.equal((server.storedBody(PRESET_ID) as Record<string, unknown>).send_sms, true);
	});

	test('Gegenprobe: regulärer Flush → PUT ohne keepalive', async () => {
		const { wiz, ctl, speicherung } = aufbau();

		wiz.sendSms = true;
		speicherung.aenderungMelden();
		await ctl.flush();

		assert.equal(puts().length, 1);
		assert.equal(puts()[0].keepalive, false, 'ohne Entladen darf kein keepalive gesetzt werden');
	});
});
