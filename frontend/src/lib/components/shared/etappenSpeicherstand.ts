// Issue #2347 S2 (AC-6/AC-13, Fix-Loop 1 F001): Rueckfall-Stand des Etappen-Reiters.
//
// Scheitert ein Auto-Save der Etappen (Nicht-412, nicht beim „Nochmal speichern"),
// fallen die Etappen sichtbar auf den zuletzt vom Server BESTAETIGTEN Stand zurueck —
// nicht auf den Oeffnungsstand und nicht auf den Stand vor der einzelnen Eingabe
// (`schedule` buendelt mehrere Eingaben zu einem PUT). Muster: Rollback der
// Ortsvergleich-Schreiber (*VergleichSpeicherung.ts, CompareTabs `persistPickedIds`).
//
// Zwei PUT-Clients, beide merken sich jede erfolgreiche Server-Antwort:
//   - `autoSaveClient`: Auto-Save ueber den Speicher-Regler, MIT Rollback.
//   - `direktClient`:   Kaskade und manuelles Speichern, OHNE Rollback — die Kaskade
//                       hat ihren eigenen Fehlerweg (#1393 R4, issue-498 AC-32).
//
// BEWUSST svelte-frei (unter node:test ladbar).

import type { PutClient } from './tripSpeicherung.ts';

export interface EtappenStandOptionen<S> {
	/** Stand beim Oeffnen (wird kopiert; darf ein $state-Proxy sein). */
	start: S[];
	/** Der eigentliche PUT-Weg (`api`). */
	client: PutClient;
	/** Laeuft gerade „Nochmal speichern"? (`SaveStatus.imWiederholen`) */
	imWiederholen: () => boolean;
	/** Setzt die angezeigten Etappen (bekommt eine eigene Kopie). */
	zuruecksetzen: (stand: S[]) => void;
}

export interface EtappenStand<S> {
	/** Kopie des zuletzt vom Server bestaetigten Etappen-Stands. */
	bestaetigt(): S[];
	autoSaveClient: PutClient;
	direktClient: PutClient;
}

// JSON-Kopie statt structuredClone: `start` kann ein Svelte-$state-Proxy sein
// (structuredClone wirft dort DataCloneError); Etappen sind reine JSON-Daten.
const kopie = <T>(x: T): T => JSON.parse(JSON.stringify(x)) as T;

function etappenAus<S>(antwort: unknown): S[] | null {
	const s = (antwort as { stages?: unknown } | null | undefined)?.stages;
	return Array.isArray(s) ? (s as S[]) : null;
}

export function erstelleEtappenStand<S>(opt: EtappenStandOptionen<S>): EtappenStand<S> {
	let bestaetigt: S[] = kopie(opt.start);

	async function direktPut<T>(pfad: string, rumpf: unknown, init?: RequestInit): Promise<T> {
		const antwort = await opt.client.put<T>(pfad, rumpf, init);
		const etappen = etappenAus<S>(antwort);
		if (etappen) bestaetigt = kopie(etappen);
		return antwort;
	}

	async function autoSavePut<T>(pfad: string, rumpf: unknown, init?: RequestInit): Promise<T> {
		try {
			return await direktPut<T>(pfad, rumpf, init);
		} catch (e) {
			// 412: „Nochmal speichern" braucht die ungespeicherte Eingabe. Beim Wiederholen
			// selbst ebenso — sonst faende der naechste Versuch keinen Unterschied mehr.
			if ((e as { status?: number })?.status !== 412 && !opt.imWiederholen()) {
				opt.zuruecksetzen(kopie(bestaetigt));
			}
			throw e;
		}
	}

	return {
		bestaetigt: () => kopie(bestaetigt),
		autoSaveClient: { put: autoSavePut },
		direktClient: { put: direktPut }
	};
}
