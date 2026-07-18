// Epic #1273 S3, Adversary-Fund F001: reine Tab-Resolve-Logik aus CompareTabs.svelte
// extrahiert, damit AC-3 (Hash→Query-Tab-Fix) per echtem Funktionsaufruf statt
// Datei-Grep geprüft werden kann (Spec verlangte das explizit). Single Source of
// Truth für gültige Tab-Werte — CompareTabs.svelte importiert von hier, keine
// Kopie der Werte.

export const COMPARE_TABS = [
	{ value: 'uebersicht', label: 'Übersicht' },
	{ value: 'orte', label: 'Orte' },
	// Issue #1311 (C1 von Epic #1301): zwischen orte und idealwerte — der neue
	// Tab entscheidet, welche Metriken ueberhaupt in der Vergleichs-Mail
	// erscheinen, bevor die Wertebereiche fuer sie konfiguriert werden.
	{ value: 'wetter-metriken', label: 'Wetter-Metriken' },
	{ value: 'idealwerte', label: 'Wertebereiche' },
	{ value: 'layout', label: 'Layout' },
	// Issue #1258 S5 (AC-19, H1): zwischen layout und versand — konsistent
	// zur Editor-Reihe aus S4 (Konvergenz-Vorgabe).
	{ value: 'alarme', label: 'Alarme' },
	{ value: 'versand', label: 'Versand' },
	{ value: 'vorschau', label: 'Vorschau' }
] as const;

export const COMPARE_TAB_VALUES: readonly string[] = COMPARE_TABS.map((t) => t.value);

export function resolveCompareTab(value: string): string {
	return COMPARE_TAB_VALUES.includes(value) ? value : 'uebersicht';
}
