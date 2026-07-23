// Issue #1319 Scheibe B Fix-Loop (F001): pure Klemm-Logik fuer das
// Tagesfenster-Start-/Endstunden-Paar, ausgelagert damit sie ohne
// Svelte-Rendering-Harness direkt testbar ist (Praezedenz:
// corridor-editor/corridorEditorState.ts openBoundValue).
//
// AC-5: waehlt der Nutzer eine Startstunde, die die aktuelle Endstunde
// ungueltig macht (start >= end), wird die Endstunde automatisch auf
// min(start+1, 23) nachgezogen -- das gebundene Paar bleibt IMMER gueltig,
// bevor VersandTab.svelte den reportConfig-$effect (und damit den PUT) feuert.
export function clampDayWindowEndHour(startHour: number, currentEndHour: number): number {
	return currentEndHour <= startHour ? Math.min(startHour + 1, 23) : currentEndHour;
}
