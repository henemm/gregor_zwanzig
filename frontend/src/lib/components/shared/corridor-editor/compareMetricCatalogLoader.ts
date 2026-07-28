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
// Issue #1373 (S2 Scheibe B): dieselbe Antwort liefert auch die Auswahllisten-
// Form samt Herkunftsfeldern (metric_id/aggregation) — eine Anfrage, zwei
// Ableitungen, kein zweiter Fetch.
import {
	toCompareSelectionEntries,
	type CompareSelectionEntry
} from '../weather-metrics-tab/compareMetricSelection.ts';

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
			// Issue #1401 (A1): Auswertung als eigenes Element neben dem Namen —
			// nur wenn die Antwort sie traegt (keine erfundenen undefined-Schluessel).
			...(entry.aggregation_label !== undefined
				? { aggregationLabel: entry.aggregation_label }
				: {}),
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
//
// Issue #1373 (S2 Scheibe B, Fix-Runde 1): gecacht wird jetzt die ROHE Antwort,
// nicht das abgeleitete CompareMetricDef[] — damit teilen sich ALLE drei
// Verbraucher (Schwellen-Editor, Auswahlliste im Wetter-Metriken-Reiter,
// Hub-Hydration der Metrik-Auswahl) EINE Anfrage pro Seiten-Load.
let cachedResponse: Promise<CompareMetricCatalogResponse> | null = null;

function fetchCompareMetricCatalogOnce(): Promise<CompareMetricCatalogResponse> {
	if (!cachedResponse) {
		cachedResponse = api
			.get<CompareMetricCatalogResponse>('/api/compare/metrics')
			.catch((e: unknown) => {
				cachedResponse = null;
				throw e;
			});
	}
	return cachedResponse;
}

export function loadCompareMetricCatalog(): Promise<CompareMetricDef[]> {
	return fetchCompareMetricCatalogOnce().then(buildCompareMetricDefs);
}

/**
 * Issue #1373 (S2 Scheibe B): dieselbe Antwort in der Auswahllisten-Form
 * (`{metric, label, metric_id, aggregation}`). `toCompareSelectionEntries()`
 * füllt dabei den Umkehr-Index Auswahl-Schlüssel <-> Größe+Auswertung, der das
 * Lesen UND Schreiben von `display_config.active_metrics` übersetzt.
 *
 * Wird von der Hub-Hydration (CompareTabs.svelte) VOR dem Setzen des
 * Dirty-Check-Grundzustands abgewartet: sonst stünde im Grundzustand die noch
 * unaufgelöste Rohform, jede Nutzergeste erzeugte einen Scheindiff, und ein
 * fehlgeschlagenes Speichern setzte die Auswahl auf die Rohform zurück
 * (Adversary-Befund F001 der Fix-Runde 1).
 */
export function loadCompareSelectionEntries(): Promise<CompareSelectionEntry[]> {
	return fetchCompareMetricCatalogOnce().then(toCompareSelectionEntries);
}
