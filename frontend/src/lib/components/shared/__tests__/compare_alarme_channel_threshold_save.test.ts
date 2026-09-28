// TDD GREEN — Issue #1461 Scheibe S3b-2b: einstellbare Dringlichkeits-Schwelle
// je Alarm-Kanal fuer Ortsvergleiche (Kanal-Schwelle + bestaetigter
// Speicher-Bug im Bearbeiten-Pfad des Vergleichs-Hubs).
//
// Spec: docs/specs/modules/feat_1461_s3b2b_compare_kanal_schwelle.md
//   (AC-9, AC-10, AC-13, AC-14, AC-15)
//
// Zwei getrennte Nachweise:
//   1. Der bestaetigte Speicher-Bug (AC-15): `AlarmSnapshot` fuehrte
//      sendTelegram/sendSms bisher nicht -- eine Kanal-Umschaltung im
//      Bearbeiten-Pfad des Vergleichs-Hubs war weder als Snapshot-Differenz
//      erkennbar noch im PUT-Body enthalten; stattdessen wurden die alten
//      Server-Werte aktiv zurueckgeschrieben.
//   2. Der neue Schwellen-Speicherweg (AC-9/AC-10, Hub) und (AC-14, Anlegen).
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/__tests__/compare_alarme_channel_threshold_save.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import type { ComparePreset } from '../../../types.ts';
// Issue #2276 S2: Speicherpfad-Helfer zogen nach shared/alarmeVergleichSpeicherung.ts;
// die Hydration bleibt in der Compare-Klebeschicht.
import { hydrateAlarmFieldsFromPreset } from '../../compare/compareHubHydration.ts';
import {
	flushPendingAlarmSave,
	rollbackAlarmSnapshot,
	type AlarmSnapshot
} from '../alarmeVergleichSpeicherung.ts';
import {
	buildComparePresetSavePayload,
	buildNewComparePresetPayload,
	type NewComparePresetFields
} from '../../compare/compareEditorSave.ts';

function makePreset(overrides: Partial<ComparePreset> = {}): ComparePreset {
	return {
		id: 'cmp-1461',
		name: 'Ortsvergleich',
		location_ids: ['loc-a', 'loc-b'],
		schedule: 'daily',
		profil: 'wandern',
		hour_from: 6,
		hour_to: 9,
		forecast_hours: 48,
		empfaenger: ['a@example.com'],
		created_at: '2026-01-01T00:00:00Z',
		send_telegram: false,
		send_sms: false,
		...overrides
	};
}

function makeAlarmSnapshot(overrides: Partial<AlarmSnapshot> = {}): AlarmSnapshot {
	return {
		officialAlertsEnabled: true,
		officialWarningsEnabled: true,
		radarAlertEnabled: false,
		metricAlertLevels: {},
		channelThresholds: {},
		channels: { email: true, telegram: false, sms: false, premium_sms: false },
		...overrides
	};
}

// ─────────────────────────────────────────────────────────────────────────
// AC-15: der bestaetigte Speicher-Bug — Kanal-Umschaltung im Alarme-Reiter
//
// 🔴 Issue #2293 Scheibe S2 (AC-9 Entkopplung): der urspruengliche Fix (#1461
// S3b-2b) fuehrte sendTelegram/sendSms im AlarmSnapshot als ALARM-Kanal-
// Traeger ein -- exakt das Feld, das #2293 S2 als Briefing-Feld reklamiert.
// Der Alarm-Kanal-Bestand laeuft seither als EIN Objekt `channels` (statt der
// zwei Flach-Felder); dieselbe Zusicherung (eine Kanal-Umschaltung ist als
// Snapshot-Differenz erkennbar UND landet im PUT-Body), nur am neuen Feld
// gemessen -- nicht geloescht, umgestellt.
// ─────────────────────────────────────────────────────────────────────────

describe('AC-15: Alarme-Reiter-Kanalumschaltung (channels) ist Teil des Snapshots', () => {
	test('hydrateAlarmFieldsFromPreset uebernimmt den Alarm-Kanal-Bestand aus dem Preset', () => {
		const preset = makePreset({ send_telegram: true, send_sms: true });
		const state: Record<string, unknown> = {};

		hydrateAlarmFieldsFromPreset(state, preset);

		assert.deepStrictEqual(state.channels, { email: true, telegram: true, sms: true, premium_sms: false });
	});

	test('eine Telegram-Umschaltung (false -> true) erzeugt einen PUT-Payload mit alert_channels.telegram=true', () => {
		const preset = makePreset({ send_telegram: false });
		const before = makeAlarmSnapshot({
			channels: { email: true, telegram: false, sms: false, premium_sms: false }
		});
		const current = makeAlarmSnapshot({
			channels: { email: true, telegram: true, sms: false, premium_sms: false }
		});

		const result = flushPendingAlarmSave(preset, current, before);

		assert.ok(
			result,
			'REPRO (vor dem Fix rot): eine reine Kanal-Umschaltung wurde nicht als ' +
				'Snapshot-Differenz erkannt -- flushPendingAlarmSave lieferte null'
		);
		assert.strictEqual(
			(result!.body as unknown as { alert_channels: { telegram: boolean } }).alert_channels.telegram,
			true,
			'REPRO: ohne den Fix fehlte der Alarm-Kanal im PUT-Body'
		);
	});

	test('eine SMS-Umschaltung (false -> true) erzeugt einen PUT-Payload mit alert_channels.sms=true', () => {
		const preset = makePreset({ send_sms: false });
		const before = makeAlarmSnapshot({
			channels: { email: true, telegram: false, sms: false, premium_sms: false }
		});
		const current = makeAlarmSnapshot({
			channels: { email: true, telegram: false, sms: true, premium_sms: false }
		});

		const result = flushPendingAlarmSave(preset, current, before);

		assert.ok(result);
		assert.strictEqual(
			(result!.body as unknown as { alert_channels: { sms: boolean } }).alert_channels.sms,
			true
		);
	});

	test('Rollback bei PUT-Fehler: die alten Kanal-Werte werden wiederhergestellt', () => {
		const before = makeAlarmSnapshot({
			channels: { email: true, telegram: false, sms: false, premium_sms: false }
		});
		const attempted = makeAlarmSnapshot({
			channels: { email: true, telegram: true, sms: false, premium_sms: false }
		});
		const state: Record<string, unknown> = {
			...makeAlarmSnapshot({ channels: { email: true, telegram: true, sms: false, premium_sms: false } })
		};

		rollbackAlarmSnapshot(state, before, attempted);

		assert.deepStrictEqual(
			state.channels,
			{ email: true, telegram: false, sms: false, premium_sms: false },
			'der gescheiterte Edit muss zurueckgerollt werden'
		);
	});

	test('ohne Aenderung (identischer Snapshot inkl. Kanaele) bleibt der Waechter gegen unnoetige PUTs intakt', () => {
		const preset = makePreset();
		const kanaele = { email: true, telegram: true, sms: true, premium_sms: false };
		const snap = makeAlarmSnapshot({ channels: kanaele });
		assert.strictEqual(flushPendingAlarmSave(preset, snap, makeAlarmSnapshot({ channels: kanaele })), null);
	});
});

// ─────────────────────────────────────────────────────────────────────────
// AC-9/AC-10 (Hub-Speicherweg): channelThresholds im Alarme-Snapshot
// ─────────────────────────────────────────────────────────────────────────

describe('AC-9/AC-10: Kanal-Schwelle im Hub-Alarme-Speicherweg', () => {
	test('hydrateAlarmFieldsFromPreset uebernimmt alert_channel_thresholds aus dem Preset', () => {
		const preset = makePreset({ alert_channel_thresholds: { telegram: 'HIGH' } });
		const state: Record<string, unknown> = {};

		hydrateAlarmFieldsFromPreset(state, preset);

		assert.deepStrictEqual(state.channelThresholds, { telegram: 'HIGH' });
	});

	test('fehlt alert_channel_thresholds im Preset, hydriert ein leeres Objekt (Startwert "gering" ueberall)', () => {
		const preset = makePreset();
		const state: Record<string, unknown> = {};

		hydrateAlarmFieldsFromPreset(state, preset);

		assert.deepStrictEqual(state.channelThresholds, {});
	});

	test('eine geaenderte Schwelle erzeugt einen PUT-Payload mit alert_channel_thresholds', () => {
		const preset = makePreset({ alert_channel_thresholds: { telegram: 'LOW' } });
		const before = makeAlarmSnapshot({ channelThresholds: { telegram: 'LOW' } });
		const current = makeAlarmSnapshot({ channelThresholds: { telegram: 'HIGH' } });

		const result = flushPendingAlarmSave(preset, current, before);

		assert.ok(result);
		assert.deepStrictEqual(result!.body.alert_channel_thresholds, { telegram: 'HIGH' });
	});

	test('AC-10: nur EIN geaenderter Kanal im Snapshot laesst den anderen im Body unangetastet, wenn er mitgesendet wird', () => {
		const preset = makePreset({ alert_channel_thresholds: { telegram: 'HIGH', sms: 'MODERATE' } });
		const before = makeAlarmSnapshot({ channelThresholds: { telegram: 'HIGH', sms: 'MODERATE' } });
		const current = makeAlarmSnapshot({ channelThresholds: { telegram: 'LOW', sms: 'MODERATE' } });

		const result = flushPendingAlarmSave(preset, current, before);

		assert.ok(result);
		assert.deepStrictEqual(result!.body.alert_channel_thresholds, { telegram: 'LOW', sms: 'MODERATE' });
	});

	test('Rollback bei PUT-Fehler: die alte Schwelle wird wiederhergestellt', () => {
		const before = makeAlarmSnapshot({ channelThresholds: { telegram: 'LOW' } });
		const attempted = makeAlarmSnapshot({ channelThresholds: { telegram: 'HIGH' } });
		const state: Record<string, unknown> = {
			...makeAlarmSnapshot({ channelThresholds: { telegram: 'HIGH' } })
		};

		rollbackAlarmSnapshot(state, before, attempted);

		assert.deepStrictEqual(state.channelThresholds, { telegram: 'LOW' });
	});
});

// ─────────────────────────────────────────────────────────────────────────
// AC-9 (Edit-Pfad, PUT /api/compare/presets/{id}): Round-Trip via
// buildComparePresetSavePayload
// ─────────────────────────────────────────────────────────────────────────

describe('AC-9: buildComparePresetSavePayload — Round-Trip fuer alert_channel_thresholds', () => {
	test('channelThresholds nicht in edits -> alert_channel_thresholds fehlt im Body, Original bleibt via Spread erhalten', () => {
		const original = makePreset({ alert_channel_thresholds: { telegram: 'HIGH' } });

		const { body } = buildComparePresetSavePayload(original, {
			name: original.name,
			activityProfile: null,
			pickedIds: original.location_ids,
			region: '',
			idealRanges: {}
		});

		assert.deepStrictEqual(
			body.alert_channel_thresholds,
			{ telegram: 'HIGH' },
			'ohne explizites channelThresholds-Feld muss der Bestand aus original erhalten bleiben (Round-Trip via Spread)'
		);
	});

	test('channelThresholds explizit gesetzt -> ueberschreibt den Body', () => {
		const original = makePreset({ alert_channel_thresholds: { telegram: 'HIGH' } });

		const { body } = buildComparePresetSavePayload(original, {
			name: original.name,
			activityProfile: null,
			pickedIds: original.location_ids,
			region: '',
			idealRanges: {},
			channelThresholds: { telegram: 'LOW', sms: 'MODERATE' }
		});

		assert.deepStrictEqual(body.alert_channel_thresholds, { telegram: 'LOW', sms: 'MODERATE' });
	});
});

// ─────────────────────────────────────────────────────────────────────────
// AC-14 (Anlege-Pfad, POST /api/compare/presets): Wert ueberlebt das Anlegen
// ─────────────────────────────────────────────────────────────────────────

describe('AC-14: buildNewComparePresetPayload — Kanal-Schwelle beim Anlegen', () => {
	function baseFields(overrides: Partial<NewComparePresetFields> = {}): NewComparePresetFields {
		return {
			name: 'Neuer Vergleich',
			pickedIds: ['loc-a'],
			activityProfile: null,
			schedule: 'daily_morning',
			officialAlertsEnabled: true,
			radarAlertEnabled: false,
			hourlyEnabled: true,
			officialAlertTriggersEnabled: true,
			sendTelegram: true,
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
			channelThresholds: {},
			...overrides
		};
	}

	test('ohne gesetzte Schwelle (Startwert "gering" ueberall) wird der Schluessel gar nicht gesendet', () => {
		const payload = buildNewComparePresetPayload(baseFields());

		assert.strictEqual(
			Object.prototype.hasOwnProperty.call(payload, 'alert_channel_thresholds'),
			false,
			'ein leeres channelThresholds-Objekt darf keinen Schluessel im POST-Body erzeugen'
		);
	});

	test('eine im Alarme-Schritt gesetzte Stufe wird beim Anlegen mitgesendet', () => {
		const payload = buildNewComparePresetPayload(
			baseFields({ channelThresholds: { telegram: 'HIGH' } })
		);

		assert.deepStrictEqual(payload.alert_channel_thresholds, { telegram: 'HIGH' });
	});
});
