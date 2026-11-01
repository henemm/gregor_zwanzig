// naechstesBriefingLader — Issue #1969 (AC-18/AC-19), Fix-Loop 1 (Adversary F002).
//
// EIN reaktiver Lader für den Backend-Wert „Nächstes Briefing", geteilt von
// VTNextBriefing (Versand-Reiter Trip + Vergleich), HubUebersicht (Hub-Stat beider
// Arten, #2682) und HubOverview (Karte „Briefings laufen"). Vorher stand dieselbe Effekt-Logik
// dreimal in Komponenten — im SSR-only-Kern unbeobachtbar. Als Runen-Modul ist
// sie in der echten Svelte-Client-Laufzeit prüfbar
// (__tests__/naechstes_briefing_lader_laufzeit.test.ts).
//
// Regeln:
//   - geladen wird, sobald `id` da ist und kein Wert von aussen kommt (`extern`);
//   - jede Aenderung von `neuLaden` laedt neu (Komponenten reichen
//     `saveController.savedAt` durch — das stempelt nur ein ERFOLGREICHES
//     Speichern, ungespeicherte Eingaben laden also nie neu, AC-18);
//   - Laufnummer: eine spaet eintreffende, aeltere Antwort ueberschreibt nie
//     eine neuere;
//   - Fehler/fehlender Eintrag ⇒ null (Anzeige „—", AC-19).

import { ladeNaechstesBriefing, type Holen } from './nextBriefingLoad.ts';
import type { NextBriefing } from './nextBriefingText.ts';

export interface LaderQuelle {
	context: 'route' | 'vergleich';
	/** Gespeichertes Objekt; fehlt (Anlege-Seite) ⇒ kein Abruf. */
	id?: string;
	/** Jede Aenderung loest einen erneuten Abruf aus. */
	neuLaden?: unknown;
	/** Wert von aussen; gesetzt (auch null) ⇒ kein eigener Abruf. */
	extern?: NextBriefing | null;
}

export interface NaechstesBriefingLader {
	/** Anzuzeigender Wert: `extern`, sonst der zuletzt geladene (undefined = noch nicht geladen). */
	readonly wert: NextBriefing | null | undefined;
	/** Die aktuell gelesene Quelle (fuer die Verdrahtungs-Pruefung der Konsumenten). */
	readonly quelle: LaderQuelle;
}

export function erstelleNaechstesBriefingLader(
	quelle: () => LaderQuelle,
	holen: Holen
): NaechstesBriefingLader {
	let geladen = $state<NextBriefing | null | undefined>(undefined);
	let lauf = 0;
	$effect(() => {
		// `quelle()` liest alle Felder (auch `neuLaden`) — damit haengt der Effekt an ihnen.
		const q = quelle();
		// Laufnummer VOR dem Ruecksprung: faellt die id weg (oder kommt ein Wert von
		// aussen), wird eine noch laufende Antwort ebenfalls verworfen.
		const meinLauf = ++lauf;
		if (q.extern !== undefined || !q.id) return;
		ladeNaechstesBriefing(holen, q.context, q.id).then((nb) => {
			if (meinLauf === lauf) geladen = nb;
		});
	});
	return {
		get wert() {
			const q = quelle();
			return q.extern !== undefined ? q.extern : geladen;
		},
		get quelle() {
			return quelle();
		}
	};
}
