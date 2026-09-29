// TDD RED — Issue #2293 Scheibe S2 (AC-10, AC-1), Epic #1374/#2345.
//
// Spec: docs/specs/modules/feat_2293_s2_compare_alarm_kanaele.md
//   Implementation Details Abschnitt 4 ("Payload-Trennung gegen den
//   Same-Tab-Race"), Mutations-Gegenprobe (b)/(c).
//
// Same-Tab-Race (#2381-Muster): beide Reiter bauen ihren PUT-Body über
// `buildComparePresetSavePayload` mit `{...original, ...}` — jedes Feld aus
// `original`, das der Aufrufer nicht explizit überschreibt, wandert
// unverändert in den Body. Ein veraltetes `original` (Alarme-Reiter
// speichert, während der Versand-Reiter noch das vor diesem Save gemountete
// `preset` hält, oder umgekehrt) würde das inzwischen geänderte Feld des
// jeweils ANDEREN Reiters beim nächsten eigenen Save zurückschreiben.
// Festlegung: nach `buildComparePresetSavePayload` entfernt jeder Reiter die
// Felder des jeweils anderen aus dem fertigen `body`.
//
// RED-Grund heute (gemessen): weder `baueAlarmNutzlast` noch
// `baueVersandNutzlast` löschen irgendwelche Felder aus dem Body — ein
// veraltetes `original` überschreibt das Feld des Nachbar-Reiters ungehindert.
// Zusätzlich fehlt `buildNewComparePresetPayload` das `alert_channels`-Feld
// komplett (AC-1/Abschnitt 1: ein neues Preset trägt es nie).
//
// Pfadregel #1409: Prüfling relativ zu DIESER Datei aufgelöst.
//
// Ausführung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/__tests__/compare_alarm_versand_nutzlast_trennung.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { baueAlarmNutzlast, type AlarmSnapshot } from '../alarmeVergleichSpeicherung.ts';
import { baueVersandNutzlast, type VersandSnapshot } from '../versandVergleichSpeicherung.ts';
import { buildNewComparePresetPayload, type NewComparePresetFields } from '../../compare/compareEditorSave.ts';
import type { ComparePreset } from '../../../types.ts';

function _preset(overrides: Partial<ComparePreset> = {}): ComparePreset {
	return {
		id: 'cp-2293-ac10',
		name: 'AC10-Test',
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

const ALARM_SNAPSHOT: AlarmSnapshot = {
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

const VERSAND_SNAPSHOT: VersandSnapshot = {
	sendTelegram: true,
	sendSms: false,
	morningEnabled: true,
	morningTime: '07:00',
	eveningEnabled: false,
	eveningTime: '18:00',
	endDate: null
};

describe('AC-10: die Alarm-Nutzlast enthaelt NIE send_telegram/send_sms/send_premium_sms', () => {
	test('auch wenn `original` (veraltet) diese Felder gesetzt hat, fehlen sie im Alarm-Body', () => {
		// `original` traegt Briefing-Kanal-Werte, die inzwischen (im selben Tab)
		// vom Versand-Reiter geaendert worden sein koennten — die Alarm-Nutzlast
		// darf sie unter KEINEN Umstaenden zurueckschreiben.
		const stalePreset = _preset({
			send_telegram: true, send_sms: true, send_premium_sms: true
		} as Partial<ComparePreset>);
		const { body } = baueAlarmNutzlast(stalePreset, ALARM_SNAPSHOT);
		const b = body as unknown as Record<string, unknown>;
		for (const feld of ['send_telegram', 'send_sms', 'send_premium_sms']) {
			assert.ok(
				!(feld in b),
				`AC-10: die Alarm-Nutzlast darf \`${feld}\` NIE enthalten (Same-Tab-Race-Schutz), ` +
					`gefunden: ${JSON.stringify(b[feld])}`
			);
		}
	});
});

describe('AC-10: die Versand-Nutzlast enthaelt NIE alert_channels', () => {
	test('auch wenn `original` (veraltet) alert_channels gesetzt hat, fehlt es im Versand-Body', () => {
		const stalePreset = _preset({
			alert_channels: { email: true, telegram: true, sms: true, premium_sms: true }
		} as Partial<ComparePreset>);
		const { body } = baueVersandNutzlast(stalePreset, VERSAND_SNAPSHOT);
		const b = body as unknown as Record<string, unknown>;
		assert.ok(
			!('alert_channels' in b),
			`AC-10: die Versand-Nutzlast darf \`alert_channels\` NIE enthalten (Same-Tab-Race-Schutz), ` +
				`gefunden: ${JSON.stringify(b.alert_channels)}`
		);
	});
});

describe('AC-1: die Alarm-Nutzlast traegt alle vier alert_channels-Booleans', () => {
	test('E-Mail aus, Telegram an (AC-1-Szenario) landet vollstaendig im Alarm-Body', () => {
		const preset = _preset();
		const current: AlarmSnapshot = {
			...ALARM_SNAPSHOT,
			// AlarmSnapshot bekommt per Spec ein Feld `channels` (vier
			// Pflicht-Booleans) statt der drei optionalen Flach-Felder.
			channels: { email: false, telegram: true, sms: false, premium_sms: false }
		} as unknown as AlarmSnapshot;
		const { body } = baueAlarmNutzlast(preset, current);
		const b = body as unknown as Record<string, unknown>;
		assert.deepStrictEqual(
			b.alert_channels,
			{ email: false, telegram: true, sms: false, premium_sms: false },
			`AC-1: die Alarm-Nutzlast muss alert_channels mit allen vier Booleans tragen, erhalten: ${JSON.stringify(b.alert_channels)}`
		);
	});
});

describe('AC-1/Abschnitt 1: buildNewComparePresetPayload sendet IMMER alert_channels', () => {
	function newFields(overrides: Partial<NewComparePresetFields> = {}): NewComparePresetFields {
		return {
			name: 'Neu',
			pickedIds: ['loc-a'],
			activityProfile: null,
			schedule: 'daily_morning',
			officialAlertsEnabled: true,
			radarAlertEnabled: false,
			hourlyEnabled: true,
			officialAlertTriggersEnabled: false,
			sendTelegram: false,
			sendSms: false,
			sendPremiumSms: false,
			officialWarningsEnabled: false,
			morningEnabled: true,
			morningTime: '07:00',
			eveningEnabled: false,
			eveningTime: '18:00',
			endDate: null,
			dayWindowStartHour: 4,
			dayWindowEndHour: 19,
			corridors: [],
			region: '',
			idealRanges: {},
			activeMetricKeys: null,
			hourlyMetricKeys: null,
			metricAlertLevels: {},
			telegramStyle: 'rich',
			...overrides
		} as NewComparePresetFields;
	}

	test('Standard-Neuanlage traegt alert_channels={email:true,telegram:false,sms:false,premium_sms:false}', () => {
		const payload = buildNewComparePresetPayload(newFields()) as Record<string, unknown>;
		assert.deepStrictEqual(
			payload.alert_channels,
			{ email: true, telegram: false, sms: false, premium_sms: false },
			`AC-1/Abschnitt 1: die Neuanlage-Payload muss immer alert_channels tragen (Standard-Default), erhalten: ${JSON.stringify(payload.alert_channels)}`
		);
	});
});
