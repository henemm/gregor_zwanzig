// TDD RED — Issue #3305 (Teil B von #3041, Epic #3122): der eine Anlege-POST trägt Tabelle und Schalter der Karte.
// Spec docs/specs/modules/feat_3305_tabelle_trip_anlegen.md, Test Plan Nr. 4 (AC-2, AC-3) und Nr. 5 (AC-7).
//
// FESTGELEGTE SCHNITTSTELLE (der Implementierer folgt diesen Namen):
//   CreateTripState.karte?: KarteAnlegeStand   (Typ aus shared/wetter-tab/wasStehtWoSpeicherung.ts)
//     KarteAnlegeStand = { placements: Placements; felder: Felder; felderStart: Felder }
//   buildCreateTripPayload(state):
//     - `karte` gesetzt: display_config.placements = karte.placements; dazu die Schalter-Differenz
//       felderNutzlast('route', karte.felder, karte.felderStart) gemischt in display_config (show_night_block) und
//       report_config (show_stage_stats, show_yesterday_comparison, email_format, telegram_style). Alles andere
//       (Versandzeiten, Kanäle, metrics, ampel, Alarm-Felder) bleibt genau wie ohne Karte.
//     - `karte` nicht gesetzt: Rumpf bitgleich zu heute (keine placements, keine Schalterfelder aus der Karte).
//
// Echte Funktion `buildCreateTripPayload`, keine Doubles. Zufalls-IDs (Trip, Etappen) werden vor dem Vergleich ersetzt.
//
//   cd frontend && npm test -- src/lib/components/trip-new/__tests__/trip_anlegen_karte_payload_3305.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import * as T from '../tripNewLogic.ts';

type J = any; // eslint-disable-line @typescript-eslint/no-explicit-any

const START_FELDER = { show_stage_stats: true, show_yesterday_comparison: true, show_night_block: true, email_format: 'full', telegram_style: 'rich', hourly_enabled: true };
const PLACEMENTS = {
	version: 1,
	rows: [
		{ metric_id: 'wind', formats: { email: 'raw' } },
		{ metric_id: 'gust', places: { telegram: false } },
		{ metric_id: 'temperature' }
	],
	outlook_reports: ['morning', 'evening']
};

/** Anlege-Zustand wie TripNewEditor ihn baut, mit Versandzeiten und Kanälen. */
function zustand(extra: Record<string, unknown> = {}): J {
	const alarm = T.initialCreateTripAlarmState();
	return {
		name: 'Neu-3305',
		startDate: '2026-12-01',
		stages: [{ id: 'a', name: 'A', waypoints: [] }, { id: 'b', name: 'B', waypoints: [] }],
		weatherMetrics: [{ metric_id: 'wind', enabled: true }, { metric_id: 'gust', enabled: true }, { metric_id: 'temperature', enabled: true }],
		channels: { email: true, telegram: true, sms: false },
		reportConfig: { morning_enabled: true, morning_time: '06:30', evening_enabled: true, evening_time: '19:00', send_email: true, send_telegram: true, email_format: 'full' },
		alarm,
		officialAlertsEnabled: alarm.officialWarningsEnabled,
		...extra
	};
}
function rumpf(state: J): J {
	const r = JSON.parse(JSON.stringify(T.buildCreateTripPayload(state)));
	r.id = 'neu';
	for (const s of r.stages) s.id = 'etappe';
	return r;
}
/** Alle Blattpfade, deren Wert sich zwischen a und b unterscheidet. */
function abweichungen(a: J, b: J, pfad = ''): string[] {
	const istObj = (x: unknown) => x !== null && typeof x === 'object' && !Array.isArray(x);
	if (istObj(a) && istObj(b)) {
		const keys = new Set([...Object.keys(a), ...Object.keys(b)]);
		return [...keys].flatMap((k) => abweichungen(a[k], b[k], pfad ? `${pfad}.${k}` : k));
	}
	return JSON.stringify(a) === JSON.stringify(b) ? [] : [pfad];
}

describe('#3305 Test 4 (AC-2, AC-3): karte gesetzt — placements und Schalter-Differenz im POST', () => {
	test('Tabelle der Karte steht unverändert in display_config.placements (Reihenfolge, Haken, Formate)', () => {
		const r = rumpf(zustand({ karte: { placements: PLACEMENTS, felder: { ...START_FELDER }, felderStart: { ...START_FELDER } } }));
		assert.deepEqual(r.display_config?.placements, PLACEMENTS);
	});

	test('alle fünf Schalter geändert: Werte an ihrem Ort, sonst weicht nichts ab (Versandzeiten, Kanäle gleich)', () => {
		const ohne = rumpf(zustand());
		const felder = { ...START_FELDER, show_night_block: false, show_stage_stats: false, show_yesterday_comparison: false, email_format: 'compact', telegram_style: 'kurzform' };
		const mit = rumpf(zustand({ karte: { placements: PLACEMENTS, felder, felderStart: { ...START_FELDER } } }));
		assert.equal(mit.display_config?.show_night_block, false);
		assert.equal(mit.report_config?.show_stage_stats, false);
		assert.equal(mit.report_config?.show_yesterday_comparison, false);
		assert.equal(mit.report_config?.email_format, 'compact');
		assert.equal(mit.report_config?.telegram_style, 'kurzform');
		assert.deepEqual(
			abweichungen(ohne, mit).sort(),
			[
				'display_config.placements',
				'display_config.show_night_block',
				'report_config.email_format',
				'report_config.show_stage_stats',
				'report_config.show_yesterday_comparison',
				'report_config.telegram_style'
			],
			'nur Tabelle und die geänderten Schalter weichen ab'
		);
		for (const k of ['morning_enabled', 'morning_time', 'evening_enabled', 'evening_time', 'send_email', 'send_telegram'])
			assert.equal(mit.report_config[k], ohne.report_config[k], `Versandfeld ${k} verändert`);
		assert.deepEqual(mit.display_config.channels, ohne.display_config.channels, 'Kanalwahl verändert');
		assert.deepEqual(mit.display_config.metrics, ohne.display_config.metrics);
	});

	test('nur gegenüber dem Kartenstart Geändertes wird angewandt (zwei Bedienstellen bis #3307)', () => {
		// Zustellung hat email_format auf compact gestellt; die Karte startete schon mit compact und bleibt so.
		const zu = zustand({ reportConfig: { ...zustand().reportConfig, email_format: 'compact' } });
		const start = { ...START_FELDER, email_format: 'compact' };
		const mit = rumpf({ ...zu, karte: { placements: PLACEMENTS, felder: { ...start, show_night_block: false }, felderStart: start } });
		assert.equal(mit.report_config.email_format, 'compact', 'unveränderter Kartenwert überschreibt nichts');
		assert.equal(mit.display_config.show_night_block, false);
		assert.deepEqual(abweichungen(rumpf(zu), mit).sort(), ['display_config.placements', 'display_config.show_night_block']);
	});

	test('Tabelle bedient, Schalter unverändert: keine Schalterfelder im POST', () => {
		const ohne = rumpf(zustand());
		const mit = rumpf(zustand({ karte: { placements: PLACEMENTS, felder: { ...START_FELDER }, felderStart: { ...START_FELDER } } }));
		assert.deepEqual(abweichungen(ohne, mit), ['display_config.placements']);
	});

	test('ohne reportConfig im Zustand: Schalter-Differenz legt report_config an', () => {
		const mit = rumpf(zustand({ reportConfig: undefined, karte: { placements: PLACEMENTS, felder: { ...START_FELDER, show_stage_stats: false }, felderStart: { ...START_FELDER } } }));
		assert.equal(mit.report_config?.show_stage_stats, false);
	});

	test('der Eingabezustand bleibt unverändert (reine Funktion)', () => {
		const z = zustand({ karte: { placements: PLACEMENTS, felder: { ...START_FELDER, email_format: 'compact' }, felderStart: { ...START_FELDER } } });
		const vorher = JSON.stringify(z);
		rumpf(z);
		assert.equal(JSON.stringify(z), vorher);
	});
});

describe('#3305 Test 5 (AC-7): karte nicht gesetzt — Rumpf wie heute (Regressionsschutz)', () => {
	test('keine placements und keine Schalterfelder aus der Karte', () => {
		const r = rumpf(zustand());
		assert.equal('placements' in r.display_config, false);
		assert.equal('show_night_block' in r.display_config, false);
		for (const k of ['show_stage_stats', 'show_yesterday_comparison', 'telegram_style']) assert.equal(k in r.report_config, false, k);
		assert.equal(r.report_config.email_format, 'full', 'email_format nur aus dem Zustand');
	});

	test('karte: undefined ist bitgleich zu einem Zustand ohne das Feld', () => {
		assert.deepEqual(rumpf(zustand({ karte: undefined })), rumpf(zustand()));
	});
});
