// premiumSmsChannelState — Issue #1717 Scheibe S3 (Premium-SMS in der
// Oberflaeche), Spec docs/specs/modules/feat_1717_s3_premium_sms_ui.md.
//
// EIN Aufruf liefert den kompletten Anzeige-Zustand der Premium-SMS-Zeile
// (Design analog channelConnectionStatus()/channelContactLabel() im selben
// Ordner). Beide Kanalblock-Komponenten rufen ihn auf — VTBriefingChannels.svelte
// (/trips/[id], /compare/*) und EditReportConfigSection.svelte (/trips/new).
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

/** Meldedatum als deutsches Kalenderdatum. Bewusst ohne toLocaleDateString:
 * das Ergebnis darf nicht von der ICU-Ausstattung der Laufzeit abhaengen. */
function formatReportedAt(iso: string | undefined): string {
	if (!iso) return '';
	const d = new Date(iso);
	if (Number.isNaN(d.getTime())) return '';
	const pad = (n: number) => String(n).padStart(2, '0');
	return `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()}`;
}

export function premiumSmsChannelState(
	profile: ConnectionProfile | null | undefined
): PremiumSmsChannelState {
	const p = profile ?? {};
	const reportedAt = formatReportedAt(p.premium_sms_reply_at);
	const reportedAtLabel = reportedAt ? `zuletzt gemeldet am ${reportedAt}` : '';
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
			statusLabel: 'nicht verfügbar',
			hint: 'Premium-SMS ab Level Premium verfügbar'
		};
	}

	// Ab hier entscheidet ausschliesslich der vom Server abgeleitete Zustand.
	if (p.premium_sms_reply_state === 'fresh') {
		return {
			...base,
			disabled: false,
			tone: 'good',
			statusLabel: 'gelernt',
			hint: 'Das Gerät hat sich gemeldet — Briefings gehen an die gelernte Rückadresse.'
		};
	}
	if (p.premium_sms_reply_state === 'stale') {
		return {
			...base,
			disabled: true,
			tone: 'warn',
			statusLabel: 'verfallen',
			hint:
				'Rückadresse verfallen — Garmin kann die Nummer inzwischen einem fremden Gerät ' +
				'zugeteilt haben. Sobald sich das Gerät wieder meldet, ist der Kanal erneut nutzbar.'
		};
	}
	// 'none' und alles Unbekannte: noch nie gemeldet. Bewusst NICHT als
	// "verfallen" ausgegeben — das behauptete ein Verfallsdatum, das es nie gab.
	return {
		...base,
		disabled: true,
		tone: 'neutral',
		statusLabel: 'nicht verbunden',
		hint: 'Das Gerät hat sich noch nie gemeldet — die Rückadresse wird beim ersten Empfang gelernt.'
	};
}
