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
// Laufende Anfragen je Eintrag (modulweit): weitere Verbraucher bzw. Effekt-Neulaeufe warten darauf,
// statt erneut anzufragen (Staging-Befund S3a: drei identische POSTs je Seitenaufruf).
const laufend = new Map<string, Promise<string>>();

/** Startet EINE gebuendelte Anfrage fuer `neu`; Erfolg landet im Cache, Fehler nicht. */
function starte(client: AufloesungClient, neu: string[], eintraege: ReturnType<typeof eintragAusAbo>[]): void {
	const anfrage = loeseAmpelnAuf(client, eintraege);
	neu.forEach((s, i) => {
		const p = anfrage.then((ergebnisse) => {
			const id = ergebnisse[i].vorlage_id;
			cache.set(s, id);
			return id;
		});
		laufend.set(s, p);
		const aufraeumen = () => {
			if (laufend.get(s) === p) laufend.delete(s);
		};
		p.then(aufraeumen, aufraeumen);
	});
}

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
			const neu = offen.filter((s) => !laufend.has(s));
			if (neu.length > 0) starte(client, neu, neu.map((s) => eintraege[schluessel.indexOf(s)]));
			try {
				await Promise.all(offen.map((s) => laufend.get(s)));
				if (meins !== ticket) return;
				melde(stand(false));
			} catch {
				if (meins === ticket) melde(stand(true));
			}
		}
	};
}
