// corridorMatch.ts — Issue #1231, Slice 1: C5 Single-Source-Match-Logik.
//
// Verbatim portiert aus der JSX-Referenz
// (claude-code-handoff/current/jsx/corridor-editor.jsx::corridorInside/
// corridorFmt). Muss identische Ergebnisse liefern wie der Python-Port
// (src/services/corridor_match.py::corridor_inside) — AC-2.

/**
 * Liegt `value` im Korridor [min, max]?
 *
 * - `value == null` -> `null` (kein Messwert, neutral — C1).
 * - `min` gesetzt und `value < min` -> `false` (unter dem Korridor).
 * - `max` gesetzt und `value > max` -> `false` (über dem Korridor).
 * - sonst -> `true` (im Korridor, Grenzwerte inklusive — < / > exklusiv geprüft).
 */
export function corridorInside(
	value: number | null | undefined,
	min: number | null | undefined,
	max: number | null | undefined
): boolean | null {
	if (value == null) return null;
	if (min != null && value < min) return false;
	if (max != null && value > max) return false;
	return true;
}

/** Formatiert einen Korridor-Grenzwert für die Anzeige ("offen" bei null). */
export function corridorFmt(v: number | null | undefined, unit?: string): string {
	if (v == null) return 'offen';
	const s = Number.isInteger(v) ? String(v) : v.toFixed(1);
	const withSign = unit === '°C' && v > 0 ? `+${s}` : s;
	return unit ? `${withSign} ${unit}` : withSign;
}
