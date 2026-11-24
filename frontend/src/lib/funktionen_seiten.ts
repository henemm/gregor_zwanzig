// Issue #3319 / #3320 — EINZIGE Liste der Unterseiten der oeffentlichen
// Funktionsuebersicht (/funktionen/<slug>): Reihenfolge, Slug und die
// Inventarpunkte, die auf der Seite stehen. Quelle fuer
//   - die oeffentliche Pfadmenge im Auth-Hook (hooks.server.ts, exakte Pfade),
//   - die Kacheln der Uebersicht, die Themen-Navigation und Weiter/Zurueck,
//   - die Kopfzeilenwahl im Layout (+layout.svelte).
// Spec: docs/specs/modules/oeffentliche_doku_3319.md (v1.1, „Seitenstruktur“).
// Bewusst ohne Importe: auch die Staging-Pruefung (frontend/e2e) liest diese Datei.
// Katalog-Schluessel: funktionen.seite.<slug>.titel | .kachel | .einleitung |
// .meta_titel | .meta_beschreibung, funktionen.<inventar>.titel.

export type FunktionenSlug =
	| 'trips'
	| 'briefings'
	| 'alarme'
	| 'ortsvergleich'
	| 'kanaele'
	| 'befehle'
	| 'wetterdaten'
	| 'konto'
	| 'level';

export type InventarId =
	| 'cockpit'
	| 'trip_anlegen'
	| 'trip_hub'
	| 'archiv'
	| 'briefings'
	| 'wetter'
	| 'alarme'
	| 'ortsvergleich'
	| 'kanaele'
	| 'zustellung'
	| 'befehle'
	| 'wetterdaten'
	| 'konto'
	| 'app';

export type FunktionenSeite = { slug: FunktionenSlug; inventar: readonly InventarId[] };

export const FUNKTIONEN_SEITEN: readonly FunktionenSeite[] = [
	{ slug: 'trips', inventar: ['cockpit', 'trip_anlegen', 'trip_hub', 'archiv'] },
	{ slug: 'briefings', inventar: ['briefings', 'wetter'] },
	{ slug: 'alarme', inventar: ['alarme'] },
	{ slug: 'ortsvergleich', inventar: ['ortsvergleich'] },
	{ slug: 'kanaele', inventar: ['kanaele', 'zustellung'] },
	{ slug: 'befehle', inventar: ['befehle'] },
	{ slug: 'wetterdaten', inventar: ['wetterdaten'] },
	{ slug: 'konto', inventar: ['konto', 'app'] },
	{ slug: 'level', inventar: [] }
];

/** Uebersicht der Funktionsseiten. */
export const FUNKTIONEN_UEBERSICHT = '/funktionen';

/** Pfad einer Unterseite. */
export const funktionenPfad = (slug: string): string => `${FUNKTIONEN_UEBERSICHT}/${slug}`;

/** Exakte oeffentliche Pfade: Uebersicht + jede Unterseite (kein Praefix-Vergleich). */
export const FUNKTIONEN_PFADE: ReadonlySet<string> = new Set([
	FUNKTIONEN_UEBERSICHT,
	...FUNKTIONEN_SEITEN.map((s) => funktionenPfad(s.slug))
]);

/** Seite zum Slug oder `undefined` (Gross-/Kleinschreibung zaehlt). */
export function funktionenSeite(slug: string): FunktionenSeite | undefined {
	return FUNKTIONEN_SEITEN.find((s) => s.slug === slug);
}
