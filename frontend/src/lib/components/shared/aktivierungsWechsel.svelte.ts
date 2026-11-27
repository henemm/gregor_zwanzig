// Issue #3443 (S5d aus #2797) — „Aktiviert“-Meldung nach dem Wechsel Entwurf → aktiv.
// Spec: docs/specs/modules/feat_3443_entwurf_aktivieren.md (Implementation Details 4).
// Runen-Modul: beobachtet den Lebenszyklus der Seite (Trip wie Orte, EIN Code); nur beim Wechsel
// draft → active (warAktivierung) wird genau einmal „nächstes Briefing“ geholt und gemeldet.
// Laufnummer wie naechstesBriefingLader: eine spät eintreffende ältere Antwort meldet nie.

import { untrack } from 'svelte';
import { ladeNaechstesBriefing, type Holen } from './versand-tab/nextBriefingLoad.ts';
import { aktiviertText, warAktivierung } from './entwurfAktivieren.ts';
import type { SubscriptionLifecycle } from './subscriptionActions.ts';

export interface AktivierungsQuelle {
	context: 'route' | 'vergleich';
	/** Fehlt ⇒ kein Abruf. */
	id: string | undefined;
	lifecycle: SubscriptionLifecycle;
}

export function erstelleAktivierungsWechsel(
	quelle: () => AktivierungsQuelle,
	holen: Holen,
	beiMeldung: (text: string) => void
): void {
	let vorher: SubscriptionLifecycle | undefined;
	let lauf = 0;
	$effect(() => {
		const q = quelle();
		const war = vorher;
		vorher = q.lifecycle;
		if (war === q.lifecycle) return;
		const meinLauf = ++lauf;
		const { context, id } = q;
		if (!warAktivierung(war, q.lifecycle) || !id) return;
		untrack(() =>
			ladeNaechstesBriefing(holen, context, id).then((nb) => {
				if (meinLauf === lauf) beiMeldung(aktiviertText(nb, context));
			})
		);
	});
}
