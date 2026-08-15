// ltChannels.ts — Issue #1232 Scheibe 3a: geteilte Kappungs-Quelle für den
// LayoutTab-Organism (context="route"|"vergleich").
//
// Issue #1719 Scheibe S3 (ADR-0050 Regel 4, "Aus ist ein Zustand"): das
// Budget-Modell ist von einer einzigen Spaltenzahl je Kanal auf eine
// EINHEIT je Kanal umgestellt (LtLimit) — SMS hat kein Spalten-Raster,
// sondern eine Zeichengrenze, und diese Zahl unterscheidet sich je
// Ausgabeweg (Trip 160 / Vergleich 153 / Alarm 140 — Letzterer lebt in
// AlertChannelPicker.svelte, ausserhalb dieses Moduls). Telegram bleibt
// EINE Spaltenzahl (7, aus CHANNEL_COL_BUDGET.telegram — trip-detail/
// metricsEditor.ts), Email bleibt unbegrenzt.
//
// Spec: docs/specs/modules/fix_1719_s3_aus_ist_ein_zustand.md (Abschnitt 5, 6)

import { CHANNEL_COL_BUDGET } from '$lib/components/trip-detail/metricsEditor';

export type ChannelId = 'email' | 'telegram' | 'sms';

export type LtLimit =
	| { kind: 'none' }
	| { kind: 'columns'; value: number }
	| { kind: 'chars'; value: number };

/**
 * Alias auf die einzige Telegram-Kappungs-Quelle (CHANNEL_COL_BUDGET.telegram,
 * metricsEditor.ts) — KEINE eigene Zahl. Beleg fuer 7:
 * src/output/renderers/channel_layout.py:110 (metric_slots = limit - 1).
 */
export const TELEGRAM_METRIC_COLUMNS = CHANNEL_COL_BUDGET.telegram;

/** Beleg: src/output/renderers/trip_report.py:446, max_length=160 (Literal). */
export const SMS_TRIP_CHAR_LIMIT = 160;

/** Beleg: src/output/renderers/channel_layout.py:45-54, GSM-7/UDH-Rechnung
 *  floor((140-6)*8/7). Gilt fuer den Ortsvergleich (VTBriefingChannels im
 *  vergleich-Kontext, CompareSmsPreview). */
export const SMS_COMPARE_CHAR_LIMIT = 153;

const CHANNEL_LABELS: Record<ChannelId, string> = {
	email: 'Email',
	telegram: 'Telegram',
	sms: 'SMS'
};

/**
 * Platzgrenze eines Kanals. Der SMS-Zeichenwert kommt vom AUFRUFER, nicht
 * aus einer geteilten Konstante — genau wie `hasLabelColumn` bei
 * LTCapNote.svelte. Eine einzige geteilte Zahl wäre in mindestens zwei der
 * drei Ausgabewege (Trip 160 / Vergleich 153 / Alarm 140) nachweislich falsch.
 */
export function ltLimitForChannel(channel: ChannelId, smsCharLimit: number): LtLimit {
	if (channel === 'email') return { kind: 'none' };
	if (channel === 'telegram') return { kind: 'columns', value: TELEGRAM_METRIC_COLUMNS };
	return { kind: 'chars', value: smsCharLimit };
}

export interface LtChannel {
	id: ChannelId;
	label: string;
	limit: LtLimit;
}

/**
 * Issue #1703 Scheibe 8 (AC-S8-12, Gegenprobe M7): Kanalliste fuer EINEN
 * Ausgabeweg — der SMS-Zeichenwert kommt vom Aufrufer, genau wie bei
 * `ltLimitForChannel`/`ltCapNoteText`. Ohne sie zeigte der Kanal-Tab-Badge im
 * Ortsvergleich die Trip-Zahl (160), waehrend der Kappungs-Hinweis darunter
 * korrekt 153 nennt — zwei sich widersprechende Aussagen auf einer Seite.
 */
export function ltChannelsFor(smsCharLimit: number): LtChannel[] {
	return (['email', 'telegram', 'sms'] as ChannelId[]).map((id) => ({
		id,
		label: CHANNEL_LABELS[id],
		limit: ltLimitForChannel(id, smsCharLimit)
	}));
}

/**
 * Kanalliste fuer den Trip-Pfad (SMS_TRIP_CHAR_LIMIT) — Default des
 * LTChannelPicker und damit unveraenderter Wert fuer WeatherMetricsTab
 * (route). Der Vergleichspfad baut sich seine Liste seit #1703 S8 ueber
 * `ltChannelsFor(SMS_COMPARE_CHAR_LIMIT)`.
 */
export const LT_CHANNELS: LtChannel[] = ltChannelsFor(SMS_TRIP_CHAR_LIMIT);

export const LT_CH_BY_ID: Record<ChannelId, LtChannel> = Object.fromEntries(
	LT_CHANNELS.map((c) => [c.id, c])
) as Record<ChannelId, LtChannel>;

/** ∞ (Email) · sonst die Zahl selbst — Spalten ODER Zeichen, je nach `limit.kind`. */
export function ltBadgeForLimit(limit: LtLimit): string {
	return limit.kind === 'none' ? '∞' : String(limit.value);
}

/**
 * Überschreitende Spaltenzahl (Chip "−n" im LTChannelPicker). NUR für
 * `kind:'columns'` — für `kind:'chars'` wird ausdrücklich KEIN Überlauf
 * berechnet (Spec Abschnitt 5: der Editor kennt die fertig gebaute SMS-Zeile
 * nicht, eine Schätzzahl wäre eine zweite falsche Behauptung), für
 * `kind:'none'` gibt es keinen Überlauf.
 */
export function ltOverflowForLimit(limit: LtLimit, count: number): number | undefined {
	if (limit.kind !== 'columns') return undefined;
	return count > limit.value ? count - limit.value : undefined;
}

/**
 * Überlauf je Kanal für denselben `colCount` (Chip-Anzeige im
 * LTChannelPicker über ALLE Kanal-Tabs, nicht nur den aktiven — unverändertes
 * Verhalten ggü. der Vorgänger-Funktion `ltOverflow`, nur auf das LtLimit-
 * Modell umgestellt).
 */
export function ltOverflowAcrossChannels(
	colCount: number,
	smsCharLimit: number
): Partial<Record<ChannelId, number>> {
	const result: Partial<Record<ChannelId, number>> = {};
	for (const id of ['email', 'telegram', 'sms'] as ChannelId[]) {
		const overflow = ltOverflowForLimit(ltLimitForChannel(id, smsCharLimit), colCount);
		if (overflow !== undefined) result[id] = overflow;
	}
	return result;
}

/**
 * Kanal-Hinweistext ohne Wertung (Spec AC-5, Commits 3da43cad + 6403c57a):
 * nennt die gemessene Platzgrenze, keine Aussage darüber, welche Werte
 * wichtig sind, keine falsche Behauptung über SMS-Reihenfolge.
 */
export function ltCapNoteText(params: {
	channel: ChannelId;
	limit: LtLimit;
	colCount: number;
	subject: string;
	hasLabelColumn: boolean;
}): string {
	const { channel, limit, colCount, subject, hasLabelColumn } = params;
	const label = CHANNEL_LABELS[channel];
	if (limit.kind === 'none') return `${label} zeigt alles · keine Begrenzung`;
	if (limit.kind === 'chars') {
		return `${label}: kein Raster, keine Tabelle — Fließtext, ${limit.value} Zeichen`;
	}
	const fits = colCount <= limit.value;
	const fitText = fits
		? `passt (max ${limit.value})`
		: `zu breit — max ${limit.value}, weiter vorne = sicherer`;
	const countLabel = hasLabelColumn ? `${colCount} Spalten (Label + ${subject})` : `${colCount} ${subject}`;
	return `${label}: ${countLabel} · ${fitText}`;
}
