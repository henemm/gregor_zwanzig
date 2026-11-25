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
// #3297/#3020: VersandTab.svelte und weatherMetricsSavePayload.ts sind geloescht; Aufrufer sind
// heute die Anlage (tripNewLogic.ergaenzeVersandStandard) und die Zustellung. Die Altschluessel
// des Ausblicks (Trend-Liste) schreibt der Payload-Bau nicht mehr.
//
// Zwei Aenderungen gegenueber dem alten Inline-Stand (Spec
// fix_2422_s3_kanal_an_aus_kette.md, Verdikt N2):
// - Der Slot-Startzustand folgt `reportSlotAktiv` (dieselbe Regel wie der
//   Versand); die Zeitbedingung `typeof morning_time === 'string'` entfaellt.
// - Die Regel steht an EINEM Ort statt zweimal.
//
// Pure Funktionen, kein Netz-/DOM-Zugriff — node:testbar.

import { toHHMMSS } from '../../../utils/time.ts';
import { leseBriefingStartwerte } from '../briefingStartwerte.ts';
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
}

/**
 * Startzustand aus dem geladenen Blob (onMount-/Erzeugungs-Logik). Slots, Zeiten
 * und Kanaele via `leseBriefingStartwerte` (#2987); telegram_style Default 'rich'.
 */
export function ladeReportZustand(rc: Record<string, unknown> | null | undefined): ReportZustand {
	return {
		...leseBriefingStartwerte(rc),
		telegram_style: rc?.telegram_style === 'kurzform' ? 'kurzform' : 'rich'
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
 * `enabled = morning_enabled || evening_enabled` und `toHHMMSS` auf beide
 * Zeiten. Unbekannte Bestandsfelder bleiben erhalten. #3297: der
 * 3-Tages-Ausblick wird nicht mehr geschrieben (Tabelle `placements.outlook_reports`,
 * ADR-0124 Nr. 6).
 */
export function baueReportConfigPayload(eingabe: ReportConfigPayloadEingabe): Record<string, unknown> {
	const z = eingabe.zustand;
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
			evening_time: toHHMMSS(z.evening_time)
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
