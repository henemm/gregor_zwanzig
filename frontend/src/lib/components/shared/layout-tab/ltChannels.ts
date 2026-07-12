// ltChannels.ts — Issue #1232 Scheibe 3a: geteilte Kappungs-Quelle für den
// LayoutTab-Organism (context="route"|"vergleich").
//
// LT_CHANNELS leitet sich AUSSCHLIESSLICH aus CHANNEL_COL_BUDGET
// (trip-detail/metricsEditor.ts) ab — keine eigene Zahl. Damit gibt es nur
// noch EINE Kappungs-Quelle (Email ∞ · Telegram 8 · SMS 0) statt der
// bisherigen vier Duplikate (Step4Layout/CE_CHANNELS, CompareTabs, CompareChatBubble,
// VTBriefingChannels).
//
// Spec: docs/specs/modules/layout_tab_vergleich.md (Implementation Details §1)

import { CHANNEL_COL_BUDGET } from '$lib/components/trip-detail/metricsEditor';

export type ChannelId = 'email' | 'telegram' | 'sms';

export interface LtChannel {
	id: ChannelId;
	label: string;
	max: number;
	note: string;
}

export const LT_CHANNELS: LtChannel[] = [
	{
		id: 'email',
		label: 'Email',
		max: CHANNEL_COL_BUDGET.email,
		note: 'alle Spalten · kein Limit'
	},
	{
		id: 'telegram',
		label: 'Telegram',
		max: CHANNEL_COL_BUDGET.telegram,
		note: `max ${CHANNEL_COL_BUDGET.telegram} Spalten`
	},
	{
		id: 'sms',
		label: 'SMS',
		max: CHANNEL_COL_BUDGET.sms,
		note: 'kein Raster · ≤ 140 Zeichen'
	}
];

export const LT_CH_BY_ID: Record<ChannelId, LtChannel> = Object.fromEntries(
	LT_CHANNELS.map((c) => [c.id, c])
) as Record<ChannelId, LtChannel>;

/** ∞ (Email) · — (SMS ohne Raster) · sonst die Zahl selbst. */
export function ltBadge(max: number): string {
	return max === Infinity ? '∞' : max === 0 ? '—' : String(max);
}

/**
 * Überschreitende Spaltenzahl je Kanal (Chip "−n" im LTChannelPicker).
 * Komplementär zu `channelOverflow` aus metricsEditor.ts: jenes liefert
 * Booleans für den Trip-Dirty-Check bei genau einer primaryCount, dieses
 * liefert die konkrete überschreitende Zahl für den Overflow-Chip. Beide
 * leiten aus derselben CHANNEL_COL_BUDGET-Quelle ab.
 */
export function ltOverflow(colCount: number): Partial<Record<ChannelId, number>> {
	const result: Partial<Record<ChannelId, number>> = {};
	for (const ch of LT_CHANNELS) {
		if (ch.max === Infinity || ch.max === 0) continue;
		if (colCount > ch.max) result[ch.id] = colCount - ch.max;
	}
	return result;
}
