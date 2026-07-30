// Issue #1411 (Epic #1372 S4b Scheibe 1) — Ortsvergleich-Grundauswahl: die
// flache Compare-Katalogantwort (26 Zeilen, je eine pro (metric_id,
// aggregation)-Paar) wird nach `metric_id` gruppiert, damit die Karte
// "Wetter-Metriken" eine Zeile je Wettergroesse zeigt statt einer je Paar.
//
// Reine Funktion, kein Svelte-Rendering-Harness noetig (Muster:
// weatherMetricsTabSections.ts, compareMetricOrder.ts im selben Ordner).
//
// Spec: docs/specs/modules/feat_1411_s4b_grundauswahl.md § Implementation
// Details 1, AC-1, AC-4, AC-8

import type { CompareSelectionEntry } from './compareMetricSelection.ts';

/** Eine einzelne ankreuzbare Auswertung innerhalb einer Gruppe — 1:1 aus dem
 *  Katalog-Eintrag, kein erfundenes Feld. */
export interface CompareAggregationOption {
	key: string;
	aggregation: string;
	aggregation_label: string;
}

/** Eine Grundauswahl-Zeile: eine Wettergroesse mit 1..n Auswertungs-Optionen. */
export interface CompareAggregationGroup {
	metric_id: string;
	label: string;
	options: CompareAggregationOption[];
}

/**
 * Gruppiert die flache `compareCatalog`-Antwort nach `metric_id`. Fundreihenfolge
 * bestimmt die Zeilenposition (erstes Auftreten einer `metric_id`); innerhalb
 * einer Gruppe bleibt die Katalog-Reihenfolge der Optionen erhalten (AC-1).
 *
 * Verlustfrei (AC-8): jeder einzelne Auswahl-Schluessel (`entry.metric`) taucht
 * danach genau einmal in genau einer Options-Liste auf — kein Zusammenfassen,
 * kein Erfinden.
 */
export function groupCompareCatalog(catalog: CompareSelectionEntry[]): CompareAggregationGroup[] {
	const groups: CompareAggregationGroup[] = [];
	const byMetricId = new Map<string, CompareAggregationGroup>();

	for (const entry of catalog) {
		const metricId = entry.metric_id ?? entry.metric;
		let group = byMetricId.get(metricId);
		if (!group) {
			group = { metric_id: metricId, label: entry.label, options: [] };
			byMetricId.set(metricId, group);
			groups.push(group);
		}
		group.options.push({
			key: entry.metric,
			aggregation: entry.aggregation ?? '',
			aggregation_label: entry.aggregation_label ?? ''
		});
	}

	return groups;
}
