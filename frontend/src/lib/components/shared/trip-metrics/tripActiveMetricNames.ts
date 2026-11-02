// Feature #1435 Etappe E3a — geteilte Drei-Zustands-Namensauflösung für den
// neuen Wetter-Metriken-Block im Übersichts-Reiter einer Trip.
// Spec: docs/specs/modules/feat_1435_e3a_uebersicht_wetter_block.md
// Implementation Details Punkt 1, Acceptance Criteria AC-1/AC-2/AC-3/AC-8/AC-11.
//
// Liegt bewusst unter shared/ (nicht trip-detail/) — die Teilungs-Invariante
// (CLAUDE.md, "möglichst viel Code zwischen Trip und Ortsvergleich teilen")
// verlangt, dass die Namensauflösung als geteilter Baustein angelegt wird,
// auch wenn heute nur der Trip-Kontext sie aufruft (AC-9). Analoge Bauart:
// shared/alarme-tab/activeAlertMetricsFromCatalog.ts (E1a-2).
//
// AC-8-Ratsche: keine lokale Metrik-ID→Name-Tabelle, keine hartkodierte
// Standard-Metrik-Liste — jeder Name kommt ausschließlich aus dem
// übergebenen `catalog`-Parameter.

import { selectTableColumns, type MetricCatalog } from '../../trip-detail/metricsEditor.ts';
import type { WeatherConfigMetric } from '$lib/types';
import { get } from 'svelte/store';
import { locale } from '../../../i18n/index.ts';
import { metricLabel } from '../../../i18n/metricLabel.ts';

export type TripMetricsOverviewState =
	| { kind: 'selected'; names: string[]; unknownCount: number }
	| { kind: 'altbestand' }
	| { kind: 'empty' };

/**
 * Drei Zustände, in dieser Reihenfolge geprüft:
 *
 * 1. `metrics` fehlt oder ist leer -> 'altbestand' (spiegelt exakt
 *    `trip_report.py:119`s `len(dc.metrics) == 0`-Bedingung — NICHT die
 *    DEFAULT_TRIP_METRIC_IDS-Liste selbst, s. Known Limitations der Spec).
 * 2. Einträge vorhanden, aber keiner `enabled === true` -> 'empty'
 *    (bewusste Leerauswahl, unterscheidbar vom Altbestand).
 * 3. sonst -> 'selected': Namen in Register-Reihenfolge (über
 *    `selectTableColumns`, keine neue Sortierlogik), plus `unknownCount` für
 *    aktivierte Kennungen, die der Katalog nicht (mehr) kennt (AC-11) —
 *    diese verschwinden nicht still, ihre rohe Kennung erscheint aber nie
 *    in `names`.
 */
export function resolveTripMetricsOverviewState(
	metrics: WeatherConfigMetric[] | undefined,
	catalog: MetricCatalog
): TripMetricsOverviewState {
	if (!metrics || metrics.length === 0) {
		return { kind: 'altbestand' };
	}

	const enabledMap: Record<string, boolean> = {};
	for (const m of metrics) enabledMap[m.metric_id] = m.enabled === true;

	const enabledIds = Object.keys(enabledMap).filter((id) => enabledMap[id]);
	if (enabledIds.length === 0) {
		return { kind: 'empty' };
	}

	const knownIds = new Set<string>();
	for (const entries of Object.values(catalog)) {
		for (const entry of entries) knownIds.add(entry.id);
	}
	const unknownCount = enabledIds.filter((id) => !knownIds.has(id)).length;

	// Issue #2654 (i18n F5): voller Name in der aktuellen Sprache aus dem Register
	// (label_en, sonst deutsch) — weiterhin keine lokale Metrik-ID→Name-Tabelle.
	const lang = get(locale);
	const names = selectTableColumns(catalog, enabledMap).map((entry) => metricLabel(entry, lang));
	return { kind: 'selected', names, unknownCount };
}
