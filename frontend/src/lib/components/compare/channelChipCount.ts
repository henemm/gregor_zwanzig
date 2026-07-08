// Issue #1097 — Deckelung der Layout-Tab-Chip-Anzahl pro Kanal.
// CHANNEL_COLS (email:99, telegram:8, sms:0) ist ein Kanal-BUDGET, kein
// Chip-Rendering-Wert. Der Layout-Tab soll die tatsächliche Orts-Anzahl
// zeigen, nie mehr als das Kanal-Budget erlaubt. Deckelung nur nach unten:
// channelChipCount(99, 8) → 8 (nicht 99), channelChipCount(8, 3) → 3,
// channelChipCount(0, 8) → 0 (SMS bleibt "flach · ohne Spalten").
export function channelChipCount(budget: number, locationCount: number): number {
	return Math.min(budget, locationCount);
}
