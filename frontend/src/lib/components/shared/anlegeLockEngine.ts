// anlegeLockEngine.ts — geteilte Freischalt-Logik der Anlege-Seiten
// (/trips/new und /compare/new). Issue #2277 Scheibe S4.
// Spec: docs/specs/modules/feat_2277_s4_anlege_lockengine.md
//
// DOM-frei, keine Svelte-Imports, rein. Der Kern kennt nur die gemeinsame
// Schwanz-Kette Wetter-Metriken -> Wertebereiche -> Alarme -> Versand. Das
// Vorderteil (Trip: Name/Startdatum/Etappen; Ortsvergleich: Name/Orte) bleibt
// kind-eigen und wird als Wahrheitswert `metrikenFrei` uebergeben. Die Besuchs-
// Flags werden vom Editor beim Reiterwechsel gesetzt und nie zurueckgesetzt.

/** Tab-IDs der Schwanz-Kette. */
export interface TailIds<T extends string = string> {
	metriken: T;
	wertebereiche: T;
	alarme: T;
	versand: T;
}

export interface TailProgress {
	/** Vorderteil erfuellt => Wetter-Metriken anklickbar. */
	metrikenFrei: boolean;
	metrikenVisited: boolean;
	wertebereicheVisited: boolean;
	alarmeVisited: boolean;
	versandVisited: boolean;
}

/**
 * Freigeschaltete Reiter der Schwanz-Kette. Rueckgabe `Set<T> & Set<string>`: fuer
 * Aufrufer mit Tab-ID-Union weiterhin als `Set<TabId>` nutzbar, fuer Aufrufer mit
 * `as const`-Literal-IDs trotzdem um weitere (Vorderteil-)IDs erweiterbar.
 */
export function tailUnlocked<T extends string>(ids: TailIds<T>, p: TailProgress): Set<T> & Set<string> {
	const s = new Set<string>() as Set<T> & Set<string>;
	if (!p.metrikenFrei) return s; // Vorderteil nicht erfuellt: gesamter Schwanz gesperrt
	s.add(ids.metriken);
	if (p.metrikenVisited) s.add(ids.wertebereiche);
	if (p.wertebereicheVisited) s.add(ids.alarme);
	if (p.alarmeVisited) s.add(ids.versand);
	return s;
}

/** Erledigte Reiter der Schwanz-Kette (= Besuchs-Flags, unabhaengig vom Vorderteil). */
export function tailDone<T extends string>(ids: TailIds<T>, p: TailProgress): Set<T> & Set<string> {
	const s = new Set<string>() as Set<T> & Set<string>;
	if (p.metrikenVisited) s.add(ids.metriken);
	if (p.wertebereicheVisited) s.add(ids.wertebereiche);
	if (p.alarmeVisited) s.add(ids.alarme);
	if (p.versandVisited) s.add(ids.versand);
	return s;
}

/** Anlegen/Aktivieren erst nach Besuch von Versand. */
export function canFinish(done: Set<string>, versandId: string = 'versand'): boolean {
	return done.has(versandId);
}

/** Zaehlt, wie viele der `steps` in `done` stehen. */
export function progressCount(done: Set<string>, steps: readonly string[]): number {
	return steps.filter((s) => done.has(s)).length;
}
