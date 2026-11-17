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

/** `location_ids` -> aufloesbare Orte in der gespeicherten Folge (= Folge der Ort-Bloecke der Mail).
 *  #3047 p10: ein geloeschter/unbekannter Ort faellt heraus wie im Versand (`order_locations_by_ids`),
 *  der Rang zaehlt nur die aufloesbaren Orte (= Position des Blocks in der Mail); keiner uebrig =
 *  leere Liste (Reiter zeigt „keine Orte", die Mail wird mit `orte_geloescht` nicht versendet). */
export function orteAufloesen<L extends OrtMitId>(ids: readonly string[], verzeichnis: ReadonlyMap<string, L>): OrtsEintrag<L>[] {
	const orte: OrtsEintrag<L>[] = [];
	for (const id of ids) {
		const loc = verzeichnis.get(id);
		if (loc) orte.push({ rank: orte.length + 1, loc });
	}
	return orte;
}

/** Nummer (Rang-Abzeichen, Bedienhilfe-Text) der Zeile an Position `i` der Reiterliste `ids`:
 *  zaehlt nur aufloesbare Orte bis einschliesslich `i` (ohne geloeschte Orte = `i + 1`). Die
 *  Kennungen geloeschter Orte bleiben in der Liste und damit beim Speichern erhalten. */
export function reiterNummer<L extends OrtMitId>(ids: readonly string[], i: number, verzeichnis: ReadonlyMap<string, L>): number {
	let nummer = 0;
	for (let k = 0; k <= i && k < ids.length; k++) if (verzeichnis.has(ids[k])) nummer++;
	return nummer;
}
