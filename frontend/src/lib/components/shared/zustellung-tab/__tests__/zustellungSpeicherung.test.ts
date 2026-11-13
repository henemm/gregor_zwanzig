// TDD RED — Issue #2795 S3b, Teilschritt 1b (Neubau Reiter „Zustellung“), Speicherer `zustellungSpeicherung.ts`.
// Spec: docs/specs/modules/feat_2795_s3b_teil1_zustellung.md — Implementation Details §3;
// AC-4, AC-8 (nichts gespeichert), AC-10 (end_date), AC-17 (alert_channel_thresholds), AC-23 (send_email Orte),
// AC-24 (Stille Stunden), AC-26 (Cooldown), AC-27 (alert_metric_channels nie geschrieben), AC-32 (nur Diff,
// Fremdfelder unveraendert), AC-33 (EIN Speicherer, zwei Nutzlast-Teile `versand` / `alarme`).
//
// Der Reiter hat genau EINEN Speicherer. Er bildet aus Basis-Stand (zuletzt geladen) und aktuellem
// Formularstand (`ZustellungStand`, siehe zustellungModell.test.ts) zwei Nutzlast-Teile:
//   - Teil `versand` (Owner 'versand'): Morgen/Abend-Zeit und -Schalter, Briefing-Kanalschalter
//     (send_email/send_telegram/send_sms/send_premium_sms), Laufzeit Orte (end_date).
//     Trip: unter `report_config` (Server-Merge je Schluessel); Orte: Top-Level.
//   - Teil `alarme` (Owner 'alarme'): alert_channels, alert_channel_thresholds, alert_quiet_from/_to,
//     alert_cooldown_minutes. Immer Top-Level.
// Gesendet werden NUR die geaenderten Felder. `alert_metric_channels`, `ampel`, `display_config`,
// `report_config` (Orte), `official_warnings`, `telegram_style` und alle Uebergangsblock-Felder stehen nie
// in einer Nutzlast des Reiters.
//
// Festgelegte API (shared/zustellung-tab/zustellungSpeicherung.ts):
//   zustellungNutzlast(context: 'route' | 'vergleich', vorher: ZustellungStand, jetzt: ZustellungStand)
//       -> { versand: Record<string, unknown> | null; alarme: Record<string, unknown> | null }  // null = nichts geaendert
//     Uhrzeiten gehen als „HH:MM:SS“ (toHHMMSS) hinaus; Stille Stunden „HH:MM“; abgeschaltete Stille Stunden
//     als `alert_quiet_from: null, alert_quiet_to: null` (fehlender Schluessel hiesse „behalten“, #2211);
//     „Bis auf Weiteres“ als `end_date: ''` (oder null); alert_channels/alert_channel_thresholds immer mit
//     allen vier Kanaelen.
//   erstelleZustellungSpeicherung(opt: {
//       context: 'route' | 'vergleich';
//       id: string;                                     // Trip-ID bzw. Preset-ID
//       client: PutClient;                              // api (If-Match, Server-Merge)
//       saveController: SaveStatus;                     // schedule(fn, ms, 'versand' | 'alarme')
//       basis: ZustellungStand;                         // Stand nach Hydration
//       enqueueHubWrite?: <T>(fn: () => Promise<T>) => Promise<T>; // nur vergleich (Hub-Queue)
//       onAntwort?: (antwort: unknown) => void;
//   }) -> { aenderungMelden(jetzt: ZustellungStand): void }
//     PUT-Ziel: Trip `/api/trips/{id}`, Orte `/api/compare/presets/{id}`. Eine Uhrzeit ausserhalb des
//     Viertelstunden-Rasters (zeitFehler ≠ null) wird NICHT gesendet (AC-8).
//
// RED heute: zustellungSpeicherung.ts / zustellungModell.ts existieren nicht.
//
//   cd frontend && npm test -- src/lib/components/shared/zustellung-tab/__tests__/zustellungSpeicherung.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../../api.ts';
import { clearEtagRegistry } from '../../../../etagRegistry.ts';
import { createPutQueue } from '../../../compare/compareHubPersistenz.ts';
import { createGoMergeServer, vollerVergleich, type GoMergeServer } from '../../__tests__/goMergeServerPruefstand.ts';
import { createController } from '../../wetter-tab/__tests__/wertebereicheVergleichPruefstand.ts';
import { hhmm, presetVoll, tripVoll, zustellungModell, zustellungSpeicherung, type Json } from './zustellungTabDaten.ts';

const VERSAND_TRIP_RC = ['enabled', 'morning_enabled', 'evening_enabled', 'morning_time', 'evening_time', 'send_email', 'send_telegram', 'send_sms', 'send_premium_sms'];
const VERSAND_ORTE = ['morning_enabled', 'evening_enabled', 'morning_time', 'evening_time', 'send_email', 'send_telegram', 'send_sms', 'send_premium_sms', 'end_date'];
const ALARME = ['alert_channels', 'alert_channel_thresholds', 'alert_quiet_from', 'alert_quiet_to', 'alert_cooldown_minutes'];
const NIE = ['alert_metric_channels', 'ampel', 'display_config', 'official_warnings', 'telegram_style', 'radar_alert_enabled', 'metric_alert_levels'];

const keys = (o: unknown) => Object.keys((o as Record<string, unknown>) ?? {}).sort();
const kopie = <T>(x: T): T => JSON.parse(JSON.stringify(x));

async function basis(context: 'route' | 'vergleich'): Promise<{ m: Json; s: Json; vorher: Json }> {
	const m = await zustellungModell();
	const s = await zustellungSpeicherung();
	const vorher = context === 'route' ? m.standAusTrip(tripVoll()) : m.standAusPreset(presetVoll());
	return { m, s, vorher };
}

/** Jede Nutzlast des Reiters enthaelt nur Eigenfelder ihres Teils — nie ein Fremdfeld (AC-27, AC-32). */
function pruefeNurEigenfelder(context: 'route' | 'vergleich', n: Json, wo: string): void {
	if (n.versand) {
		if (context === 'route') {
			assert.deepEqual(keys(n.versand), ['report_config'], `${wo}: Trip-Versand-Teil ausser report_config: ${keys(n.versand)}`);
			for (const k of keys(n.versand.report_config)) assert.ok(VERSAND_TRIP_RC.includes(k), `${wo}: Fremdfeld report_config.${k} im Versand-Teil`);
		} else {
			for (const k of keys(n.versand)) assert.ok(VERSAND_ORTE.includes(k), `${wo}: Fremdfeld ${k} im Versand-Teil`);
		}
	}
	if (n.alarme) for (const k of keys(n.alarme)) assert.ok(ALARME.includes(k), `${wo}: Fremdfeld ${k} im Alarm-Teil`);
	const alles = JSON.stringify(n);
	for (const k of NIE) assert.ok(!alles.includes(`"${k}"`), `${wo}: ${k} darf der Reiter nie schreiben`);
}

// ── Reine Nutzlast-Bildung ──────────────────────────────────────────────────

for (const context of ['route', 'vergleich'] as const) {
	describe(`AC-32/AC-33 (${context}): nur geaenderte Felder, Teil versand vs. Teil alarme`, () => {
		test(`ac32_${context}_unveraendert_keine_nutzlast`, async () => {
			const { s, vorher } = await basis(context);
			assert.deepEqual(s.zustellungNutzlast(context, vorher, kopie(vorher)), { versand: null, alarme: null });
		});

		test(`ac4_ac32_${context}_nur_morgenzeit_0645`, async () => {
			const { s, vorher } = await basis(context);
			const n = s.zustellungNutzlast(context, vorher, { ...kopie(vorher), morgenZeit: '06:45' });
			assert.equal(n.alarme, null, 'Zeitaenderung darf den Alarm-Teil nicht senden');
			const teil = context === 'route' ? n.versand?.report_config : n.versand;
			assert.deepEqual(keys(teil), ['morning_time'], `nur morning_time erwartet, gesendet: ${JSON.stringify(n.versand)}`);
			assert.equal(hhmm(teil.morning_time), '06:45', '06:45 wird ungekappt gesendet');
			assert.match(String(teil.morning_time), /^06:45(:00)?$/);
			pruefeNurEigenfelder(context, n, 'Morgenzeit');
		});

		test(`ac32_${context}_nur_dringlichkeit_nur_alarm_teil`, async () => {
			const { s, vorher } = await basis(context);
			const jetzt = kopie(vorher);
			jetzt.dringlichkeit.email = 'MODERATE';
			const n = s.zustellungNutzlast(context, vorher, jetzt);
			assert.equal(n.versand, null, 'nur Dringlichkeit geaendert ⇒ kein Versand-Teil');
			assert.deepEqual(keys(n.alarme), ['alert_channel_thresholds']);
			assert.equal(n.alarme.alert_channel_thresholds.email, 'MODERATE');
			assert.deepEqual(keys(n.alarme.alert_channel_thresholds), ['email', 'premium_sms', 'sms', 'telegram'], 'alle vier Kanaele explizit');
			pruefeNurEigenfelder(context, n, 'Dringlichkeit');
		});

		test(`ac17_${context}_alarm_kanal_an_sendet_alert_channels_vollstaendig`, async () => {
			const { s, vorher } = await basis(context);
			const jetzt = kopie(vorher);
			jetzt.alarme.premium_sms = true;
			const n = s.zustellungNutzlast(context, vorher, jetzt);
			assert.equal(n.versand, null);
			assert.deepEqual(keys(n.alarme), ['alert_channels']);
			assert.deepEqual(n.alarme.alert_channels, { ...vorher.alarme, premium_sms: true });
			pruefeNurEigenfelder(context, n, 'Alarm-Kanal');
		});

		test(`ac33_${context}_briefing_kanal_ist_versand_teil`, async () => {
			const { s, vorher } = await basis(context);
			const jetzt = kopie(vorher);
			jetzt.briefing.sms = true;
			const n = s.zustellungNutzlast(context, vorher, jetzt);
			assert.equal(n.alarme, null, 'Briefing-Schalter gehoert dem Versand-Teil, nicht dem Alarm-Teil');
			const teil = context === 'route' ? n.versand?.report_config : n.versand;
			assert.deepEqual(keys(teil), ['send_sms']);
			assert.equal(teil.send_sms, true);
			pruefeNurEigenfelder(context, n, 'Briefing-Kanal');
		});

		test(`ac33_${context}_beide_teile_bei_gemischter_aenderung`, async () => {
			const { s, vorher } = await basis(context);
			const jetzt = { ...kopie(vorher), abendZeit: '19:15', cooldown: 30 };
			const n = s.zustellungNutzlast(context, vorher, jetzt);
			const teil = context === 'route' ? n.versand?.report_config : n.versand;
			assert.deepEqual(keys(teil), ['evening_time']);
			assert.equal(hhmm(teil.evening_time), '19:15');
			assert.deepEqual(n.alarme, { alert_cooldown_minutes: 30 });
			pruefeNurEigenfelder(context, n, 'gemischt');
		});

		test(`ac24_${context}_stille_stunden_zeit_und_aus`, async () => {
			const { s, vorher } = await basis(context);
			const zeit = s.zustellungNutzlast(context, vorher, { ...kopie(vorher), stilleVon: '23:00' });
			assert.equal(zeit.versand, null);
			assert.deepEqual(keys(zeit.alarme), ['alert_quiet_from']);
			assert.equal(hhmm(zeit.alarme.alert_quiet_from), '23:00');
			const aus = s.zustellungNutzlast(context, vorher, { ...kopie(vorher), stilleAn: false });
			assert.deepEqual(aus.alarme, { alert_quiet_from: null, alert_quiet_to: null }, 'Ausschalten loescht beide Felder explizit');
		});

		test(`ac26_${context}_cooldown`, async () => {
			const { s, vorher } = await basis(context);
			const n = s.zustellungNutzlast(context, vorher, { ...kopie(vorher), cooldown: 90 });
			assert.deepEqual(n, { versand: null, alarme: { alert_cooldown_minutes: 90 } });
		});

		test(`ac27_${context}_alert_metric_channels_nie_auch_nicht_bei_vollem_wechsel`, async () => {
			const { s, vorher } = await basis(context);
			const jetzt = kopie(vorher);
			for (const k of ['email', 'telegram', 'sms', 'premium_sms']) {
				jetzt.alarme[k] = !jetzt.alarme[k];
				jetzt.briefing[k] = !jetzt.briefing[k];
				jetzt.dringlichkeit[k] = 'HIGH';
			}
			Object.assign(jetzt, { morgenAn: !jetzt.morgenAn, abendAn: !jetzt.abendAn, morgenZeit: '05:15', abendZeit: '20:30', stilleAn: false, cooldown: 15 });
			if (context === 'vergleich') jetzt.endDate = '2027-03-31';
			const n = s.zustellungNutzlast(context, vorher, jetzt);
			assert.ok(n.versand && n.alarme, 'beide Teile erwartet');
			pruefeNurEigenfelder(context, n, 'Vollwechsel');
		});
	});
}

describe('AC-23: E-Mail-Briefing der Orte als send_email', () => {
	test('ac23_orte_email_aus_und_wieder_an', async () => {
		const { s, vorher } = await basis('vergleich');
		const aus = s.zustellungNutzlast('vergleich', vorher, { ...kopie(vorher), briefing: { ...vorher.briefing, email: false } });
		assert.deepEqual(aus, { versand: { send_email: false }, alarme: null });
		const anVorher = { ...kopie(vorher), briefing: { ...vorher.briefing, email: false } };
		const an = s.zustellungNutzlast('vergleich', anVorher, { ...kopie(anVorher), briefing: { ...anVorher.briefing, email: true } });
		assert.deepEqual(an, { versand: { send_email: true }, alarme: null });
	});

	test('ac23_trip_email_unter_report_config', async () => {
		const { s, vorher } = await basis('route');
		const aus = s.zustellungNutzlast('route', vorher, { ...kopie(vorher), briefing: { ...vorher.briefing, email: false } });
		assert.deepEqual(aus, { versand: { report_config: { send_email: false } }, alarme: null });
	});
});

describe('AC-10: Laufzeit der Orte als end_date', () => {
	test('ac10_bis_datum_und_zurueck', async () => {
		const { s, vorher } = await basis('vergleich');
		assert.equal(vorher.endDate, null, 'Messaufbau: Preset ohne end_date');
		const datum = s.zustellungNutzlast('vergleich', vorher, { ...kopie(vorher), endDate: '2027-03-31' });
		assert.deepEqual(datum, { versand: { end_date: '2027-03-31' }, alarme: null });
		const mitDatum = { ...kopie(vorher), endDate: '2027-03-31' };
		const offen = s.zustellungNutzlast('vergleich', mitDatum, { ...kopie(mitDatum), endDate: null });
		assert.deepEqual(keys(offen.versand), ['end_date']);
		assert.ok(offen.versand.end_date === '' || offen.versand.end_date === null, `„Bis auf Weiteres“ loescht end_date, gesendet: ${JSON.stringify(offen.versand.end_date)}`);
	});

	test('ac10_trip_schreibt_nie_end_date', async () => {
		const { s, vorher } = await basis('route');
		const n = s.zustellungNutzlast('route', vorher, { ...kopie(vorher), endDate: '2027-03-31' });
		assert.ok(!JSON.stringify(n).includes('end_date'), 'Trip-Laufzeit kommt aus den Etappen, der Reiter schreibt kein end_date');
	});
});

// ── Orchestrierung: ein Speicherer, Server-Merge, Fremdfelder ───────────────

const PRESET_ID = 'cp-2795-zustellung';
let server: GoMergeServer;

describe('AC-32/AC-33 (vergleich): EIN Speicherer gegen den Go-Merge-Pruefstand', () => {
	beforeEach(() => {
		clearEtagRegistry();
		server = createGoMergeServer({ [PRESET_ID]: vollerVergleich(PRESET_ID) });
		server.install();
	});
	afterEach(() => server.restore());

	async function hub(): Promise<{ m: Json; sp: Json; ctl: Json; vorher: Json }> {
		const m = await zustellungModell();
		const s = await zustellungSpeicherung();
		const ctl = createController(PRESET_ID);
		const queue = createPutQueue();
		const vorher = m.standAusPreset(server.stand(PRESET_ID));
		const sp = s.erstelleZustellungSpeicherung({
			context: 'vergleich',
			id: PRESET_ID,
			client: api,
			saveController: ctl,
			basis: vorher,
			enqueueHubWrite: <T>(fn: () => Promise<T>) => queue.enqueue(fn)
		});
		return { m, sp, ctl, vorher };
	}

	test('ac32_nur_morgenzeit_ein_put_fremdfelder_unveraendert', async () => {
		const { sp, ctl, vorher } = await hub();
		const davor = server.stand(PRESET_ID);
		sp.aenderungMelden({ ...kopie(vorher), morgenZeit: '06:45' });
		await ctl.flush();
		const ruempfe = server.putRuempfe();
		assert.equal(ruempfe.length, 1, 'genau ein PUT');
		assert.deepEqual(keys(ruempfe[0]), ['morning_time'], `Nutzlast: ${JSON.stringify(ruempfe[0])}`);
		const danach = server.stand(PRESET_ID);
		assert.equal(hhmm(danach.morning_time), '06:45', 'AC-4: 06:45 gespeichert');
		const ohneZeit = (x: Json) => ({ ...x, morning_time: undefined });
		assert.deepEqual(ohneZeit(danach), ohneZeit(davor), 'AC-32: kein anderes Feld veraendert (ampel, display_config, alert_channels, …)');
	});

	test('ac32_nur_dringlichkeit_ein_put_nur_alarm_teil', async () => {
		const { sp, ctl, vorher } = await hub();
		const jetzt = kopie(vorher);
		jetzt.dringlichkeit.telegram = 'MODERATE';
		sp.aenderungMelden(jetzt);
		await ctl.flush();
		const ruempfe = server.putRuempfe();
		assert.equal(ruempfe.length, 1);
		assert.deepEqual(keys(ruempfe[0]), ['alert_channel_thresholds']);
		assert.equal((server.stand(PRESET_ID).alert_channel_thresholds as Json).telegram, 'MODERATE');
	});

	test('ac33_gemischte_aenderung_zwei_puts_getrennte_teile', async () => {
		const { sp, ctl, vorher } = await hub();
		sp.aenderungMelden({ ...kopie(vorher), abendZeit: '19:15', cooldown: 30 });
		await ctl.flush();
		await ctl.flush();
		const ruempfe = server.putRuempfe();
		assert.equal(ruempfe.length, 2, `zwei Nutzlast-Teile = zwei PUTs, gesendet: ${JSON.stringify(ruempfe)}`);
		const teile = ruempfe.map((r) => keys(r).join(',')).sort();
		assert.deepEqual(teile, ['alert_cooldown_minutes', 'evening_time']);
		const st = server.stand(PRESET_ID);
		assert.equal(hhmm(st.evening_time), '19:15');
		assert.equal(st.alert_cooldown_minutes, 30);
	});

	test('ac8_rasterfremde_zeit_wird_nicht_gesendet', async () => {
		const { sp, ctl, vorher } = await hub();
		sp.aenderungMelden({ ...kopie(vorher), morgenZeit: '06:50' });
		await ctl.flush();
		assert.equal(server.putRuempfe().length, 0, '06:50 darf nicht gespeichert werden');
		assert.equal(server.stand(PRESET_ID).morning_time, '06:30:00', 'gespeicherter Wert bleibt unveraendert');
	});

	test('ac23_send_email_aus_im_preset', async () => {
		const { sp, ctl, vorher } = await hub();
		assert.equal(vorher.briefing.email, true, 'Messaufbau: Preset ohne send_email gilt als an');
		sp.aenderungMelden({ ...kopie(vorher), briefing: { ...vorher.briefing, email: false } });
		await ctl.flush();
		assert.equal(server.stand(PRESET_ID).send_email, false);
		assert.deepEqual(keys(server.putRuempfe()[0]), ['send_email']);
	});
});

describe('AC-4/AC-33 (route): Trip-Speicherweg PUT /api/trips/{id}', () => {
	test('ac4_trip_morgenzeit_put_auf_trip_mit_report_config_teilfeld', async () => {
		const m = await zustellungModell();
		const s = await zustellungSpeicherung();
		const gesendet: Array<{ pfad: string; body: Json }> = [];
		const client = {
			async put<T>(pfad: string, body: unknown): Promise<T> {
				gesendet.push({ pfad, body: kopie(body) });
				return tripVoll() as T;
			}
		};
		const ctl = createController('trip-2795');
		const vorher = m.standAusTrip(tripVoll());
		const sp = s.erstelleZustellungSpeicherung({ context: 'route', id: 'trip-2795', client, saveController: ctl, basis: vorher });
		sp.aenderungMelden({ ...kopie(vorher), morgenZeit: '06:45' });
		await ctl.flush();
		assert.equal(gesendet.length, 1, 'genau ein PUT');
		assert.equal(gesendet[0].pfad, '/api/trips/trip-2795');
		assert.deepEqual(keys(gesendet[0].body), ['report_config']);
		assert.deepEqual(keys(gesendet[0].body.report_config), ['morning_time']);
		assert.equal(hhmm(gesendet[0].body.report_config.morning_time), '06:45');
	});

	test('ac8_trip_rasterfremde_zeit_kein_put', async () => {
		const m = await zustellungModell();
		const s = await zustellungSpeicherung();
		let puts = 0;
		const client = {
			async put<T>(): Promise<T> {
				puts++;
				return tripVoll() as T;
			}
		};
		const ctl = createController('trip-2795');
		const vorher = m.standAusTrip(tripVoll());
		const sp = s.erstelleZustellungSpeicherung({ context: 'route', id: 'trip-2795', client, saveController: ctl, basis: vorher });
		sp.aenderungMelden({ ...kopie(vorher), abendZeit: '18:50' });
		await ctl.flush();
		assert.equal(puts, 0, '18:50 darf nicht gesendet werden');
	});
});
