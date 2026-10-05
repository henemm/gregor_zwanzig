// Issue #2287 (Epic #2345, Etappe P2 „eine Reiterleiste"): EINE Reiter-Tabelle und
// EINE Aufloesung fuer Trip- und Ortsvergleich-Hub. Beide Hubs fuehren dieselben
// Kennungen; einziger kind-eigener Reiter ist der Punkte-Reiter (Trip `etappen`,
// Vergleich `orte`). Ersetzt `compare/compareTabsResolve.ts` und die Trip-eigene
// Tabelle in `TripTabs.svelte`.

export type SubscriptionKind = 'trip' | 'vergleich';

export interface SubscriptionTab {
	id: string;
	label: string;
}

export interface ResolvedTab {
	tab: string;
	/** true = Alt- oder kind-fremde Kennung; der Hub bereinigt die Adresszeile einmal. */
	legacy: boolean;
	/** false = unbekannte Kennung (Rest-Fallback Uebersicht, tab-Parameter entfernen). */
	known: boolean;
}

const PUNKTE: Record<SubscriptionKind, SubscriptionTab> = {
	trip: { id: 'etappen', label: 'Etappen & Wegpunkte' },
	vergleich: { id: 'orte', label: 'Orte' }
};

/** Reiterleiste in der Reihenfolge beider Hubs (Desktop und MTabBar). */
export function subscriptionTabs(kind: SubscriptionKind): SubscriptionTab[] {
	return [
		{ id: 'uebersicht', label: 'Übersicht' },
		PUNKTE[kind],
		{ id: 'wetter-metriken', label: 'Wetter-Metriken' },
		{ id: 'wertebereiche', label: 'Wertebereiche' },
		{ id: 'alarme', label: 'Alarme' },
		{ id: 'versand', label: 'Versand' },
		{ id: 'vorschau', label: 'Vorschau' }
	];
}

/**
 * Alt-Kennungen (Lesezeichen, Verlauf, geteilte Links) — kind-uebergreifend.
 * `stages` zeigt auf den Punkte-Reiter und wird je kind aufgeloest.
 */
const LEGACY: Record<string, string> = {
	overview: 'uebersicht',
	stages: 'punkte',
	weather: 'wetter-metriken',
	alerts: 'wertebereiche',
	briefings: 'versand',
	preview: 'vorschau',
	idealwerte: 'wertebereiche',
	layout: 'wetter-metriken'
};

const FALLBACK: ResolvedTab = { tab: 'uebersicht', legacy: false, known: false };

export function resolveTab(kind: SubscriptionKind, raw: string | null | undefined): ResolvedTab {
	if (typeof raw !== 'string') return { ...FALLBACK };
	if (subscriptionTabs(kind).some((t) => t.id === raw)) return { tab: raw, legacy: false, known: true };
	const alt = Object.prototype.hasOwnProperty.call(LEGACY, raw) ? LEGACY[raw] : undefined;
	if (alt !== undefined) {
		return { tab: alt === 'punkte' ? PUNKTE[kind].id : alt, legacy: true, known: true };
	}
	const fremd = PUNKTE[kind === 'trip' ? 'vergleich' : 'trip'].id;
	if (raw === fremd) return { tab: PUNKTE[kind].id, legacy: true, known: true };
	return { ...FALLBACK };
}

/**
 * Bereinigte Adresse (Pfad + Query + Hash) fuer eine aufgeloeste Kennung, oder
 * `null`, wenn nichts umzuschreiben ist. Alt-/kind-fremde Kennung → `?tab=<neu>`;
 * unbekannte Kennung → Parameter `tab` entfernt (Spec E3/E4, AC-3/AC-6).
 * Nach dem Umschreiben ist die Kennung neu (`legacy: false`) → keine Schleife.
 */
export function bereinigteTabAdresse(href: string, r: ResolvedTab): string | null {
	if (r.known && !r.legacy) return null;
	const url = new URL(href);
	if (r.known) {
		url.searchParams.set('tab', r.tab);
	} else {
		if (!url.searchParams.has('tab')) return null;
		url.searchParams.delete('tab');
	}
	return url.pathname + url.search + url.hash;
}
