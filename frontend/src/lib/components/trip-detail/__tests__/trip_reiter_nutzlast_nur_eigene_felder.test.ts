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
// Erwartet gruen schon heute: Kopf, Aktivitaet, Etappen (sind bereits Teilfeld).
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
function keineFremdschluessel(body: Record<string, unknown>, label: string): void {
	const rc = (body.report_config ?? {}) as Record<string, unknown>;
	for (const k of P.NIE_GESENDET_REPORT) {
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
	]) {
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

// Desktop (`CorridorEditor.svelte`) UND Mobile (`CorridorEditorMobile.svelte`):
// zwei Schreibwege, dieselbe Zusicherung (AC-12).
for (const mobil of [false, true]) {
	const ort = mobil ? 'Mobile' : 'Desktop';
	describe(`AC-12: Wertebereiche (${ort}) — ausschliesslich corridors`, () => {
		test('Korridor aendern: Rumpf = { corridors } ohne display_config', async () => {
			const a = P.neuerAufbau();
			const wb = await P.wertebereicheReiter(a, mobil);
			wb.inst.u.rows = [{ metric: 'wind_max_kmh', label: 'Wind', min: 0, max: 55, notify: true, mark: true }];
			wb.speichern();
			await P.fertig(a.ctl);

			const b = rumpf(0);
			assert.deepEqual(
				P.sortiert(b),
				['corridors'],
				`Wertebereiche-${ort}-Rumpf: ${JSON.stringify(P.sortiert(b))} (heute inkl. der ganzen display_config)`
			);
			keineFremdschluessel(b, `Wertebereiche ${ort}`);
		});

		test('Leerung: corridors = [] wird gesendet (der Server loescht nie von selbst)', async () => {
			const a = P.neuerAufbau();
			const wb = await P.wertebereicheReiter(a, mobil);
			wb.inst.u.rows = [];
			wb.speichern();
			await P.fertig(a.ctl);

			assert.deepEqual(rumpf(0).corridors, []);
			assert.deepEqual(P.sortiert(rumpf(0)), ['corridors']);
		});
	});
}

describe('AC-13: Wetter-Metriken — /weather-config nur Wetter-Metriken-Schluessel, Trip-PUT nur Inhalt + Tagesfenster', () => {
	test('Metriken speichern: /weather-config ohne metric_alert_levels und Fremdschluessel', async () => {
		const a = P.neuerAufbau();
		const wm = await P.wetterMetrikenReiter(a);
		wm.metrikenSpeichern();
		await P.fertig(a.ctl);

		assert.equal(puts().length, 2, 'Messaufbau: /weather-config, dann Trip-PUT');
		assert.match(puts()[0].path, /\/weather-config$/);
		const w = rumpf(0);
		const unerlaubt = P.sortiert(w).filter((k) => !(P.DISPLAY_WETTER_METRIKEN as readonly string[]).includes(k));
		assert.deepEqual(unerlaubt, [], `/weather-config traegt Fremdschluessel: ${JSON.stringify(unerlaubt)} (heute: Spread der ganzen display_config)`);
		for (const k of ['metrics', 'channel_layouts']) {
			assert.ok(k in w, `/weather-config muss den Eigen-Schluessel ${k} senden`);
		}
		assert.ok(!('metric_alert_levels' in w), 'metric_alert_levels gehoert dem Reiter Alarme');
		keineFremdschluessel({ display_config: w }, 'Wetter-Metriken /weather-config');
	});

	test('Metriken speichern: Trip-PUT = { official_alerts_enabled, report_config(nur Inhalt/Tagesfenster) }', async () => {
		const a = P.neuerAufbau();
		const wm = await P.wetterMetrikenReiter(a);
		wm.metrikenSpeichern();
		await P.fertig(a.ctl);

		const t = rumpf(1);
		assert.deepEqual(P.sortiert(t), ['official_alerts_enabled', 'report_config']);
		const unerlaubt = P.sortiert(t.report_config).filter((k) => !(P.REPORT_WETTER_METRIKEN as readonly string[]).includes(k));
		assert.deepEqual(
			unerlaubt,
			[],
			`report_config traegt Fremdschluessel: ${JSON.stringify(unerlaubt)} (Versandzeiten, Kanaele, skip_next, … gehoeren nicht in diesen Reiter)`
		);
		// EXAKT, nicht nur Teilmenge: ein vergessener Eigen-Schluessel (Hauptrisiko der Spec,
		// „wird still nicht mehr gespeichert") faellt sonst nicht auf. Der Seed traegt alle neun.
		assert.deepEqual(
			P.sortiert(t.report_config),
			alsSet(P.REPORT_WETTER_METRIKEN),
			'report_config muss GENAU die Inhalt-/Tagesfenster-Schluessel des Reiters tragen'
		);
		keineFremdschluessel(t, 'Wetter-Metriken Trip-PUT');
	});

	test('Tagesfenster/Inhalt (reportConfig-only-Pfad): nur Inhalt/Tagesfenster-Schluessel', async () => {
		const a = P.neuerAufbau();
		const wm = await P.wetterMetrikenReiter(a);
		wm.reportConfigSpeichern({ day_window_start_hour: 6 });
		await P.fertig(a.ctl);

		assert.equal(puts().length, 1);
		const t = rumpf(0);
		assert.deepEqual(P.sortiert(t), ['official_alerts_enabled', 'report_config']);
		const unerlaubt = P.sortiert(t.report_config).filter((k) => !(P.REPORT_WETTER_METRIKEN as readonly string[]).includes(k));
		assert.deepEqual(unerlaubt, [], `report_config traegt Fremdschluessel: ${JSON.stringify(unerlaubt)}`);
		assert.deepEqual(
			P.sortiert(t.report_config),
			alsSet(P.REPORT_WETTER_METRIKEN),
			'auch der reportConfig-only-Pfad muss GENAU die Eigenschluessel des Reiters tragen (kein vergessener Schluessel)'
		);
		assert.equal((t.report_config as Record<string, unknown>).day_window_start_hour, 6);
		keineFremdschluessel(t, 'Wetter-Metriken Tagesfenster');
	});
});

describe('AC-14: Versand — nur Versand-Schluessel, kein Tagesfenster, kein E-Mail-Inhalt', () => {
	test('Versandzeit aendern: Rumpf = { report_config } mit genau den Versand-Schluesseln', async () => {
		const a = P.neuerAufbau();
		const v = await P.versandReiter(a);
		v.aendern({ morning_time: '08:00:00' });
		await P.fertig(a.ctl);

		assert.equal(puts().length, 1);
		const b = rumpf(0);
		assert.deepEqual(P.sortiert(b), ['report_config'], 'der Versand-Reiter sendet nur report_config');
		assert.deepEqual(
			P.sortiert(b.report_config),
			alsSet(P.REPORT_VERSAND),
			`Versand-report_config: ${JSON.stringify(P.sortiert(b.report_config))} (heute die ganze Vollkopie inkl. day_window_*, skip_next, E-Mail-Inhalt)`
		);
		const rc = b.report_config as Record<string, unknown>;
		assert.equal(rc.morning_time, '08:00:00');
		assert.ok(!('day_window_start_hour' in rc) && !('day_window_end_hour' in rc), 'kein Tagesfenster');
		keineFremdschluessel(b, 'Versand');
	});
});

describe('AC-15: Kopf, Aktivitaet, Etappen — nur das eigene Feld (heute schon so)', () => {
	test('Kopf: { name }', async () => {
		const a = P.neuerAufbau();
		const k = await P.kopfReiter(a);
		await k.umbenennen('Neuer Name');
		assert.deepEqual(rumpf(0), { name: 'Neuer Name' });
	});

	test('Aktivitaet: { activity }', async () => {
		const a = P.neuerAufbau();
		const t = await P.aktivitaetReiter(a);
		await t.aendern('skitour');
		assert.deepEqual(rumpf(0), { activity: 'skitour' });
	});

	test('Etappen: { stages }', async () => {
		const a = P.neuerAufbau();
		const e = await P.etappenReiter(a);
		e.speichern([{ id: 'T1', name: 'Umbenannt', date: '2026-10-10', waypoints: [] }]);
		await P.fertig(a.ctl);
		assert.deepEqual(P.sortiert(rumpf(0)), ['stages']);
	});
});
