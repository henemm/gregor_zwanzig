// premiumSmsChannelState — Issue #1717 Scheibe S3 (Premium-SMS in der
// Oberflaeche), Spec docs/specs/modules/feat_1717_s3_premium_sms_ui.md.
//
// EIN Aufruf liefert den kompletten Anzeige-Zustand der Premium-SMS-Zeile
// (Design analog channelConnectionStatus()/channelContactLabel() im selben
// Ordner). Beide Kanalblock-Komponenten rufen ihn auf — VTBriefingChannels.svelte
// (/trips/[id], /compare/*) und die frühere Report-Config-Section (#2277 S5 entfernt) (/trips/new).
// Eine dritte, wortgleiche Kopie der Zustandslogik waere der Default-Fehler
// dieser Scheibe (vgl. channelContactLabel vor seiner Extraktion, #1510).
//
// KEINE Frist-Rechnung hier (AC-5). Die 30-Tage-Frist der gelernten
// Rueckadresse lebt serverseitig — im Python-Sendepfad
// (PREMIUM_SMS_REPLY_TTL, src/output/channels/premium_sms.py) und in der
// Go-Ableitung fuer GET /api/auth/profile (model.PremiumSmsReplyTTL,
// internal/model/premium_sms.go). Der Helfer folgt ausschliesslich dem fertig
// gelieferten Feld `premium_sms_reply_state`. Eine dritte Zahl im Frontend
// wuerde zwangslaeufig irgendwann "frisch" anzeigen, wo der Sendepfad schon
// blockt — deshalb steht im Hinweistext auch keine Tage-Zahl in Prosaform.
//
// Pure Funktion, kein Netz-/DOM-Zugriff — node:testbar.

import type { ConnectionProfile } from './channelConnectionStatus';
import { get } from 'svelte/store';
import { tr, locale } from '../../../i18n/index.ts';
import { fmtDate } from '../../../i18n/format.ts';

export type PremiumSmsTone = 'good' | 'warn' | 'neutral';

export interface PremiumSmsChannelState {
	/** Checkbox nicht anklickbar (Tarif gesperrt ODER Rueckadresse nicht frisch). */
	disabled: boolean;
	/** Dot-Ton neben dem Status-Label (Dot akzeptiert 'warn', ui/dot/Dot.svelte). */
	tone: PremiumSmsTone;
	/** Mono-Label neben dem Dot — Vokabular wie channelConnectionStatus(). */
	statusLabel: string;
	/** Prosa-Hinweis unter der Checkbox. Drei Zustaende, drei Texte. */
	hint: string;
	/** Meldedatum als eigenes Daten-Label ("zuletzt gemeldet am …"), leer wenn
	 * sich das Geraet noch nie gemeldet hat. */
	reportedAtLabel: string;
	/** Suffix fuer die Checkbox-Beschriftung — zeigt WOHIN gesendet wird
	 * (Muster channelContactLabel: " (nummer)"). */
	contactLabel: string;
}

/** Meldedatum: deutsch `TT.MM.JJJJ`, englisch `Thu 30 Oct` ohne Jahr (#2655, Annahme A2).
 * Bewusst ohne toLocaleDateString: das Ergebnis darf nicht von der
 * ICU-Ausstattung der Laufzeit abhaengen. */
function formatReportedAt(iso: string | undefined): string {
	if (!iso) return '';
	const d = new Date(iso);
	if (Number.isNaN(d.getTime())) return '';
	if (get(locale) === 'en') return fmtDate(d, 'en', 'kurz');
	const pad = (n: number) => String(n).padStart(2, '0');
	return `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()}`;
}

export function premiumSmsChannelState(
	profile: ConnectionProfile | null | undefined
): PremiumSmsChannelState {
	const p = profile ?? {};
	const reportedAt = formatReportedAt(p.premium_sms_reply_at);
	const reportedAtLabel = reportedAt ? tr('versand.premium_sms.zuletzt_gemeldet', { datum: reportedAt }) : '';
	const contactLabel = p.premium_sms_reply_to ? ` (${p.premium_sms_reply_to})` : '';
	const base = { reportedAtLabel, contactLabel };

	// Tarif-Gate zuerst: es ist eigenstaendig (nur Level Premium) und NICHT von
	// sms_allowed abgeleitet — model.PremiumSmsAllowed, AC-6. Ein noch nicht
	// geladenes Profil (null) laeuft bewusst hier hinein: alles gesperrt, bis
	// der Server geantwortet hat (Verhalten der drei bestehenden Kanaele).
	if (p.premium_sms_allowed !== true) {
		return {
			...base,
			disabled: true,
			tone: 'neutral',
			statusLabel: tr('versand.premium_sms.nicht_verfuegbar'),
			hint: tr('versand.premium_sms.hinweis.nicht_verfuegbar')
		};
	}

	// Ab hier entscheidet ausschliesslich der vom Server abgeleitete Zustand.
	if (p.premium_sms_reply_state === 'fresh') {
		return {
			...base,
			disabled: false,
			tone: 'good',
			statusLabel: tr('versand.premium_sms.gelernt'),
			hint: tr('versand.premium_sms.hinweis.gelernt')
		};
	}
	if (p.premium_sms_reply_state === 'stale') {
		return {
			...base,
			disabled: true,
			tone: 'warn',
			statusLabel: tr('versand.premium_sms.verfallen'),
			hint: tr('versand.premium_sms.hinweis.verfallen')
		};
	}
	// 'none' und alles Unbekannte: noch nie gemeldet. Bewusst NICHT als
	// "verfallen" ausgegeben — das behauptete ein Verfallsdatum, das es nie gab.
	return {
		...base,
		disabled: true,
		tone: 'neutral',
		statusLabel: tr('versand.status.nicht_verbunden'),
		hint: tr('versand.premium_sms.hinweis.nie_gemeldet')
	};
}
