// Issue #2795 S3b, Teilschritt 1b (AC-30): Telegram-Kurzstil — Formen der Teilfeld-Nutzlast (Trip
// `report_config`, Orte `display_config.telegram_style`).
// Issue #3154 (#3122 B3b, Spec feat_3122_was_steht_wo.md Teil B Nr. 14): die Bedienung im Uebergangsblock
// (KanalStil, eigener Speicherer mit Owner 'kanal-stil') ist entfernt. Den Kurzstil schaltet allein die Karte
// „Was steht wo“ (wasStehtWoSpeicherung.ts formt ihre Nutzlast hier); den Ausblick je Briefing schreibt die
// Karte als `outlook_reports`.
// Issue #3297 (Spec feat_3297_trip_pfad_ohne_altfelder.md AC-4): der unsichtbare Mehrtages-Trend-Schalter ist
// ersatzlos entfernt (ADR-0124 Nr. 6) — die Nutzlast traegt nur noch `telegram_style`, keine Trend-Felder.
//
// Kein Browser-/SvelteKit-Import — lauffaehig unter node --experimental-strip-types.

import type { Kontext } from './zustellungModell.ts';

export interface KanalStilStand {
	stil: 'rich' | 'kurzform';
}

/** #3047 E2: mit `vorher` nur bei geaendertem Stil. */
function tripNutzlast(s: KanalStilStand, vorher?: KanalStilStand): Record<string, unknown> {
	const stil = !vorher || vorher.stil !== s.stil;
	return { report_config: stil ? { telegram_style: s.stil } : {} };
}

/** Kontext-Unterschiede als Daten (Ratsche context_herkunft_zweige_eingefroren). */
const KONTEXT: Record<Kontext, { nutzlast: (s: KanalStilStand, vorher?: KanalStilStand) => Record<string, unknown>; pfad: (id: string) => string }> = {
	route: { nutzlast: tripNutzlast, pfad: (id) => `/api/trips/${id}` },
	vergleich: {
		nutzlast: (s) => ({ display_config: { telegram_style: s.stil } }),
		pfad: (id) => `/api/compare/presets/${id}`
	}
};

/** Nutzlast: Trip unter report_config (Kurzstil), Orte display_config.telegram_style.
 *  `vorher` = zuletzt gespeicherter Stand: der Trip sendet dann nur, was sich geaendert hat (#3047 E2). */
export function kanalStilNutzlast(context: Kontext, s: KanalStilStand, vorher?: KanalStilStand): Record<string, unknown> {
	return KONTEXT[context].nutzlast(s, vorher);
}
