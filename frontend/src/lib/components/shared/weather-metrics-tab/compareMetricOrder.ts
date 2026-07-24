// Issue #1359 Scheibe 1 — Pure-Function-Kern fuer die Metrik-REIHENFOLGE im
// Ortsvergleich (Muster: weatherMetricsTabSections.ts im selben Ordner; keine
// neue Struktur, nur Anwendung der etablierten).
//
// Warum ueberhaupt herausgeloest: `toggleCompareMetric` lag als lokale
// Funktion in WeatherMetricsTab.svelte und war dadurch nicht deterministisch
// testbar (AC-2 verlangt genau das).
//
// Spec: docs/specs/modules/compare_metric_order.md (AC-2, Known Limitations)

/**
 * An-/Abwaehlen einer Metrik unter ERHALT der Reihenfolge aller uebrigen.
 *
 * Vorher baute der Aufrufer die Liste ueber ein `Set` neu auf — dabei ging die
 * eingestellte Reihenfolge verloren (Issue #1359). Jetzt Trip-Muster
 * (`onToggleMetric` im route-Zweig): Abwaehlen entfernt die ID an ihrer
 * Position, Wiederanwaehlen haengt sie ans ENDE an. Das Ans-Ende-Rutschen ist
 * beabsichtigt und dokumentiert (AC-2): keine geheime Merk-Position, und ab
 * jetzt per Ziehen korrigierbar.
 *
 * Reine Funktion: liefert immer ein NEUES Array, mutiert `active` nie.
 */
export function toggleCompareMetricKey(active: readonly string[], metric: string): string[] {
	if (active.includes(metric)) return active.filter((m) => m !== metric);
	return [...active, metric];
}
