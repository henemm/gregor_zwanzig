// Issue #1350 Teil 3: geteilter Katalog-Loader fuer den Schwellen-Editor des
// Ortsvergleichs (CorridorEditor/CorridorEditorMobile, context="vergleich").
// Baut CompareMetricDef[] aus GET /api/compare/metrics (SSoT, Teil 1, live
// seit a824a6cc) statt aus dem geloeschten Frontend-Import
// compareMetricDefs.ts::ALL_METRICS.
//
// Spec: docs/specs/modules/compare_metric_ssot_final.md § Implementation
// Details Punkt 2, AC-1, AC-2.
//
// Vorbild-Mapper: weather-metrics-tab/compareMetricSelection.ts (Teil 2) —
// dieser Mapper ist vollstaendiger (CompareMetricDef statt nur {metric,label}).

import { api } from '$lib/api';
import type { CompareMetricCatalogEntry, CompareMetricCatalogResponse } from '$lib/types';
import { _COMPARE_DEFAULTS, type CompareMetricDef } from './corridorEditorState.ts';

/**
 * Reiner, testbarer Mapper: Endpoint-Eintrag -> CompareMetricDef. `kind`
 * (Plattdrücken von 'enum' auf 'range', wie heute — precip_type_dominant
 * bleibt ein generischer Zahlen-Slider, Scale [0,100], keine abweichende
 * Editor-Darstellung). `defaultMin`/`defaultMax` kommen aus der duennen
 * FE-UX-Tabelle `_COMPARE_DEFAULTS` (D1 Hybrid), nicht aus dem Endpoint.
 */
export function buildCompareMetricDefs(response: CompareMetricCatalogResponse): CompareMetricDef[] {
	return (response.metrics ?? []).map((entry: CompareMetricCatalogEntry) => {
		const kind: 'range' | 'ordinal' = entry.kind === 'ordinal' ? 'ordinal' : 'range';
		const scale: [number, number] = kind === 'ordinal'
			? [0, (entry.ordinalLabels?.length ?? 1) - 1]
			: [entry.rangeMin ?? 0, entry.rangeMax ?? 100];
		const defaults = _COMPARE_DEFAULTS[entry.key] ?? { defaultMin: null, defaultMax: null };
		return {
			metric: entry.key,
			label: entry.label,
			unit: entry.unit ?? '',
			scale,
			step: entry.step ?? 1,
			kind,
			ordinalLabels: entry.ordinalLabels,
			defaultMin: defaults.defaultMin,
			defaultMax: defaults.defaultMax,
			alarmCapable: entry.alarmCapable ?? false,
		};
	});
}

// Modul-weiter Promise-Cache (einmal pro Seiten-Load, nicht pro Komponenten-
// Instanz) — verhindert Doppel-Fetch, falls WeatherMetricsTab (Teil 2) und
// CorridorEditor im selben Seiten-Load beide fetchen. Ein Fehler invalidiert
// den Cache (naechster Aufruf fetcht erneut, kein dauerhaft gecachter
// Fehlerzustand).
let cachedCatalog: Promise<CompareMetricDef[]> | null = null;

export function loadCompareMetricCatalog(): Promise<CompareMetricDef[]> {
	if (!cachedCatalog) {
		cachedCatalog = api
			.get<CompareMetricCatalogResponse>('/api/compare/metrics')
			.then(buildCompareMetricDefs)
			.catch((e: unknown) => {
				cachedCatalog = null;
				throw e;
			});
	}
	return cachedCatalog;
}
