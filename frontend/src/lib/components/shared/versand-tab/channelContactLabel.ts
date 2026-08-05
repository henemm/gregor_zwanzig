// channelContactLabel — Issue #1510.
// Liefert die Kontakt-Beschriftungs-Suffixe je Kanal aus einem ConnectionProfile
// (z.B. " (a@b.de)" oder "" wenn kein Kontakt hinterlegt). Ersetzt die sechs
// bisherigen Ternary-Duplikate in VTBriefingChannels.svelte und
// EditReportConfigSection.svelte.
//
// Design: EIN Aufruf liefert alle drei Kanäle als Objekt (analog
// channelConnectionStatus()), statt drei Einzelfunktionen — hält den Aufrufaufwand
// pro Komponente bei einem $derived-Aufruf. Liefert bewusst nur den Suffix, nicht
// das ganze Label inkl. Kanalname — der Kanalname bleibt literaler Text im Template.
//
// Spec: docs/specs/modules/fix_1510_versand_ziel_dedupe.md (AC-1)
// Pure Funktion, kein Netz-/DOM-Zugriff — node:testbar, analog channelConnectionStatus.

import type { ConnectionProfile } from './channelConnectionStatus';

export interface ChannelContactLabels {
	email: string;
	telegram: string;
	sms: string;
}

export function channelContactLabel(
	profile: ConnectionProfile | null | undefined
): ChannelContactLabels {
	const p = profile ?? {};
	return {
		email: p.mail_to ? ` (${p.mail_to})` : '',
		telegram: p.telegram_chat_id ? ` (${p.telegram_chat_id})` : '',
		sms: p.sms_to ? ` (${p.sms_to})` : ''
	};
}
