// TDD RED — Issue #1433: jeder Trip-Reiter sendet NUR die Felder, die er selbst
// bedient (Feld-Eigentuemer-Tabelle der Spec, §2) — nie eine Vollkopie fremder
// Felder, nie Python-eigene Schluessel.
//
// Spec: docs/specs/bugfix/trip_mehrreiter_konfliktschutz.md — §2, §3,
//       AC-11, AC-12, AC-13, AC-14, AC-15, AC-16.
//
// Gemessen wird der ANFRAGE-Rumpf, den der ECHTE Reiter (echtes Instanz-Skript,
// echtes `api`) tatsaechlich an den Ersatz-Server schickt — nicht ein nachgebauter
// Payload-Builder. Der lokale Altstand der Reiter traegt JEDEN Schluessel der
// Tabelle (vollerTrip), sodass ein Fremdfeld im Rumpf nicht an einem fehlenden
// Seed vorbeirutscht. Exakte Schluesselmengen: sowohl ein ZUVIEL als auch ein
// ZUWENIG (vergessener Eigen-Schluessel) faellt auf.
//
// Erwartet gruen schon heute: Kopf, Tempo, Etappen (sind bereits Teilfeld).
// Issue #2284 S2: Kopf/Region laufen ueber `TripHeader.onSaveField` (Tempo seit #3196 ueber Etappen)
// (Pruefstand `kopfReiter`, AC-17) — RED, bis der Kopf die Funktion deklariert.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/trip-detail/__tests__/trip_reiter_nutzlast_nur_eigene_felder.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../api.ts';
import { clearEtagRegistry } from '../../../etagRegistry.ts';
import { createFakeTripServer, type FakeTripServer } from '../../../__tests__/fakeTripServer.ts';
import * as P from './tripMehrreiterPruefstand.ts';

let server: FakeTripServer;

beforeEach(async () => {
	clearEtagRegistry();
	server = createFakeTripServer({ merge: true });
	server.install();
	server.seed(P.TRIP_ID, P.vollerTrip());
	await api.get(P.TRIP_PFAD); // kein Konflikt: jeder PUT geht durch
});
afterEach(() => server.restore());

const puts = () => server.calls.filter((c) => c.method === 'PUT');
const rumpf = (i: number): Record<string, unknown> => {
	const p = puts()[i];
	assert.ok(p, `Messaufbau: es gibt keinen PUT Nr. ${i + 1} (gesehen: ${puts().length})`);
	return p.anfrage as Record<string, unknown>;
};
const alsSet = (liste: readonly string[]): string[] => [...liste].sort();

/** AC-16: in KEINEM Rumpf ein Python-eigener oder unbekannter Schluessel. */
function keineFremdschluessel(body: Record<string, unknown>, label: string, erlaubt: readonly string[] = [], erlaubtReport: readonly string[] = []): void {
	const rc = (body.report_config ?? {}) as Record<string, unknown>;
	for (const k of P.NIE_GESENDET_REPORT.filter((k) => !erlaubtReport.includes(k))) {
		assert.ok(!(k in rc), `${label}: report_config.${k} darf kein Reiter je senden (Python-eigen / ohne Eigentuemer)`);
	}
	const dc = (body.display_config ?? {}) as Record<string, unknown>;
	for (const k of [
		'channel_layouts_per_report',
		'show_night_block',
		'night_interval_hours',
		'thunder_forecast_days',
		'sms_metrics',
		'multi_day_trend_reports',
		'alert_preset',
		'trip_id',
		'updated_at'
	].filter((k) => !erlaubt.includes(k))) {
		// Issue #1721: `show_night_block` gehoert der Karte „Was steht wo“ (nur dort erlaubt).
		assert.ok(!(k in dc), `${label}: display_config.${k} hat keinen Reiter-Eigentuemer und darf nie gesendet werden`);
	}
	assert.ok(!('skip_next' in body), `${label}: Top-Level skip_next darf nie gesendet werden`);
}

describe('AC-11: Alarme — Eigenfelder, display_config nur mit metric_alert_levels', () => {
	test('Alarm-Empfindlichkeit aendern: genau die Alarme-Felder, display_config = { metric_alert_levels }', async () => {
		const a = P.neuerAufbau();
		const alarme = await P.alarmeReiter(a);
		alarme.empfindlichkeitAendern('wind', 'sensibel');
		await P.fertig(a.ctl);

		assert.equal(puts().length, 1);
		const b = rumpf(0);
		assert.deepEqual(P.sortiert(b), alsSet([...P.TOP_ALARME, 'display_config']), `Alarme-Rumpf: ${JSON.stringify(P.sortiert(b))}`);
		assert.deepEqual(
			P.sortiert(b.display_config),
			['metric_alert_levels'],
			'Alarme darf von display_config NUR metric_alert_levels senden (heute: die ganze Kopie als Spread)'
		);
		keineFremdschluessel(b, 'Alarme');
	});

	test('Kanal-Umschalten: dieselbe Schluesselmenge (jede Alarm-Aenderung sendet alle Alarme-Felder)', async () => {
		const a = P.neuerAufbau();
		const alarme = await P.alarmeReiter(a);
		alarme.kanalUmschalten('sms');
		await P.fertig(a.ctl);

		const b = rumpf(0);
		assert.deepEqual(P.sortiert(b), alsSet([...P.TOP_ALARME, 'display_config']));
		assert.deepEqual(P.sortiert(b.display_config), ['metric_alert_levels']);
	});
});

// AC-12 Wertebereiche (Desktop `CorridorEditor.svelte` UND Mobile `CorridorEditorMobile.svelte`):
// #2794 S3a Teil-PR 4a (AC-31) mit beiden Schreibwegen entfernt — die Grenzen schreibt der
// Reiter Wetter (Nutzlast-Tests in shared/wetter-tab/__tests__/).

// #3020 S1 (Adversary F1): `wetterReiter` bindet die Karte „Was steht wo“ wie der Hub. Ob `placements` mitfaehrt,
// haengt allein daran, ob am Trip eine Tabelle gespeichert ist; beide Faelle stehen unten.
// #3020 S1: AC-13/AC-14 an den lebenden Schreibern (Reiter Wetter, Karte „Was steht wo“, Reiter Zustellung)
// statt WeatherMetricsTab/BriefingScheduleTab.
// BEFUND: der Trip-PUT des Reiters Wetter traegt report_config als VOLLKOPIE (tripSpeicherPayload in
// ampelSchreiben.ts) — Versandzeiten, Kanaele und Python-eigene Felder eingeschlossen. Die exakte Zusicherung
// bleibt stehen und ist als `todo` sichtbar rot, bis der Speicherweg repariert ist (kein Produktionscode in
// #3020 S1). NICHT streichen, NICHT abschwaechen.
const BEFUND_VOLLKOPIE = 'Befund #3020 S1: Reiter Wetter sendet report_config als Vollkopie (#1433 AC-13/AC-16 am lebenden Modul verletzt, Bug #3355)';

describe('AC-13: Reiter Wetter — /weather-config nur Wetter-Schluessel, Trip-PUT nur Warnungen/Radar + Tagesfenster', () => {
	test('Trip ohne gespeicherte Tabelle: /weather-config = { ampel, metrics }, ohne metric_alert_levels und Fremdschluessel', async () => {
		const a = P.neuerAufbau();
		const w = await P.wetterReiter(a);
		w.abwaehlen('wind');
		await P.fertig(a.ctl);

		assert.equal(puts().length, 2, 'Messaufbau: /weather-config, dann Trip-PUT');
		assert.match(puts()[0].path, /\/weather-config$/);
		assert.deepEqual(P.sortiert(rumpf(0)), ['ampel', 'metrics'], 'EXAKT die Eigenschluessel (kein Zuviel, kein Zuwenig)');
		keineFremdschluessel({ display_config: rumpf(0) }, 'Wetter /weather-config');
	});

	test('Trip MIT gespeicherter Tabelle: /weather-config = { ampel, metrics, placements }, weiter genau zwei PUTs', async () => {
		const doc = P.vollerTrip();
		(doc.display_config as Record<string, unknown>).placements = { version: 1, rows: [{ metric_id: 'temperature' }, { metric_id: 'wind' }], outlook_reports: ['evening'] };
		const a = P.neuerAufbau(doc);
		const w = await P.wetterReiter(a);
		w.abwaehlen('wind');
		await P.fertig(a.ctl);

		assert.equal(puts().length, 2, 'die Karte schreibt keinen eigenen Tabellen-PUT (#3237 Runde 13)');
		assert.deepEqual(P.sortiert(rumpf(0)), ['ampel', 'metrics', 'placements']);
		assert.deepEqual(rumpf(0).placements, { version: 1, rows: [{ metric_id: 'temperature' }], outlook_reports: ['evening'] });
		keineFremdschluessel({ display_config: rumpf(0) }, 'Wetter /weather-config');
	});

	test('Grundauswahl speichern: Trip-PUT traegt Warn-Felder, Radar und report_config mit Tagesfenster', async () => {
		const a = P.neuerAufbau();
		const w = await P.wetterReiter(a);
		w.aendern({ tagesfenster: { start: 6, end: 20 } });
		await P.fertig(a.ctl);

		const t = rumpf(1);
		assert.deepEqual(P.sortiert(t), ['official_alerts_enabled', 'official_warnings', 'radar_alert_enabled', 'report_config']);
		const rc = t.report_config as Record<string, unknown>;
		assert.deepEqual([rc.day_window_start_hour, rc.day_window_end_hour], [6, 20]);
	});

	for (const [geste, tun] of [
		['Grundauswahl', (w: Awaited<ReturnType<typeof P.wetterReiter>>) => w.abwaehlen('wind')],
		['Tagesfenster', (w: Awaited<ReturnType<typeof P.wetterReiter>>) => w.aendern({ tagesfenster: { start: 6, end: 20 } })]
	] as const)
		test(`${geste}: report_config des Trip-PUT GENAU das Tagesfenster, keine Fremd- und Python-Schluessel`, { todo: BEFUND_VOLLKOPIE }, async () => {
			const a = P.neuerAufbau();
			tun(await P.wetterReiter(a));
			await P.fertig(a.ctl);
			const t = rumpf(1);
			assert.deepEqual(P.sortiert(t.report_config), ['day_window_end_hour', 'day_window_start_hour']);
			keineFremdschluessel(t, 'Wetter Trip-PUT');
		});
});

describe('AC-13: Karte „Was steht wo“ — je Schalter genau EIN Feld an seinem Ort', () => {
	for (const [feld, wert] of Object.entries(P.KARTE_REPORT)) {
		test(`${feld}: { report_config: { ${feld} } }`, async () => {
			const a = P.neuerAufbau();
			(await P.karteWasStehtWo(a)).schalten(feld, wert);
			await P.fertig(a.ctl);
			assert.equal(puts().length, 1);
			assert.deepEqual(rumpf(0), { report_config: { [feld]: wert } });
			keineFremdschluessel(rumpf(0), `Karte ${feld}`, [], [feld]);
		});
	}
	test('#1721 show_night_block: { display_config: { show_night_block } }', async () => {
		const a = P.neuerAufbau();
		(await P.karteWasStehtWo(a)).schalten('show_night_block', false);
		await P.fertig(a.ctl);
		assert.equal(puts().length, 1);
		assert.deepEqual(rumpf(0), { display_config: { show_night_block: false } });
		keineFremdschluessel(rumpf(0), 'Karte show_night_block', ['show_night_block']);
	});
	test('Tabelle: PUT placements mit dem vollstaendigen Stand, kein Trip-Feld', async () => {
		const a = P.neuerAufbau();
		(await P.karteWasStehtWo(a)).haken('temperature', 'telegram', false);
		await P.fertig(a.ctl);
		assert.equal(puts().length, 1);
		assert.equal(puts()[0].path, `/api/briefings/${P.TRIP_ID}/placements?kind=route`);
		assert.deepEqual(P.sortiert(rumpf(0)), ['outlook_reports', 'rows', 'version']);
	});
});

describe('AC-14: Reiter Zustellung — nur geaenderte Zustellungs-Felder, kein Tagesfenster, kein E-Mail-Inhalt', () => {
	test('Versandzeit aendern: Rumpf = { report_config: { morning_time } }', async () => {
		const a = P.neuerAufbau();
		const v = await P.zustellungReiter(a);
		v.aendern({ morgenZeit: '08:00' });
		await P.fertig(a.ctl);

		assert.equal(puts().length, 1);
		const b = rumpf(0);
		assert.deepEqual(b, { report_config: { morning_time: '08:00:00' } }, 'EXAKT das geaenderte Feld');
		keineFremdschluessel(b, 'Zustellung');
	});

	test('alle Versand-Felder auf einmal: GENAU die Versand-Schluessel des Reiters', async () => {
		const a = P.neuerAufbau();
		const v = await P.zustellungReiter(a);
		v.aendern({ morgenAn: false, abendAn: false, morgenZeit: '08:00', abendZeit: '19:00', briefing: { email: false, telegram: false, sms: true, premium_sms: true } });
		await P.fertig(a.ctl);

		assert.equal(puts().length, 1);
		const b = rumpf(0);
		assert.deepEqual(P.sortiert(b), ['report_config']);
		assert.deepEqual(P.sortiert(b.report_config), alsSet(P.REPORT_ZUSTELLUNG));
		keineFremdschluessel(b, 'Zustellung');
	});

	test('Alarm-Kanaele und Stille Stunden: eigener PUT nur mit Alarm-Feldern', async () => {
		const a = P.neuerAufbau();
		const v = await P.zustellungReiter(a);
		v.aendern({ alarme: { email: true, telegram: false, sms: false, premium_sms: true }, stilleVon: '23:00' });
		await P.fertig(a.ctl);

		assert.equal(puts().length, 1);
		assert.deepEqual(rumpf(0), { alert_channels: { email: true, telegram: false, sms: false, premium_sms: true }, alert_quiet_from: '23:00' });
	});
});

describe('AC-15: Kopf, Tempo, Etappen — nur das eigene Feld (heute schon so)', () => {
	test('Kopf: { name }', async () => {
		const a = P.neuerAufbau();
		const k = await P.kopfReiter(a);
		await k.umbenennen('Neuer Name');
		assert.deepEqual(rumpf(0), { name: 'Neuer Name' });
	});

	// #3196: Tempo-Karte im Reiter Etappen — Rumpf des Reiters { stages, tempo }, nie activity.
	test('Tempo: { stages, tempo } (#3196)', async () => {
		const a = P.neuerAufbau();
		const t = await P.tempoReiter(a);
		await t.aendern({ fortbewegung: 'ski', grundtempo_kmh: 3 });
		assert.deepEqual(P.sortiert(rumpf(0)), ['stages', 'tempo']);
		assert.deepEqual((rumpf(0) as { tempo: unknown }).tempo, { fortbewegung: 'ski', grundtempo_kmh: 3 });
	});

	test('Etappen: { stages }', async () => {
		const a = P.neuerAufbau();
		const e = await P.etappenReiter(a);
		e.speichern([{ id: 'T1', name: 'Umbenannt', date: '2026-10-10', waypoints: [] }]);
		await P.fertig(a.ctl);
		assert.deepEqual(P.sortiert(rumpf(0)), ['stages']);
	});
});

// Issue #2284 S2 (AC-6, AC-17): alle drei Kopf-Felder ueber `TripHeader.onSaveField` —
// je PUT exakt EIN Schluessel, nie ein Spread des Seiten-Trips (Fehlerklasse #2375/#2381).
describe('#2284 S2 AC-6: Kopf-Region — nur das Eigenfeld, auch beim Leeren', () => {
	test('Region: { region }', async () => {
		const a = P.neuerAufbau();
		const k = await P.kopfReiter(a);
		await k.regionAendern('Alpen Nord');
		assert.deepEqual(rumpf(0), { region: 'Alpen Nord' });
	});

	test('Region leeren: { region: "" } — der Schluessel bleibt im Rumpf (sonst kommt das Leeren nie an)', async () => {
		const a = P.neuerAufbau();
		const k = await P.kopfReiter(a);
		await k.regionAendern('');
		assert.deepEqual(rumpf(0), { region: '' });
	});

	test('Folge Name ⇒ Region: zwei PUTs mit je genau einem Schluessel', async () => {
		const a = P.neuerAufbau();
		const k = await P.kopfReiter(a);
		await k.umbenennen('Neuer Name');
		await k.regionAendern('Alpen Nord');
		assert.equal(puts().length, 2);
		assert.deepEqual(rumpf(0), { name: 'Neuer Name' });
		assert.deepEqual(rumpf(1), { region: 'Alpen Nord' });
	});
});
