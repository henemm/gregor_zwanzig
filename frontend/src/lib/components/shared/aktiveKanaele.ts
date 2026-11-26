// Issue #2990 — EINE Kanal-Ableitung fuer Trip (report_config) und Ortsvergleich (Preset).
// Spec: docs/specs/modules/refactor_2990_kanal_ableitung_eine_quelle.md
//
// Flags nur ueber `leseBriefingStartwerte` (E-Mail fehlend = an, uebrige nur bei genau `true`).
// Feste Reihenfolge email, telegram, sms, premium-sms; Signal existiert nicht (#610).
// `empfaenger` und `channel_layouts` haben keinen Einfluss. Pure, node:testbar.

import { leseBriefingStartwerte } from './briefingStartwerte.ts';

export const KANAL_ANZEIGENAME: Record<string, string> = {
	email: 'Email',
	telegram: 'Telegram',
	sms: 'SMS',
	'premium-sms': 'Premium-SMS'
};

/** Aktive Kanal-Schluessel in fester Reihenfolge. */
export function aktiveKanaele(quelle: Record<string, unknown> | null | undefined): string[] {
	const z = leseBriefingStartwerte(quelle);
	const out: string[] = [];
	if (z.send_email) out.push('email');
	if (z.send_telegram) out.push('telegram');
	if (z.send_sms) out.push('sms');
	if (z.send_premium_sms) out.push('premium-sms');
	return out;
}

/** Dieselbe Liste als Anzeigenamen (Email, Telegram, SMS, Premium-SMS). */
export function aktiveKanalNamen(quelle: Record<string, unknown> | null | undefined): string[] {
	return aktiveKanaele(quelle).map((k) => KANAL_ANZEIGENAME[k]);
}
