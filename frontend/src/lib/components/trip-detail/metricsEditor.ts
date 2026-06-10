// Epic #138 Phase 2 — Metriken-Editor Hilfsmodul (Issues #174–178).
// Spec: docs/specs/modules/epic_138_174_178_metriken_ui.md
//
// Reine Funktionen ohne Svelte-Abhaengigkeit, damit sie via node:test
// unit-getestet werden koennen (siehe metricsEditor.test.ts).

// Issue #435 — Single Source of Truth in $lib/types.ts (Adversary F002).
import type { MetricEntry } from '$lib/types';
export type { MetricEntry };

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

export const CATEGORY_LABELS: Record<string, string> = {
	temperature: 'Temperatur',
	wind: 'Wind',
	precipitation: 'Niederschlag',
	atmosphere: 'Atmosphäre',
	winter: 'Winter / Schnee',
};

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

// =============================================================================
// Issue #364 (Schritt B von #361) — Bucket-Editor-Logik (AC-1..AC-8)
// =============================================================================
//
// Spec: docs/specs/modules/issue_364_metrics_editor_buckets.md
// Design: docs/design/epic_331_output_layout/screen-metrics-editor.jsx

export interface Buckets {
	primary: string[];
	secondary: string[];
	off: string[];
}

export type Horizons = { today: boolean; tomorrow: boolean; day_after: boolean };
const HORIZONS_ALL: Horizons = { today: true, tomorrow: true, day_after: true };

// Metrik mit bucket/order — Round-Trip-Shape fuer PUT /weather-config.
export interface BucketWeatherConfigMetric {
	metric_id: string;
	enabled: boolean;
	use_friendly_format: boolean;
	horizons: Horizons;
	bucket?: 'primary' | 'secondary';
	order: number;
}

/**
 * Heuristik-Prioritaet — KONSISTENT mit Backend #360
 * (src/output/renderers/channel_layout.py::METRIC_PRIORITY). Hoeher = wichtiger.
 * Die 5 wichtigsten landen via autoAssign im primary-Bucket (Signal-safe).
 */
export const METRIC_PRIORITY: Record<string, number> = {
	temperature: 95, wind: 90, gust: 88, rain_probability: 85,
	precipitation: 78, wind_chill: 70, cloud_total: 65, thunder: 60,
	fresh_snow: 55, visibility: 55, freezing_level: 50, uv_index: 45,
	wind_direction: 40, snow_depth: 35, precip_type: 35, snowfall_limit: 35,
	cloud_low: 30, humidity: 25, sunshine: 25, dewpoint: 20,
	pressure: 18, cape: 15, cloud_mid: 12, cloud_high: 10,
};

// Anzahl Metriken, die autoAssign als primary markiert (= Signal-Budget,
// Uhrzeit nicht mitgezaehlt). Deckt sich mit Backend _PRIMARY_SLOTS = 5.
const PRIMARY_SLOTS = 5;

/**
 * Waehlbare Metrik-Spalten je Kanal (Uhrzeit NICHT mitgezaehlt).
 * Telegram-Budget = 8 (#587: Signal entfernt, Budget von 7→8 angehoben).
 * Signal entfernt (#610). Anzeige-Budget, KEIN hartes Limit.
 */
export const CHANNEL_COL_BUDGET: Record<'email' | 'telegram' | 'sms', number> = {
	email: Infinity,
	telegram: 8,
	sms: 0,
};

/**
 * AC-7 / #587: Verlustfreie Migration des alten Bucket-Modells (primary/secondary/off)
 * in eine geordnete Spaltenliste. primary zuerst, dann secondary, off weggelassen.
 * Dubletten werden entfernt (erstes Vorkommen behalten).
 */
export function bucketsToColumns(buckets: { primary: string[]; secondary: string[]; off: string[] }): string[] {
	const seen = new Set<string>();
	const result: string[] = [];
	for (const id of [...buckets.primary, ...buckets.secondary]) {
		if (!seen.has(id)) {
			seen.add(id);
			result.push(id);
		}
	}
	return result;
}

/** Flache Liste aller Katalog-IDs (Insertion-Order der Kategorien). */
function allCatalogIds(catalog: MetricCatalog): string[] {
	const ids: string[] = [];
	for (const metrics of Object.values(catalog)) {
		for (const m of metrics) ids.push(m.id);
	}
	return ids;
}

/**
 * AC-1 / AC-8: Verteilt aktive Metrik-IDs auf primary/secondary/off.
 *
 * Top-5 nach METRIC_PRIORITY -> primary (in Prioritaets-Reihenfolge), Rest der
 * aktiven -> secondary, im Katalog vorhandene aber nicht aktive -> off.
 * Stabil: bei gleicher Prioritaet entscheidet die Eingabe-Reihenfolge.
 * Konsistent mit Backend auto_distribute (5 in primary, Signal-safe).
 */
export function autoAssign(activeIds: string[], catalog: MetricCatalog): Buckets {
	// F002-Härtung: doppelte IDs entfernen (erste Vorkommen behalten), damit
	// eine Metrik nie zweimal in primary/secondary landet.
	const uniqueIds = [...new Set(activeIds)];

	const ranked = uniqueIds
		.map((id, idx) => ({ id, idx, prio: METRIC_PRIORITY[id] ?? 0 }))
		.sort((a, b) => (b.prio - a.prio) || (a.idx - b.idx))
		.map((x) => x.id);

	const primary = ranked.slice(0, PRIMARY_SLOTS);
	const secondary = ranked.slice(PRIMARY_SLOTS);

	const activeSet = new Set(uniqueIds);
	const off = allCatalogIds(catalog).filter((id) => !activeSet.has(id));

	return { primary, secondary, off };
}

/**
 * AC-2 / AC-6: Verschiebt eine Metrik zwischen Buckets (immutabel).
 * Entfernt aus `from`, haengt an `to` an. Andere Buckets unveraendert.
 *
 * F001-Härtung: Liegt `id` nicht in `b[from]`, ist der Aufruf ein No-Op
 * (Shallow-Copy) — keine Phantom-ID darf in `to` auftauchen.
 */
export function move(b: Buckets, id: string, from: keyof Buckets, to: keyof Buckets): Buckets {
	if (!b[from].includes(id)) return { ...b };
	const next: Buckets = {
		primary: [...b.primary],
		secondary: [...b.secondary],
		off: [...b.off],
	};
	next[from] = next[from].filter((x) => x !== id);
	if (!next[to].includes(id)) next[to] = [...next[to], id];
	return next;
}

/**
 * AC-3: Vertauscht eine Metrik mit ihrem Nachbarn (dir=-1 hoch, dir=+1 runter).
 * An den Raendern No-Op (gibt das unveraenderte Objekt zurueck).
 */
export function reorder(b: Buckets, bucket: keyof Buckets, id: string, dir: -1 | 1): Buckets {
	const list = [...b[bucket]];
	const idx = list.indexOf(id);
	if (idx === -1) return b;
	const target = idx + dir;
	if (target < 0 || target >= list.length) return b;
	[list[idx], list[target]] = [list[target], list[idx]];
	return { ...b, [bucket]: list };
}

/**
 * AC-5: Liefert je Kanal, ob die primary-Spaltenzahl das Budget ueberschreitet.
 * `> budget` (nicht `>=`) — exakt am Budget ist noch ok. Signal entfernt (#610).
 */
export function channelOverflow(
	primaryCount: number,
): { email: boolean; telegram: boolean; sms: boolean } {
	return {
		email: primaryCount > CHANNEL_COL_BUDGET.email,
		telegram: primaryCount > CHANNEL_COL_BUDGET.telegram,
		sms: primaryCount > CHANNEL_COL_BUDGET.sms,
	};
}

/**
 * AC-7 / AC-4: Baut die display_config.metrics-Liste fuer den Save.
 *
 * - primary/secondary -> enabled:true mit bucket + lueckenlosem order (0..n-1
 *   je Bucket).
 * - off -> enabled:false, bucket weggelassen, order 0.
 * - use_friendly_format aus friendlyMap (Default true), horizons aus
 *   horizonsMap (Default HORIZONS_ALL).
 *
 * Reihenfolge der Ausgabe folgt der Katalog-Reihenfolge, damit kein Metrik
 * verloren geht (alle Katalog-IDs erscheinen genau einmal).
 */
export function buildWeatherConfigMetrics(
	buckets: Buckets,
	friendlyMap: Record<string, boolean>,
	horizonsMap: Record<string, Horizons>,
	catalog: MetricCatalog,
): BucketWeatherConfigMetric[] {
	const orderOf: Record<string, number> = {};
	const bucketOf: Record<string, 'primary' | 'secondary'> = {};
	buckets.primary.forEach((id, i) => { orderOf[id] = i; bucketOf[id] = 'primary'; });
	buckets.secondary.forEach((id, i) => { orderOf[id] = i; bucketOf[id] = 'secondary'; });

	const seen = new Set<string>();
	const out: BucketWeatherConfigMetric[] = [];

	const emit = (id: string) => {
		if (seen.has(id)) return;
		seen.add(id);
		const bucket = bucketOf[id];
		out.push({
			metric_id: id,
			enabled: bucket !== undefined,
			use_friendly_format: friendlyMap[id] ?? true,
			horizons: horizonsMap[id] ?? { ...HORIZONS_ALL },
			...(bucket ? { bucket } : {}),
			order: orderOf[id] ?? 0,
		});
	};

	// Erst alle Katalog-Metriken in Katalog-Reihenfolge, dann etwaige
	// Bucket-IDs die (noch) nicht im Katalog stehen.
	for (const id of allCatalogIds(catalog)) emit(id);
	for (const id of [...buckets.primary, ...buckets.secondary, ...buckets.off]) emit(id);

	return out;
}

// =============================================================================
// Issue #365 (Schritt C von #361) — 4-Kanal-Live-Vorschau (AC-1..AC-4)
// =============================================================================
//
// Spec: docs/specs/modules/issue_365_channel_preview_mobile.md
// Design: docs/design/epic_331_output_layout/screen-metrics-editor.jsx (Z. 555-667)

export interface ChannelLayout {
	inTable: string[];
	detail: string[];
	demoted: number;
}

/**
 * AC-1..AC-3: Wendet das Spalten-Budget eines Kanals auf eine Bucket-Auswahl an.
 * Deckt sich mit Backend render_for_channel (#360):
 * - budget === Infinity (Email): alles als Spalte, kein Demote.
 * - budget === 0 (SMS): keine Tabelle, alles flach in detail, demoted == |primary|.
 * - sonst (Telegram 7): inTable gekappt; überzählige primary vorne
 *   in detail (vor secondary), demoted == overflow.
 */
export function applyChannel(
	primary: string[],
	secondary: string[],
	budget: number,
): ChannelLayout {
	if (budget === 0) {
		return { inTable: [], detail: [...primary, ...secondary], demoted: primary.length };
	}
	// F001-Sauberkeit: Email-Pfad gibt eine KOPIE von primary zurück (kein Alias).
	const inTable = budget === Infinity ? [...primary] : primary.slice(0, budget);
	const overflow = budget === Infinity ? [] : primary.slice(budget);
	return { inTable, detail: [...overflow, ...secondary], demoted: overflow.length };
}

export interface BucketSummary {
	spalten: number;
	detail: number;
	skala: number;
}

/**
 * AC-4: Bucket-bewusste Preset-Zusammenfassung für den SavePresetDialog.
 * - spalten: |primary|
 * - detail:  |secondary|
 * - skala:   aktive (primary+secondary) Metriken mit friendlyMap[id]===true.
 *            off-Metriken zählen NICHT.
 */

// =============================================================================
// Issue #587 AC-2 — diffHighlight (Diff-Aufleuchten)
// =============================================================================

export type HighlightKind = 'added' | 'removed' | 'moved' | 'mode' | 'preset';

export interface Highlight {
	id: string | null;
	kind: HighlightKind;
}

export interface WeatherSnapshot {
	columns: string[];
	mode: Record<string, 'raw' | 'indicator'>;
	presetId: string;
}

/**
 * Vergleicht zwei WeatherSnapshot-Objekte und liefert eine Highlight-Beschreibung
 * der ersten relevanten Änderung zurück.
 *
 * Präzedenz (oben = höher):
 * 1. presetId≠ UND Spaltenmenge unterschiedlich → { id:null, kind:'preset' }
 * 2. genau eine neue id → { id, kind:'added' }
 * 3. genau eine entfernte id → { id, kind:'removed' }
 * 4. gleiche Menge, andere Reihenfolge → { id:<erste verschobene>, kind:'moved' }
 * 5. gleiche Spalten, ein mode[id] unterschiedlich → { id, kind:'mode' }
 * 6. sonst → null
 */
export function diffHighlight(prev: WeatherSnapshot, next: WeatherSnapshot): Highlight | null {
	// F001-Härtung: Duplikate in columns entfernen (erstes Vorkommen behalten),
	// damit der moved-Vergleich keine Phantom-Ergebnisse durch undefined liefert.
	const dedupCols = (cols: string[]) => [...new Set(cols)];
	const prevCols = dedupCols(prev.columns);
	const nextCols = dedupCols(next.columns);

	const prevSet = new Set(prevCols);
	const nextSet = new Set(nextCols);

	// Regel 1: preset gewechselt + Spaltenmenge geändert
	if (prev.presetId !== next.presetId) {
		const setsEqual = prevSet.size === nextSet.size && [...prevSet].every((id) => nextSet.has(id));
		if (!setsEqual) {
			return { id: null, kind: 'preset' };
		}
	}

	// Diff der Mengen
	const added = nextCols.filter((id) => !prevSet.has(id));
	const removed = prevCols.filter((id) => !nextSet.has(id));

	// Regel 2: genau eine Spalte hinzugefügt
	if (added.length === 1 && removed.length === 0) {
		return { id: added[0], kind: 'added' };
	}

	// Regel 3: genau eine Spalte entfernt
	if (removed.length === 1 && added.length === 0) {
		return { id: removed[0], kind: 'removed' };
	}

	// Regel 4: gleiche Menge, andere Reihenfolge
	if (added.length === 0 && removed.length === 0) {
		for (let i = 0; i < prevCols.length; i++) {
			if (prevCols[i] !== nextCols[i]) {
				return { id: prevCols[i], kind: 'moved' };
			}
		}

		// Regel 5: gleiche Spalten + gleiche Reihenfolge, aber ein mode geändert
		const allIds = prevCols;
		for (const id of allIds) {
			const prevMode = prev.mode[id] ?? 'raw';
			const nextMode = next.mode[id] ?? 'raw';
			if (prevMode !== nextMode) {
				return { id, kind: 'mode' };
			}
		}
	}

	return null;
}

export function buildBucketSummary(
	buckets: Buckets,
	friendlyMap: Record<string, boolean>,
): BucketSummary {
	const active = [...buckets.primary, ...buckets.secondary];
	const skala = active.filter((id) => friendlyMap[id] === true).length;
	return { spalten: buckets.primary.length, detail: buckets.secondary.length, skala };
}
