// Issue #2518 — Alarm-Kanal-Vorbelegung bei Neuanlage: E-Mail an, SMS aus.
// Spec: docs/specs/modules/alert_channel_new_default.md (AC-1..AC-4)
//
// Reine Verhaltenstests ohne Mocks: treiben die ECHTEN Payload-Bau-Funktionen
// (Trip-Anlegen, Ortsvergleich-Anlegen) und die Kanal-Aufloesung.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/__tests__/alert_channel_new_default.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import { resolveAlertChannels } from '../alarme-tab/alertChannelState.ts';
import {
	buildCreateTripPayload,
	type CreateTripState
} from '../../trip-new/tripNewLogic.ts';
import {
	buildNewComparePresetPayload,
	type NewComparePresetFields
} from '../../compare/compareEditorSave.ts';

const NEUER_DEFAULT = { email: true, telegram: true, sms: false, premium_sms: false };

function tripState(): CreateTripState {
	return {
		name: 'Testtrip',
		region: 'Karnische Alpen',
		startDate: '2026-06-15',
		stages: [{ id: 1, name: 'Etappe 1' }],
		weatherMetrics: [{ key: 'temp', enabled: true }],
		channels: { email: true, telegram: true, sms: false },
		reportConfig: { enabled: true, morning_time: '06:00', evening_time: '18:00' }
	};
}

function compareFields(over: Partial<NewComparePresetFields> = {}): NewComparePresetFields {
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
		...over
	} as NewComparePresetFields;
}

test('#2518 AC-1: neuer Trip ohne Alarme-Interaktion speichert alert_channels = neuer Default', () => {
	const p = buildCreateTripPayload(tripState()) as unknown as Record<string, unknown>;
	assert.deepEqual(p.alert_channels, NEUER_DEFAULT);
});

test('#2518 AC-2: neuer Ortsvergleich speichert den Default, unabhaengig von den Briefing-Schaltern', () => {
	for (const [tg, sms, psms] of [
		[false, false, false],
		[true, true, true],
		[false, true, false]
	]) {
		const body = buildNewComparePresetPayload(
			compareFields({ sendTelegram: tg, sendSms: sms, sendPremiumSms: psms } as Partial<NewComparePresetFields>)
		);
		assert.deepEqual(body.alert_channels, NEUER_DEFAULT, `send_*=${[tg, sms, psms]}`);
	}
});

test('#2518 AC-3: resolveAlertChannels(undefined/null) = E-Mail+Telegram an, SMS/Premium-SMS aus', () => {
	assert.deepEqual(resolveAlertChannels(undefined), NEUER_DEFAULT);
	assert.deepEqual(resolveAlertChannels(null), NEUER_DEFAULT);
	// Rueckgabe ist eine Kopie — Mutation darf den Default nicht verschmutzen.
	resolveAlertChannels(undefined).sms = true;
	assert.deepEqual(resolveAlertChannels(undefined), NEUER_DEFAULT);
});

test('#2518 AC-4: Bestand bleibt erhalten (kein Default-Overwrite)', () => {
	const bestand = { telegram: true, sms: true, email: false };
	assert.deepEqual(resolveAlertChannels(bestand), { ...bestand, premium_sms: false });
	// Ortsvergleich-Anlegen mit explizit gelieferten Kanaelen des Alarme-Reiters.
	const eigene = { email: false, telegram: true, sms: true, premium_sms: false };
	const body = buildNewComparePresetPayload(compareFields({ alertChannels: eigene }));
	assert.deepEqual(body.alert_channels, eigene);
	// Trip-Anlegen mit explizitem Alarm-State.
	const st = tripState();
	st.alarm = {
		officialWarningsEnabled: false,
		channels: { telegram: true, sms: true, email: false, premium_sms: false },
		channelThresholds: { telegram: 'LOW', sms: 'LOW', email: 'LOW', premium_sms: 'LOW' },
		metricLevels: {}
	};
	const p = buildCreateTripPayload(st) as unknown as Record<string, unknown>;
	assert.deepEqual(p.alert_channels, { telegram: true, sms: true, email: false, premium_sms: false });
});
