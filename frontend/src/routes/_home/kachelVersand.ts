// Issue #2346 S2 (AC-18) — Versand-Werte der Startseiten-Kachel (beide kinds).
// Keine eigene Faelligkeitsrechnung: der naechste Versand kommt ausschliesslich aus der
// Backend-Antwort GET /api/next-briefings (#1969) ueber formatNextBriefing (at===null => Grund,
// fehlende Antwort => "—"). Letzter Versand (S4): fuer beide kinds aus `last_briefing` derselben Antwort.
// Pure Funktion, relative Importe — node:testbar.

import type { ComparePreset, Trip } from '../../lib/types.ts';
import type { SubscriptionKind } from '../../lib/components/shared/subscriptionTabs.ts';
import { formatNextBriefing, type NextBriefing } from '../../lib/components/shared/versand-tab/nextBriefingText.ts';
import { relativeLastSent } from '../../lib/components/compare/subscriptionHelpers.ts';

/** Antwort von GET /api/next-briefings: getrennte Maps je kind (#1969). */
export type NextBriefings = {
	trips?: Record<string, NextBriefing>;
	compare?: Record<string, NextBriefing>;
} | null | undefined;

/** Eintrag der Sammelantwort fuer genau dieses kind (Trip -> `trips`, Vergleich -> `compare`). */
export function kachelNextBriefing(kind: SubscriptionKind, id: string | undefined, nbs: NextBriefings): NextBriefing | null {
	if (!id || !nbs) return null;
	return (kind === 'trip' ? nbs.trips : nbs.compare)?.[id] ?? null;
}

export function kachelVersand(
	kind: SubscriptionKind,
	sub: Trip | ComparePreset,
	nb: NextBriefing | null | undefined
): { nextSend: string; lastSent: string | null } {
	const nextSend = formatNextBriefing(nb, kind === 'trip' ? 'route' : 'vergleich');
	// #2346 S4: beide kinds aus derselben Quelle (last_briefing der Sammelantwort).
	const lastSent = relativeLastSent(nb?.last_briefing ?? undefined) || null;
	return { nextSend, lastSent };
}
