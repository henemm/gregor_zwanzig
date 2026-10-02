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
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/trip-detail/__tests__/trip_reiter_roundtrip_jedes_feld.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../api.ts';
import { clearEtagRegistry } from '../../../etagRegistry.ts';
import { createFakeTripServer, type FakeTripServer } from '../../../__tests__/fakeTripServer.ts';
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

for (const mobil of [false, true]) {
	describe(`Wertebereiche ${mobil ? 'Mobile' : 'Desktop'} (AC-12, AC-17)`, () => {
		const zeile = (metric: string, max: number) => ({ metric, label: metric, min: 0, max, notify: true, mark: true });

		test('Korridor aendern', async () => {
			const a = P.neuerAufbau();
			const r = await P.wertebereicheReiter(a, mobil);
			r.inst.u.rows = [zeile('wind_max_kmh', 55)];
			r.speichern();
			await P.fertig(a.ctl);
			assert.deepEqual(stand().corridors, [{ metric: 'wind_max_kmh', range: [0, 55], notify: true, mark: true }]);
			assert.deepEqual(stand().display_config, SEED.display_config, 'display_config bleibt vollstaendig erhalten');
		});

		test('Korridor hinzufuegen', async () => {
			const a = P.neuerAufbau();
			const r = await P.wertebereicheReiter(a, mobil);
			r.inst.u.rows = [zeile('wind_max_kmh', 40), zeile('snow_depth_cm', 200)];
			r.speichern();
			await P.fertig(a.ctl);
			assert.equal((stand().corridors as unknown[]).length, 2);
		});

		test('alle Korridore leeren: [] kommt auf dem Server an', async () => {
			const a = P.neuerAufbau();
			const r = await P.wertebereicheReiter(a, mobil);
			r.inst.u.rows = [];
			r.speichern();
			await P.fertig(a.ctl);
			assert.deepEqual(stand().corridors, []);
		});
	});
}

describe('Wetter-Metriken (AC-13, AC-17)', () => {
	async function mitReiter(): Promise<{ a: P.Aufbau; w: Awaited<ReturnType<typeof P.wetterMetrikenReiter>> }> {
		const a = P.neuerAufbau();
		return { a, w: await P.wetterMetrikenReiter(a) };
	}

	test('Kanal-Layout/Telegram-Kurzform', async () => {
		const { a, w } = await mitReiter();
		w.inst.u.telegramKurzform = true;
		w.metrikenSpeichern();
		await P.fertig(a.ctl);
		assert.equal(dc().telegram_kurzform, true);
	});

	test('Voreinstellung (preset_name)', async () => {
		const { a, w } = await mitReiter();
		w.inst.u.selectedTemplate = 'skitour';
		w.metrikenSpeichern();
		await P.fertig(a.ctl);
		assert.equal(dc().preset_name, 'skitour');
	});

	test('Metrik-Auswahl: zwei Metriken aktiv', async () => {
		const { a, w } = await mitReiter();
		w.inst.u.buckets = { primary: ['temperature', 'wind'], secondary: [], off: [] };
		w.metrikenSpeichern();
		await P.fertig(a.ctl);
		const aktiv = (dc().metrics as Array<{ metric_id: string; enabled: boolean }>).filter((m) => m.enabled).map((m) => m.metric_id);
		assert.deepEqual(aktiv, ['temperature', 'wind']);
	});

	test('Loeschfall: ALLE Metriken abgewaehlt — keine aktive Metrik auf dem Server', async () => {
		const { a, w } = await mitReiter();
		w.inst.u.buckets = { primary: [], secondary: [], off: ['temperature', 'wind'] };
		w.metrikenSpeichern();
		await P.fertig(a.ctl);
		const aktiv = (dc().metrics as Array<{ enabled: boolean }>).filter((m) => m.enabled);
		assert.equal(aktiv.length, 0, 'die Leerauswahl muss ankommen (der Server-Merge loescht nie von selbst)');
	});

	test('Kanal-Layout Telegram: eigener Eintrag, Bestand der anderen Kanaele bleibt', async () => {
		const { a, w } = await mitReiter();
		const cb = w.inst.u.channelBuckets as Record<string, unknown>;
		w.inst.u.channelBuckets = { ...cb, telegram: { buckets: { primary: ['wind'], secondary: [], off: [] }, friendlyMap: {} } };
		w.metrikenSpeichern();
		await P.fertig(a.ctl);
		const cl = dc().channel_layouts as Record<string, Array<{ metric_id: string }>>;
		assert.deepEqual(cl.telegram.map((m) => m.metric_id), ['wind']);
		assert.ok(cl.email?.some((m) => m.metric_id === 'temperature'), 'der Bestand des E-Mail-Layouts muss erhalten bleiben');
	});

	test('Ausblick: Auswahl und Loeschfall (leer)', async () => {
		const { a, w } = await mitReiter();
		(w.inst.u.onOutlookMetricKeys as (k: string[]) => void)(['temp_max_c', 'wind_max_kmh']);
		await P.fertig(a.ctl);
		assert.deepEqual(dc().outlook_metrics, ['temp_max_c', 'wind_max_kmh']);
		(w.inst.u.onOutlookMetricKeys as (k: string[]) => void)([]);
		await P.fertig(a.ctl);
		assert.deepEqual(dc().outlook_metrics, [], 'die Leerung des Ausblicks muss als [] ankommen');
	});

	test('Ausblick-Formate: Auswahl und Leerung', async () => {
		const { a, w } = await mitReiter();
		(w.inst.u.onOutlookMetricFormats as (f: Record<string, boolean>) => void)({ temp_max_c: false });
		await P.fertig(a.ctl);
		assert.deepEqual(dc().outlook_metric_formats, { temp_max_c: false });
		(w.inst.u.onOutlookMetricFormats as (f: Record<string, boolean>) => void)({});
		await P.fertig(a.ctl);
		assert.deepEqual(dc().outlook_metric_formats, {}, 'die Leerung der Formate muss als {} ankommen');
	});

	test('Amtliche Warnungen im Bericht AUS (official_alerts_enabled=false)', async () => {
		const { a, w } = await mitReiter();
		(w.inst.u.onToggleOfficialAlerts as (e: unknown) => void)({ target: { checked: false } });
		await P.fertig(a.ctl);
		assert.equal(stand().official_alerts_enabled, false, 'false muss ankommen (Server-Merge loescht nie)');
	});

	test('E-Mail-Inhalt (alle sieben Schluessel, je ein Wert ungleich dem Seed) und Tagesfenster', async () => {
		const { a, w } = await mitReiter();
		const neu = {
			show_compact_summary: false,
			wind_exposition_min_elevation_m: 2000,
			show_stage_stats: false,
			show_metrics_summary: false,
			show_outlook: false,
			email_format: 'compact',
			show_yesterday_comparison: true,
			day_window_start_hour: 6,
			day_window_end_hour: 20
		};
		const seedRc = SEED.report_config as Record<string, unknown>;
		for (const [k, v] of Object.entries(neu)) {
			assert.notDeepEqual(v, seedRc[k], `Messaufbau: der neue Wert fuer ${k} muss vom Seed abweichen, sonst beweist der Test nichts`);
		}
		w.reportConfigSpeichern(neu);
		await P.fertig(a.ctl);
		for (const [k, v] of Object.entries(neu)) {
			assert.deepEqual(rc()[k], v, `report_config.${k} (Eigenfeld des Wetter-Metriken-Reiters) muss auf dem Server ankommen — vergessener Eigen-Schluessel?`);
		}
		pythonEigenesUnveraendert();
	});
});

describe('Versand (AC-14, AC-17)', () => {
	test('Zeiten, Slots und Hauptschalter', async () => {
		const a = P.neuerAufbau();
		const v = await P.versandReiter(a);
		v.aendern({ morning_time: '06:00:00', evening_time: '19:00:00', morning_enabled: false, evening_enabled: false, enabled: false });
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
		const v = await P.versandReiter(a);
		v.aendern({ send_email: false, send_telegram: false, send_sms: true, send_premium_sms: true });
		await P.fertig(a.ctl);
		assert.equal(rc().send_email, false);
		assert.equal(rc().send_telegram, false);
		assert.equal(rc().send_sms, true);
		assert.equal(rc().send_premium_sms, true);
	});

	test('Telegram-Stil und Mehrtages-Trend-Schalter', async () => {
		const a = P.neuerAufbau();
		const v = await P.versandReiter(a);
		v.aendern({
			telegram_style: 'kurzform',
			multi_day_trend_morning: true,
			multi_day_trend_evening: false,
			multi_day_trend_reports: ['morning']
		});
		await P.fertig(a.ctl);
		assert.equal(rc().telegram_style, 'kurzform');
		assert.equal(rc().multi_day_trend_morning, true);
		assert.equal(rc().multi_day_trend_evening, false);
		assert.deepEqual(rc().multi_day_trend_reports, ['morning']);
	});

	test('der Versand-Reiter beruehrt weder Tagesfenster noch E-Mail-Inhalt auf dem Server', async () => {
		const a = P.neuerAufbau();
		const v = await P.versandReiter(a);
		v.aendern({ morning_time: '08:00:00' });
		await P.fertig(a.ctl);
		const seedRc = SEED.report_config as Record<string, unknown>;
		for (const k of P.REPORT_WETTER_METRIKEN) assert.deepEqual(rc()[k], seedRc[k], `${k} gehoert dem Wetter-Metriken-Reiter`);
	});
});

describe('Kopf, Aktivitaet, Etappen (AC-15)', () => {
	test('Name', async () => {
		const a = P.neuerAufbau();
		const k = await P.kopfReiter(a);
		await k.umbenennen('Neuer Name');
		assert.equal(stand().name, 'Neuer Name');
	});

	test('Aktivitaet', async () => {
		const a = P.neuerAufbau();
		const t = await P.aktivitaetReiter(a);
		await t.aendern('skitour');
		assert.equal(stand().activity, 'skitour');
	});

	test('Etappen', async () => {
		const a = P.neuerAufbau();
		const e = await P.etappenReiter(a);
		e.speichern([{ id: 'T1', name: 'Umbenannt', date: '2026-10-10', waypoints: [] }]);
		await P.fertig(a.ctl);
		assert.equal((stand().stages as Array<{ name: string }>)[0].name, 'Umbenannt');
	});
});
