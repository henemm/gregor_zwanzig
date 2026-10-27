// reportConfigPayload.ts — Issue #2422 S3 (AC-22, AC-24).
//
// Startzustand und Payload-Bau des `report_config`-Blobs, verhaltensgleich
// aus dem `onMount`-/`$effect`-Rumpf von VersandTab.svelte und
// die frühere Report-Config-Section (#2277 S5 entfernt) herausgezogen (Vorbild
// weather-metrics-tab/weatherMetricsSavePayload.ts). Beide Komponenten rufen
// BEIDE Funktionen auf. `$effect`/`onMount` laufen unter svelte/server nie —
// als reine Funktionen ist die Regel per node:test messbar, ohne Nachbau im
// Test.
//
// Zwei Aenderungen gegenueber dem alten Inline-Stand (Spec
// fix_2422_s3_kanal_an_aus_kette.md, Verdikt N2):
// - Der Slot-Startzustand folgt `reportSlotAktiv` (dieselbe Regel wie der
//   Versand); die Zeitbedingung `typeof morning_time === 'string'` entfaellt.
// - Die Regel steht an EINEM Ort statt zweimal.
//
// Pure Funktionen, kein Netz-/DOM-Zugriff — node:testbar.

import { toHHMMSS } from '../../../utils/time.ts';
import { reportSlotAktiv } from '../../../utils/reportSlotAktiv.ts';
import { mergeReportConfig } from './mergeReportConfig.ts';

export interface ReportZustand {
	morning_enabled: boolean;
	evening_enabled: boolean;
	/** 'HH:MM' */
	morning_time: string;
	/** 'HH:MM' */
	evening_time: string;
	send_email: boolean;
	send_telegram: boolean;
	send_sms: boolean;
	send_premium_sms: boolean;
	/** Nur VersandTab besitzt den Kurzstil-Schalter (#1260 S5). Fehlt er im
	 *  Zustand, wird er NICHT geschrieben — sonst waere es ein zweiter
	 *  Schreibpfad auf ein fremdes Feld (#1738 Fix-Loop 4). */
	telegram_style?: 'rich' | 'kurzform';
	multi_day_trend_morning: boolean;
	multi_day_trend_evening: boolean;
}

/** Trend-Standardwerte, wenn der Blob weder Bool-Felder noch Legacy-Array
 *  traegt (VersandTab: beide aus; die frühere Report-Config-Section (#2277 S5 entfernt): Abend an). */
export interface TrendVorgaben {
	multi_day_trend_morning?: boolean;
	multi_day_trend_evening?: boolean;
}

function trendAus(
	c: Record<string, unknown>,
	slot: 'morning' | 'evening',
	vorgabe: boolean
): boolean {
	const wert = c[`multi_day_trend_${slot}`];
	if (typeof wert === 'boolean') return wert;
	if (Array.isArray(c.multi_day_trend_reports)) return c.multi_day_trend_reports.includes(slot);
	return vorgabe;
}

/**
 * Startzustand aus dem geladenen Blob (onMount-/Erzeugungs-Logik). Slots via
 * `reportSlotAktiv` (AC-24); Zeiten 07:00/18:00 als Default; E-Mail Default an,
 * die anderen drei Kanaele Default aus; telegram_style Default 'rich'.
 */
export function ladeReportZustand(
	rc: Record<string, unknown> | null | undefined,
	vorgaben: TrendVorgaben = {}
): ReportZustand {
	const c: Record<string, unknown> = rc ?? {};
	return {
		morning_enabled: reportSlotAktiv(rc, 'morning'),
		evening_enabled: reportSlotAktiv(rc, 'evening'),
		morning_time: typeof c.morning_time === 'string' ? c.morning_time.slice(0, 5) : '07:00',
		evening_time: typeof c.evening_time === 'string' ? c.evening_time.slice(0, 5) : '18:00',
		send_email: c.send_email !== false,
		send_telegram: c.send_telegram === true,
		send_sms: c.send_sms === true,
		send_premium_sms: c.send_premium_sms === true,
		telegram_style: c.telegram_style === 'kurzform' ? 'kurzform' : 'rich',
		multi_day_trend_morning: trendAus(c, 'morning', vorgaben.multi_day_trend_morning ?? false),
		multi_day_trend_evening: trendAus(c, 'evening', vorgaben.multi_day_trend_evening ?? false)
	};
}

export interface ReportConfigPayloadEingabe {
	snapshot?: Record<string, unknown> | null;
	live: Record<string, unknown> | null | undefined;
	zustand: ReportZustand;
	/** Weitere Felder, die die aufrufende Instanz besitzt (Mail-Inhalt). */
	eigene?: Record<string, unknown> | null;
	/** Zeigt die Instanz den Zeitplan? Default an (VersandTab immer). */
	showSchedule?: boolean;
	/** Zeigt die Instanz die Kanal-Schalter? Default an (VersandTab immer). */
	showChannels?: boolean;
}

/**
 * `$effect`-Rumpf: Read-Modify-Write ueber `mergeReportConfig` mit
 * `enabled = morning_enabled || evening_enabled`, `toHHMMSS` auf beide Zeiten
 * und `multi_day_trend_reports` aus den beiden Trend-Flags. Unbekannte
 * Bestandsfelder bleiben erhalten.
 */
export function baueReportConfigPayload(eingabe: ReportConfigPayloadEingabe): Record<string, unknown> {
	const z = eingabe.zustand;
	const multi_day_trend_reports: string[] = [];
	if (z.multi_day_trend_morning) multi_day_trend_reports.push('morning');
	if (z.multi_day_trend_evening) multi_day_trend_reports.push('evening');
	return mergeReportConfig({
		snapshot: eingabe.snapshot,
		live: eingabe.live,
		own: {
			...(eingabe.eigene ?? {}),
			...(z.telegram_style !== undefined ? { telegram_style: z.telegram_style } : {})
		},
		showSchedule: eingabe.showSchedule ?? true,
		schedule: {
			enabled: z.morning_enabled || z.evening_enabled,
			morning_enabled: z.morning_enabled,
			evening_enabled: z.evening_enabled,
			morning_time: toHHMMSS(z.morning_time),
			evening_time: toHHMMSS(z.evening_time),
			multi_day_trend_morning: z.multi_day_trend_morning,
			multi_day_trend_evening: z.multi_day_trend_evening,
			multi_day_trend_reports
		},
		showChannels: eingabe.showChannels ?? true,
		channels: {
			send_email: z.send_email,
			send_telegram: z.send_telegram,
			send_sms: z.send_sms,
			send_premium_sms: z.send_premium_sms
		}
	});
}
