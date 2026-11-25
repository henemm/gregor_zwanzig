// Issue #2987 — Startwerte des Trip-Briefings aus EINER Lesefunktion.
// Spec: docs/specs/modules/refactor_2987_standardwerte_eine_quelle.md
//
// Leser: Reiter Zustellung (`standAusTrip`) und Anlege-Weg (`ladeReportZustand`). Das Orts-Briefing
// (`standAusPreset`) nutzt nur Zeit-Standards und `hhmm`; seine Slot-Vorgaben (Abend aus) sind eigene.
// Pure Funktionen; importiert nur aus utils/ (keine Importzyklen) — node:testbar.

import { reportSlotAktiv } from '../../utils/reportSlotAktiv.ts';

export const MORGEN_STANDARD = '07:00';
export const ABEND_STANDARD = '18:00';

/** 'HH:MM' aus 'HH:MM' oder 'HH:MM:SS'; fehlend, leer oder ungueltig = Standard. */
export const hhmm = (v: unknown, standard: string): string => (typeof v === 'string' && /^\d{2}:\d{2}/.test(v) ? v.slice(0, 5) : standard);

/** Slots (Regel des Versands), Zeiten 'HH:MM' und die vier Kanaele (E-Mail an, uebrige aus). */
export function leseBriefingStartwerte(rc: Record<string, unknown> | null | undefined) {
	const c: Record<string, unknown> = rc ?? {};
	return {
		morning_enabled: reportSlotAktiv(rc, 'morning'),
		evening_enabled: reportSlotAktiv(rc, 'evening'),
		morning_time: hhmm(c.morning_time, MORGEN_STANDARD),
		evening_time: hhmm(c.evening_time, ABEND_STANDARD),
		send_email: c.send_email !== false,
		send_telegram: c.send_telegram === true,
		send_sms: c.send_sms === true,
		send_premium_sms: c.send_premium_sms === true
	};
}
