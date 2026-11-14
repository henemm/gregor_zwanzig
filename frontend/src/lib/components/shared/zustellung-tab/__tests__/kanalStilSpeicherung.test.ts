// Issue #2795 S3b, Teilschritt 1b — Fix-Loop 1 (Adversary Runde 1, F001 + F004).
// Spec: docs/specs/modules/feat_2795_s3b_teil1_zustellung.md — AC-30 (Uebergangsblock: Telegram-
// Kurzstil und Mehrtages-Trend bleiben bedienbar und speichern wie vorher), AC-32/AC-33.
//
// F004 (Mutation M16): die Nutzlast des Kanal-Stils je Kontext — Trip unter `report_config`
// (inkl. `multi_day_trend_reports`, das der Python-Report liest), Orte `display_config.telegram_style`;
// keine fremden Schluessel, Read-Modify-Write ohne Fremdfelder (Orte gegen den Go-Merge-Pruefstand).
//
// F001 (Mutation M4): der Kanal-Stil speichert unter EIGENEM Owner. Ein gleicher Owner wie der
// Reiter-Speicherer ('versand') ersetzte im SaveStatus-Slot die wartende Zeit-/Kanal-Aenderung
// (saveStatusStore.schedule: gleicher Owner ersetzt, fremder Owner wird vorher gesendet) — der Nutzer
// verloere still seine Uhrzeit. Gemessen am ECHTEN SaveStatus mit beiden echten Speicherern.
//
//   cd frontend && npm test -- src/lib/components/shared/zustellung-tab/__tests__/kanalStilSpeicherung.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../../api.ts';
import { clearEtagRegistry } from '../../../../etagRegistry.ts';
import { createGoMergeServer, vollerVergleich, type GoMergeServer } from '../../__tests__/goMergeServerPruefstand.ts';
import { createController } from '../../wetter-tab/__tests__/wertebereicheVergleichPruefstand.ts';
import { ladeReportZustand } from '../../versand-tab/reportConfigPayload.ts';
import { erstelleKanalStilSpeicherung, kanalStilNutzlast, kanalStilStart } from '../kanalStilSpeicherung.ts';
import { erstelleZustellungSpeicherung } from '../zustellungSpeicherung.ts';
import { standAusTrip } from '../zustellungModell.ts';
import { hhmm, presetVoll, tripVoll, type Json } from './zustellungTabDaten.ts';

const kopie = <T>(x: T): T => JSON.parse(JSON.stringify(x));
const ticks = async (n = 10) => {
	for (let i = 0; i < n; i++) await new Promise((r) => setTimeout(r, 0));
};

// ── F004: Nutzlast je Kontext ───────────────────────────────────────────────

describe('F004: Nutzlast des Kanal-Stils', () => {
	test('f004_trip_report_config_mit_trend_liste_ohne_fremde_schluessel', () => {
		const start = kanalStilStart('route', tripVoll());
		assert.deepEqual(start, { stil: 'rich', trendMorgen: false, trendAbend: true }, 'Messaufbau: Startwerte aus report_config');
		const n = kanalStilNutzlast('route', { stil: 'kurzform', trendMorgen: true, trendAbend: true });
		assert.deepEqual(n, {
			report_config: {
				telegram_style: 'kurzform',
				multi_day_trend_morning: true,
				multi_day_trend_evening: true,
				multi_day_trend_reports: ['morning', 'evening']
			}
		});
		assert.deepEqual(
			(kanalStilNutzlast('route', { stil: 'rich', trendMorgen: false, trendAbend: false }) as Json).report_config.multi_day_trend_reports,
			[],
			'beide Trends aus ⇒ leere Liste (sonst bliebe der alte Trend beim Python-Report aktiv)'
		);
	});

	test('f004_trip_nach_server_merge_bleiben_fremdfelder_und_der_trend_kommt_wieder', () => {
		const trip = tripVoll();
		const n = kanalStilNutzlast('route', { stil: 'kurzform', trendMorgen: true, trendAbend: false }) as Json;
		// Go mergt report_config je Schluessel.
		const danach = { ...trip.report_config, ...n.report_config };
		for (const k of ['enabled', 'morning_time', 'evening_time', 'send_email', 'show_outlook', 'email_format', 'day_window_start_hour']) {
			assert.deepEqual(danach[k], trip.report_config[k], `report_config.${k} wurde ueberschrieben`);
		}
		const neuGeladen = ladeReportZustand(danach);
		assert.equal(neuGeladen.telegram_style, 'kurzform');
		assert.equal(neuGeladen.multi_day_trend_morning, true, 'Morgen-Trend ist nach dem Neuladen weg');
		assert.equal(neuGeladen.multi_day_trend_evening, false, 'Abend-Trend ist nach dem Neuladen noch an');
		assert.deepEqual(kanalStilStart('route', { ...trip, report_config: danach }), { stil: 'kurzform', trendMorgen: true, trendAbend: false });
	});

	test('f004_orte_nur_display_config_telegram_style', () => {
		assert.deepEqual(kanalStilStart('vergleich', undefined, presetVoll()), { stil: 'rich', trendMorgen: false, trendAbend: false });
		assert.deepEqual(kanalStilNutzlast('vergleich', { stil: 'kurzform', trendMorgen: true, trendAbend: true }), {
			display_config: { telegram_style: 'kurzform' }
		});
	});
});

const PRESET_ID = 'cp-2795-kanalstil';
let server: GoMergeServer;

describe('F004 (vergleich): Read-Modify-Write gegen den Go-Merge-Pruefstand', () => {
	beforeEach(() => {
		clearEtagRegistry();
		server = createGoMergeServer({ [PRESET_ID]: vollerVergleich(PRESET_ID) });
		server.install();
	});
	afterEach(() => server.restore());

	test('f004_orte_kurzstil_aendert_nur_telegram_style', async () => {
		const ctl = createController(PRESET_ID);
		const davor = server.stand(PRESET_ID);
		const sp = erstelleKanalStilSpeicherung({ context: 'vergleich', id: PRESET_ID, client: api, saveController: ctl });
		sp.aenderungMelden({ stil: 'kurzform', trendMorgen: false, trendAbend: false });
		await ctl.flush();
		const ruempfe = server.putRuempfe();
		assert.equal(ruempfe.length, 1);
		assert.deepEqual(ruempfe[0], { display_config: { telegram_style: 'kurzform' } });
		const danach = server.stand(PRESET_ID);
		assert.equal((danach.display_config as Json).telegram_style, 'kurzform');
		const ohneStil = (x: Json) => ({ ...x, display_config: { ...x.display_config, telegram_style: undefined } });
		assert.deepEqual(ohneStil(danach), ohneStil(davor), 'ein anderes Feld des Orts-Briefings wurde veraendert');
	});
});

// ── F001: eigener Owner — kein Verdraengen der wartenden Reiter-Aenderung ──

describe('F001: Kurzstil-Aenderung verdraengt keine wartende Zeit-/Kanal-Aenderung', () => {
	for (const reihenfolge of ['zeit_dann_stil', 'stil_dann_zeit'] as const) {
		test(`f001_${reihenfolge}_beide_aenderungen_kommen_beim_server_an`, async () => {
			const gesendet: Array<{ pfad: string; body: Json }> = [];
			const client = {
				async put<T>(pfad: string, body: unknown): Promise<T> {
					gesendet.push({ pfad, body: kopie(body) });
					return tripVoll() as T;
				}
			};
			const ctl = createController('trip-2795');
			const vorher = standAusTrip(tripVoll());
			const reiter = erstelleZustellungSpeicherung({ context: 'route', id: 'trip-2795', client, saveController: ctl, basis: vorher });
			const stil = erstelleKanalStilSpeicherung({ context: 'route', id: 'trip-2795', client, saveController: ctl });
			const zeit = () => reiter.aenderungMelden({ ...kopie(vorher), morgenZeit: '06:45' });
			const kurz = () => stil.aenderungMelden({ stil: 'kurzform', trendMorgen: false, trendAbend: true });
			if (reihenfolge === 'zeit_dann_stil') {
				zeit();
				kurz();
			} else {
				kurz();
				zeit();
			}
			await ctl.flush();
			await ticks();
			const rc = gesendet.map((g) => g.body.report_config ?? {});
			assert.ok(
				rc.some((r) => r.morning_time && hhmm(r.morning_time) === '06:45'),
				`die Morgenzeit 06:45 ging verloren — gesendet: ${JSON.stringify(gesendet)}`
			);
			assert.ok(rc.some((r) => r.telegram_style === 'kurzform'), `der Kurzstil ging verloren — gesendet: ${JSON.stringify(gesendet)}`);
			assert.equal(gesendet.length, 2, 'zwei getrennte Vorgaenge erwartet');
			for (const g of gesendet) assert.equal(g.pfad, '/api/trips/trip-2795');
		});
	}
});
