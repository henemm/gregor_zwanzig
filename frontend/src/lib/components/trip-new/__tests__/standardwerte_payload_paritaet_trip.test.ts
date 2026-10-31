// TDD RED — Onboarding S3 (Issue #2521), AC-6 (+ Trip-Teil von AC-9/AC-11 lokal):
// „Mit Standardwerten speichern" erzeugt im Trip dieselbe `report_config` wie das
// unveraenderte Durchklicken aller Reiter.
// Spec: docs/specs/modules/onboarding_standardwerte_hilfe.md
//
// VERGLEICHSMASSSTAB (nicht tautologisch): Was die ECHTEN Reiter beim Oeffnen in
// den Editor-Zustand schreiben — die `onMount`- und `$effect`-Ruempfe von
// `VersandTab.svelte` und `MailInhaltCard.svelte`, ausgewertet gegen ihr echtes
// Instanz-Skript (svelteInstanzPruefstand.ts). Dieser Test ruft
// `ladeReportZustand`/`baueReportConfigPayload`/`ladeMailZustand` NIE selbst auf;
// die Referenz entsteht ausschliesslich aus dem Komponenten-Code. Aendert jemand
// den Reiter-Effekt (Feld weg, anderer Default), wird der Vergleich rot.
//
// Reihenfolge wie im Browser (TripNewEditor bettet VersandTab vor MailInhaltCard
// ein, beide an `bind:reportConfig`): beide Instanz-Skripte entstehen zuerst
// (Startzustand aus dem Blob VOR jedem Effekt), dann laufen onMount + $effect des
// VersandTab, danach onMount + $effect der MailInhaltCard auf dem LEBENDEN Blob.
//
// Vertrag (Spec: „reiner Ergaenzer in tripNewLogic.ts"):
//   ergaenzeStandardwerteReportConfig(rc: ReportConfig | undefined): ReportConfig
//   — ergaenzt fehlende Felder, ueberschreibt nichts Gesetztes, schreibt
//     `multi_day_trend_reports: []` wie der Versand-Reiter.
//
// Mutationen, die hier rot werden muessen (Spec AC-6):
//   „Ergaenzer laesst den Mail-Baustein weg", „Ergaenzer setzt
//   multi_day_trend_reports nicht".
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/trip-new/__tests__/standardwerte_payload_paritaet_trip.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import * as logik from '../tripNewLogic.ts';
import { effekteVon, type Knoten } from '../../shared/__tests__/svelteInstanzPruefstand.ts';
import {
	TRIP_EDITOR,
	editorUmgebung,
	knopfEinbettungen,
	knopfAttribut,
	ruhe,
	derivedNeu,
	type EditorUmgebung
} from '../../shared/__tests__/standardwerteEditorPruefstand.ts';

const SHARED = join(dirname(fileURLToPath(import.meta.url)), '..', '..', 'shared');
const VERSAND_TAB = join(SHARED, 'VersandTab.svelte');
const MAIL_KARTE = join(SHARED, 'MailInhaltCard.svelte');

/** Was /trips/new vor dem ersten Versand-Besuch in report_config haelt: nur das
 *  Tagesfenster aus dem (dauerhaft gemounteten) Wetter-Metriken-Reiter. */
const VOR_VERSAND = { day_window_start_hour: 4, day_window_end_hour: 19 };

function klon<T>(v: T): T {
	return JSON.parse(JSON.stringify(v));
}

function effekteMit(e: EditorUmgebung, bezeichner: string): Array<() => void> {
	const f = effekteVon(e.ast, e.quelle, e.u, bezeichner);
	assert.ok(f.length >= 1, `Messaufbau kaputt: kein $effect mit \`${bezeichner}\` in ${e.quelle.length} Zeichen Quelltext`);
	return f;
}

/** report_config nach unveraendertem Oeffnen von Versand-Reiter + Mail-Inhalt-Karte. */
async function durchgeklickt(start: Knoten): Promise<Knoten> {
	const versand = await editorUmgebung(VERSAND_TAB, { reportConfig: klon(start), context: 'route' });
	const mail = await editorUmgebung(MAIL_KARTE, { reportConfig: klon(start) });
	for (const fn of versand.mounts) fn();
	for (const fn of effekteMit(versand, 'baueReportConfigPayload')) fn();
	// bind:reportConfig — derselbe lebende Blob erreicht die Mail-Karte.
	mail.u.reportConfig = versand.u.reportConfig;
	for (const fn of mail.mounts) fn();
	for (const fn of effekteMit(mail, 'baueReportConfigPayload')) fn();
	const ergebnis = mail.u.reportConfig as Knoten;
	// Positivkontrolle: die Reiter haben wirklich geschrieben (sonst waere der
	// Vergleich gegen einen leeren Blob vakuum-gruen).
	for (const feld of ['enabled', 'morning_time', 'send_email', 'telegram_style', 'multi_day_trend_reports', 'email_format', 'show_outlook', 'daily_summary_metrics']) {
		assert.ok(feld in ergebnis, `Messaufbau kaputt: Reiter-Referenz ohne Feld \`${feld}\``);
	}
	return klon(ergebnis);
}

type Ergaenzer = (rc: Knoten | undefined) => Knoten;
function ergaenzer(): Ergaenzer {
	const f = (logik as Record<string, unknown>).ergaenzeStandardwerteReportConfig;
	assert.equal(
		typeof f,
		'function',
		'tripNewLogic.ts exportiert keinen reinen Ergaenzer `ergaenzeStandardwerteReportConfig` (Spec Teil A)'
	);
	return f as Ergaenzer;
}

describe('AC-6: Ergaenzer == unveraendertes Durchklicken (Versand-Reiter + Mail-Inhalt-Karte)', () => {
	test('Messaufbau: Referenz aus den echten Reitern enthaelt Briefing-, Kanal- und Mail-Felder', async () => {
		const ref = await durchgeklickt(VOR_VERSAND);
		assert.equal(ref.day_window_start_hour, 4, 'Tagesfenster des Wetter-Reiters geht verloren');
		assert.deepEqual(ref.multi_day_trend_reports, []);
	});

	test('Trip ohne Versand-Besuch: Ergaenzer liefert exakt die report_config des Durchklickens (Deep-Equal)', async () => {
		const ref = await durchgeklickt(VOR_VERSAND);
		assert.deepEqual(klon(ergaenzer()(klon(VOR_VERSAND))), ref);
	});

	test('kein Mehrtages-Trend im Abend-Briefing: multi_day_trend_reports ist explizit []', () => {
		const rc = ergaenzer()(klon(VOR_VERSAND));
		assert.ok('multi_day_trend_reports' in rc, 'Feld fehlt — Python-Lese-Default ["evening"] wuerde greifen');
		assert.deepEqual(rc.multi_day_trend_reports, []);
	});

	test('Mail-Baustein ist enthalten (email_format, show_*, daily_summary_metrics wie die Mail-Karte)', async () => {
		const ref = await durchgeklickt(VOR_VERSAND);
		const rc = ergaenzer()(klon(VOR_VERSAND));
		for (const k of Object.keys(ref).filter((k) => k === 'email_format' || k.startsWith('show_') || k === 'daily_summary_metrics' || k === 'wind_exposition_min_elevation_m')) {
			assert.deepEqual(rc[k], ref[k], `Mail-Feld ${k}`);
		}
	});

	test('ohne report_config (undefined) == Durchklicken ab leerem Blob', async () => {
		const ref = await durchgeklickt({});
		assert.deepEqual(klon(ergaenzer()(undefined)), ref);
	});

	test('ueberschreibt nichts Gesetztes: vorhandene Werte gewinnen, Ergebnis == Durchklicken mit denselben Werten', async () => {
		const gesetzt = {
			...VOR_VERSAND,
			morning_time: '06:30:00',
			send_telegram: true,
			email_format: 'compact',
			show_outlook: false,
			change_threshold_temp: 3
		};
		const ref = await durchgeklickt(gesetzt);
		const rc = ergaenzer()(klon(gesetzt));
		assert.equal(rc.email_format, 'compact');
		assert.equal(rc.show_outlook, false);
		assert.equal(rc.send_telegram, true);
		assert.equal(rc.change_threshold_temp, 3, 'unbekanntes Bestandsfeld geht verloren');
		assert.deepEqual(klon(rc), ref);
	});

	test('rein: Eingabe wird nicht veraendert', () => {
		const ein = klon(VOR_VERSAND);
		ergaenzer()(ein);
		assert.deepEqual(ein, VOR_VERSAND);
	});
});

// ── Wirkstelle: Klick im echten TripNewEditor ────────────────────────────────
const GPX = { file: 'a.gpx', km: 10, asc: 500 };

async function editorMitKlickSpion() {
	const posts: Array<{ url: string; body: Knoten }> = [];
	const ziele: string[] = [];
	const e = await editorUmgebung(TRIP_EDITOR, {
		stateOverride: {},
		name: 'Trip X',
		startDate: '2026-07-01',
		stages: [1, 2].map((id) => ({ id, name: `E${id}`, gpx: GPX, waypoints: [] })),
		catalogLoaded: true,
		reportConfig: klon(VOR_VERSAND),
		goto: async (ziel: string) => {
			ziele.push(ziel);
		},
		api: {
			post: async (url: string, body: Knoten) => {
				posts.push({ url, body: klon(body) });
				return { id: 'neu-1' };
			},
			get: async () => ({})
		}
	});
	const knoepfe = knopfEinbettungen(e.ast);
	assert.ok(knoepfe.length >= 1, 'TripNewEditor bettet <StandardwerteSpeichernKnopf> nicht ein');
	const klick = () => (knopfAttribut(knoepfe[0], e, 'onclick') as () => unknown)();
	return { e, posts, ziele, klick };
}

describe('AC-6/AC-9/AC-11 an der Wirkstelle: Klick im echten Trip-Editor', () => {
	test('Klick speichert ueber POST /api/trips — report_config == Durchklicken', async () => {
		const ref = await durchgeklickt(VOR_VERSAND);
		const { posts, klick } = await editorMitKlickSpion();
		await klick();
		await ruhe();
		assert.equal(posts.length, 1, `erwartet genau einen POST, gesehen ${posts.length}`);
		assert.equal(posts[0].url, '/api/trips');
		assert.deepEqual(posts[0].body.report_config, ref);
	});
	test('Klick landet auf der Detailseite des neuen Trips', async () => {
		const { ziele, klick } = await editorMitKlickSpion();
		await klick();
		await ruhe();
		assert.ok(ziele.includes('/trips/neu-1'), `Navigation nach dem Speichern: ${JSON.stringify(ziele)}`);
	});
	test('zweiter Klick nach erfolgreichem Speichern erzeugt keinen zweiten POST (savedTripId)', async () => {
		const { posts, klick } = await editorMitKlickSpion();
		await klick();
		await ruhe();
		await klick();
		await ruhe();
		assert.equal(posts.length, 1);
	});
});

// ── Adversary F001: defaultsBereit kommt ueber den ECHTEN Rueckkanal ──────────
// `catalogLoaded` wird hier NICHT gesaet: der Editor-Handler, den der
// Wetter-Metriken-Reiter nach seinem Katalog-Laden bedient
// (`onWeatherMetricsChange={handleWeatherMetricsChange}`), muss den Knopf
// freischalten.
async function editorOhneKatalogSaat() {
	const posts: string[] = [];
	const e = await editorUmgebung(TRIP_EDITOR, {
		stateOverride: {},
		name: 'Trip X',
		startDate: '2026-07-01',
		stages: [1, 2].map((id) => ({ id, name: `E${id}`, gpx: GPX, waypoints: [] })),
		reportConfig: klon(VOR_VERSAND),
		api: {
			post: async (url: string) => {
				posts.push(url);
				return { id: 'neu-1' };
			},
			get: async () => ({})
		}
	});
	const knoepfe = knopfEinbettungen(e.ast);
	assert.ok(knoepfe.length >= 2, 'TripNewEditor bettet <StandardwerteSpeichernKnopf> nicht Desktop UND mobil ein');
	const aktiv = () => knoepfe.map((k) => Boolean(knopfAttribut(k, e, 'enabled')));
	return { e, posts, aktiv, klick: () => (knopfAttribut(knoepfe[0], e, 'onclick') as () => unknown)() };
}

describe('F001: Rueckkanal des Wetter-Metriken-Reiters schaltet den Standardwerte-Knopf frei', () => {
	test('vor der Meldung des Reiters gesperrt, danach aktiv; Klick speichert genau einmal', async () => {
		const { e, posts, aktiv, klick } = await editorOhneKatalogSaat();
		assert.ok(aktiv().every((a) => a === false), 'Knopf aktiv, bevor der Reiter seine Standardauswahl gemeldet hat');
		assert.equal(typeof e.u.handleWeatherMetricsChange, 'function', 'Messaufbau: handleWeatherMetricsChange fehlt');
		e.u.handleWeatherMetricsChange([{ metric_id: 'temperature', enabled: true }]);
		derivedNeu(e);
		// #2347 S4 (AC-20, Race): mit aktiver Metrik wartet der Knopf zusaetzlich auf
		// die Wertebereiche-Vorbelegung (CorridorEditor → onVorbelegungFertig).
		assert.ok(aktiv().every((a) => a === false), 'Knopf frei, bevor die Wertebereiche vorbelegt sind');
		assert.equal(typeof e.u.handleVorbelegungFertig, 'function', 'Messaufbau: handleVorbelegungFertig fehlt');
		e.u.handleVorbelegungFertig();
		derivedNeu(e);
		assert.ok(aktiv().every((a) => a === true), 'Meldung des Reiters + Vorbelegung schalten den Knopf nicht frei');
		await klick();
		await ruhe();
		assert.deepEqual(posts, ['/api/trips']);
	});
});

// ── Adversary F002: beide Trip-Guards einzeln ────────────────────────────────
describe('F002: gesperrtes Gate — jeder Trip-Guard wirkt fuer sich', () => {
	test('Klick-Handler bei gesperrtem Gate ruft buildAndSave gar nicht auf', async () => {
		const { e, klick } = await editorOhneKatalogSaat();
		let aufrufe = 0;
		e.u.buildAndSave = async () => {
			aufrufe++;
			return null;
		};
		await klick();
		await ruhe();
		assert.equal(aufrufe, 0, 'Klick-Handler ignoriert das gesperrte Standardwerte-Gate');
	});
	test('buildAndSave(true) bei gesperrtem Gate speichert nichts', async () => {
		const { e, posts } = await editorOhneKatalogSaat();
		const id = await e.u.buildAndSave(true);
		await ruhe();
		assert.equal(id, null);
		assert.deepEqual(posts, [], 'buildAndSave(mitStandardwerten) ignoriert das gesperrte Gate');
	});
});
