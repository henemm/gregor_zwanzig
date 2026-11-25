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
// Issue #3154 (#3122 B3b, Spec feat_3122_was_steht_wo.md Teil B Nr. 14): der Kurzstil-Schalter des
// Uebergangsblocks (eigener Speicherer, Owner 'kanal-stil') ist entfernt; den Kurzstil schaltet allein die
// Karte „Was steht wo“ ueber `erstelleFelderSpeicherung` (Owner 'was-steht-wo-schalter'), die ihre Nutzlast
// mit `kanalStilNutzlast` formt. F004 (Orte, Go-Merge) und F001 (kein Verdraengen der wartenden
// Zustellungs-Aenderung im geteilten Hub-Controller) gelten unveraendert und laufen jetzt gegen diesen Speicherer.
//
//   cd frontend && npm test -- src/lib/components/shared/zustellung-tab/__tests__/kanalStilSpeicherung.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../../api.ts';
import { clearEtagRegistry } from '../../../../etagRegistry.ts';
import { createGoMergeServer, vollerVergleich, type GoMergeServer } from '../../__tests__/goMergeServerPruefstand.ts';
import { createController } from '../../wetter-tab/__tests__/wertebereicheVergleichPruefstand.ts';
import { ladeReportZustand } from '../../versand-tab/reportConfigPayload.ts';
import { kanalStilNutzlast } from '../kanalStilSpeicherung.ts';
import { erstelleFelderSpeicherung, felderAusAntwort, type Felder } from '../../wetter-tab/wasStehtWoSpeicherung.ts';
import { erstelleZustellungSpeicherung } from '../zustellungSpeicherung.ts';
import { standAusTrip } from '../zustellungModell.ts';
import { hhmm, presetVoll, tripVoll, type Json } from './zustellungTabDaten.ts';

const kopie = <T>(x: T): T => JSON.parse(JSON.stringify(x));
const ticks = async (n = 10) => {
	for (let i = 0; i < n; i++) await new Promise((r) => setTimeout(r, 0));
};

// ── F004: Nutzlast je Kontext ───────────────────────────────────────────────

// #3297 (AC-4): der unsichtbare Mehrtages-Trend-Schalter ist entfernt — die Trip-Nutzlast traegt nur
// `telegram_style`, keine Trend-Felder (der Ausblick steht in `placements.outlook_reports`).
describe('F004: Nutzlast des Kanal-Stils', () => {
	test('f004_trip_report_config_nur_telegram_style', () => {
		assert.deepEqual(kanalStilNutzlast('route', { stil: 'kurzform' }), { report_config: { telegram_style: 'kurzform' } });
		assert.deepEqual(kanalStilNutzlast('route', { stil: 'rich' }, { stil: 'rich' }), { report_config: {} }, 'unveraenderter Stil sendet nichts');
	});

	test('f004_trip_nach_server_merge_bleiben_fremdfelder', () => {
		const trip = tripVoll();
		const n = kanalStilNutzlast('route', { stil: 'kurzform' }) as Json;
		// Go mergt report_config je Schluessel.
		const danach = { ...trip.report_config, ...n.report_config };
		for (const k of Object.keys(trip.report_config).filter((k) => k !== 'telegram_style')) {
			assert.deepEqual(danach[k], trip.report_config[k], `report_config.${k} wurde ueberschrieben`);
		}
		assert.equal(ladeReportZustand(danach).telegram_style, 'kurzform');
	});

	test('f004_orte_nur_display_config_telegram_style', () => {
		assert.deepEqual(kanalStilNutzlast('vergleich', { stil: 'kurzform' }), {
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
		const start = felderAusAntwort({ blocks: {} });
		const sp = erstelleFelderSpeicherung({ kind: 'vergleich', id: PRESET_ID, client: api, saveController: ctl, start });
		sp.melden({ ...start, telegram_style: 'kurzform' });
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
			const start: Felder = felderAusAntwort({ blocks: {} });
			const stil = erstelleFelderSpeicherung({ kind: 'route', id: 'trip-2795', client, saveController: ctl, start });
			const zeit = () => reiter.aenderungMelden({ ...kopie(vorher), morgenZeit: '06:45' });
			const kurz = () => stil.melden({ ...start, telegram_style: 'kurzform' });
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
