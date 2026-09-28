// TDD — Alarme- und Versand-Reiter des Ortsvergleichs schreiben einander
// nicht zurück.
//
// Issue #2276 Scheibe S2 (Epic #2345): S2-AC-2 (kein Zurückschreiben alter
//   Alarmwerte durch den Nachbar-Reiter), S2-AC-3 (Basis erst bei Ausführung
//   in der Hub-Queue lesen).
// Issue #2276 Scheibe S5: S5-AC-11 (Legacy-Restfelder live aus wiz).
//
// 🔴 Issue #2293 Scheibe S2 (Nachtrag, Abschnitt 4 "Payload-Trennung"): S5-AC-2
//   und S5-AC-3 testeten ursprünglich EIN geteiltes Feld (`wiz.sendTelegram`/
//   `wiz.sendSms`), das sich Alarme (Schreiber) und Versand (Briefing-Snapshot)
//   teilten — genau die stille Kopplung, die #2293 S2 auflöst. Seit der
//   Payload-Trennung schreibt der Alarme-Reiter `wiz.channels` (Alarm-Kanäle),
//   der Versand-Reiter weiterhin `wiz.sendTelegram`/`sendSms` (Briefing-Kanäle)
//   — zwei disjunkte Felder. Beide Tests unten sind auf die NEUE Zusicherung
//   umgestellt (Gegenrichtung: ein Alarm-Kanal-Klick darf den Briefing-Kanal
//   NICHT beeinflussen), nicht gelöscht.
//
// Spec: docs/specs/modules/rework_2276_s2_alarme.md — AC-2, AC-3
//       docs/specs/modules/rework_2276_s5_versand.md — AC-11
//       docs/specs/modules/feat_2293_s2_compare_alarm_kanaele.md — Abschnitt 4
//
// 🔴 REWORK statt Import-Swap (S5): diese Datei baute den Versand-Zweig bisher
// intern nach (`flushPendingVersandSave` + eigener `hubPutQueue.enqueue`-
// Block) — das war der Nachbau von `handleVersandCommit` aus
// CompareTabs.svelte. Mit S5 speichert der Versand-Reiter selbst; der Nachbau
// entfällt und wird durch die echte Orchestrierung
// `erstelleVersandVergleichSpeicherung()` ersetzt. Ein Nachbau würde sonst
// eine Mechanik prüfen, die es nicht mehr gibt.
//
// Geprüft wird jeweils der tatsächlich abgeschickte PUT-Rumpf (Request), nicht
// der Server-Stand — `fakeTripServer.ts` ersetzt den Stand komplett und nimmt
// jedes Feld an.
//
// Zielschnittstelle (existiert noch NICHT → RED per ERR_MODULE_NOT_FOUND):
//   shared/versandVergleichSpeicherung.ts →
//     erstelleVersandVergleichSpeicherung, hydrateVersandFieldsFromPreset
//   (Vertrag s. versand_vergleich_speichert_selbst.test.ts).
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
import type { PutClient } from '../tripSpeicherung.ts';
import { erstelleAlarmeVergleichSpeicherung } from '../alarmeVergleichSpeicherung.ts';
import {
	erstelleVersandVergleichSpeicherung,
	hydrateVersandFieldsFromPreset
} from '../versandVergleichSpeicherung.ts';

const PRESET_ID = 'cp-2276-basis';
const PRESET_PFAD = `/api/compare/presets/${PRESET_ID}`;

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

/** EIN Wizard-Zustand für BEIDE Reiter — wie im Hub (`wizardState`). */
function hubZustand(preset: ComparePreset): Record<string, unknown> {
	const wiz: Record<string, unknown> = {};
	hydrateAlarmFieldsFromPreset(wiz, preset, []);
	Object.assign(wiz, hydrateVersandFieldsFromPreset(preset));
	return wiz;
}

describe('S2-AC-2: ein Nachbar-Reiter schreibt die gerade gespeicherten Alarmwerte NICHT zurück', () => {
	test('Alarm-PUT, danach Versand-PUT → der Rumpf des ZWEITEN PUT trägt die neuen Alarmwerte', async () => {
		let currentPreset = makePreset();
		const wiz = hubZustand(currentPreset);
		const ctl = createController();
		const hubPutQueue = createPutQueue();
		const gemeinsam = {
			client: api as PutClient,
			zustand: wiz,
			preset: () => currentPreset,
			enqueueHubWrite: <T,>(fn: () => Promise<T>) => hubPutQueue.enqueue(fn),
			onCompareUpdate: (p: ComparePreset) => {
				currentPreset = p;
			},
			saveController: ctl
		};
		const alarme = erstelleAlarmeVergleichSpeicherung({ ...gemeinsam, zustand: wiz });
		const versand = erstelleVersandVergleichSpeicherung(gemeinsam);

		// 1) Alarm-Änderung: Radar an, Kurzstil, Telegram-Schwelle, Metrik-Stufe
		wiz.radarAlertEnabled = true;
		wiz.telegramStyle = 'kurzform';
		wiz.channelThresholds = { email: 'gering', telegram: 'hoch', sms: 'gering', premium_sms: 'gering' };
		wiz.metricAlertLevels = { wind_gust: 'alarm' };
		alarme.aenderungMelden();
		await ctl.flush();
		assert.equal(gesendet.length, 1, 'Vorbedingung: der Alarm-PUT ist raus');
		assert.equal(gesendet[0].radar_alert_enabled, true, 'Vorbedingung: der Alarm-PUT trägt die Änderung');

		// 2) Versand-Reiter: Morgen-Uhrzeit ändern — über den ECHTEN Speicherweg
		wiz.morningTime = '07:15';
		versand.aenderungMelden();
		await ctl.flush();

		// THEN: Rumpf des ZWEITEN PUT
		assert.equal(gesendet.length, 2, 'genau zwei PUTs erwartet (Alarm, dann Versand)');
		const zweiter = gesendet[1];
		assert.equal(server.calls.filter((c) => c.method === 'PUT')[1].path, PRESET_PFAD);
		assert.equal(zweiter.morning_time, '07:15:00', 'Vorbedingung: der zweite PUT ist der Versand-PUT');
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
		assert.equal(gesendet[0].name, 'Ortsvergleich Basis', 'Vorbedingung: der erste PUT lief vor der Basis-Änderung');
		const zweiterPut = gesendet[1];
		assert.equal(zweiterPut.name, 'Neuer Name', 'der zweite PUT hat die Basis beim Einreihen eingefroren');
		assert.equal(zweiterPut.morning_time, '08:00:00', 'der zweite PUT hat die Basis beim Einreihen eingefroren');
		assert.equal(zweiterPut.radar_alert_enabled, true, 'die erste Alarm-Änderung muss erhalten bleiben');
		assert.equal(
			(zweiterPut.alert_channels as Record<string, boolean>).sms,
			true,
			'die zweite Alarm-Änderung muss im PUT stehen'
		);
		assert.equal(ctl.state, 'idle');
	});
});

describe('S5-AC-2 (Issue #2293 S2 aktualisiert): Alarme-SMS-Kanal und Versand-`sendSms` sind ENTKOPPELTE Felder', () => {
	// Vor #2293 S2 teilten sich Alarme- und Versand-Reiter dasselbe Feld
	// `wiz.sendSms` — dieser Test prüfte damals, dass der Versand-Speicherer es
	// LIVE liest (sonst überschriebe ein eingefrorener Snapshot die
	// Alarme-Änderung). Mit der Payload-Trennung (Implementation Details
	// Abschnitt 4) gibt es dieses geteilte Feld nicht mehr: der Alarme-Reiter
	// schreibt `wiz.channels.sms` (Alarm-Kanal), der Versand-Reiter liest
	// weiterhin `wiz.sendSms` (Briefing-Kanal) — beide völlig unabhängig. Die
	// NEUE Zusicherung ist deshalb die Gegenrichtung: ein Alarme-Klick auf den
	// SMS-ALARM-Kanal darf `send_sms` (Briefing) im Versand-PUT NICHT ändern.
	test('Alarme schaltet den SMS-ALARM-Kanal an, danach ändert Versand nur die Morgen-Uhrzeit → der Versand-PUT trägt weiterhin send_sms:false', async () => {
		let currentPreset = makePreset({ send_sms: false });
		const wiz = hubZustand(currentPreset);
		const ctl = createController();
		const hubPutQueue = createPutQueue();
		const gemeinsam = {
			client: api as PutClient,
			zustand: wiz,
			preset: () => currentPreset,
			enqueueHubWrite: <T,>(fn: () => Promise<T>) => hubPutQueue.enqueue(fn),
			onCompareUpdate: (p: ComparePreset) => {
				currentPreset = p;
			},
			saveController: ctl
		};
		const versand = erstelleVersandVergleichSpeicherung(gemeinsam);
		const alarme = erstelleAlarmeVergleichSpeicherung({ ...gemeinsam, zustand: wiz });
		assert.equal(wiz.sendSms, false, 'Vorbedingung: der Briefing-SMS-Kanal ist aus');

		// 1) Alarme-Reiter: SMS-ALARM-Kanal an (AlarmeTab.handleChannelToggle
		// mutiert seit #2293 S2 `wiz.channels`, NICHT mehr `wiz.sendSms`).
		wiz.channels = { ...(wiz.channels as Record<string, boolean>), sms: true };
		alarme.aenderungMelden();
		await ctl.flush();
		assert.equal(gesendet.length, 1, 'Vorbedingung: der Alarm-PUT ist raus');
		assert.equal(
			(gesendet[0].alert_channels as Record<string, boolean>).sms,
			true,
			'Vorbedingung: der Alarm-PUT trägt den eingeschalteten SMS-ALARM-Kanal'
		);

		// 2) Versand-Reiter: NUR die Morgen-Uhrzeit, der Briefing-Kanal bleibt unberührt
		wiz.morningTime = '07:15';
		versand.aenderungMelden();
		await ctl.flush();

		assert.equal(gesendet.length, 2, 'genau zwei PUTs erwartet (Alarm, dann Versand)');
		const versandPut = gesendet[1];
		assert.equal(versandPut.morning_time, '07:15:00', 'Vorbedingung: der zweite PUT ist der Versand-PUT');
		assert.equal(
			versandPut.send_sms,
			false,
			'der Versand-PUT darf den Briefing-Kanal NICHT vom Alarm-Kanal-Klick übernehmen (Entkopplung, AC-9)'
		);
		assert.equal(
			(wiz.channels as Record<string, boolean>).sms,
			true,
			'der Alarm-Kanal-Schalter der Oberfläche darf nicht zurückspringen'
		);
	});
});

describe('S5-AC-11: der Versand-PUT traegt die LIVE in wiz stehenden Legacy-Restfelder', () => {
	// Adversary-Befund F004: die explizite Weitergabe von
	// alertCooldownMinutes/alertQuietFrom/alertQuietTo in `baueVersandNutzlast`
	// war in KEINEM Test wirksam geprueft — solange `wiz` und `preset` dieselben
	// Werte tragen, liefert der `...original`-Spread dasselbe Ergebnis, ob die
	// drei Felder weitergereicht werden oder nicht. Der Fall, den die Weitergabe
	// wirklich schuetzt, ist derselbe Race wie AC-2 bei sendTelegram/sendSms:
	// der Alarme-Reiter hat die drei Felder bereits in `wiz` geaendert, sein
	// eigener PUT ist aber noch nicht durch — dann traegt der Versand-PUT den
	// NEUEN Wert, nicht den Bestand aus dem Preset.
	//
	// Mutations-Gegenprobe (M10, Spec AC-11): die drei Felder aus
	// `baueVersandNutzlast` entfernen ⇒ der Body faellt auf den Preset-Stand
	// zurueck ⇒ rot.
	test('Alarme aendert Cooldown/Stille Stunden in wiz, danach speichert Versand → der Versand-PUT traegt die NEUEN Werte', async () => {
		let currentPreset = makePreset({
			alert_cooldown_minutes: 90,
			alert_quiet_from: '22:00',
			alert_quiet_to: '07:00'
		});
		const wiz = hubZustand(currentPreset);
		const ctl = createController();
		const hubPutQueue = createPutQueue();
		const versand = erstelleVersandVergleichSpeicherung({
			client: api as PutClient,
			zustand: wiz,
			preset: () => currentPreset,
			enqueueHubWrite: <T,>(fn: () => Promise<T>) => hubPutQueue.enqueue(fn),
			onCompareUpdate: (p: ComparePreset) => {
				currentPreset = p;
			},
			saveController: ctl
		});
		assert.equal(wiz.alertCooldownMinutes, 90, 'Vorbedingung: der Bestandswert steht im Wizard-Zustand');

		// 1) Alarme-Reiter mutiert die drei Felder direkt in `wiz`
		// (AlertCooldownCard/AlertQuietHoursCard im vergleich-Zweig) — sein
		// eigener PUT ist noch nicht durch, `currentPreset` traegt weiter 90.
		wiz.alertCooldownMinutes = 30;
		wiz.alertQuietFrom = '23:30';
		wiz.alertQuietTo = '05:45';

		// 2) Versand-Reiter aendert NUR die Morgen-Uhrzeit und speichert
		wiz.morningTime = '07:15';
		versand.aenderungMelden();
		await ctl.flush();

		assert.equal(gesendet.length, 1, 'genau ein PUT erwartet (der Versand-PUT)');
		const versandPut = gesendet[0];
		assert.equal(versandPut.morning_time, '07:15:00', 'Vorbedingung: der PUT ist der Versand-PUT');
		assert.equal(
			versandPut.alert_cooldown_minutes,
			30,
			'der Versand-PUT schreibt den Cooldown auf den alten Preset-Stand zurueck (Datenverlust an einem Alarm-Zustellungsfeld)'
		);
		assert.equal(versandPut.alert_quiet_from, '23:30', 'Stille Stunden (von) fallen auf den Preset-Stand zurueck');
		assert.equal(versandPut.alert_quiet_to, '05:45', 'Stille Stunden (bis) fallen auf den Preset-Stand zurueck');
	});
});

describe('S5-AC-3 (Issue #2293 S2 aktualisiert): Rollback des Versand-PUT rührt den Alarm-Kanal-Bestand NICHT an', () => {
	// Vor #2293 S2 teilte sich `wiz.sendTelegram` zwischen Alarme (Schreiber)
	// und Versand (VersandSnapshot-Feld) — ein Rollback des Versand-PUT hätte
	// die Alarme-Änderung an genau diesem Feld treffen können, wäre der
	// Rollback NICHT diff-basiert. Seit der Payload-Trennung (Implementation
	// Details Abschnitt 4) schreibt der Alarme-Reiter `wiz.channels`, ein Feld,
	// das `VersandSnapshot`/`rollbackVersandSnapshot` gar nicht kennen — die
	// Zusicherung ist jetzt strukturell statt diff-basiert erzwungen. Dieser
	// Test bewacht, dass sie es auch bleibt.
	test('Alarme setzt den Telegram-ALARM-Kanal während des Versand-PUT → der Rollback lässt ihn unangetastet, nimmt aber die eigene Uhrzeit zurück', async () => {
		let basis = makePreset({ send_telegram: false });
		const wiz = hubZustand(basis);
		assert.equal(
			(wiz.channels as Record<string, boolean>).telegram,
			false,
			'Vorbedingung: der Telegram-ALARM-Kanal ist aus (materialisiert aus send_telegram)'
		);

		// Der Versand-PUT hängt an einem Tor fest und scheitert dann mit 500 —
		// deterministisch statt zeitabhängig.
		let torOeffnen!: () => void;
		const tor = new Promise<void>((r) => {
			torOeffnen = r;
		});
		let putGestartet!: () => void;
		const gestartet = new Promise<void>((r) => {
			putGestartet = r;
		});
		const haengenderClient: PutClient = {
			put: async () => {
				putGestartet();
				await tor;
				throw Object.assign(new Error('Netzwerkfehler (simuliert)'), { status: 500 });
			}
		};

		const versandCtl = createController();
		const versandQueue = createPutQueue();
		const versand = erstelleVersandVergleichSpeicherung({
			client: haengenderClient,
			zustand: wiz,
			preset: () => basis,
			enqueueHubWrite: (fn) => versandQueue.enqueue(fn),
			onCompareUpdate: (p: ComparePreset) => {
				basis = p;
			},
			saveController: versandCtl
		});
		// Eigener Controller + eigene Queue für den Alarme-Zweig: im Hub teilen
		// sich beide Reiter Queue und Controller, hier würde der hängende
		// Versand-PUT den Alarm-PUT dahinter blockieren — geprüft wird aber die
		// Rollback-ENTSCHEIDUNG, nicht die Serialisierung (die prüft
		// hub_put_queue.test.ts).
		const alarmCtl = createController();
		const alarme = erstelleAlarmeVergleichSpeicherung({
			client: api,
			zustand: wiz,
			preset: () => basis,
			enqueueHubWrite: (fn) => createPutQueue().enqueue(fn),
			onCompareUpdate: (p: ComparePreset) => {
				basis = p;
			},
			saveController: alarmCtl
		});

		// 1) Versand-Reiter ändert NUR die Morgen-Uhrzeit → PUT geht raus und hängt
		wiz.morningTime = '07:15';
		versand.aenderungMelden();
		const versandLauf = versandCtl.flush();
		await gestartet;

		// 2) Währenddessen: Alarme-Reiter schaltet den Telegram-ALARM-Kanal AN
		// und speichert erfolgreich (wiz.channels statt wiz.sendTelegram, AC-9).
		wiz.channels = { ...(wiz.channels as Record<string, boolean>), telegram: true };
		alarme.aenderungMelden();
		await alarmCtl.flush();
		assert.equal(
			(gesendet.at(-1)?.alert_channels as Record<string, boolean> | undefined)?.telegram,
			true,
			'Vorbedingung: die Alarme-Änderung ist gespeichert'
		);

		// 3) Jetzt scheitert der Versand-PUT → Rollback
		torOeffnen();
		await versandLauf;

		assert.equal(versandCtl.state, 'error', 'Vorbedingung: der Versand-PUT ist gescheitert');
		assert.equal(
			(wiz.channels as Record<string, boolean>).telegram,
			true,
			'der Versand-Rollback darf den Alarm-Kanal-Bestand NICHT anfassen — er kennt `channels` gar nicht (strukturelle Trennung, AC-9)'
		);
		assert.equal(wiz.morningTime, '06:30', 'das eigene, gescheiterte Feld MUSS zurückgerollt werden');
	});
});
