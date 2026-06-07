// Issue #617 — pure Helper für Kanal-Verkettung aus Wetter-Metriken.
// Spec: docs/specs/modules/issue_617_briefing_channel_chaining.md
// Exportierte Symbole werden von EditReportConfigSection.svelte und
// issue_617_briefing_channel_gating.test.ts genutzt.

/** Kanal-Aktivierungszustand aus display_config.channels (#587). */
export type ChannelConfig = { email: boolean; telegram: boolean; sms: boolean };

/**
 * Gibt zurück, welche Kanäle sichtbar sind.
 * undefined → Altverhalten: alle drei true.
 * Sonst 1:1 die übergebenen Flags.
 */
export function visibleChannels(weatherChannels?: ChannelConfig): ChannelConfig {
	if (weatherChannels === undefined) {
		return { email: true, telegram: true, sms: true };
	}
	return { ...weatherChannels };
}

/**
 * Lesbare Labels der AKTIVEN Kanäle in fester Reihenfolge: email, telegram, sms.
 * Labels exakt: 'Email', 'Telegram', 'SMS'.
 */
export function activeChannelLabels(weatherChannels: ChannelConfig): string[] {
	const labels: string[] = [];
	if (weatherChannels.email) labels.push('Email');
	if (weatherChannels.telegram) labels.push('Telegram');
	if (weatherChannels.sms) labels.push('SMS');
	return labels;
}

/**
 * true NUR wenn weatherChannels gesetzt UND 0 aktive Kanäle.
 * undefined → false (Altverhalten).
 */
export function hasNoActiveChannel(weatherChannels?: ChannelConfig): boolean {
	if (weatherChannels === undefined) return false;
	return !weatherChannels.email && !weatherChannels.telegram && !weatherChannels.sms;
}

/**
 * Read-Modify-Write: Kopie von reportConfig; für jeden Kanal mit
 * weatherChannels[x]===false → send_x:=false.
 * Aktive Kanäle: Nutzerwahl bleibt erhalten.
 * undefined → reportConfig unverändert zurück (Kopie ok).
 * ALLE übrigen Felder erhalten (kein Datenverlust).
 */
export function syncSendFlags(
	reportConfig: Record<string, unknown>,
	weatherChannels?: ChannelConfig
): Record<string, unknown> {
	if (weatherChannels === undefined) {
		return { ...reportConfig };
	}
	const result: Record<string, unknown> = { ...reportConfig };
	if (!weatherChannels.email) result['send_email'] = false;
	if (!weatherChannels.telegram) result['send_telegram'] = false;
	if (!weatherChannels.sms) result['send_sms'] = false;
	return result;
}
