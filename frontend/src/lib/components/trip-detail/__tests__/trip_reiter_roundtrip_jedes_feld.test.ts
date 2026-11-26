// TDD (Regressionswaechter) — Issue #1433: je Trip-Reiter landet JEDES bedienbare
// Feld nach dem Umbau auf Teilfeld-Nutzlasten auf dem Server — inklusive der
// Loeschfaelle (leere Auswahl, leere Liste, false). Schutz gegen den stillen
// Fehler „ein Eigen-Schluessel wurde in der Allowlist vergessen und wird nicht
// mehr gespeichert".
//
// Spec: docs/specs/bugfix/trip_mehrreiter_konfliktschutz.md — §2 (Tabelle),
//       §2 Regel 2 (Loeschsemantik), AC-11 bis AC-15, AC-17.
//
// Hinweis zum Status: diese Datei ist VOR der Umsetzung weitgehend gruen (die
// heutige Vollkopie schreibt auch die Eigenfelder) — sie soll NACH der Umsetzung
// gruen BLEIBEN und faengt jeden vergessenen Eigen-Schluessel. Sie ist ein
// Waechter, kein Bug-Nachweis (den liefern W1/W2 und die Nutzlast-Datei).
//
// Gemessen: der SERVER-Stand im Ersatz-Server (Go-Merge) nach dem Speichern ueber
// den ECHTEN Reiter (Instanz-Skript + echtes `api`). Frischer Stand, kein Konflikt.
//
// Issue #2284 S2 (AC-17): Kopf (Name, NEU Region) ueber `TripHeader.onSaveField`
// (Pruefstand `kopfReiter`); Tempo seit #3196 ueber den Reiter Etappen (`tempoReiter`).
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/trip-detail/__tests__/trip_reiter_roundtrip_jedes_feld.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../api.ts';
import { clearEtagRegistry } from '../../../etagRegistry.ts';
import { createFakeTripServer, type FakeTripServer } from '../../../__tests__/fakeTripServer.ts';
import { live } from '../../shared/wetter-tab/__tests__/wetterTabDaten.ts';
import * as P from './tripMehrreiterPruefstand.ts';

let server: FakeTripServer;
const SEED = P.vollerTrip();

beforeEach(async () => {
	clearEtagRegistry();
	server = createFakeTripServer({ merge: true });
	server.install();
	server.seed(P.TRIP_ID, P.vollerTrip());
	await api.get(P.TRIP_PFAD);
});
afterEach(() => server.restore());

const stand = () => server.stand(P.TRIP_ID);
const dc = () => stand().display_config as Record<string, unknown>;
const rc = () => stand().report_config as Record<string, unknown>;
/** Rumpf des letzten PUT auf den Trip (fuer Felder, die der Ersatz-Server nicht fuehrt). */
const gesendet = () => server.calls.filter((c) => c.method === 'PUT' && c.path === P.TRIP_PFAD).at(-1)?.anfrage as Record<string, unknown>;

/** Python-eigene Schluessel duerfen sich bei KEINEM Reiter aendern. */
function pythonEigenesUnveraendert(): void {
	const seedRc = SEED.report_config as Record<string, unknown>;
	for (const k of P.PYTHON_EIGEN_REPORT) {
		assert.deepEqual(rc()[k], seedRc[k], `report_config.${k} ist Python-eigen und darf nie veraendert werden`);
	}
}

describe('Alarme (AC-11, AC-17)', () => {
	test('Kanal einschalten (SMS)', async () => {
		const a = P.neuerAufbau();
		const r = await P.alarmeReiter(a);
		r.kanalUmschalten('sms');
		await P.fertig(a.ctl);
		assert.deepEqual(stand().alert_channels, { email: true, telegram: true, sms: true, premium_sms: false });
		pythonEigenesUnveraendert();
	});

	test('Kanal AUSschalten (E-Mail): false kommt an', async () => {
		const a = P.neuerAufbau();
		const r = await P.alarmeReiter(a);
		r.kanalUmschalten('email');
		await P.fertig(a.ctl);
		assert.equal((stand().alert_channels as Record<string, unknown>).email, false);
	});

	test('Kanal-Schwelle (Telegram)', async () => {
		const a = P.neuerAufbau();
		const r = await P.alarmeReiter(a);
		r.schwelleAendern('telegram', 'LOW');
		await P.fertig(a.ctl);
		assert.deepEqual(stand().alert_channel_thresholds, { email: 'LOW', telegram: 'LOW', sms: 'MODERATE', premium_sms: 'HIGH' });
	});

	test('Abkuehlzeit', async () => {
		const a = P.neuerAufbau();
		const r = await P.alarmeReiter(a);
		r.cooldownAendern(30);
		await P.fertig(a.ctl);
		assert.equal(stand().alert_cooldown_minutes, 30);
	});

	test('Ruhezeiten', async () => {
		const a = P.neuerAufbau();
		const r = await P.alarmeReiter(a);
		r.ruhezeitAendern('23:00', '06:00');
		await P.fertig(a.ctl);
		assert.equal(stand().alert_quiet_from, '23:00');
		assert.equal(stand().alert_quiet_to, '06:00');
	});

	test('Amtliche Warnungen aus: enabled=false, sources bleiben (Server-Merge)', async () => {
		const a = P.neuerAufbau();
		const r = await P.alarmeReiter(a);
		r.amtlicheWarnungenUmschalten(false);
		await P.fertig(a.ctl);
		assert.deepEqual(stand().official_warnings, { enabled: false, sources: ['meteoalarm'] });
	});

	test('Alarm-Empfindlichkeit: metric_alert_levels aktualisiert, display_config sonst unberuehrt', async () => {
		const a = P.neuerAufbau();
		const r = await P.alarmeReiter(a);
		r.empfindlichkeitAendern('wind', 'sensibel');
		await P.fertig(a.ctl);
		const seedDc = SEED.display_config as Record<string, unknown>;
		assert.deepEqual(dc().metric_alert_levels, {
			...(seedDc.metric_alert_levels as object),
			wind: 'sensibel'
		});
		assert.deepEqual({ ...dc(), metric_alert_levels: undefined }, { ...seedDc, metric_alert_levels: undefined });
	});
});

// Wertebereiche Desktop/Mobile (AC-12, AC-17): #2794 S3a Teil-PR 4a (AC-31) mit dem
// CorridorEditor entfernt — die Grenzen schreibt der Reiter Wetter.

// #3020 R1: lebende Reiter (Wetter, Karte „Was steht wo“, Zustellung) statt der mit #3357 geloeschten
// WeatherMetricsTab/BriefingScheduleTab. Zuordnung der Alt-Felder: preset_name -> ampel.template;
// channel_layouts/outlook_metrics/outlook_metric_formats/multi_day_trend_* -> Tabelle `placements` (Karte, ADR-0124);
// E-Mail-Inhalt -> Schalter der Karte. Ohne lebende Bedienung sind telegram_kurzform,
// wind_exposition_min_elevation_m, show_metrics_summary, show_outlook: sie muessen jede lebende Speicherung
// ueberleben (Fall „Altfelder“ unten).
/** Altfelder ohne lebende Bedienung (Merge, nie Replace; ADR-0101). */
const ALTFELDER_DISPLAY = ['channel_layouts', 'preset_name', 'telegram_kurzform', 'outlook_metrics', 'outlook_metric_formats', 'channel_layouts_per_report', 'sms_metrics', 'multi_day_trend_reports'];
const ALTFELDER_REPORT = ['multi_day_trend_morning', 'multi_day_trend_evening', 'multi_day_trend_reports', 'wind_exposition_min_elevation_m', 'show_metrics_summary', 'show_outlook'];

describe('Wetter (AC-13, AC-17)', () => {
	async function mitReiter(): Promise<{ a: P.Aufbau; w: Awaited<ReturnType<typeof P.wetterReiter>> }> {
		const a = P.neuerAufbau();
		return { a, w: await P.wetterReiter(a) };
	}
	const aktiv = () => (dc().metrics as Array<{ metric_id: string; enabled: boolean }>).filter((m) => m.enabled).map((m) => m.metric_id);

	test('Vorlage uebernehmen (ampel.template, Auswahl der Vorlage)', async () => {
		// #2988: echte Vorlage aus dem Python-Kern statt einer erfundenen; Temperatur und gefuehlte Temperatur bringen
		// im Trip ihre abgeleiteten Groessen mit (p5c_ableitung_hub_orte_ausgabe.test.ts).
		const kinder = ['temperature', 'wind_chill'].flatMap((id) => ['night', 'day_low', 'day_high'].map((k) => `${id}_${k}`));
		const vorlage = Object.entries(live().templates.find((t) => t.id === 'skitouren')!.ampel.metrics as Record<string, { enabled?: boolean }>);
		const soll = vorlage.filter(([, m]) => m.enabled).map(([id]) => id);
		assert.ok(soll.includes('temperature') && soll.includes('wind_chill') && soll.includes('gust'), 'Messaufbau: Auswahl der Vorlage');
		const { a, w } = await mitReiter();
		assert.notEqual(w.inst.u.stand.vorlageId, 'skitouren', 'Messaufbau: der Trip steht auf einer anderen Vorlage');
		w.vorlage('skitouren');
		await P.fertig(a.ctl);
		assert.equal((dc().ampel as { template: string }).template, 'skitouren');
		assert.deepEqual(aktiv().sort(), [...new Set([...soll, ...kinder])].sort());
	});

	test('Metrik-Auswahl: „+“ haengt an, „−“ nimmt weg, uebrige Eintragsfelder bleiben', async () => {
		const { a, w } = await mitReiter();
		w.hinzufuegen('gust');
		w.abwaehlen('wind');
		await P.fertig(a.ctl);
		// `temperature` bringt seine abgeleiteten Groessen mit (Tageshoch/-tief, Nacht).
		assert.deepEqual([aktiv()[0], aktiv().at(-1)], ['temperature', 'gust']);
		assert.ok(!aktiv().includes('wind'), aktiv().join());
		const temperatur = (dc().metrics as Array<Record<string, unknown>>).find((m) => m.metric_id === 'temperature');
		assert.deepEqual(temperatur?.aggregations, ['min', 'max'], 'Read-Modify-Write je Eintrag');
	});

	test('Loeschfall: ALLE Metriken abgewaehlt — keine aktive Metrik auf dem Server', async () => {
		const { a, w } = await mitReiter();
		for (const id of [...(w.inst.u.stand.auswahl as string[])]) w.abwaehlen(id);
		await P.fertig(a.ctl);
		assert.deepEqual(aktiv(), [], 'die Leerauswahl muss ankommen (der Server-Merge loescht nie von selbst)');
	});

	test('Amtliche Warnungen AUS: official_alerts_enabled=false, sources bleiben; Radar AUS', async () => {
		const { a, w } = await mitReiter();
		w.aendern({ warnungenAn: false, radarAn: false });
		await P.fertig(a.ctl);
		assert.equal(stand().official_alerts_enabled, false, 'false muss ankommen (Server-Merge loescht nie)');
		assert.deepEqual(stand().official_warnings, { enabled: false, sources: ['meteoalarm'] });
		assert.equal(gesendet().radar_alert_enabled, false);
	});

	test('Tagesfenster (je ein Wert ungleich dem Seed)', async () => {
		const { a, w } = await mitReiter();
		w.aendern({ tagesfenster: { start: 6, end: 20 } });
		await P.fertig(a.ctl);
		assert.deepEqual([rc().day_window_start_hour, rc().day_window_end_hour], [6, 20]);
		pythonEigenesUnveraendert();
	});
});

describe('Karte „Was steht wo“ (AC-13, AC-17)', () => {
	for (const [feld, wert] of Object.entries(P.KARTE_REPORT)) {
		test(`Schalter ${feld}: kommt an, sonst bleibt der ganze Trip unveraendert`, async () => {
			const vorher = stand();
			const seedRc = vorher.report_config as Record<string, unknown>;
			assert.notDeepEqual(wert, seedRc[feld], 'Messaufbau: der neue Wert muss vom Seed abweichen');
			const a = P.neuerAufbau();
			(await P.karteWasStehtWo(a)).schalten(feld, wert);
			await P.fertig(a.ctl);
			assert.deepEqual(stand(), { ...vorher, report_config: { ...seedRc, [feld]: wert } });
		});
	}
	test('Schalter show_night_block (display_config): kommt an, sonst bleibt der ganze Trip unveraendert', async () => {
		const vorher = stand();
		const a = P.neuerAufbau();
		(await P.karteWasStehtWo(a)).schalten('show_night_block', false);
		await P.fertig(a.ctl);
		assert.deepEqual(stand(), { ...vorher, display_config: { ...(vorher.display_config as object), show_night_block: false } });
	});

	/** Zuletzt gesendeter Stand der Tabelle (der Ersatz-Server fuehrt `placements` nicht selbst). */
	const tabelle = () => {
		const p = server.calls.filter((c) => c.method === 'PUT' && c.path === `/api/briefings/${P.TRIP_ID}/placements?kind=route`).at(-1);
		assert.ok(p, 'kein PUT der Tabelle');
		return p!.anfrage as { rows: Array<{ metric_id: string; places?: Record<string, unknown>; formats?: Record<string, unknown> }>; outlook_reports: string[] };
	};
	const zeile = (id: string) => tabelle().rows.find((r) => r.metric_id === id)!;

	test('Telegram-Haken entfernt: nur dort abgewaehlt, die anderen Stellen und Zeilen bleiben', async () => {
		const a = P.neuerAufbau();
		(await P.karteWasStehtWo(a)).haken('temperature', 'telegram', false);
		await P.fertig(a.ctl);
		assert.deepEqual(zeile('temperature').places, { telegram: false });
		assert.equal(zeile('wind').places, undefined);
	});
	test('Ausblick: Auswahl und Loeschfall (leer)', async () => {
		const a = P.neuerAufbau();
		const k = await P.karteWasStehtWo(a);
		k.ausblick('morning', true);
		await P.fertig(a.ctl);
		assert.deepEqual(tabelle().outlook_reports, ['morning', 'evening']);
		k.ausblick('morning', false);
		k.ausblick('evening', false);
		await P.fertig(a.ctl);
		assert.deepEqual(tabelle().outlook_reports, [], 'die Leerung des Ausblicks muss als [] ankommen');
	});
	test('Ausblick je Metrik: Haken und Format der Stelle outlook', async () => {
		const a = P.neuerAufbau();
		const k = await P.karteWasStehtWo(a);
		k.haken('wind', 'outlook', false);
		k.format('temperature', 'outlook', 'raw');
		await P.fertig(a.ctl);
		assert.deepEqual(zeile('wind').places, { outlook: false });
		assert.deepEqual(zeile('temperature').formats, { outlook: 'raw' });
	});
});

describe('#3020 AC-2: Altfelder und ein zweiter Trip ueberleben jede lebende Speicherung', () => {
	test('Wetter, Karte und Zustellung nacheinander: Altfelder byte-gleich, zweiter Trip unberuehrt', async () => {
		server.seed('t-zweiter-nutzer', P.vollerTrip('t-zweiter-nutzer'));
		const zweiter = server.stand('t-zweiter-nutzer');
		const a = P.neuerAufbau();
		(await P.wetterReiter(a)).abwaehlen('wind');
		await P.fertig(a.ctl);
		(await P.karteWasStehtWo(a)).schalten('email_format', 'compact');
		await P.fertig(a.ctl);
		(await P.zustellungReiter(a)).aendern({ morgenZeit: '08:00' });
		await P.fertig(a.ctl);
		const wind = (dc().metrics as Array<Record<string, unknown>>).find((m) => m.metric_id === 'wind');
		assert.deepEqual(
			[wind?.enabled, rc().email_format, rc().morning_time],
			[false, 'compact', '08:00:00'],
			'Messaufbau: alle drei haben gespeichert'
		);
		const seedDc = SEED.display_config as Record<string, unknown>;
		const seedRc = SEED.report_config as Record<string, unknown>;
		for (const k of ALTFELDER_DISPLAY) assert.deepEqual(dc()[k], seedDc[k], `display_config.${k}`);
		for (const k of ALTFELDER_REPORT) assert.deepEqual(rc()[k], seedRc[k], `report_config.${k}`);
		pythonEigenesUnveraendert();
		assert.deepEqual(server.stand('t-zweiter-nutzer'), zweiter, 'fremder Trip veraendert');
		for (const c of server.calls) assert.ok(!c.path.includes('t-zweiter-nutzer'), `fremder Trip angesprochen: ${c.path}`);
	});
});

describe('Zustellung (AC-14, AC-17)', () => {
	test('Zeiten, Slots und Hauptschalter', async () => {
		const a = P.neuerAufbau();
		const v = await P.zustellungReiter(a);
		v.aendern({ morgenZeit: '06:00', abendZeit: '19:00', morgenAn: false, abendAn: false });
		await P.fertig(a.ctl);
		assert.equal(rc().morning_time, '06:00:00');
		assert.equal(rc().evening_time, '19:00:00');
		assert.equal(rc().morning_enabled, false);
		assert.equal(rc().evening_enabled, false);
		assert.equal(rc().enabled, false);
		pythonEigenesUnveraendert();
	});

	test('Kanaele: alle vier, auch das Abschalten (false)', async () => {
		const a = P.neuerAufbau();
		const v = await P.zustellungReiter(a);
		v.aendern({ briefing: { email: false, telegram: false, sms: true, premium_sms: true } });
		await P.fertig(a.ctl);
		assert.equal(rc().send_email, false);
		assert.equal(rc().send_telegram, false);
		assert.equal(rc().send_sms, true);
		assert.equal(rc().send_premium_sms, true);
	});

	// Telegram-Stil: Schalter der Karte (oben); Mehrtages-Trend: `outlook_reports` der Tabelle (oben).

	test('der Reiter Zustellung beruehrt weder Tagesfenster noch E-Mail-Inhalt auf dem Server', async () => {
		const a = P.neuerAufbau();
		const v = await P.zustellungReiter(a);
		v.aendern({ morgenZeit: '08:00' });
		await P.fertig(a.ctl);
		const seedRc = SEED.report_config as Record<string, unknown>;
		assert.deepEqual(rc(), { ...seedRc, morning_time: '08:00:00' }, 'nur die Morgenzeit aendert sich');
		for (const k of P.REPORT_WETTER_METRIKEN) assert.deepEqual(rc()[k], seedRc[k], `${k} gehoert dem Wetter-Metriken-Reiter`);
	});
});

describe('Kopf, Tempo, Etappen (AC-15)', () => {
	test('Name', async () => {
		const a = P.neuerAufbau();
		const k = await P.kopfReiter(a);
		await k.umbenennen('Neuer Name');
		assert.equal(stand().name, 'Neuer Name');
	});

	// #3196: Tempo (Reiter Etappen) statt Aktivitaet (Kopf); activity bleibt als Altfeld.
	test('Tempo (#3196)', async () => {
		const a = P.neuerAufbau();
		const t = await P.tempoReiter(a);
		await t.aendern({ fortbewegung: 'rad', grundtempo_kmh: 18 });
		assert.deepEqual(stand().tempo, { fortbewegung: 'rad', grundtempo_kmh: 18 });
		assert.equal(stand().activity, 'trekking');
	});

	test('Etappen', async () => {
		const a = P.neuerAufbau();
		const e = await P.etappenReiter(a);
		e.speichern([{ id: 'T1', name: 'Umbenannt', date: '2026-10-10', waypoints: [] }]);
		await P.fertig(a.ctl);
		assert.equal((stand().stages as Array<{ name: string }>)[0].name, 'Umbenannt');
	});
});

// Issue #2284 S2 (AC-2, AC-3, AC-6, AC-17): Region ist neues Eigenfeld des Kopfs
// (`TripHeader.onSaveField('region', …)`); Name/Region nacheinander lassen
// jedes andere Feld des Trips unveraendert.
describe('#2284 S2: Kopf-Region und die Kopf-Folge Name ⇒ Region', () => {
	test('Region setzen', async () => {
		const a = P.neuerAufbau();
		const k = await P.kopfReiter(a);
		await k.regionAendern('Alpen Nord');
		assert.equal(stand().region, 'Alpen Nord');
		assert.equal(k.geschlossen.region, 1, 'gespeichert ⇒ der Kopf schliesst das Feld');
	});

	test('Region leeren: der Leerstring kommt an (Go: omitempty laesst den Schluessel fallen)', async () => {
		const a = P.neuerAufbau();
		const k = await P.kopfReiter(a);
		await k.regionAendern('');
		assert.equal(stand().region ?? '', '', 'die alte Region „Korsika" darf nicht stehen bleiben');
		assert.equal(k.geschlossen.region, 1);
	});

	test('AC-6: nacheinander Name, Region — danach ist ALLES uebrige unveraendert', async () => {
		const a = P.neuerAufbau();
		const vorher = stand();
		const k = await P.kopfReiter(a);
		await k.umbenennen('Neuer Name');
		await k.regionAendern('Alpen Nord');
		assert.deepEqual(stand(), { ...vorher, name: 'Neuer Name', region: 'Alpen Nord' });
		pythonEigenesUnveraendert();
	});
});
