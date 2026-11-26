// Issue #3399 S1 (AC-6): gebuendelter, gecachter Lader „Abo -> vorlage_id".
// Spec: docs/specs/modules/rework_3399_vorlage_aufloesung.md („Implementation Details", S1).
//
// Die Vorlagen-Rangfolge kennt allein der Server (resolve_entwurf); hier wird nur `vorlage_id`
// uebernommen, nie die aufgeloeste Ampel (die enthaelt Abo-Abweichungen, AC-7). Cache je Eintrag
// (modulweit, Fehler werden nicht gecacht), ein Ticket verwirft veraltete Antworten und Fehler,
// das Promise scheitert nie. Vorbild hub-uebersicht/tripAufloesung.ts.
// Kein Browser-/SvelteKit-Import, lauffaehig unter node --experimental-strip-types.

import { eintragAusAbo, loeseAmpelnAuf, type AufloesungClient } from './ampelAufloesung.ts';

export type VorlageIdZustand = { zustand: 'laedt' | 'geladen' | 'fehler'; vorlageId: string | null };
/** Abo-Sicht (Trip oder Orts-Briefing): gelesen werden nur `display_config` und `profil`. */
export type AboArg = { display_config?: object | null; profil?: unknown } | null | undefined;

const cache = new Map<string, string>();

export function erstelleVorlagenIdLader(
	client: AufloesungClient,
	melde: (zustaende: VorlageIdZustand[]) => void
): { laden(abos: AboArg[]): Promise<void> } {
	let ticket = 0;
	return {
		async laden(abos) {
			const eintraege = abos.map((a) => eintragAusAbo(a as Parameters<typeof eintragAusAbo>[0]));
			const schluessel = eintraege.map((e) => JSON.stringify(e));
			const offen = [...new Set(schluessel.filter((s) => !cache.has(s)))];
			const stand = (fehler: boolean): VorlageIdZustand[] =>
				schluessel.map((s) => {
					const id = cache.get(s);
					if (id !== undefined) return { zustand: 'geladen', vorlageId: id };
					return { zustand: fehler ? 'fehler' : 'laedt', vorlageId: null };
				});
			const meins = ++ticket;
			melde(stand(false));
			if (offen.length === 0) return;
			try {
				const ergebnisse = await loeseAmpelnAuf(client, offen.map((s) => eintraege[schluessel.indexOf(s)]));
				if (meins !== ticket) return;
				offen.forEach((s, i) => cache.set(s, ergebnisse[i].vorlage_id));
				melde(stand(false));
			} catch {
				if (meins === ticket) melde(stand(true));
			}
		}
	};
}
