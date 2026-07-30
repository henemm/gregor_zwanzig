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
import {
	_COMPARE_DEFAULTS,
	ROUTE_CORRIDOR_CATALOG_IDS,
	type CompareMetricDef,
	type RouteMetricDef
} from './corridorEditorState.ts';
// Issue #1373 (S2 Scheibe B): dieselbe Antwort liefert auch die Auswahllisten-
// Form samt Herkunftsfeldern (metric_id/aggregation) — eine Anfrage, zwei
// Ableitungen, kein zweiter Fetch.
import {
	toCompareSelectionEntries,
	type CompareSelectionEntry
} from '../weather-metrics-tab/compareMetricSelection.ts';

// Issue #1424 (M2, PO-Entscheidung 2026-07-30): diese zwei Groessen taugen
// nicht als Von/Bis-Bereich und werden im Wertebereichs-Angebot nicht mehr
// gefuehrt — precip_type_dominant ist ein Enum (RAIN/SNOW/MIXED/
// FREEZING_RAIN) ohne Zahlenskala, wind_direction_deg ist zyklisch (0-360°,
// "von 350° bis 10°" ist mit einem Von/Bis-Paar nicht ausdrueckbar). Beide
// bleiben normale Wettergroessen im Reiter Wetter-Metriken —
// COMPARE_METRIC_KEYS (corridorEditorState.ts) und der Katalog-Endpoint sind
// unveraendert. Die Entfernung sitzt bewusst NUR hier (einziger Ort, an dem
// Katalog-Eintraege zu Editor-Definitionen werden).
const _COMPARE_RANGE_UNSUPPORTED = new Set(['precip_type_dominant', 'wind_direction_deg']);

/**
 * Reiner, testbarer Mapper: Endpoint-Eintrag -> CompareMetricDef. `kind`
 * (Plattdrücken von 'enum' auf 'range', wie heute — precip_type_dominant
 * bleibt ein generischer Zahlen-Slider, Scale [0,100], keine abweichende
 * Editor-Darstellung). `defaultMin`/`defaultMax` kommen aus der duennen
 * FE-UX-Tabelle `_COMPARE_DEFAULTS` (D1 Hybrid), nicht aus dem Endpoint.
 */
export function buildCompareMetricDefs(response: CompareMetricCatalogResponse): CompareMetricDef[] {
	return (response.metrics ?? [])
		.filter((entry: CompareMetricCatalogEntry) => !_COMPARE_RANGE_UNSUPPORTED.has(entry.key))
		.map((entry: CompareMetricCatalogEntry) => {
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

// ════════════════════════════════════════════════════════════════════════
// Issue #1425 (Schritt 2, Teil 1): derselbe Katalog speist jetzt auch den
// Trip-Reiter "Wertebereiche" (context="route"). Spec:
// docs/specs/modules/fix_1425_s2_corridor_pool.md.
// ════════════════════════════════════════════════════════════════════════

// Die SCHLUESSEL der Namensraum-Bruecke sind exakt die Katalog-IDs, die die
// fest verdrahteten ROUTE_METRIC_DEFS bereits abdecken (gust, precipitation,
// temperature, thunder, snowfall_limit, freezing_level). Abgeleitet statt
// dupliziert — sonst driftet die Liste beim naechsten Bruecken-Eintrag.
// "thunder" faellt dadurch automatisch mit heraus: die Gewitter-Skala bleibt
// die alte Prozent-Definition, die Ordinal-Vereinheitlichung ist ein
// separater Folge-Workflow (AC-3).
const _ROUTE_COVERED_METRIC_IDS = new Set(Object.keys(ROUTE_CORRIDOR_CATALOG_IDS));

/**
 * Reiner, testbarer Mapper: Katalog-Eintraege -> die ZUSAETZLICHEN
 * Trip-Wertebereichs-Definitionen (RouteMetricDef), also alles ausser
 *  - was die alten 6 ROUTE_METRIC_DEFS ueber `metric_id` schon abdecken (AC-2/AC-3),
 *  - was als Von/Bis-Bereich nicht darstellbar ist (_COMPARE_RANGE_UNSUPPORTED).
 *
 * Katalog-Reihenfolge bleibt erhalten (keine eigene Sortierung).
 * `defaultMin`/`defaultMax` kommen aus derselben `_COMPARE_DEFAULTS`-Tabelle
 * wie im Ortsvergleich — verhindert strukturell den #1424-Fehler (beidseitig
 * offene Zeile blockt validateCorridorRows direkt nach dem Hinzufuegen).
 */
export function buildRouteMetricDefsFromCatalog(
	entries: CompareMetricCatalogEntry[]
): RouteMetricDef[] {
	return (entries ?? [])
		.filter((entry: CompareMetricCatalogEntry) =>
			!_ROUTE_COVERED_METRIC_IDS.has(entry.metric_id ?? '')
			&& !_COMPARE_RANGE_UNSUPPORTED.has(entry.key))
		.map((entry: CompareMetricCatalogEntry) => {
			const defaults = _COMPARE_DEFAULTS[entry.key] ?? { defaultMin: null, defaultMax: null };
			return {
				metric: entry.key,
				label: entry.label,
				unit: entry.unit ?? '',
				scale: [entry.rangeMin ?? 0, entry.rangeMax ?? 100] as [number, number],
				step: entry.step ?? 1,
				defaultMin: defaults.defaultMin,
				defaultMax: defaults.defaultMax,
			};
		});
}

/** Katalog laden (geteilter Promise-Cache, kein zweiter Request) und als
 *  Zusatz-Definitionen fuer buildRoutePool(..., extraDefs) abbilden. */
export function loadRouteExtraMetricDefs(): Promise<RouteMetricDef[]> {
	return fetchCompareMetricCatalogOnce().then((r) =>
		buildRouteMetricDefsFromCatalog(r.metrics ?? [])
	);
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
