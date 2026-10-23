// Issue #2287 (Epic #2345, Etappe P2 „eine Reiterleiste"): EINE Reiter-Tabelle und
// EINE Aufloesung fuer Trip- und Ortsvergleich-Hub. Beide Hubs fuehren dieselben
// Kennungen; einziger kind-eigener Reiter ist der Punkte-Reiter (Trip `etappen`,
// Vergleich `orte`). Ersetzt `compare/compareTabsResolve.ts` und die Trip-eigene
// Tabelle in `TripTabs.svelte`.
//
// Issue #1743: fuenf Reiter (`versand`/`vorschau` entfallen; Versand steht unten im
// Reiter Wetter-Metriken, Anker `#versand`). Hub-Leiste UND Anlege-Kette
// (/trips/new, /compare/new) werden aus EINER Definition (`REITER_DEFINITION`)
// abgeleitet — eine zweite Liste gibt es nicht.

export type SubscriptionKind = 'trip' | 'vergleich';

export interface SubscriptionTab {
	id: string;
	label: string;
}

/** Anlege-Schritt: Reiter plus anlege-eigene Zusatzfelder (#1743). */
export interface AnlegeSchritt extends SubscriptionTab {
	lockHint?: string;
	optional?: boolean;
}

/** Die EINE Definition. Hub-Leiste = [uebersicht, punkte[kind], ...schwanz];
 *  Anlege-Kette = [...anlegeKopf[kind], ...schwanz]. */
export interface ReiterDefinition {
	uebersicht: SubscriptionTab;
	punkte: Record<SubscriptionKind, SubscriptionTab>;
	schwanz: SubscriptionTab[];
	anlegeKopf: Record<SubscriptionKind, AnlegeSchritt[]>;
}

export const REITER_DEFINITION: ReiterDefinition = {
	uebersicht: { id: 'uebersicht', label: 'Übersicht' },
	punkte: {
		trip: { id: 'etappen', label: 'Etappen & Wegpunkte' },
		vergleich: { id: 'orte', label: 'Orte' }
	},
	schwanz: [
		{ id: 'wetter-metriken', label: 'Wetter-Metriken' },
		{ id: 'wertebereiche', label: 'Wertebereiche' },
		{ id: 'alarme', label: 'Alarme' }
	],
	anlegeKopf: {
		trip: [
			{ id: 'route', label: 'Route' },
			{ id: 'etappen', label: 'Etappen & GPX', lockHint: 'erst Trip-Name + Startdatum' },
			{ id: 'wegpunkte', label: 'Wegpunkte prüfen', lockHint: 'erst alle GPX hochladen', optional: true }
		],
		vergleich: [
			{ id: 'vergleich', label: 'Vergleich' },
			{ id: 'orte', label: 'Orte', lockHint: 'erst Vergleich benennen' }
		]
	}
};

/** Anlege-eigene Sperr-Hinweise der Schwanz-Schritte (Kennung/Label kommen aus `schwanz`).
 *  Der Hinweis eines Schritts nennt den Vorgaenger; der erste Schwanz-Schritt haengt am
 *  Kopf und ist daher kind-eigen. */
const ANLEGE_SCHWANZ_HINWEIS: Record<SubscriptionKind, Record<string, string>> = {
	trip: { 'wetter-metriken': 'erst alle GPX hochladen' },
	vergleich: { 'wetter-metriken': 'erst mind. 2 Orte auswählen' }
};

/** Sperr-Hinweis eines Schwanz-Schritts: kind-eigen oder „erst <Vorgaenger> öffnen". */
function schwanzHinweis(kind: SubscriptionKind, schwanz: SubscriptionTab[], i: number): string | undefined {
	const eigen = ANLEGE_SCHWANZ_HINWEIS[kind][schwanz[i].id];
	if (eigen !== undefined) return eigen;
	return i > 0 ? `erst ${schwanz[i - 1].label} öffnen` : undefined;
}

/** Reiterleiste in der Reihenfolge beider Hubs (Desktop und MTabBar). */
export function subscriptionTabs(kind: SubscriptionKind, def: ReiterDefinition = REITER_DEFINITION): SubscriptionTab[] {
	return [def.uebersicht, def.punkte[kind], ...def.schwanz].map((t) => ({ id: t.id, label: t.label }));
}

/** Schrittfolge der Anlege-Seite je kind — Schwanz aus derselben Definition wie der Hub. */
export function anlegeKette(kind: SubscriptionKind, def: ReiterDefinition = REITER_DEFINITION): AnlegeSchritt[] {
	const kopf = def.anlegeKopf[kind].map((s) => ({ ...s }));
	const schwanz = def.schwanz.map((t, i) => {
		const schritt: AnlegeSchritt = { id: t.id, label: t.label };
		const hinweis = schwanzHinweis(kind, def.schwanz, i);
		if (hinweis !== undefined) schritt.lockHint = hinweis;
		return schritt;
	});
	return [...kopf, ...schwanz];
}

export interface ResolvedTab {
	tab: string;
	/** true = Alt- oder kind-fremde Kennung; der Hub bereinigt die Adresszeile einmal. */
	legacy: boolean;
	/** false = unbekannte Kennung (Rest-Fallback Uebersicht, tab-Parameter entfernen). */
	known: boolean;
	/** #1743: Sprungziel im Reiter (Versand-Abschnitt unter Wetter-Metriken). Fehlt sonst ganz. */
	anchor?: 'versand';
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
	briefings: 'wetter-metriken',
	versand: 'wetter-metriken',
	preview: 'uebersicht',
	vorschau: 'uebersicht',
	idealwerte: 'wertebereiche',
	layout: 'wetter-metriken'
};

/** #1743: Alt-Kennungen, die auf den Versand-Abschnitt springen. */
const LEGACY_ANKER: Record<string, 'versand'> = { briefings: 'versand', versand: 'versand' };

const FALLBACK: ResolvedTab = { tab: 'uebersicht', legacy: false, known: false };

const hat = (o: object, k: string): boolean => Object.prototype.hasOwnProperty.call(o, k);

export function resolveTab(kind: SubscriptionKind, raw: string | null | undefined): ResolvedTab {
	if (typeof raw !== 'string') return { ...FALLBACK };
	if (subscriptionTabs(kind).some((t) => t.id === raw)) return { tab: raw, legacy: false, known: true };
	if (hat(LEGACY, raw)) {
		const alt = LEGACY[raw];
		const r: ResolvedTab = { tab: alt === 'punkte' ? REITER_DEFINITION.punkte[kind].id : alt, legacy: true, known: true };
		if (hat(LEGACY_ANKER, raw)) r.anchor = LEGACY_ANKER[raw];
		return r;
	}
	const fremd = REITER_DEFINITION.punkte[kind === 'trip' ? 'vergleich' : 'trip'].id;
	if (raw === fremd) return { tab: REITER_DEFINITION.punkte[kind].id, legacy: true, known: true };
	return { ...FALLBACK };
}

/** #1743: Startwert des Sprung-Zaehlers der Hubs — 1, wenn die Kennung den Anker
 *  traegt oder die geladene Adresse `#versand` enthaelt, sonst 0 (SSR: kein window). */
export function versandSprungStart(r: ResolvedTab): number {
	if (r.anchor === 'versand') return 1;
	return typeof window !== 'undefined' && window.location?.hash === '#versand' ? 1 : 0;
}

/**
 * Bereinigte Adresse (Pfad + Query + Hash) fuer eine aufgeloeste Kennung, oder
 * `null`, wenn nichts umzuschreiben ist. Alt-/kind-fremde Kennung → `?tab=<neu>`
 * (#1743: mit Anker → Hash `#versand`); unbekannte Kennung → Parameter `tab`
 * entfernt (Spec E3/E4, AC-3/AC-6). Nach dem Umschreiben ist die Kennung neu
 * (`legacy: false`) → keine Schleife.
 */
export function bereinigteTabAdresse(href: string, r: ResolvedTab): string | null {
	if (r.known && !r.legacy) return null;
	const url = new URL(href);
	if (r.known) {
		url.searchParams.set('tab', r.tab);
		if (r.anchor) url.hash = r.anchor;
	} else {
		if (!url.searchParams.has('tab')) return null;
		url.searchParams.delete('tab');
	}
	return url.pathname + url.search + url.hash;
}
