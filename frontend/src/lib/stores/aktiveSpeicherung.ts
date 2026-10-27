// Issue #2317 Baustein 2 — „Aktualisieren" (Update-Hinweis, #2316) wartet auf
// eine ausstehende Speicherung der offenen Detailseite.
// Spec: docs/specs/modules/speicherung_beim_neuladen.md § Baustein 2, AC-6, AC-7
//
// Das Layout erzeugt die Anmeldestelle und legt sie per Svelte-Context ab;
// `/trips/[id]` und `/compare/[id]` melden ihren SaveStatus beim Mount an und
// beim Unmount ab (Kontext fliesst nur Eltern -> Kind, deshalb Anmeldestelle
// statt direktem Zugriff). BEWUSST svelte-frei — unter node:test ladbar.

import type { SaveStatus } from './saveStatusStore.svelte.ts';

/** Context-Schluessel, unter dem das Layout die Anmeldestelle ablegt. */
export const AKTIVE_SPEICHERUNG = 'aktive-speicherung';

export interface SpeicherAnmeldestelle {
	/** Meldet einen SaveStatus an; liefert die Abmeldung. */
	anmelden(ctl: SaveStatus): () => void;
	/**
	 * Schliesst jede ausstehende Speicherung REGULAER ab (ohne keepalive, damit
	 * sie durch die Warteschlange mit If-Match laeuft). true = die neue Fassung
	 * darf uebernehmen; false = Konflikt/Fehler, die Anzeige des Reiters bleibt.
	 */
	wartenAufAusstehendeSpeicherung(): Promise<boolean>;
}

export function erzeugeSpeicherAnmeldestelle(): SpeicherAnmeldestelle {
	const angemeldet = new Set<SaveStatus>();
	return {
		anmelden(ctl) {
			angemeldet.add(ctl);
			return () => {
				angemeldet.delete(ctl);
			};
		},
		async wartenAufAusstehendeSpeicherung() {
			let ok = true;
			for (const ctl of [...angemeldet]) {
				// Erst eine schon UNTERWEGS befindliche Speicherung abwarten (Timer
				// abgelaufen, hasPending false), dann eine noch ausstehende absetzen.
				// Begrenzt, damit ein staendig neu tippender Nutzer nicht ewig haelt.
				for (let runde = 0; runde < 5; runde++) {
					const laufend = ctl.laufendeSpeicherung;
					if (laufend) await laufend;
					else if (ctl.hasPending) await ctl.flush();
					else break;
				}
				if (ctl.state === 'error' || ctl.state === 'conflict') ok = false;
			}
			return ok;
		}
	};
}
