// Issue #2987 — Trip-Briefing-Startwerte aus EINER Lesefunktion (AC-2, AC-3, AC-4).
// Spec: docs/specs/modules/refactor_2987_standardwerte_eine_quelle.md
// Dieselbe Fallliste mit FESTEN Werten laeuft durch Lesefunktion, Reiter Zustellung und Anlege-Weg.
// Schnittstelle: leseBriefingStartwerte(rc) -> Felder wie STANDARD (Zeiten 'HH:MM').
//   cd frontend && npm test -- src/lib/components/shared/__tests__/briefing_startwerte.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { ladeReportZustand } from '../versand-tab/reportConfigPayload.ts';
import { standAusPreset, standAusTrip } from '../zustellung-tab/zustellungModell.ts';
import type { ComparePreset, Trip } from '../../../types.ts';

type Blob = Record<string, unknown> | null | undefined;
const STANDARD = {
	morning_enabled: true, evening_enabled: true, morning_time: '07:00', evening_time: '18:00',
	send_email: true, send_telegram: false, send_sms: false, send_premium_sms: false
};
const AUS = { morning_enabled: false, evening_enabled: false };

/** [Fall, Blob, Abweichung vom Standard] */
const FAELLE: Array<[string, Blob, Partial<typeof STANDARD>]> = [
	['undefined', undefined, {}],
	['null', null, {}],
	['unbekannte Felder', { change_threshold_temp: 3 }, {}],
	['enabled:false schlaegt gesetzte Slots', { enabled: false, morning_enabled: true, evening_enabled: true }, AUS],
	['nur Morgen', { evening_enabled: false }, { evening_enabled: false }],
	['nur Abend', { morning_enabled: false, evening_enabled: true }, { morning_enabled: false }],
	['beide Slots an', { enabled: true, morning_enabled: true, evening_enabled: true }, {}],
	['Slots null', { morning_enabled: null, evening_enabled: null }, {}],
	['Zeiten HH:MM:SS', { morning_time: '06:45:00', evening_time: '19:15:00' }, { morning_time: '06:45', evening_time: '19:15' }],
	['Zeiten HH:MM', { morning_time: '05:30', evening_time: '20:00' }, { morning_time: '05:30', evening_time: '20:00' }],
	['Zeiten null', { morning_time: null, evening_time: null }, {}],
	['Zeiten leer', { morning_time: '', evening_time: '' }, {}],
	['Zeiten ungueltig', { morning_time: 'abc', evening_time: '9:15' }, {}],
	['Zeiten mit Text davor', { morning_time: ' 06:45', evening_time: 'x19:15' }, {}],
	['Zeiten kein Text', { morning_time: 645, evening_time: 1915 }, {}],
	['E-Mail aus', { send_email: false }, { send_email: false }],
	['E-Mail null = an', { send_email: null }, {}],
	['Telegram an', { send_telegram: true }, { send_telegram: true }],
	['SMS an', { send_sms: true }, { send_sms: true }],
	['Premium-SMS an', { send_premium_sms: true }, { send_premium_sms: true }],
	['Kanaele kein bool = Vorgabe', { send_email: '', send_telegram: 'true', send_sms: 1, send_premium_sms: null }, {}]
];

const MODUL = '../briefingStartwerte.ts'; // dynamisch: fehlt es, laufen die uebrigen Leser trotzdem

/** Briefing-Teil des Reiters Zustellung in den Feldnamen des Blobs. */
function ausReiter(rc: Blob): typeof STANDARD {
	const { morgenAn, abendAn, morgenZeit, abendZeit, briefing: b } = standAusTrip({ stages: [], report_config: rc } as unknown as Trip);
	return {
		morning_enabled: morgenAn, evening_enabled: abendAn, morning_time: morgenZeit, evening_time: abendZeit,
		send_email: b.email, send_telegram: b.telegram, send_sms: b.sms, send_premium_sms: b.premium_sms
	};
}

describe('#2987 AC-2/AC-3: eine Lesefunktion, zwei Leser, feste Werte', () => {
	for (const [fall, blob, abweichung] of FAELLE) {
		const erwartet = { ...STANDARD, ...abweichung };
		test(`Lesefunktion: ${fall}`, async () => assert.deepEqual((await import(MODUL)).leseBriefingStartwerte(blob), erwartet));
		test(`Reiter Zustellung: ${fall}`, () => assert.deepEqual(ausReiter(blob), erwartet));
		test(`Anlege-Weg: ${fall}`, () => assert.deepEqual(ladeReportZustand(blob), { ...erwartet, telegram_style: 'rich' }));
	}
});

describe('#2987 AC-4: Orts-Briefing behaelt seine eigenen Slot-Vorgaben', () => {
	for (const [fall, felder, erwartet] of [
		['neu', {}, [true, '07:00', false, '18:00']],
		['enabled:false ist keine Trip-Slot-Regel', { enabled: false, evening_enabled: true }, [true, '07:00', true, '18:00']],
		['Zeiten HH:MM:SS', { morning_time: '06:45:00', evening_time: '19:15:00' }, [true, '06:45', false, '19:15']],
		['Zeiten leer/ungueltig', { morning_time: '', evening_time: 'abc' }, [true, '07:00', false, '18:00']]
	] as const) {
		test(fall, () => {
			const s = standAusPreset(felder as unknown as ComparePreset);
			assert.deepEqual([s.morgenAn, s.morgenZeit, s.abendAn, s.abendZeit], erwartet);
			assert.deepEqual(s.briefing, { email: true, telegram: false, sms: false, premium_sms: false });
		});
	}
});
