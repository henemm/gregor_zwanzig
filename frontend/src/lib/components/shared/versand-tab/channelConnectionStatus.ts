// channelConnectionStatus — Issue #1258 Scheibe S6 (R5).
// Leitet je Kanal einen ehrlichen Verbindungsstatus aus dem Profil ab
// (Zustands-Matrix: Spec docs/specs/modules/issue_1258_alarme_tab_official_warnings.md
// Abschnitt 12, AC-21). Pure Funktion, kein Netz-/DOM-Zugriff — node:testbar.

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
