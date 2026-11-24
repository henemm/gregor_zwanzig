// TDD RED — Issue #3332 (Teil D1 von #3307, Epic #3122): der Stand des Reiters „Zustellung“ im einen
// Anlege-POST. Spec docs/specs/modules/feat_3332_zustellung_anlegen_trip.md, Test Plan Nr. 2 und 4
// (AC-2, AC-3, AC-7) — reiner Helfer, Muster `mitKarte` (#3305).
//
// FESTGELEGTE SCHNITTSTELLE (trip-new/tripNewLogic.ts):
//   mitZustellung(reportConfig: ReportConfig | undefined, alarm: CreateTripAlarmState, stand: ZustellungStand | undefined)
//     -> { reportConfig: ReportConfig | undefined; alarm: CreateTripAlarmState }
//   Rein (Eingaben bleiben unverändert), Read-Modify-Write:
//     report_config: morning_enabled, evening_enabled, enabled (= Morgen || Abend), morning_time/evening_time
//       („HH:MM:SS“, nur rastergültige Zeiten — eine rasterfremde Zeit lässt den vorhandenen Wert stehen),
//       send_email/telegram/sms/premium_sms; alle übrigen Felder (Tagesfenster, Mail-Inhalt, Karte) bleiben.
//     alarm: channels (vier Kanäle), channelThresholds (vier Kanäle), quietFrom/quietTo (aus = undefined),
//       cooldownMinutes; officialWarningsEnabled, metricLevels, metricChannels bleiben.
//   stand === undefined (Reiter nie bedient): Ausgabe gleich Eingabe.
// Der POST entsteht danach wie heute über buildCreateTripPayload (dort geprüft: genau die Felder im Körper).
//
// Echte Funktionen, keine Doubles.
//
//   cd frontend && npm test -- src/lib/components/trip-new/__tests__/trip_anlegen_zustellung_payload_3332.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import * as T from '../tripNewLogic.ts';
import { standAusTrip, type ZustellungStand } from '../../shared/zustellung-tab/zustellungModell.ts';

type J = any; // eslint-disable-line @typescript-eslint/no-explicit-any
const klon = <T>(v: T): T => (v === undefined ? v : JSON.parse(JSON.stringify(v)));

function mitZustellung(rc: J, alarm: J, stand: J): { reportConfig: J; alarm: J } {
	const f = (T as J).mitZustellung;
	assert.equal(typeof f, 'function', 'tripNewLogic.ts exportiert keinen reinen Helfer `mitZustellung`');
	return f(rc, alarm, stand);
}

/** report_config, wie der Editor ihn vor dem POST hält: Tagesfenster aus dem Reiter Wetter, Mail-Inhalt. */
const RC = { day_window_start_hour: 4, day_window_end_hour: 19, email_format: 'compact', show_stability: true, morning_time: '07:00:00' };
const START: ZustellungStand = standAusTrip({ id: '__new__', name: 'x', stages: [], report_config: undefined } as J);
function alarm0(): J {
	return { ...T.initialCreateTripAlarmState(), metricLevels: { wind: 'HIGH' } };
}
function bedient(): ZustellungStand {
	return {
		...klon(START),
		morgenAn: true,
		morgenZeit: '06:45',
		abendAn: false,
		abendZeit: '19:30',
		briefing: { email: true, telegram: true, sms: true, premium_sms: false },
		alarme: { email: true, telegram: true, sms: true, premium_sms: false },
		dringlichkeit: { email: 'LOW', telegram: 'HIGH', sms: 'MODERATE', premium_sms: 'LOW' },
		stilleAn: true,
		stilleVon: '22:30',
		stilleBis: '06:15',
		cooldown: 45
	};
}
function post(reportConfig: J, alarm: J): J {
	const r = klon(T.buildCreateTripPayload({
		name: 'Neu-3332', startDate: '2026-12-01', stages: [{ id: 'a', name: 'A', waypoints: [] }],
		weatherMetrics: [], channels: { email: true, telegram: true, sms: false },
		reportConfig: T.ergaenzeVersandStandard(reportConfig), alarm, officialAlertsEnabled: alarm.officialWarningsEnabled
	} as J));
	return r;
}

describe('#3332 Test 2 (AC-2, AC-3): mitZustellung mischt den Stand in report_config und Alarm-Felder', () => {
	test('Zeiten, Schalter, Briefing-Kanäle in report_config; bestehende Felder erhalten', () => {
		const { reportConfig } = mitZustellung(klon(RC), alarm0(), bedient());
		assert.equal(reportConfig.morning_enabled, true);
		assert.equal(reportConfig.evening_enabled, false);
		assert.equal(reportConfig.enabled, true);
		assert.equal(reportConfig.morning_time, '06:45:00');
		assert.equal(reportConfig.evening_time, '19:30:00');
		assert.equal(reportConfig.send_email, true);
		assert.equal(reportConfig.send_telegram, true);
		assert.equal(reportConfig.send_sms, true);
		assert.equal(reportConfig.send_premium_sms, false);
		for (const [k, v] of Object.entries(RC)) if (k !== 'morning_time') assert.deepEqual(reportConfig[k], v, `Bestandsfeld ${k} verloren`);
	});

	test('beide Briefings aus: enabled false', () => {
		const { reportConfig } = mitZustellung(klon(RC), alarm0(), { ...bedient(), morgenAn: false, abendAn: false });
		assert.equal(reportConfig.enabled, false);
	});

	test('Alarm-Kanäle, Dringlichkeit, Stille, Cooldown in den Alarm-Zustand; Metrik-Stufen und Warnungen bleiben', () => {
		const a0 = alarm0();
		const { alarm } = mitZustellung(klon(RC), a0, bedient());
		assert.deepEqual(alarm.channels, { email: true, telegram: true, sms: true, premium_sms: false });
		assert.deepEqual(alarm.channelThresholds, { email: 'LOW', telegram: 'HIGH', sms: 'MODERATE', premium_sms: 'LOW' });
		assert.equal(alarm.quietFrom, '22:30');
		assert.equal(alarm.quietTo, '06:15');
		assert.equal(alarm.cooldownMinutes, 45);
		assert.deepEqual(alarm.metricLevels, { wind: 'HIGH' });
		assert.equal(alarm.officialWarningsEnabled, a0.officialWarningsEnabled);
	});

	test('Stille Stunden aus: quietFrom/quietTo leer, im POST null', () => {
		const { reportConfig, alarm } = mitZustellung(klon(RC), alarm0(), { ...bedient(), stilleAn: false });
		assert.equal(alarm.quietFrom ?? null, null);
		assert.equal(alarm.quietTo ?? null, null);
		const p = post(reportConfig, alarm);
		assert.equal(p.alert_quiet_from, null);
		assert.equal(p.alert_quiet_to, null);
	});

	test('im POST: report_config und Alarm-Felder tragen genau die eingestellten Werte', () => {
		const { reportConfig, alarm } = mitZustellung(klon(RC), alarm0(), bedient());
		const p = post(reportConfig, alarm);
		assert.equal(p.report_config.morning_time, '06:45:00');
		assert.equal(p.report_config.evening_enabled, false);
		assert.equal(p.report_config.send_telegram, true);
		assert.deepEqual(p.alert_channels, { email: true, telegram: true, sms: true, premium_sms: false });
		assert.equal(p.alert_channel_thresholds.telegram, 'HIGH');
		assert.equal(p.alert_quiet_from, '22:30');
		assert.equal(p.alert_quiet_to, '06:15');
		assert.equal(p.alert_cooldown_minutes, 45);
		assert.ok('multi_day_trend_reports' in p.report_config, 'ergaenzeVersandStandard bleibt im POST');
		assert.equal(p.report_config.email_format, 'compact', 'Mail-Inhalt verloren');
	});

	test('Reiter nie bedient (stand undefined): Ausgabe gleich Eingabe', () => {
		const rc = klon(RC);
		const a = alarm0();
		const r = mitZustellung(rc, a, undefined);
		assert.deepEqual(r.reportConfig, RC);
		assert.deepEqual(r.alarm, alarm0());
	});

	test('rein: Eingaben bleiben unverändert', () => {
		const rc = klon(RC);
		const a = alarm0();
		const s = bedient();
		const vorher = JSON.stringify([rc, a, s]);
		mitZustellung(rc, a, s);
		assert.equal(JSON.stringify([rc, a, s]), vorher);
	});

	test('ohne report_config im Editor: Helfer legt ihn an', () => {
		const { reportConfig } = mitZustellung(undefined, alarm0(), bedient());
		assert.equal(reportConfig?.morning_time, '06:45:00');
	});
});

describe('#3332 Test 4 (AC-7): rasterfremde Uhrzeit wird nie übernommen', () => {
	test('06:50: vorhandene gültige Zeit bleibt, 06:50 nirgends im POST', () => {
		const { reportConfig, alarm } = mitZustellung({ ...klon(RC), morning_time: '06:45:00' }, alarm0(), { ...bedient(), morgenZeit: '06:50' });
		assert.equal(reportConfig.morning_time, '06:45:00');
		assert.ok(!JSON.stringify(post(reportConfig, alarm)).includes('06:50'));
	});

	test('Abendzeit 18:07 ohne vorhandenen Wert: kein evening_time aus dem Stand (Standard aus dem POST-Ergänzer)', () => {
		const { reportConfig, alarm } = mitZustellung(klon(RC), alarm0(), { ...bedient(), abendZeit: '18:07' });
		assert.notEqual(reportConfig.evening_time, '18:07:00');
		assert.ok(!JSON.stringify(post(reportConfig, alarm)).includes('18:07'));
	});

	test('gültige Zeiten derselben Meldung gehen trotzdem durch', () => {
		const { reportConfig } = mitZustellung(klon(RC), alarm0(), { ...bedient(), morgenZeit: '06:50', abendZeit: '20:15' });
		assert.equal(reportConfig.evening_time, '20:15:00');
	});
});
