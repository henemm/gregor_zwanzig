// anlegeLockEngine.ts — geteilte Freischalt-Logik der Anlege-Seiten
// (/trips/new und /compare/new). Issue #2277 Scheibe S4.
// Spec: docs/specs/modules/feat_2277_s4_anlege_lockengine.md
//
// DOM-frei, keine Svelte-Imports, rein. Der Kern kennt nur die gemeinsame
// Schwanz-Kette Wetter -> Zustellung (#2794 S3a Teil-PR 2; vorher Wetter-Metriken
// -> Wertebereiche -> Alarme). Das Vorderteil (Trip: Name/Startdatum/Etappen;
// Ortsvergleich: Name/Orte) bleibt kind-eigen und wird als Wahrheitswert
// `metrikenFrei` uebergeben. Die Besuchs-Flags werden vom Editor beim
// Reiterwechsel gesetzt und nie zurueckgesetzt.

/** Tab-IDs der Schwanz-Kette. */
export interface TailIds<T extends string = string> {
	/** Erster Schwanz-Schritt (Wetter). */
	metriken: T;
	/** Letzter Schritt (Zustellung) — sein Besuch schaltet Speichern/Aktivieren frei. */
	zustellung: T;
}

export interface TailProgress {
	/** Vorderteil erfuellt => Wetter anklickbar. */
	metrikenFrei: boolean;
	metrikenVisited: boolean;
	zustellungVisited: boolean;
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
	if (p.metrikenVisited) s.add(ids.zustellung);
	return s;
}

/** Erledigte Reiter der Schwanz-Kette (= Besuchs-Flags, unabhaengig vom Vorderteil). */
export function tailDone<T extends string>(ids: TailIds<T>, p: TailProgress): Set<T> & Set<string> {
	const s = new Set<string>() as Set<T> & Set<string>;
	if (p.metrikenVisited) s.add(ids.metriken);
	if (p.zustellungVisited) s.add(ids.zustellung);
	return s;
}

/** Anlegen/Aktivieren erst nach Besuch von Zustellung (#2794 S3a, letzter Schritt der Kette). */
export function canFinish(done: Set<string>, letzterId: string = 'zustellung'): boolean {
	return done.has(letzterId);
}

/**
 * „Mit Standardwerten speichern" (Issue #2521 S3, kind-neutral): frei, wenn die
 * Pflichtangaben erfuellt und die Standardwerte bereit sind und der
 * Bestandsknopf (`canFinish` bzw. `canSave`) noch gesperrt ist — nie beide
 * gleichzeitig aktiv.
 */
export function canFinishMitStandardwerten(p: {
	pflichtErfuellt: boolean;
	defaultsBereit: boolean;
	bestandFrei: boolean;
}): boolean {
	return p.pflichtErfuellt && p.defaultsBereit && !p.bestandFrei;
}

/** Zaehlt, wie viele der `steps` in `done` stehen. */
export function progressCount(done: Set<string>, steps: readonly string[]): number {
	return steps.filter((s) => done.has(s)).length;
}
