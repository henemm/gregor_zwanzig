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
//
// Issue #2794 S3a (Teil-PR 2): vier Reiter Übersicht · Etappen|Orte · Wetter ·
// Zustellung; Versand-Abschnitt (`#versand`) steht im Reiter Zustellung.

import { tr, type MessageKey } from '../../i18n/index.ts';

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
 *  Anlege-Kette = [...anlegeKopf[kind], ...schwanz].
 *  Issue #2658 (i18n F9): `label`/`lockHint` der Definition sind Katalog-Schluessel
 *  (aktionen.* wortgleich fuer beide Hubs, trip.anlegen.*, vergleich.anlegen.*); der
 *  Text entsteht erst in `subscriptionTabs`/`anlegeKette` in der aktuellen Sprache.
 *  Ein Wert, der kein Schluessel ist, steht unveraendert (translate-Rueckfall). */
export interface ReiterDefinition {
	uebersicht: SubscriptionTab;
	punkte: Record<SubscriptionKind, SubscriptionTab>;
	schwanz: SubscriptionTab[];
	anlegeKopf: Record<SubscriptionKind, AnlegeSchritt[]>;
}

export const REITER_DEFINITION: ReiterDefinition = {
	uebersicht: { id: 'uebersicht', label: 'aktionen.reiter.uebersicht' },
	punkte: {
		trip: { id: 'etappen', label: 'aktionen.reiter.etappen_wegpunkte' },
		vergleich: { id: 'orte', label: 'aktionen.reiter.orte' }
	},
	// Issue #2794 S3a (Teil-PR 2): Wetter · Zustellung ersetzen Wetter-Metriken ·
	// Wertebereiche · Alarme (Alt-Kennungen werden ueber LEGACY umgeleitet).
	schwanz: [
		{ id: 'wetter', label: 'aktionen.reiter.wetter' },
		{ id: 'zustellung', label: 'aktionen.reiter.zustellung' }
	],
	anlegeKopf: {
		trip: [
			{ id: 'route', label: 'trip.anlegen.reiter_route' },
			{ id: 'etappen', label: 'trip.anlegen.reiter_etappen', lockHint: 'trip.anlegen.sperre_etappen' },
			{ id: 'wegpunkte', label: 'trip.anlegen.reiter_wegpunkte', lockHint: 'trip.anlegen.sperre_gpx', optional: true }
		],
		vergleich: [
			{ id: 'vergleich', label: 'vergleich.anlegen.reiter' },
			{ id: 'orte', label: 'aktionen.reiter.orte', lockHint: 'vergleich.anlegen.sperre_orte' }
		]
	}
};

/** Anlege-eigene Sperr-Hinweise der Schwanz-Schritte (Kennung/Label kommen aus `schwanz`).
 *  Der Hinweis eines Schritts nennt den Vorgaenger; der erste Schwanz-Schritt haengt am
 *  Kopf und ist daher kind-eigen. */
const ANLEGE_SCHWANZ_HINWEIS: Record<SubscriptionKind, Record<string, string>> = {
	trip: { wetter: 'trip.anlegen.sperre_gpx' },
	vergleich: { wetter: 'vergleich.anlegen.sperre_wetter' }
};

/** Schluessel (oder freier Text einer ersetzten Definition) in der aktuellen Sprache. */
const text = (k: string): string => tr(k as MessageKey);

/** Sperr-Hinweis eines Schwanz-Schritts: kind-eigen oder „erst <Vorgaenger> öffnen". */
function schwanzHinweis(kind: SubscriptionKind, schwanz: SubscriptionTab[], i: number): string | undefined {
	const eigen = ANLEGE_SCHWANZ_HINWEIS[kind][schwanz[i].id];
	if (eigen !== undefined) return text(eigen);
	return i > 0 ? tr('aktionen.sperre.oeffnen', { reiter: text(schwanz[i - 1].label) }) : undefined;
}

/** Reiterleiste in der Reihenfolge beider Hubs (Desktop und MTabBar). */
export function subscriptionTabs(kind: SubscriptionKind, def: ReiterDefinition = REITER_DEFINITION): SubscriptionTab[] {
	return [def.uebersicht, def.punkte[kind], ...def.schwanz].map((t) => ({ id: t.id, label: text(t.label) }));
}

/** Schrittfolge der Anlege-Seite je kind — Schwanz aus derselben Definition wie der Hub. */
export function anlegeKette(kind: SubscriptionKind, def: ReiterDefinition = REITER_DEFINITION): AnlegeSchritt[] {
	const kopf = def.anlegeKopf[kind].map((s) => {
		const schritt: AnlegeSchritt = { ...s, label: text(s.label) };
		if (s.lockHint !== undefined) schritt.lockHint = text(s.lockHint);
		return schritt;
	});
	const schwanz = def.schwanz.map((t, i) => {
		const schritt: AnlegeSchritt = { id: t.id, label: text(t.label) };
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
	/** #1743: Sprungziel im Reiter (Versand-Abschnitt, seit #2794 im Reiter Zustellung). Fehlt sonst ganz. */
	anchor?: 'versand';
}

/**
 * Alt-Kennungen (Lesezeichen, Verlauf, geteilte Links) — kind-uebergreifend.
 * `stages` zeigt auf den Punkte-Reiter und wird je kind aufgeloest.
 */
const LEGACY: Record<string, string> = {
	overview: 'uebersicht',
	stages: 'punkte',
	weather: 'wetter',
	alerts: 'wetter',
	briefings: 'zustellung',
	versand: 'zustellung',
	preview: 'uebersicht',
	vorschau: 'uebersicht',
	idealwerte: 'wetter',
	layout: 'wetter',
	// Issue #2794 S3a: die Reiter von #1743 bis Teil-PR 1
	'wetter-metriken': 'wetter',
	wertebereiche: 'wetter',
	alarme: 'zustellung'
};

/** #1743: Alt-Kennungen, die auf den Versand-Abschnitt springen (seit #2794 im Reiter Zustellung). */
const LEGACY_ANKER: Record<string, 'versand'> = { briefings: 'versand', versand: 'versand' };

const FALLBACK: ResolvedTab = { tab: 'uebersicht', legacy: false, known: false };

const hat = (o: object, k: string): boolean => Object.prototype.hasOwnProperty.call(o, k);

/** Reiter, in dem der Versand-Abschnitt (`#versand`) steht (#2794 S3a). */
const VERSAND_REITER = 'zustellung';

/**
 * Kennung → Reiter. `hash` = Anker der geladenen Adresse (`#versand`): der Anker
 * gewinnt gegen die Reiterkennung (#2794 S3a §1) — eine bekannte Kennung mit
 * `#versand` landet im Reiter Zustellung mit Anker `versand`.
 */
export function resolveTab(kind: SubscriptionKind, raw: string | null | undefined, hash?: string | null): ResolvedTab {
	const r = resolveKennung(kind, raw);
	if (!r.known || r.tab === VERSAND_REITER || (hash !== '#versand' && hash !== 'versand')) return r;
	return { tab: VERSAND_REITER, legacy: true, known: true, anchor: 'versand' };
}

function resolveKennung(kind: SubscriptionKind, raw: string | null | undefined): ResolvedTab {
	if (typeof raw !== 'string') return { ...FALLBACK };
	// i18n F9: nur Kennungen vergleichen (kein Text) — die Aufloesung bleibt sprachunabhaengig.
	const def = REITER_DEFINITION;
	if ([def.uebersicht, def.punkte[kind], ...def.schwanz].some((t) => t.id === raw)) return { tab: raw, legacy: false, known: true };
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
