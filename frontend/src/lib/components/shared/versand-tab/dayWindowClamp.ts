// Issue #1319 Scheibe B Fix-Loop (F001): pure Klemm-Logik fuer das
// Tagesfenster-Start-/Endstunden-Paar, ausgelagert damit sie ohne
// Svelte-Rendering-Harness direkt testbar ist (Praezedenz:
// corridor-editor/corridorEditorState.ts openBoundValue).
//
// Issue #1361/#1372 S1b (PO-Entscheidung 2026-07-25): ein Fenster mit
// end < start ist seit dieser Scheibe ein GUELTIGES Fenster ueber Mitternacht
// (z. B. 22-2 Uhr) -- keine Nachzieh-Korrektur mehr. Die einzige verbleibende
// Mehrdeutigkeit ist end === start (Nullstunden-/Ganztags-Fenster); nur dieser
// Fall wird noch auf die naechste Stunde (modulo 24, damit Start=23 auf 0
// nachzieht statt auf ein erneut gleiches 24) nachgezogen, damit das
// gebundene Paar nie in der Zweideutigkeit landet, bevor der Auto-Save-Effekt
// feuert.
export function clampDayWindowEndHour(startHour: number, currentEndHour: number): number {
	return currentEndHour === startHour ? (startHour + 1) % 24 : currentEndHour;
}
