// Issue #3190 (Epic #2913) — geteilte Bedienlogik der Karte „Als eigene Vorlage speichern“.
// Genutzt von SavePresetDialog (Karte), VorlageKarte (Reiter Wetter, Trip und Orts-Vergleich) und
// WeatherMetricsTab (gelöscht, #3297) (Alt-Editor), damit beide Auslöser gleich umschalten und den Fokus gleich zurückgeben.
// Liegt bewusst außerhalb lib/components: reine Logik, kein Baustein (ADR-0112, Regel (a)).
// Spec: docs/specs/modules/feat_3190_vorlage_dialog_inline.md (AC-6, AC-7, AC-8, AC-10)

/** Alles, was den Fokus annehmen kann (HTMLElement im Browser, Attrappe im Test). */
export type Fokussierbar = { focus: () => void };

/** AC-6: Escape in der Karte schließt sie — nicht, solange gespeichert wird (Abbrechen ist dann gesperrt). */
export function karteSchliesstPerTaste(taste: string, speichert: boolean): boolean {
	return taste === 'Escape' && !speichert;
}

/** AC-7: Escape am Fenster schließt nur die offene Vorlagen-Auswahl (die Karte beendet ihr Escape selbst). */
export function pickerSchliesstPerTaste(taste: string, pickerOffen: boolean): boolean {
	return pickerOffen && taste === 'Escape';
}

/**
 * AC-8: Zustandswechsel der Karte. Offen ⇒ Fokus ins Namensfeld (sobald es existiert);
 * geschlossen ⇒ Eingaben zurücksetzen (auch beim Schließen über den Umschalter).
 */
export function beiKartenWechsel(offen: boolean, namensfeld: Fokussierbar | null): 'fokus' | 'zuruecksetzen' {
	if (!offen) return 'zuruecksetzen';
	namensfeld?.focus();
	return 'fokus';
}

/**
 * AC-1/AC-6/AC-10: Auslöser der Karte. `umschalten` merkt den geklickten Knopf und liefert den neuen
 * Offen-Zustand; `zurueck` gibt den Fokus nach Abbrechen, Escape oder Speichern an ihn zurück.
 */
export function speicherKarteAusloeser() {
	let ausloeser: Fokussierbar | null = null;
	return {
		umschalten(knopf: Fokussierbar | null, offen: boolean): boolean {
			if (knopf) ausloeser = knopf;
			return !offen;
		},
		zurueck(): void {
			ausloeser?.focus();
		}
	};
}
