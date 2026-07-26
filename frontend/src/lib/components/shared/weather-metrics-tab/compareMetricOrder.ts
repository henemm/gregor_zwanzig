// Issue #1359 Scheibe 1 — Pure-Function-Kern fuer die Metrik-REIHENFOLGE im
// Ortsvergleich (Muster: weatherMetricsTabSections.ts im selben Ordner; keine
// neue Struktur, nur Anwendung der etablierten).
//
// Warum ueberhaupt herausgeloest: `toggleCompareMetric` lag als lokale
// Funktion in WeatherMetricsTab.svelte und war dadurch nicht deterministisch
// testbar (AC-2 verlangt genau das).
//
// Spec: docs/specs/modules/compare_metric_order.md (AC-2, Known Limitations)
//
// Issue #1366 F002 (symmetrisch zu F001/compareHourlyMetricDefs.ts):
// materializeActiveMetricKeys/toggleCompareMetricKeyFromState unterscheiden
// „nie eingestellt" (`null`) von „bewusst leer" (`[]`) -- EINZIGE Quelle der
// Wahrheit fuer Anzeige UND Umschalt-Handler in WeatherMetricsTab.svelte.

import { COMPARE_METRIC_KEYS } from '../corridor-editor/corridorEditorState.ts';

/**
 * `null` (nie eingestellt) -> Vorgabemenge (COMPARE_METRIC_KEYS, dieselbe
 * Liste wie die Legacy-Default-Ableitung in weatherMetricsCompareSave.ts).
 * `[]` (bewusste Leerauswahl) bleibt unveraendert leer.
 */
export function materializeActiveMetricKeys(keys: string[] | null): string[] {
	return keys === null ? COMPARE_METRIC_KEYS : keys;
}

/**
 * Umschalt-Handler-Pfad wie WeatherMetricsTab.svelte ihn tatsaechlich
 * aufruft -- materialisiert zuerst (analog Anzeige), toggelt danach. Ohne
 * diesen Umweg erzeugte ein Klick aus "nie eingestellt" (Anzeige zeigt alle
 * Metriken an) faelschlich eine leere Liste statt "alle minus eine" (F001-
 * Regressionsmuster, hier fuer die Uebersichtstabelle vorab geschlossen).
 */
export function toggleCompareMetricKeyFromState(
	currentKeys: string[] | null,
	metric: string
): string[] {
	return toggleCompareMetricKey(materializeActiveMetricKeys(currentKeys), metric);
}

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
