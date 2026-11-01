// briefingHistoryLader — Issue #2682 (Epic #2345), Entscheidung 3 / AC-12.
//
// EIN Laden der Versand-Historie für die Hub-Übersicht: die Kennzahl „Zuletzt
// raus" und die Liste in BriefingHistory lesen dieselbe Antwort (kein zweiter
// Abruf). Muster: versand-tab/naechstesBriefingLader.svelte.ts.
//
// Regeln:
//   - geladen wird, sobald `id` da ist (ohne id: kein Abruf, Zustand „laedt");
//   - Laufnummer: eine spät eintreffende Antwort für eine alte Kennung wird
//     verworfen (Stale-Guard), auch wenn die id inzwischen weggefallen ist;
//   - Fehler ⇒ Zustand „fehler" (Anzeige „—" bzw. Fehlertext der Liste).

import { briefingHistoryUrl, type BriefingHistoryEntry, type BriefingHistoryKind } from './briefingHistory.ts';
import { neuesterPlanmaessigerEintrag } from './hub-uebersicht/hubUebersichtModell.ts';

export type BriefingHistoryZustand = 'laedt' | 'geladen' | 'fehler';

export interface BriefingHistoryLader {
	readonly zustand: BriefingHistoryZustand;
	/** Chronologisch wie vom Server (älteste zuerst). */
	readonly eintraege: BriefingHistoryEntry[];
	/** neuesterPlanmaessigerEintrag(eintraege) — dieselbe Regel wie das Modell. */
	readonly neuesterPlanmaessiger: BriefingHistoryEntry | null;
}

export function erstelleBriefingHistoryLader(
	quelle: () => { kind: BriefingHistoryKind; id?: string },
	holen: (pfad: string) => Promise<unknown>
): BriefingHistoryLader {
	let zustand = $state<BriefingHistoryZustand>('laedt');
	let eintraege = $state<BriefingHistoryEntry[]>([]);
	let lauf = 0;
	$effect(() => {
		const q = quelle();
		// Laufnummer VOR dem Rücksprung: fällt die id weg, wird eine laufende Antwort verworfen.
		const meinLauf = ++lauf;
		zustand = 'laedt';
		eintraege = [];
		if (!q.id) return;
		holen(briefingHistoryUrl(q.id, q.kind)).then(
			(daten) => {
				if (meinLauf !== lauf) return;
				eintraege = Array.isArray(daten) ? (daten as BriefingHistoryEntry[]) : [];
				zustand = 'geladen';
			},
			() => {
				if (meinLauf === lauf) zustand = 'fehler';
			}
		);
	});
	const neuester = $derived(neuesterPlanmaessigerEintrag(eintraege));
	return {
		get zustand() {
			return zustand;
		},
		get eintraege() {
			return eintraege;
		},
		get neuesterPlanmaessiger() {
			return neuester;
		}
	};
}
