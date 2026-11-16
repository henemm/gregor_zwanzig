// Issue #3047 Runde 7, Paket p10 (Matrixzellen orte.ortsfolge / orte.orte_auswahl / orte.ortsnamen):
// die Orts-Aufloesung des Orte-Reiters (CompareTabs.svelte) als reine, pruefbare Funktionen.
// Vorher inline im Reiter (`locationById` + `resolvedLocations`); Verhalten unveraendert herausgezogen.

/** Mindestform eines Orts fuer die Aufloesung (Location aus `$lib/types`). */
export type OrtMitId = { id: string; name: string };

/** Ein Eintrag je Kennung aus `location_ids`, in derselben Folge (Index = Position der Kennung). */
export type OrtsEintrag<L extends OrtMitId> = { rank: number; loc?: L };

/** Kennung -> Ort. `locations` (Orte des Abos aus dem Seitenlader) hat Vorrang vor den im
 *  Hinzufuegen-Panel nachgeladenen Orten (`nachgeladen`). */
export function ortsVerzeichnis<L extends OrtMitId>(locations: readonly L[], nachgeladen: readonly L[]): Map<string, L> {
	const map = new Map<string, L>();
	for (const l of locations) map.set(l.id, l);
	for (const l of nachgeladen) if (!map.has(l.id)) map.set(l.id, l);
	return map;
}

/** `location_ids` -> Eintraege in der gespeicherten Folge (= Folge der Ort-Bloecke der Mail). */
export function orteAufloesen<L extends OrtMitId>(ids: readonly string[], verzeichnis: ReadonlyMap<string, L>): OrtsEintrag<L>[] {
	return ids.map((id, idx) => ({
		rank: idx + 1,
		loc: verzeichnis.get(id)
	}));
}

/** Nummer (Rang-Abzeichen, Bedienhilfe-Text) der Zeile an Position `i` der Reiterliste `ids`. */
export function reiterNummer<L extends OrtMitId>(_ids: readonly string[], i: number, _verzeichnis: ReadonlyMap<string, L>): number {
	return i + 1;
}
