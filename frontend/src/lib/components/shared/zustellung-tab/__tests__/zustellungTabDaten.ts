// Pruefstand-Daten fuer die node-Tests des Reiters Zustellung (Issue #2795 S3b, Teilschritt 1b).
// Spec: docs/specs/modules/feat_2795_s3b_teil1_zustellung.md
//
// Keine .test.ts-Datei: wird nur von den Tests unter zustellung-tab/__tests__/ importiert.
//
// Die Module des Reiters werden DYNAMISCH geladen (Muster wetterTabDaten.ts): fehlt ein Modul
// (TDD RED), wird jeder Test einzeln mit „Modul fehlt“ rot, statt die ganze Datei beim Import
// abzubrechen.
//
// Profile und Abos sind die Formen, die GET /api/auth/profile, GET /api/trips/{id} und
// GET /api/compare/presets/{id} liefern (Go: profileResponse, model.Trip, model.ComparePreset).

import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HIER = dirname(fileURLToPath(import.meta.url));
export const ZUSTELLUNG_TAB = resolve(HIER, '..');

export type Json = any; // eslint-disable-line @typescript-eslint/no-explicit-any

async function lade(datei: string): Promise<Json> {
	const pfad = join(ZUSTELLUNG_TAB, datei);
	if (!existsSync(pfad)) {
		assert.fail(`TDD RED: shared/zustellung-tab/${datei} fehlt (Modul noch nicht angelegt)`);
	}
	return import(pathToFileURL(pfad).href);
}

export const zustellungModell = () => lade('zustellungModell.ts');
export const zustellungSpeicherung = () => lade('zustellungSpeicherung.ts');

export const KANAELE = ['email', 'telegram', 'sms', 'premium_sms'] as const;
export type KanalId = (typeof KANAELE)[number];

// ── Profile (GET /api/auth/profile) ─────────────────────────────────────────

/** Alles verbunden, Premium-SMS mit frischer Rueckadresse (Mockup-Zustand „normal“). */
export function profilAllesVerbunden(): Json {
	return {
		tier: 'premium',
		mail_to: 'henning@example.com',
		email_verified: true,
		telegram_chat_id: '4711',
		sms_to: '+49171000000',
		sms_allowed: true,
		sms_verified: true,
		premium_sms_allowed: true,
		premium_sms_reply_to: '+881600000000',
		premium_sms_reply_at: '2026-11-01T18:04:00Z',
		premium_sms_reply_state: 'fresh'
	};
}

/** Mockup-Zustand „luecken“: Telegram fehlt, SMS unbestaetigt, Premium-SMS-Rueckadresse verfallen. */
export function profilLuecken(): Json {
	return {
		...profilAllesVerbunden(),
		telegram_chat_id: '',
		sms_verified: false,
		pending_sms_to: '+49171000000',
		premium_sms_reply_state: 'stale'
	};
}

export function profilMit(over: Json): Json {
	return { ...profilAllesVerbunden(), ...over };
}

// ── Abos ────────────────────────────────────────────────────────────────────

/** Trip mit allen Feldern, die der Reiter liest, plus Fremdfelder (Wetter, Uebergangsblock). */
export function tripVoll(over: Json = {}): Json {
	return {
		id: 'trip-2795',
		name: 'GR221',
		stages: [
			{ id: 'E1', name: 'E1', date: '2026-02-23', waypoints: [] },
			{ id: 'E2', name: 'E2', date: '2026-02-24', waypoints: [] },
			{ id: 'E3', name: 'E3', date: '2026-02-25', waypoints: [] },
			{ id: 'E4', name: 'E4', date: '2026-02-26', waypoints: [] }
		],
		display_config: {
			ampel: { template: 'wandern', metrics: { gust: { alarm_ab: 'red' } } },
			metrics: [{ metric_id: 'gust', enabled: true }],
			channel_layouts: { email: ['gust'] },
			telegram_kurzform: false
		},
		report_config: {
			enabled: true,
			morning_enabled: true,
			evening_enabled: true,
			morning_time: '07:00:00',
			evening_time: '18:00:00',
			send_email: true,
			send_telegram: true,
			send_sms: false,
			send_premium_sms: false,
			telegram_style: 'rich',
			show_outlook: true,
			email_format: 'full',
			multi_day_trend_reports: ['evening'],
			day_window_start_hour: 6,
			day_window_end_hour: 20
		},
		alert_channels: { email: true, telegram: true, sms: true, premium_sms: false },
		alert_channel_thresholds: { email: 'LOW', telegram: 'LOW', sms: 'MODERATE' },
		alert_cooldown_minutes: 45,
		alert_quiet_from: '22:00',
		alert_quiet_to: '06:00',
		official_warnings: { enabled: true, sources: ['meteoalarm'] },
		alert_metric_channels: { gust: { email: true, telegram: false, sms: false, premium_sms: false } },
		...over
	};
}

/** Orts-Briefing (Preset) mit allen Feldern, die der Reiter liest, plus Fremdfelder. */
export function presetVoll(over: Json = {}): Json {
	return {
		id: 'cp-2795',
		name: 'Münsterland',
		location_ids: ['loc-a', 'loc-b'],
		schedule: 'daily',
		profil: 'wandern',
		hour_from: 6,
		hour_to: 9,
		forecast_hours: 48,
		empfaenger: ['a@example.com'],
		created_at: '2026-01-01T00:00:00Z',
		official_alerts_enabled: true,
		official_warnings: { enabled: true, sources: ['meteoalarm'] },
		radar_alert_enabled: true,
		send_email: true,
		send_telegram: true,
		send_sms: false,
		send_premium_sms: false,
		alert_channels: { email: true, telegram: true, sms: false, premium_sms: false },
		alert_channel_thresholds: { email: 'LOW', telegram: 'HIGH' },
		alert_cooldown_minutes: 45,
		alert_quiet_from: '22:00',
		alert_quiet_to: '07:00',
		morning_enabled: true,
		morning_time: '07:00:00',
		evening_enabled: true,
		evening_time: '18:00:00',
		hourly_enabled: true,
		outlook_enabled: true,
		day_window_start_hour: 5,
		day_window_end_hour: 18,
		alert_metric_channels: { gust: { email: true, telegram: false, sms: false, premium_sms: false } },
		display_config: {
			ampel: { template: 'wandern' },
			active_metrics: ['gust'],
			metric_alert_levels: { gust: 'standard' },
			telegram_style: 'rich',
			hourly_metrics: ['gust'],
			outlook_metrics: ['gust']
		},
		...over
	};
}

/** Erste fuenf Zeichen einer Uhrzeit („06:45:00“ -> „06:45“); Speicherformat HH:MM oder HH:MM:SS. */
export const hhmm = (v: unknown): string => String(v ?? '').slice(0, 5);
