// Issue #3399 S1 Fix-Loop 1 (Adversary F001): Verdrahtung „Abo -> Lader -> Vorlagen-ID" des
// Alarme-Reiters als Runen-Modul, damit sie in der echten Svelte-Client-Laufzeit pruefbar ist
// (__tests__/abo_vorlage_id_laufzeit_3399.test.ts; Muster versand-tab/naechstesBriefingLader.svelte.ts).
//
// Regeln: geladen wird je Abo-Eintrag, solange kein Wert von aussen kommt (`extern`, auch null);
// beim Abo-Wechsel sofort null (Anzeige „—"), nie die alte ID; Fehler => null.

import { erstelleVorlagenIdLader, type AboArg } from '../wetter-tab/vorlagenIdLader.ts';
import type { AufloesungClient } from '../wetter-tab/ampelAufloesung.ts';

export interface AboVorlageQuelle {
	abo: AboArg;
	/** Wert von aussen (Testhaken); gesetzt (auch null) => kein eigener Abruf. */
	extern?: string | null;
}

export function erstelleAboVorlageId(quelle: () => AboVorlageQuelle, client: AufloesungClient): { readonly id: string | null } {
	let geladen = $state<string | null>(null);
	const lader = erstelleVorlagenIdLader(client, ([z]) => (geladen = z?.vorlageId ?? null));
	$effect(() => {
		const q = quelle();
		if (q.extern === undefined) void lader.laden([q.abo]);
	});
	return {
		get id() {
			const q = quelle();
			return q.extern !== undefined ? q.extern : geladen;
		}
	};
}
