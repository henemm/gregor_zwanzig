// Issue #2988 S4 (AC-16): Lademodul der aufgeloesten Ampel fuer die Trip-Uebersicht.
// Spec: docs/specs/modules/rework_2988_ampel_ableitung.md („S4 – Übersichten").
//
// Ein Aufruf je neuem Eintrag (`eintragAusAbo`); gleicher Eintrag wie zuletzt (und nicht gescheitert)
// ⇒ nichts. Ein Ticket verwirft veraltete Antworten und Fehler (Vorbild wasStehtWoSpeicherung.ts).
// Das Promise scheitert nie. Kein Browser-/SvelteKit-Import, lauffaehig unter node --experimental-strip-types.

import { eintragAusAbo, loeseAmpelnAuf, type Aufgeloest, type AufloesungClient } from '../wetter-tab/ampelAufloesung.ts';

export type TripAufloesung = { zustand: 'laedt' | 'geladen' | 'fehler'; aufgeloest: Aufgeloest | null };
/** Trip (oder jede Abo-Sicht): gelesen werden nur `display_config` und `profil`. */
type AboArg = { display_config?: object | null; profil?: unknown } | null | undefined;

export function erstelleTripAufloesung(client: AufloesungClient, melde: (s: TripAufloesung) => void): { laden(trip: AboArg): Promise<void> } {
	let ticket = 0;
	let letzter: string | null = null;
	let gescheitert = false;
	return {
		async laden(trip) {
			const eintrag = eintragAusAbo(trip as Parameters<typeof eintragAusAbo>[0]);
			const schluessel = JSON.stringify(eintrag);
			if (schluessel === letzter && !gescheitert) return;
			letzter = schluessel;
			gescheitert = false;
			const meins = ++ticket;
			melde({ zustand: 'laedt', aufgeloest: null });
			try {
				const [ergebnis] = await loeseAmpelnAuf(client, [eintrag]);
				if (meins === ticket) melde({ zustand: 'geladen', aufgeloest: ergebnis });
			} catch {
				if (meins !== ticket) return;
				gescheitert = true;
				melde({ zustand: 'fehler', aufgeloest: null });
			}
		}
	};
}
