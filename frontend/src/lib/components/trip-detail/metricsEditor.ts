// Epic #138 Phase 2 — Metriken-Editor Hilfsmodul (Issues #174–178).
// Spec: docs/specs/modules/epic_138_174_178_metriken_ui.md
//
// Reine Funktionen ohne Svelte-Abhaengigkeit, damit sie via node:test
// unit-getestet werden koennen (siehe metricsEditor.test.ts).

export interface MetricEntry {
	id: string;
	label: string;
	unit: string;
	category: string;
	default_enabled: boolean;
	has_friendly_format: boolean;
}

export type MetricCatalog = Record<string, MetricEntry[]>;

// =============================================================================
// §4 INDICATOR_MAP (#175) — 12 Metriken
// =============================================================================
//
// 9 backend-eligible (has_friendly_format=true im Backend-Katalog)
// + 3 frontend-erweitert (wind, gust, rain_probability).
//
// Hinweis: wind/gust/rain_probability haben has_friendly_format=false im
// Backend — der Python-Formatter ignoriert use_friendly_format=true fuer
// diese IDs stillschweigend und gibt Rohwerte aus. Der INDICATOR_MAP steuert
// nur die Frontend-UI, nicht den Formatter (siehe Spec §4 / Known Limitations).
export const INDICATOR_MAP: Record<string, string> = {
	// 9 backend-eligible
	wind_direction:   'N / O / S / W',
	thunder:          'keins / mittel / hoch / extrem',
	cape:             'niedrig / mittel / hoch / extrem',
	cloud_total:      'klar / teilw. / bewölkt / bedeckt',
	cloud_low:        'klar / teilw. / bewölkt / bedeckt',
	cloud_mid:        'klar / teilw. / bewölkt / bedeckt',
	cloud_high:       'klar / teilw. / bewölkt / bedeckt',
	visibility:       'gut / eingeschränkt / schlecht / sehr schlecht',
	sunshine:         'hell / wechselhaft / bedeckt',
	// 3 frontend-erweitert
	wind:             'ruhig / mäßig / stark / sturm',
	gust:             'harmlos / mäßig / stark / orkan',
	rain_probability: 'niedrig / mittel / hoch / sehr hoch',
};

// Kategorie-Reihenfolge fuer Tabellen-Vorschau (Spec §5 + AC-5).
export const CATEGORY_ORDER: readonly string[] = [
	'temperature',
	'wind',
	'precipitation',
	'atmosphere',
	'winter',
];

/**
 * Liefert true, wenn die Metrik einen Roh/Indikator-Toggle bekommt.
 * Wrapper ueber INDICATOR_MAP — siehe Spec §4.
 */
export function indicatorCapable(id: string): boolean {
	return id in INDICATOR_MAP;
}

// =============================================================================
// dirty-State (#178, Spec §1) — AC-1, AC-2
// =============================================================================

/**
 * Serialisiert enabledMap + friendlyMap als stabilen JSON-String.
 * Wird als savedSnapshot persistiert und mit dem aktuellen Zustand verglichen.
 */
export function buildDirtySnapshot(
	enabledMap: Record<string, boolean>,
	friendlyMap: Record<string, boolean>,
): string {
	return JSON.stringify({ enabledMap, friendlyMap });
}

/**
 * Liefert true, wenn enabledMap oder friendlyMap vom gespeicherten Snapshot abweichen.
 */
export function isDirty(
	enabledMap: Record<string, boolean>,
	friendlyMap: Record<string, boolean>,
	snapshot: string,
): boolean {
	return buildDirtySnapshot(enabledMap, friendlyMap) !== snapshot;
}

// =============================================================================
// MetricGroup-Zaehler (#174, Spec §2) — AC-3, AC-8
// =============================================================================

/**
 * Zaehlt aktivierte Metriken in einer Kategorie. Fehlende enabledMap-Eintraege
 * werden als false interpretiert.
 */
export function countActiveInCategory(
	metricIds: string[],
	enabledMap: Record<string, boolean>,
): number {
	let count = 0;
	for (const id of metricIds) {
		if (enabledMap[id] === true) count++;
	}
	return count;
}

// =============================================================================
// SavePresetDialog-Zusammenfassung (#177, Spec §6) — AC-6
// =============================================================================

export interface PresetSummary {
	activeCount: number;
	rawCount: number;
	indicatorCount: number;
}

/**
 * Liefert die Zaehler fuer die Dialog-Zusammenfassung.
 *
 * - activeCount: alle Metriken mit enabledMap[id]=true
 * - rawCount: indicatorCapable + enabled + friendlyMap[id]===false (Rohwert-Modus)
 * - indicatorCount: indicatorCapable + enabled + friendlyMap[id]===true (Indikator-Modus)
 *
 * Metriken ohne indicatorCapable zaehlen NUR in activeCount, weder bei
 * rawCount noch indicatorCount.
 */
export function buildPresetSummary(
	enabledMap: Record<string, boolean>,
	friendlyMap: Record<string, boolean>,
): PresetSummary {
	let activeCount = 0;
	let rawCount = 0;
	let indicatorCount = 0;
	for (const [id, enabled] of Object.entries(enabledMap)) {
		if (!enabled) continue;
		activeCount++;
		if (!indicatorCapable(id)) continue;
		if (friendlyMap[id] === true) {
			indicatorCount++;
		} else if (friendlyMap[id] === false) {
			rawCount++;
		}
	}
	return { activeCount, rawCount, indicatorCount };
}

// =============================================================================
// TablePreview-Spaltenauswahl (#176, Spec §5) — AC-5
// =============================================================================

/**
 * Liefert alle aktivierten Metriken in CATEGORY_ORDER-Reihenfolge.
 * Kategorien ausserhalb von CATEGORY_ORDER werden hinten alphabetisch
 * (Insertion-Order von Object.keys) angehaengt.
 */
export function selectTableColumns(
	catalog: MetricCatalog,
	enabledMap: Record<string, boolean>,
): MetricEntry[] {
	const knownCats = Object.keys(catalog);
	const ordered = CATEGORY_ORDER.filter((c) => knownCats.includes(c)).concat(
		knownCats.filter((c) => !CATEGORY_ORDER.includes(c)),
	);
	const cols: MetricEntry[] = [];
	for (const cat of ordered) {
		for (const m of catalog[cat] ?? []) {
			if (enabledMap[m.id] === true) cols.push(m);
		}
	}
	return cols;
}
