// Issue #1350 Teil 2: Compare-Metrik-Auswahlliste bezieht ihre Einträge aus
// GET /api/compare/metrics (Teil 1, live seit a824a6cc) statt aus dem
// statischen Frontend-Import COMPARE_METRIC_DEFS.
// Spec: docs/specs/modules/compare_metric_selection_source.md § AC-1, AC-2
import type { CompareMetricCatalogEntry } from '$lib/types';

export interface CompareSelectionEntry {
	metric: string;
	label: string;
}

/**
 * Mappt die Antwort von GET /api/compare/metrics auf die Auswahllisten-Form
 * (key -> metric, label -> label), Reihenfolge unveraendert. Fehlendes/leeres
 * `metrics` -> [] (kein Crash, kein still leerer Fehlerpfad im Aufrufer).
 */
export function toCompareSelectionEntries(
	response: { metrics: CompareMetricCatalogEntry[] }
): CompareSelectionEntry[] {
	// Laufzeit bleibt defensiv (response.metrics ?? []), obwohl der Typ das
	// Feld als Pflicht deklariert — der Endpoint darf nie ohne `metrics`
	// antworten, ein fehlerhafter/leerer Body darf aber trotzdem nicht crashen.
	return (response.metrics ?? []).map((m) => ({ metric: m.key, label: m.label }));
}
