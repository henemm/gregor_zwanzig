// Issue #1350 Teil 2: Compare-Metrik-Auswahlliste bezieht ihre Einträge aus
// GET /api/compare/metrics (Teil 1, live seit a824a6cc) statt aus dem
// statischen Frontend-Import COMPARE_METRIC_DEFS.
// Spec: docs/specs/modules/compare_metric_selection_source.md § AC-1, AC-2
import type { CompareMetricCatalogEntry } from '$lib/types';

export interface CompareSelectionEntry {
	metric: string;
	label: string;
	// Issue #1373 (S2 Scheibe A): Herkunft aus dem zentralen Wetterkatalog,
	// unveraendert durchgereicht. Nur vorhanden, wenn der Endpoint sie liefert.
	metric_id?: string;
	aggregation?: string;
	// Issue #1401 (A1): Auswertung als eigenes Anzeige-Element neben dem Namen.
	aggregation_label?: string;
	// Issue #1435 (E1a-2): Alarm-Identitaet aus dem zentralen Register (`null` =
	// nicht alarmfaehig) — Quelle der Alarm-Zeilen im Alarme-Reiter.
	alertMetric?: string | null;
	// Issue #1453 (AC-7): englische Fachkurzform und SMS-Kuerzel derselben
	// Groesse, unveraendert aus der Katalogantwort durchgereicht.
	col_label?: string;
	sms_code?: string;
	// Issue #1406 Scheibe B: Stundenverlauf-Angaben, unveraendert aus der
	// Katalogantwort durchgereicht (s. types.ts CompareMetricCatalogEntry).
	hourlySelectable?: boolean;
	hourlyNotSelectableReason?: string;
	hourlyDefault?: boolean;
	hourlyMergeOnly?: boolean;
	hourly_legacy_keys?: string[];
	// Issue #1911: Ordinal-Beschriftungen (z.B. Gewitter "kein"/"leicht"/
	// "mittel"/"hoch"), unveraendert aus der Katalogantwort durchgereicht.
	ordinalLabels?: string[];
}

/**
 * Mappt die Antwort von GET /api/compare/metrics auf die Auswahllisten-Form
 * (key -> metric, label -> label), Reihenfolge unveraendert. Fehlendes/leeres
 * `metrics` -> [] (kein Crash, kein still leerer Fehlerpfad im Aufrufer).
 *
 * `metric_id`/`aggregation` (#1373) werden NUR ergaenzt, wenn der Eintrag sie
 * traegt — keine erfundenen `undefined`-Schluessel, sonst bricht der strikte
 * deepEqual-Vergleich aus #1350 (AC-2).
 */
export function toCompareSelectionEntries(
	response: { metrics: CompareMetricCatalogEntry[] }
): CompareSelectionEntry[] {
	// Laufzeit bleibt defensiv (response.metrics ?? []), obwohl der Typ das
	// Feld als Pflicht deklariert — der Endpoint darf nie ohne `metrics`
	// antworten, ein fehlerhafter/leerer Body darf aber trotzdem nicht crashen.
	const entries = (response.metrics ?? []).map((m) => ({
		metric: m.key,
		label: m.label,
		...(m.metric_id !== undefined ? { metric_id: m.metric_id } : {}),
		...(m.aggregation !== undefined ? { aggregation: m.aggregation } : {}),
		...(m.aggregation_label !== undefined
			? { aggregation_label: m.aggregation_label }
			: {}),
		...(m.alertMetric !== undefined ? { alertMetric: m.alertMetric } : {}),
		// #1453 (AC-7): die beiden uebrigen Namensformen derselben Groesse —
		// unveraendert durchgereicht, damit der Editor alle drei zeigen kann.
		// Nur ergaenzen, wenn der Endpoint sie liefert (deepEqual-Vertrag #1350).
		...(m.col_label !== undefined ? { col_label: m.col_label } : {}),
		...(m.sms_code !== undefined ? { sms_code: m.sms_code } : {}),
		// #1406 B: nur ergaenzen, wenn der Endpoint sie liefert — sonst braechen
		// die strikten deepEqual-Vergleiche aus #1350 (AC-2).
		...(m.hourlySelectable !== undefined ? { hourlySelectable: m.hourlySelectable } : {}),
		...(m.hourlyNotSelectableReason !== undefined
			? { hourlyNotSelectableReason: m.hourlyNotSelectableReason }
			: {}),
		...(m.hourlyDefault !== undefined ? { hourlyDefault: m.hourlyDefault } : {}),
		...(m.hourlyMergeOnly !== undefined ? { hourlyMergeOnly: m.hourlyMergeOnly } : {}),
		...(m.hourly_legacy_keys !== undefined
			? { hourly_legacy_keys: m.hourly_legacy_keys }
			: {}),
		...(m.ordinalLabels !== undefined ? { ordinalLabels: m.ordinalLabels } : {})
	}));
	// Issue #1373 (S2 Scheibe B): dieselbe geladene Katalogantwort ist die
	// EINZIGE Quelle für die Übersetzung Auswahl-Schlüssel <-> Größe+Auswertung
	// im Browser. Hier ist der einzige Durchlauf-Punkt der Antwort — also wird
	// der Umkehr-Index hier gefüllt, ohne eine zweite Anfrage und ohne eine
	// zweite Tabelle im Frontend.
	registerCompareMetricCatalog(entries);
	return entries;
}

// ── Issue #1373 S2 Scheibe B: Speicherformat der Metrik-Auswahl ────────────
//
// Gespeichert wird ab dieser Lieferung Größe + Auswertung
// (`{metric_id, aggregation}`); gelesen wird dauerhaft BEIDES (Altformat =
// Auswahl-Schlüssel als Zeichenkette). Die Bedienoberfläche arbeitet
// unverändert auf `string[]` (Auswahl-Schlüssel) — nur Lese-/Schreibrand
// übersetzt.
//
// GRUNDREGEL: jede Übersetzung ist VERLUSTFREI. Was nicht auflösbar ist (der
// Katalog ist noch nicht geladen oder kennt das Paar nicht), wird UNVERÄNDERT
// durchgereicht statt verworfen — der Backend-Auflöser liest beide Formate,
// eine unübersetzte Zeichenkette bleibt also wirksam (kein Datenverlust der
// Klasse #102).

/** Ein Eintrag in `display_config.active_metrics`: Neuformat-Objekt oder
 *  Altformat-Zeichenkette. */
export type StoredActiveMetric = string | { metric_id: string; aggregation: string };

let registeredCatalog: CompareSelectionEntry[] = [];

/** Legt die geladene Katalogantwort als Übersetzungsquelle ab. Wird von
 *  `toCompareSelectionEntries()` aufgerufen; Tests setzen sie direkt. */
export function registerCompareMetricCatalog(entries: CompareSelectionEntry[]): void {
	registeredCatalog = entries ?? [];
}

/** Die aktuell bekannte Katalogantwort (leer = noch nicht geladen). */
export function registeredCompareMetricCatalog(): CompareSelectionEntry[] {
	return registeredCatalog;
}

/** Auswahl-Schlüssel eines gespeicherten Eintrags — `null`, wenn er (noch)
 *  nicht auflösbar ist. */
export function compareMetricKeyFromStored(
	item: unknown,
	catalog: CompareSelectionEntry[] = registeredCatalog
): string | null {
	if (typeof item === 'string') return item;
	if (item && typeof item === 'object') {
		const { metric_id, aggregation } = item as { metric_id?: unknown; aggregation?: unknown };
		if (typeof metric_id !== 'string' || typeof aggregation !== 'string') return null;
		const hit = catalog.find((e) => e.metric_id === metric_id && e.aggregation === aggregation);
		return hit ? hit.metric : null;
	}
	return null;
}

/**
 * Lesenormalisierung: gespeicherte Metrik-Auswahl (Alt- ODER Neuformat, auch
 * gemischt) -> Auswahl-Schlüssel für die Oberfläche. `null` heißt „kein Array"
 * (Feld fehlt → Profil-Defaults, #1191-Semantik unverändert).
 *
 * Nicht auflösbare Einträge bleiben unverändert in der Liste stehen (Cast auf
 * `string[]`, wie bisher an dieser Naht) — genau das heutige Verhalten für
 * unbekannte Schlüssel (Restrisiko R1 der Spec: die Auswahl zeigt sich dann als
 * nicht angehakt, heilt sich beim nächsten Laden mit geladenem Katalog selbst),
 * aber ohne dass ein späteres Speichern die Auswahl verliert.
 */
export function normalizeStoredActiveMetrics(
	stored: unknown,
	catalog: CompareSelectionEntry[] = registeredCatalog
): string[] | null {
	if (!Array.isArray(stored)) return null;
	return stored.map((item) => compareMetricKeyFromStored(item, catalog) ?? item) as string[];
}

/**
 * Lesenormalisierung des AUSBLICKS (#1848 A2): gespeicherte Auswahl -> reine
 * Kennungen, jede genau einmal, Reihenfolge des ersten Auftretens erhalten.
 *
 * Bewusst getrennt von `normalizeStoredActiveMetrics()`: die Übersichts-
 * Grundauswahl (`active_metrics`) spricht weiterhin Katalog-Schlüssel und
 * speichert Paare (ADR-0037). Der Ausblick dagegen speichert seit A2 die
 * Kennung — Temperatur-Tief und -Hoch sind dort EIN Eintrag, weil sie in der
 * Mail EINE Spannen-Spalte ergeben. Beide Formate werden gelesen: die
 * Paar-Altform, der Katalog-Schlüssel eines Bestands-Presets und die Kennung
 * selbst.
 *
 * `null` heißt „kein Array" (Feld fehlt → die sieben festen Spalten) und
 * bleibt von `[]` („bewusst geleert") unterscheidbar.
 */
export function normalizeStoredOutlookMetrics(
	stored: unknown,
	catalog: CompareSelectionEntry[] = registeredCatalog
): string[] | null {
	if (!Array.isArray(stored)) return null;
	const kennungen: string[] = [];
	for (const item of stored) {
		let metricId: string | null = null;
		if (typeof item === 'string') {
			metricId = catalog.find((e) => e.metric === item)?.metric_id ?? item;
		} else if (item && typeof item === 'object') {
			const { metric_id } = item as { metric_id?: unknown };
			if (typeof metric_id === 'string') metricId = metric_id;
		}
		if (metricId !== null && !kennungen.includes(metricId)) kennungen.push(metricId);
	}
	return kennungen;
}

/**
 * Schreibübersetzung: Auswahl-Schlüssel -> Größe + Auswertung (Neuformat).
 * Reihenfolge positionsgetreu (#1335/#1359), keine Deduplizierung, kein `set()`
 * — „Temperatur max" und „Temperatur min" teilen die Größe und dürfen niemals
 * verschmelzen.
 *
 * Ein Schlüssel ohne Katalog-Entsprechung (unbekannt, oder Katalog noch nicht
 * geladen) bleibt als Zeichenkette stehen; ein bereits übersetzter Eintrag
 * wird unverändert durchgereicht.
 */
export function toStoredActiveMetrics(
	keys: readonly unknown[],
	catalog: CompareSelectionEntry[] = registeredCatalog
): StoredActiveMetric[] {
	return keys.map((key) => {
		if (typeof key !== 'string') return key as StoredActiveMetric;
		const hit = catalog.find((e) => e.metric === key);
		return hit && hit.metric_id !== undefined && hit.aggregation !== undefined
			? { metric_id: hit.metric_id, aggregation: hit.aggregation }
			: key;
	});
}
