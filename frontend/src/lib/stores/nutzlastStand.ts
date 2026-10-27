// Fix-Loop 3 (#1433, F201/F101): die Eigenfeld-Nutzlast einer Speicherfunktion als DATEN.
//
// Wurzel: nach einem 412 liegen ungesicherte Eingaben nur in der Liste des Controllers
// (Closures). Der Seitenstand, aus dem Reiter beim (Wieder-)Mount lesen, weiss davon
// nichts — zwei Wahrheiten. Invariante: Seitenstand = letzter Serverstand ⊕ ausstehende
// Eigenfeld-Nutzlasten der Liste. Dieses Modul traegt die Nutzlast am Funktionsobjekt
// (`merkeNutzlast`, beim SENDEN gesetzt — nie nachtraeglich neu berechnet) und wendet sie
// mit der Merge-Regel des Servers an (`wendeNutzlastAn`).
//
// BEWUSST svelte-frei und ohne Import des Controllers (kein Zirkel).

type Rec = Record<string, unknown>;
type MitNutzlast = { nutzlast?: unknown };

const istObjekt = (v: unknown): v is Rec => v !== null && typeof v === 'object' && !Array.isArray(v);
/** Wie JSON.stringify: Schluessel mit `undefined` werden nie gesendet. */
const ohneUndefined = (o: Rec): Rec => Object.fromEntries(Object.entries(o).filter(([, v]) => v !== undefined));

/** Haengt die zuletzt GESENDETE Nutzlast an die Speicherfunktion (liefert `fn` zurueck). */
export function merkeNutzlast<F extends (...args: never[]) => unknown>(fn: F, nutzlast: unknown): F {
	(fn as unknown as MitNutzlast).nutzlast = nutzlast;
	return fn;
}

/** Die zuletzt gesendete Nutzlast der Funktion; `undefined`, wenn keine bekannt ist. */
export function nutzlastVon(fn: unknown): unknown {
	return (fn as MitNutzlast | undefined)?.nutzlast;
}

/**
 * Stand ⊕ Nutzlast, einstufig wie Go `mergeConfigMap`/`mergeBriefingPatch`: jeder
 * Top-Level-Schluessel der Nutzlast ueberschreibt; sind beide Seiten Objekte, wird eine
 * Ebene tiefer gemergt (`display_config`, `report_config`); Arrays und alles darunter
 * werden ersetzt; `undefined` (nie gesendet) wird uebersprungen. Liefert bei fehlender
 * Nutzlast denselben `stand` zurueck, sonst eine NEUE Referenz (nie in-place).
 */
export function wendeNutzlastAn<T>(stand: T, nutzlast: unknown): T {
	if (!istObjekt(nutzlast) || !istObjekt(stand)) return stand;
	const out: Rec = { ...stand };
	for (const [k, v] of Object.entries(nutzlast)) {
		if (v === undefined) continue;
		out[k] = istObjekt(v) && istObjekt(out[k]) ? { ...(out[k] as Rec), ...ohneUndefined(v) } : v;
	}
	return out as T;
}

/** Stand ⊕ alle Nutzlasten in Reihenfolge der Liste (Eintraege ohne Nutzlast zaehlen nicht). */
export function wendeNutzlastenAn<T>(stand: T, eintraege: ReadonlyArray<{ nutzlast?: unknown }>): T {
	return eintraege.reduce((s, e) => wendeNutzlastAn(s, e.nutzlast), stand);
}
