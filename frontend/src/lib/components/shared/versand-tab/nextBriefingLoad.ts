// nextBriefingLoad — Issue #1969 (Nächstes Briefing), AC-18/AC-19.
// Spec: docs/specs/modules/feat_1969_naechstes_briefing.md
//
// EINE Lade-Naht für den Backend-Wert: GET /api/next-briefings?trip_id=|?preset_id=
// → { trips: {id: NB}, compare: {id: NB} }. Kein Zwischenspeicher — jeder
// Aufruf fragt das Backend (Neuladen nach Speichern, AC-18). Fehler, kaputte
// Antwort oder fehlender Eintrag ⇒ null (Anzeige „—", AC-19).

import type { NextBriefing } from './nextBriefingText.ts';

export type Holen = (pfad: string) => Promise<unknown>;

/** Abfrage-Parameter und Antwort-Bereich je Abo-Art (Datentabelle statt Verzweigung). */
const ADRESSE: Record<'route' | 'vergleich', { param: string; bereich: string }> = {
	route: { param: 'trip_id', bereich: 'trips' },
	vergleich: { param: 'preset_id', bereich: 'compare' }
};

export async function ladeNaechstesBriefing(
	holen: Holen,
	context: 'route' | 'vergleich',
	id: string
): Promise<NextBriefing | null> {
	const { param, bereich } = ADRESSE[context] ?? ADRESSE.route;
	try {
		const antwort = await holen(`/api/next-briefings?${param}=${encodeURIComponent(id)}`);
		if (antwort == null || typeof antwort !== 'object') return null;
		const eintraege = (antwort as Record<string, unknown>)[bereich];
		if (eintraege == null || typeof eintraege !== 'object') return null;
		if (!Object.prototype.hasOwnProperty.call(eintraege, id)) return null;
		const nb = (eintraege as Record<string, unknown>)[id];
		return nb != null && typeof nb === 'object' ? (nb as NextBriefing) : null;
	} catch {
		return null;
	}
}
