// ltIdealRange.ts — Issue #1232 Scheibe 3a Fix-Runde (Adversary F003).
//
// Die Grünfärbung in LTComparePreview MUSS die echten nutzerdefinierten
// Idealbereiche (wizard.idealRanges, Step 3 des Compare-Wizards) lesen statt
// fester Demo-Schwellen — Expected Behavior + Out-of-Scope der Spec sagen das
// explizit ("nur die bestehenden ideal_ranges werden in der Vorschau
// gelesen"). Ist für eine Metrik KEIN Range konfiguriert (kein Eintrag oder
// weder min noch max numerisch gesetzt — z. B. Enum-Metriken wie
// thunder_level_max), fällt die Bewertung auf die bisherigen JSX-Demo-
// Schwellen zurück, damit die Vorschau ohne Step-3-Konfiguration nicht
// farblos ist.

export interface IdealRangeLite {
	min?: number | null;
	max?: number | string | null;
}

/**
 * Liefert true/false anhand des konfigurierten Idealbereichs, wenn einer mit
 * mindestens einer numerischen Grenze existiert — sonst `fallbackGood(value)`.
 */
export function isIdealGood(
	value: number,
	range: IdealRangeLite | undefined,
	fallbackGood: (value: number) => boolean
): boolean {
	const hasMin = typeof range?.min === 'number';
	const hasMax = typeof range?.max === 'number';
	if (!hasMin && !hasMax) return fallbackGood(value);
	if (hasMin && value < (range!.min as number)) return false;
	if (hasMax && value > (range!.max as number)) return false;
	return true;
}
