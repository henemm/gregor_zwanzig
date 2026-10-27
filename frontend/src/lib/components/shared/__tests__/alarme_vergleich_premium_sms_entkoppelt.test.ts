// TDD RED — Issue #2293 Scheibe S2 (AC-9), Epic #1374/#2345 — löst #2448
// (stille Kopplung "Alarm-Premium-SMS-Klick schaltet Briefing-Premium-SMS
// mit ein") auf.
//
// Spec: docs/specs/modules/feat_2293_s2_compare_alarm_kanaele.md AC-9,
//   Implementation Details Abschnitt 5, Mutations-Gegenprobe (f).
//
// Vor dieser Scheibe schrieb `alarmePropsAus.ts::onChannelToggle` fuer den
// Kanal `premium_sms` NUR `wiz.sendPremiumSms = !wiz.sendPremiumSms` — genau
// das Feld, das `hydrateVersandFieldsFromPreset`/`VersandSnapshot`
// (versandVergleichSpeicherung.ts) als BRIEFING-Opt-in lesen. Ein reiner
// Alarm-Kanal-Klick im Alarme-Reiter aenderte damit unsichtbar den
// kostenpflichtigen Premium-SMS-BRIEFING-Versand mit.
//
// RED-Grund heute (gemessen): `alarmePropsAus(wiz).onChannelToggle('premium_sms')`
// mutiert `wiz.sendPremiumSms` (alarmePropsAus.ts:100) — der erste Test unten
// erwartet, dass dieses Feld dadurch UNVERAENDERT bleibt, und faellt am
// heutigen Stand durch.
//
// Pfadregel #1409: Pruefling relativ zu DIESER Datei aufgeloest.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/__tests__/alarme_vergleich_premium_sms_entkoppelt.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { alarmePropsAus } from '../../compare/alarmePropsAus.ts';
import { baueAlarmNutzlast, type AlarmSnapshot } from '../alarmeVergleichSpeicherung.ts';
import type { ComparePreset } from '../../../types.ts';

describe('AC-9: Premium-SMS-Alarm-Toggle aendert NICHT das Briefing-Feld send_premium_sms', () => {
	test('onChannelToggle("premium_sms") laesst wiz.sendPremiumSms (Briefing-Feld) unangetastet', () => {
		const wiz: Record<string, unknown> = {
			sendTelegram: true,
			sendSms: false,
			// Briefing-Premium-SMS ist AUS — der Nutzer hat es NIE ueber den
			// Versand-Reiter bestellt.
			sendPremiumSms: false
		};
		const props = alarmePropsAus(wiz as never);
		props.onChannelToggle('premium_sms');

		assert.strictEqual(
			wiz.sendPremiumSms,
			false,
			'AC-9: ein Klick auf den Premium-SMS-ALARM-Kanal im Alarme-Reiter darf das ' +
				'Briefing-Feld send_premium_sms NICHT veraendern — sonst bestellt ein reiner ' +
				'Alarm-Kanal-Klick unsichtbar ein kostenpflichtiges Premium-SMS-Briefing (#2448).'
		);
	});

	test('onChannelToggle("premium_sms") bei bereits AN gesetztem Briefing-Feld laesst es AN', () => {
		const wiz: Record<string, unknown> = {
			sendTelegram: true,
			sendSms: false,
			// Briefing-Premium-SMS ist bewusst AN (echter Versand-Schalter-Klick).
			sendPremiumSms: true
		};
		const props = alarmePropsAus(wiz as never);
		props.onChannelToggle('premium_sms');

		assert.strictEqual(
			wiz.sendPremiumSms,
			true,
			'AC-9 (Gegenrichtung): ein Alarm-Kanal-Klick darf ein bewusst gesetztes ' +
				'Briefing-Opt-in ebenfalls nicht aendern — die Entkopplung gilt in BEIDE Richtungen.'
		);
	});
});

function _preset(overrides: Partial<ComparePreset> = {}): ComparePreset {
	return {
		id: 'cp-2293-ac9',
		name: 'AC9-Test',
		location_ids: ['loc-a'],
		schedule: 'manual',
		profil: 'ALLGEMEIN',
		hour_from: 8,
		hour_to: 17,
		empfaenger: ['a@example.com'],
		forecast_hours: 48,
		created_at: '2026-01-01T00:00:00Z',
		corridors: [],
		...overrides
	} as ComparePreset;
}

describe('AC-9: die Alarm-Nutzlast selbst enthaelt niemals send_premium_sms', () => {
	test('baueAlarmNutzlast sendet kein send_premium_sms, auch wenn preset einen Stale-Wert traegt', () => {
		// preset traegt einen (moeglicherweise veralteten) Briefing-Premium-SMS-
		// Wert — der Alarme-Reiter darf ihn nie zurueckschreiben (Abschnitt 4 der
		// Spec, Payload-Trennung).
		const preset = _preset({ send_premium_sms: true } as Partial<ComparePreset>);
		const current: AlarmSnapshot = {
			officialAlertsEnabled: true,
			officialWarningsEnabled: false,
			radarAlertEnabled: false,
			metricAlertLevels: {},
			telegramStyle: 'rich',
			sendTelegram: false,
			sendSms: false,
			sendPremiumSms: false,
			channelThresholds: {}
		};
		const { body } = baueAlarmNutzlast(preset, current);

		assert.ok(
			!('send_premium_sms' in body),
			'AC-9/Abschnitt 4: die Alarm-Nutzlast darf send_premium_sms (Briefing-Feld) NIE enthalten — ' +
				`gefunden: ${JSON.stringify((body as unknown as Record<string, unknown>).send_premium_sms)}`
		);
	});
});
