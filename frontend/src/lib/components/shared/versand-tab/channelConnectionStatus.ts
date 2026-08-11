// channelConnectionStatus — Issue #1258 Scheibe S6 (R5).
// Leitet je Kanal einen ehrlichen Verbindungsstatus aus dem Profil ab
// (Zustands-Matrix: Spec docs/specs/modules/issue_1258_alarme_tab_official_warnings.md
// Abschnitt 12, AC-21). Pure Funktion, kein Netz-/DOM-Zugriff — node:testbar.
//
// Verwandte Bausteine im selben Ordner, die dieselbe ConnectionProfile-Datenbasis
// konsumieren: sendTargetLabel.ts (#1471, Ziel-Satz im Bestätigungsdialog) und
// channelContactLabel.ts (#1510, Kontakt-Suffixe für die Checkbox-Labels).

export type ConnectionTone = 'good' | 'neutral';

export interface ChannelConnectionInfo {
	tone: ConnectionTone;
	label: string;
}

export interface ChannelConnectionStatus {
	email: ChannelConnectionInfo;
	telegram: ChannelConnectionInfo;
	sms: ChannelConnectionInfo;
}

export interface ConnectionProfile {
	mail_to?: string;
	email_verified?: boolean;
	telegram_chat_id?: string;
	sms_to?: string;
	sms_allowed?: boolean;
	/** Issue #1717 S3 — Premium-SMS (Garmin inReach). Vier lesende Felder aus
	 * GET /api/auth/profile (Go: profileResponse). Hier und NICHT in den lokalen
	 * `interface Profile`-Kopien der Komponenten, damit es eine kanonische
	 * Profilform gibt; ausgewertet von premiumSmsChannelState(). */
	premium_sms_allowed?: boolean;
	premium_sms_reply_to?: string;
	premium_sms_reply_at?: string;
	premium_sms_reply_state?: 'none' | 'stale' | 'fresh';
}

const NOT_CONNECTED: ChannelConnectionInfo = { tone: 'neutral', label: 'nicht verbunden' };

export function channelConnectionStatus(
	profile: ConnectionProfile | null | undefined
): ChannelConnectionStatus {
	const p = profile ?? {};

	let email: ChannelConnectionInfo;
	if (!p.mail_to) {
		email = NOT_CONNECTED;
	} else if (p.email_verified) {
		email = { tone: 'good', label: 'bestätigt' };
	} else {
		email = { tone: 'neutral', label: 'nicht bestätigt' };
	}

	const telegram: ChannelConnectionInfo = p.telegram_chat_id
		? { tone: 'good', label: 'verbunden' }
		: NOT_CONNECTED;

	const sms: ChannelConnectionInfo =
		p.sms_to && p.sms_allowed !== false ? { tone: 'good', label: 'hinterlegt' } : NOT_CONNECTED;

	return { email, telegram, sms };
}
