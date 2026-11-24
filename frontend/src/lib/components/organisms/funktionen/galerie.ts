// Issue #3319 (AC-13, Spec 1.2) — reine Logik der Bildergalerie der oeffentlichen
// Funktionsseiten: welche Bilder zu einer Seite gehoeren (in Seitenreihenfolge),
// Blaettern, Pfeiltasten, Wischen, Zaehler und die Katalogschluessel der Bedienelemente.
// Darstellung: Bildergalerie.svelte; Test: organisms/__tests__/funktionen_galerie.test.ts.
//
// Rand-Verhalten: NICHT umlaufend. Auf dem ersten Bild gibt es kein „Zurueck“, auf dem
// letzten kein „Vor“ (Schaltflaeche deaktiviert; Pfeiltaste und Wischen tun dort nichts).
import type { MessageKey } from '$lib/i18n';
import { funktionenSeite, type FunktionenSlug } from '$lib/funktionen_seiten';
import { INVENTAR, type Bild } from './inhalt';

export type Richtung = 'vor' | 'zurueck';

/** Katalogschluessel der Galerie-Bedienelemente (DE/EN). */
export const GALERIE_TEXTE = {
	/** Beschriftung der Bild-Schaltflaeche, Platzhalter {bild} = Alt-Text. */
	oeffnen: 'funktionen.galerie.oeffnen',
	/** Name des Dialogs. */
	titel: 'funktionen.galerie.titel',
	schliessen: 'funktionen.galerie.schliessen',
	vor: 'funktionen.galerie.vor',
	zurueck: 'funktionen.galerie.zurueck',
	/** Vorlesetext zum Zaehler, Platzhalter {n} und {m}. */
	position: 'funktionen.galerie.position'
} as const satisfies Record<string, MessageKey>;

/**
 * Bilder einer Unterseite in der Reihenfolge, in der die Seite sie zeigt (Bilder je
 * Inventarpunkt). Die Uebersicht /funktionen hat KEINE Galerie (AC-13): dort ist das
 * Vorschaubild Teil des Kachel-Links zur Unterseite.
 */
export function galerieBilder(seite: FunktionenSlug): readonly Bild[] {
	return (funktionenSeite(seite)?.inventar ?? []).flatMap((id) => INVENTAR[id].bilder);
}

/** Index des naechsten Bildes oder `null` auf dem letzten Bild. */
export function naechsterIndex(i: number, n: number): number | null {
	return i + 1 < n ? i + 1 : null;
}

/** Index des vorherigen Bildes oder `null` auf dem ersten Bild. */
export function vorherigerIndex(i: number, n: number): number | null {
	return i > 0 && n > 0 ? i - 1 : null;
}

/** Neuer Index nach einem Schritt; am Rand bleibt er stehen. */
export function blaettern(i: number, n: number, richtung: Richtung | null): number {
	if (richtung === 'vor') return naechsterIndex(i, n) ?? i;
	if (richtung === 'zurueck') return vorherigerIndex(i, n) ?? i;
	return i;
}

/** Pfeiltaste → Richtung (andere Tasten: `null`). */
export function tasteZuRichtung(key: string): Richtung | null {
	if (key === 'ArrowRight') return 'vor';
	if (key === 'ArrowLeft') return 'zurueck';
	return null;
}

/** Mindestweg eines Wischens in Pixeln. */
export const WISCH_SCHWELLE = 50;

/** Wischen nach links = vor, nach rechts = zurueck; kurz oder ueberwiegend senkrecht = nichts. */
export function wischRichtung(dx: number, dy: number): Richtung | null {
	if (Math.abs(dx) < WISCH_SCHWELLE || Math.abs(dx) <= Math.abs(dy)) return null;
	return dx < 0 ? 'vor' : 'zurueck';
}

/** Sichtbarer Zaehler „n / m“ (ab 1). */
export function zaehler(i: number, n: number): string {
	return `${i + 1} / ${n}`;
}
