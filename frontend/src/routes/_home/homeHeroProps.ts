// Issue #2346 S3 (AC-11/AC-12) — Verdrahtung des Startseiten-Heros als pure Funktion, damit die
// Zusicherungen dort pruefbar sind, wo sie wirken: +page.svelte reicht genau dieses Ergebnis per
// Spread an <HomeHero> (bewacht von home_hero_verdrahtung.test.ts). Kanaele aus den Flags
// (homeHeroChannels, nie empfaenger, #1452); naechster Versand wie die Kachel aus der
// Backend-Antwort GET /api/next-briefings (kachelVersand, keine eigene Faelligkeitsrechnung).

import type { ComparePreset, Trip } from '../../lib/types.ts';
import type { SubscriptionKind } from '../../lib/components/shared/subscriptionTabs.ts';
import { homeHeroChannels } from './homeHeroChannels.ts';
import { kachelNextBriefing, kachelVersand, type NextBriefings } from './kachelVersand.ts';
import { get } from 'svelte/store';
import { locale, trnFor, type Lang } from '../../lib/i18n/index.ts';

export interface HomeHeroProps {
	kind: SubscriptionKind;
	id: string;
	name: string;
	href: string;
	subtitle: string;
	channels: string[];
	nextSend: string;
}

/** Untertitel je kind: Trip = Region; Vergleich = Region (falls gesetzt) + Orte-Zahl. */
function untertitel(kind: SubscriptionKind, sub: Trip | ComparePreset, lang: Lang): string {
	if (kind === 'trip') return (sub as Trip).region ?? '';
	const preset = sub as ComparePreset;
	const region = (preset.display_config as Record<string, unknown> | undefined)?.region as string | undefined;
	const orte = trnFor(lang, 'home.hero.orte_verglichen', preset.location_ids.length);
	return region ? `${region} · ${orte}` : orte;
}

/** `lang`: Anzeigesprache (#2652); die Seite reicht `$locale`, damit der Untertitel dem Sprachwechsel folgt. */
export function homeHeroProps(
	kind: SubscriptionKind,
	sub: Trip | ComparePreset,
	nbs: NextBriefings,
	lang: Lang = get(locale)
): HomeHeroProps {
	return {
		kind,
		id: sub.id,
		name: sub.name,
		href: kind === 'trip' ? `/trips/${sub.id}?tab=uebersicht` : `/compare/${sub.id}`,
		subtitle: untertitel(kind, sub, lang),
		channels: homeHeroChannels(kind, sub),
		nextSend: kachelVersand(kind, sub, kachelNextBriefing(kind, sub.id, nbs)).nextSend
	};
}
