// Issue #1357 (Epic #1372 S4a) — Auswertungswahl je Wettergroesse fuer die
// Mail-Kachelzeile. Die Liste der berechenbaren Auswertungen kommt aus dem
// zentralen Katalog (`/api/metrics` -> `MetricEntry.aggregations`, gespeist aus
// `src/app/metric_catalog.py::available_aggregations`) — hier steht KEINE
// zweite Tabelle. Diese Datei traegt nur die Ableitungsregeln, damit sie ohne
// Svelte-Rendering-Harness pruefbar sind.
//
// PO 2026-07-28: „Es gibt kein zusaetzlich: entweder oder." Die Wahl ist eine
// EINZELWAHL ueber sich ausschliessende Moeglichkeiten (Spanne, nur Tiefstwert,
// nur Hoechstwert, nur Mittelwert) — die widerspruechliche Kombination, von der
// die Kachel nur einen Teil zeigen koennte, kann gar nicht erst entstehen.
// Gegenstueck im Renderer: `email/helpers.py::pill_aggregation_choices()`.
// Spec: docs/specs/modules/trip_aggregation_selection.md (AC-5, AC-6, AC-8)

import type { MetricEntry } from '$lib/types';

export type AggregationOption = { id: string; label: string };
/** Eine der sich ausschliessenden Moeglichkeiten: Kennung, Beschriftung und
 *  die Liste, die dafuer als `MetricConfig.aggregations` gespeichert wird. */
export type AggregationChoice = { id: string; label: string; aggregations: string[] };

export const RANGE_CHOICE_ID = 'range';

/** Berechenbare Auswertungen einer Groesse (leer, wenn der Katalog schweigt). */
export function aggregationOptions(entry: MetricEntry | undefined): AggregationOption[] {
	return entry?.aggregations ?? [];
}

/** Die Moeglichkeiten einer Groesse, abgeleitet aus dem Katalog-Angebot: die
 *  Spanne nur, wenn Tiefst- UND Hoechstwert berechenbar sind, dazu je ein
 *  Einzelwert. Bei `wind_chill` (kein `avg` im Katalog) entfaellt „nur
 *  Mittelwert" damit von selbst — ohne Sonderfall fuer diese Groesse. */
export function aggregationChoices(entry: MetricEntry | undefined): AggregationChoice[] {
	const options = aggregationOptions(entry);
	const ids = options.map((o) => o.id);
	const range: AggregationChoice[] =
		ids.includes('min') && ids.includes('max')
			? [{ id: RANGE_CHOICE_ID, label: 'Spanne', aggregations: ['min', 'max'] }]
			: [];
	return range.concat(
		options.map((o) => ({ id: o.id, label: `Nur ${o.label}`, aggregations: [o.id] })),
	);
}

/** AC-5: Auswahl nur zeigen, wo es etwas zu waehlen gibt — eine Groesse mit
 *  genau einer Moeglichkeit bekaeme ein wirkungsloses Bedienelement. */
export function showsAggregationChoice(entry: MetricEntry | undefined): boolean {
	return aggregationChoices(entry).length > 1;
}

/** Vorbelegung ohne Nutzereinschraenkung: `{min, max}` geschnitten auf das
 *  Angebot, sonst das gesamte Angebot. Spiegelt
 *  `metric_catalog.pill_default_aggregations()`. */
export function defaultAggregations(entry: MetricEntry | undefined): string[] {
	const available = aggregationOptions(entry).map((o) => o.id);
	const preferred = available.filter((a) => a === 'min' || a === 'max');
	return preferred.length ? preferred : available;
}

const sameList = (a: string[], b: string[]) =>
	a.length === b.length && a.every((x, i) => x === b[i]);

/** Angezeigter Zustand. `undefined` (nie eingeschraenkt) faellt auf die Vorgabe
 *  zurueck; eine ausdrueckliche leere Liste bleibt leer (AC-8). Eine Liste ohne
 *  Entsprechung (Altbestand, z.B. `["min","max","avg"]` aus der Katalog-
 *  Vorgabe) wird auf die naechstliegende abgebildet — min+max heisst Spanne.
 *  Gespiegelt aus `email/helpers.py::_resolve_pill_aggregations()`; rein
 *  anzeigend — gespeichert wird erst durch eine Nutzeraktion. */
export function effectiveAggregations(
	entry: MetricEntry | undefined,
	saved: string[] | undefined,
): string[] {
	if (saved === undefined) return defaultAggregations(entry);
	const kept = aggregationOptions(entry).map((o) => o.id).filter((a) => saved.includes(a));
	if (!kept.length) return [];
	if (aggregationChoices(entry).some((c) => sameList(c.aggregations, kept))) return kept;
	if (kept.includes('min') && kept.includes('max')) return ['min', 'max'];
	if (kept.includes('min')) return ['min'];
	if (kept.includes('max')) return ['max'];
	return [kept[0]];
}

/** Welche Moeglichkeit ist ausgewaehlt? `null` = keine (ausdruecklich leere
 *  Wahl, AC-8) — die Oberflaeche bietet sie nicht an, muss sie aber anzeigen
 *  koennen, ohne ungefragt etwas auszuwaehlen. */
export function selectedChoiceId(
	entry: MetricEntry | undefined,
	saved: string[] | undefined,
): string | null {
	const effective = effectiveAggregations(entry, saved);
	if (!effective.length) return null;
	return aggregationChoices(entry).find((c) => sameList(c.aggregations, effective))?.id ?? null;
}

/** Getroffene Wahl -> gespeicherte Liste (`MetricConfig.aggregations`). */
export function choiceAggregations(entry: MetricEntry | undefined, choiceId: string): string[] {
	return aggregationChoices(entry).find((c) => c.id === choiceId)?.aggregations ?? [];
}
