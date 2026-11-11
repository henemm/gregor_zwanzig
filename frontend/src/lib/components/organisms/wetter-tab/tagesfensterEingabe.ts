// Issue #2913 Scheibe (c) (AC-5): reine Eingabe-Logik und Verdrahtung des Tagesfensters der Karte „Anpassen".
// Spec: docs/specs/modules/feat_2913_scheibe_c_wetter_rest.md
//
// Das Tagesfenster kennt nur ganze Stunden (`day_window_*_hour`, ADR-0035). Die Uhrzeitfelder im
// Stundenraster melden `HH:00`; eine Minute wird ignoriert (`06:30` ⇒ 6), ungültige Stunden (außer 0–23,
// keine Uhrzeit) werden abgewiesen. Ein Fenster über Mitternacht (Ende < Start) ist gültig; nur
// Ende = Start wird über clampDayWindowEndHour auf die nächste Stunde gezogen (PO-Entscheidung #1361/#1372).
// Die Komponente AnpassenKarte erzeugt nur die Steuerung und hängt beiStart/beiEnde an die Felder
// (Adversary F004: die Wirkstelle liegt hier und ist ohne DOM prüfbar).
// Kein Svelte-/Browser-Import, lauffähig unter node --experimental-strip-types.

import { clampDayWindowEndHour } from '../../shared/versand-tab/dayWindowClamp.ts';

export interface Fenster {
	start: number;
	end: number;
}

/** Ergebnis einer Eingabe: neue Werte (nur was sich ändert) und ob das Ende-Feld neu aufgebaut werden muss. */
export interface FensterAenderung {
	/** Neue Startstunde (nur bei Eingabe im Start-Feld). */
	start?: number;
	/** Neue Endstunde, falls sie gemeldet werden muss. */
	ende?: number;
	/**
	 * Das Ende-Feld zeigt die getippte Stunde, gespeichert wird aber eine geklemmte: dann muss es neu
	 * aufgebaut werden (sonst bliebe bei unverändertem Wert, z. B. Start 6, Ende 7, getippt 6, die
	 * getippte Stunde stehen).
	 */
	endeNeuAufbauen: boolean;
}

/** Ganze Stunde aus `HH:MM` (Minute ignoriert); außerhalb 0–23 oder unlesbar ⇒ null. */
export function stundeAusEingabe(wert: string): number | null {
	const m = /^(\d{1,2}):(\d{2})$/.exec(wert.trim());
	if (!m) return null;
	const h = Number(m[1]);
	return h >= 0 && h <= 23 ? h : null;
}

/** `HH:00` für die Anzeige im Uhrzeitfeld. */
export const stundeAlsUhrzeit = (h: number): string => `${String(h).padStart(2, '0')}:00`;

/** Eingabe im Start-Feld: Start übernehmen; fällt das Ende auf den neuen Start, wird es nachgezogen. */
export function startEingabe(fenster: Fenster, wert: string): FensterAenderung | null {
	const h = stundeAusEingabe(wert);
	if (h === null) return null;
	const ende = clampDayWindowEndHour(h, fenster.end);
	return ende === fenster.end ? { start: h, endeNeuAufbauen: false } : { start: h, ende, endeNeuAufbauen: false };
}

/** Eingabe im Ende-Feld: Ende = Start wird nachgezogen, alles andere (auch vor dem Start) gilt. */
export function endeEingabe(fenster: Fenster, wert: string): FensterAenderung | null {
	const h = stundeAusEingabe(wert);
	if (h === null) return null;
	const ende = clampDayWindowEndHour(fenster.start, h);
	return { ende, endeNeuAufbauen: ende !== h };
}

export interface SteuerungsEingabe {
	/** Liest das aktuelle Fenster zum Zeitpunkt der Eingabe (lebender Stand, keine eingefrorene Kopie). */
	fenster: () => Fenster;
	onStart: (h: number) => void;
	onEnde: (h: number) => void;
	/** Das Ende-Feld muss neu aufgebaut werden (Aufrufer zählt seinen {#key}-Wert hoch). */
	onNeuAufbau: () => void;
}

export interface TagesfensterSteuerung {
	/** onchange des Start-Feldes (`HH:00`). */
	beiStart: (wert: string) => void;
	/** onchange des Ende-Feldes (`HH:00`). */
	beiEnde: (wert: string) => void;
}

/** Verdrahtung der beiden Uhrzeitfelder: ruft onStart/onEnde mit geklemmten Werten und meldet Neuaufbau. */
export function tagesfensterSteuerung(e: SteuerungsEingabe): TagesfensterSteuerung {
	const anwenden = (a: FensterAenderung | null): void => {
		if (!a) return;
		if (a.start !== undefined) e.onStart(a.start);
		if (a.ende !== undefined) e.onEnde(a.ende);
		if (a.endeNeuAufbauen) e.onNeuAufbau();
	};
	return {
		beiStart: (wert) => anwenden(startEingabe(e.fenster(), wert)),
		beiEnde: (wert) => anwenden(endeEingabe(e.fenster(), wert))
	};
}
