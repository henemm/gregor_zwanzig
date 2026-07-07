// Issue #1093 — Auswahl der Vorschau-Zeilen für LayoutPreview.
// Reine Illustration: es wird NICHT nach echten pickedIds gefiltert (echte
// Location-UUIDs matchen die statischen Dummy-IDs nie → früher rows=[] → Crash).
// Stattdessen so viele Beispielzeilen wie Orte gewählt, gedeckelt auf verfügbare Dummys.
// Invariante: bei pickedIds.length > 0 ist das Ergebnis nie leer (dummies.length >= 1).
export function selectPreviewRows<T>(pickedIds: string[], dummies: T[]): T[] {
	return pickedIds.length > 0
		? dummies.slice(0, Math.min(pickedIds.length, dummies.length))
		: dummies;
}
