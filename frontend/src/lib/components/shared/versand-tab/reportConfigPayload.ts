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

/** #3155 (Spec feat_3155 Nr. 9): liegt ein GESPEICHERTER report_config vor?
 *  Der Server schreibt `enabled` bei jedem gespeicherten Trip mit; die Anlage
 *  (/trips/new) traegt vor dem ersten Versand-Lauf nur Wetter-Felder. */
export function istGespeicherterReportConfig(rc: Record<string, unknown> | null | undefined): boolean {
	return typeof rc?.enabled === 'boolean';
}

/** #3155 (Ober-Spec feat_3122 Nr. 6, AC-9): Vorbelegung des 3-Tages-Ausblicks
 *  bei der Anlage -- allein das Morgen-Briefing an -> ['morning'], sonst
 *  ['evening'] (dieselbe Regel wie `resolve_outlook_reports` im Kern). */
export function ausblickVorbelegung(morning_enabled: boolean, evening_enabled: boolean): string[] {
	return morning_enabled && !evening_enabled ? ['morning'] : ['evening'];
}

/** #3155: `multi_day_trend_reports` beim Speichern. Ein gespeicherter Wert
 *  gewinnt immer (Schnappschuss vor dem lebenden Blob: in der Anlage traegt der
 *  lebende Blob die eigene Vorbelegung des letzten Laufs). Fehlt er, belegt nur
 *  die Anlage nach der Regel vor; ein bestehender Trip bleibt beim Stand vor B4
 *  (`[]`), die Vorbelegung wird nie nachtraeglich gesetzt (AC-13). */
function ausblickReports(eingabe: ReportConfigPayloadEingabe): string[] {
	for (const quelle of [eingabe.snapshot, eingabe.ausblickVorbelegung ? null : eingabe.live]) {
		const liste = quelle?.multi_day_trend_reports;
		if (Array.isArray(liste)) return liste.filter((r): r is string => typeof r === 'string');
	}
	const z = eingabe.zustand;
	return eingabe.ausblickVorbelegung ? ausblickVorbelegung(z.morning_enabled, z.evening_enabled) : [];
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
	/** #3155: Trip-ANLAGE -- fehlt `multi_day_trend_reports`, wird der
	 *  3-Tages-Ausblick nach der Regel vorbelegt. Default aus (Speichern eines
	 *  bestehenden Trips setzt die Liste nie neu). */
	ausblickVorbelegung?: boolean;
}

/**
 * `$effect`-Rumpf: Read-Modify-Write ueber `mergeReportConfig` mit
 * `enabled = morning_enabled || evening_enabled`, `toHHMMSS` auf beide Zeiten
 * und `multi_day_trend_reports` (#3155: gespeicherter Wert, sonst Vorbelegung
 * der Anlage bzw. `[]`). Unbekannte Bestandsfelder bleiben erhalten.
 */
export function baueReportConfigPayload(eingabe: ReportConfigPayloadEingabe): Record<string, unknown> {
	const z = eingabe.zustand;
	const multi_day_trend_reports = ausblickReports(eingabe);
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
