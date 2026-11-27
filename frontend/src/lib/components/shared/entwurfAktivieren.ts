// Issue #3443 (S5d aus #2797, Epic #2791) — „Aktivieren“ im Entwurf (Kopf-Knopf und Kebab).
// Spec: docs/specs/modules/feat_3443_entwurf_aktivieren.md (Implementation Details 3 und 4).
// Ein Entwurf ist ein abgeleiteter Zustand (es fehlen Daten): der Klick schaltet nichts ein, er nennt,
// was fehlt, und nennt die Stelle, an der es sich ergänzen lässt. Reine Funktionen, EIN Code für Trip
// und Orts-Vergleich (ADR-0097), Texte nur über den Katalog in der aktuellen Sprache — node:testbar.

import type { ComparePreset, Trip } from '../../types.js';
import { tr, type MessageKey } from '../../i18n/index.ts';
import type { SubscriptionKind } from './subscriptionTabs.ts';
import type { SubscriptionLifecycle } from './subscriptionActions.ts';
import { formatNextBriefing, type NextBriefing } from './versand-tab/nextBriefingText.ts';
import { deriveStatusFromPreset } from '../compare/subscriptionHelpers.ts';

export type AktivierungsTeil = 'etappen_datum' | 'name' | 'orte';

/** Was am Entwurf fehlt — wiederholt die Regeln von deriveTripStatus / deriveStatusFromPreset unverändert. */
export function fehltFuerAktivierung(kind: SubscriptionKind, objekt: Trip | ComparePreset): AktivierungsTeil[] {
	if (kind === 'trip') {
		const stages = (objekt as Trip).stages ?? [];
		return stages.some((s) => !!s.date) ? [] : ['etappen_datum'];
	}
	const p = objekt as ComparePreset;
	const teile: AktivierungsTeil[] = [];
	if (!p.name) teile.push('name');
	if ((p.location_ids ?? []).length === 0) teile.push('orte');
	return teile;
}

/** Ganze Sätze je Fall (keine Grammatik-Zusammensetzung), Schlüssel aus sortierten Teilen. */
const HINWEIS: Record<string, MessageKey> = {
	etappen_datum: 'aktionen.aktivieren.hinweis_etappen_datum',
	orte: 'aktionen.aktivieren.hinweis_orte',
	name: 'aktionen.aktivieren.hinweis_name',
	'name+orte': 'aktionen.aktivieren.hinweis_name_orte'
};

export function hinweisFuer(teile: readonly AktivierungsTeil[]): string | null {
	const key = HINWEIS[[...teile].sort().join('+')];
	return key ? tr(key) : null;
}

/** Reiter, in dem sich das Fehlende ergänzen lässt; fehlt nur der Name, bleibt die Seite stehen. */
const ZIEL: Record<AktivierungsTeil, string | null> = {
	etappen_datum: '?tab=etappen',
	orte: '?tab=orte',
	name: null
};

export function zielFuer(_kind: SubscriptionKind, teile: readonly AktivierungsTeil[]): string | null {
	for (const teil of teile) if (ZIEL[teil]) return ZIEL[teil];
	return null;
}

/** Nur der Wechsel Entwurf → aktiv ist eine Aktivierung (nie beim ersten Lesen). */
export function warAktivierung(vorher: SubscriptionLifecycle | undefined, nachher: SubscriptionLifecycle): boolean {
	return vorher === 'draft' && nachher === 'active';
}

/**
 * Orte-Hub nach einem erfolgreichen Speichern: nur im Entwurf den gespeicherten Stand prüfen (sonst
 * `null` ⇒ kein Abruf); übernommen wird er nur, wenn er den Entwurf aktiviert — sonst bleibt der Hub stehen.
 */
export function aktivierungsUebernahme(lifecycle: SubscriptionLifecycle): ((frisch: ComparePreset) => boolean) | null {
	if (lifecycle !== 'draft') return null;
	return (frisch) => deriveStatusFromPreset(frisch) !== 'draft';
}

/** „Aktiviert. Das erste Briefing kommt {wann}.“ — ohne Termin nur „Aktiviert.“, nie eine erfundene Zeit. */
export function aktiviertText(nb: NextBriefing | null | undefined, context: 'route' | 'vergleich'): string {
	if (nb && typeof nb === 'object' && nb.at != null) {
		const wann = formatNextBriefing(nb, context);
		if (wann !== '—') return tr('aktionen.aktivieren.erfolg_mit_zeit', { wann });
	}
	return tr('aktionen.aktivieren.erfolg');
}
