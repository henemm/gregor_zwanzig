// Issue #3122 B3b — Speichern der Karte „Was steht wo“ (Spec Teil B Nr. 13; AC-20, AC-29).
//
// Tabelle: jede Änderung meldet die Karte hier (`aenderung`); der Hub-Controller entprellt (Besitzer
// 'was-steht-wo') und ruft den Vorgang, der den VOLLSTÄNDIGEN lokalen Stand erst beim Senden liest und per
// PUT /api/briefings/{id}/placements?kind=… schreibt. Der PUT läuft über `api` und damit durch die
// Schreib-Warteschlange des Abos mit If-Match (etagRegistry.ts) — hinter jedem anderen Schreibvorgang
// desselben Abos, nie daneben. Danach holt ein frisches GET Beispielwerte, Marken und SMS-Beispiel.
//   Reihenfolge: eine Versionsnummer zählt lokale Änderungen. Ein GET wird nur übernommen, wenn seit seinem
//   Start keine lokale Änderung kam und kein jüngeres GET schon übernommen wurde — so überschreibt nie ein
//   älterer Stand einen neueren, und ein Klick während eines Speichervorgangs geht nicht verloren (er
//   fährt mit dem nächsten PUT mit).
//   412: Konflikt melden, eigene Änderung verwerfen, aktuellen Stand laden, Fehler weiterwerfen (der
//   Controller zeigt den Konflikt wie bei jedem Reiter des Hubs). Anderer Fehler: melden, gespeicherten
//   Stand laden, weiterwerfen (Controller zeigt den Fehler).
// Schalter unter der Tabelle (Blöcke, Kanal-Einstellungen): nur geänderte Felder an ihrem heutigen Ort
// (Trip `report_config` bzw. `display_config.show_night_block`, Orte `hourly_enabled` bzw.
// `display_config.telegram_style`) über den geteilten Teilfeld-PUT (`baueSpeicherung`); den Kurzstil
// formt `kanalStilNutzlast` wie bisher im Übergangsblock.
// Kein Browser-/SvelteKit-Import, lauffähig unter node --experimental-strip-types.

import type { SaveFn } from '../../../stores/saveStatusStore.svelte.ts';
import { baueSpeicherung, mitKonfliktSchluessel, type PutClient } from '../tripSpeicherung.ts';
import { kanalStilNutzlast } from '../zustellung-tab/kanalStilSpeicherung.ts';
import type { Placements, PlacementsAntwort } from './wasStehtWoStand.ts';

export type Kind = 'route' | 'vergleich';
/** Besitzer im Hub-Controller (Entprellung je Besitzer, Konflikt-Schlüssel). */
export const TABELLE_OWNER = 'was-steht-wo';
export const FELDER_OWNER = 'was-steht-wo-schalter';

export interface LeseSchreibClient extends PutClient {
	get<T>(path: string): Promise<T>;
	/** #3305: nur im Anlege-Modus (Vorschau des Entwurfs). */
	post?<T>(path: string, body: unknown): Promise<T>;
}
export interface Planer {
	schedule(fn: SaveFn, ms?: number, owner?: string): void;
}

export const tabellenPfad = (kind: Kind, id: string) => `/api/briefings/${encodeURIComponent(id)}/placements?kind=${kind}`;
/** #3305: Vorschau eines noch nicht angelegten Entwurfs (#3304, `stored=false`, schreibt nichts). */
export const vorschauPfad = (kind: Kind) => `/api/briefings/placements/vorschau?kind=${kind}`;
/** #3305: Entprellung des Nachladens nach einem Metrikwechsel im Anlegen. */
const VORSCHAU_MS = 400;

/** #3305: Stand der Karte im Anlegen — geht mit dem einen Anlege-POST, nie per PUT. */
export interface KarteAnlegeStand {
	placements: Placements;
	felder: Felder;
	/** Schalter beim Start der Karte; der POST wendet nur die Differenz dazu an. */
	felderStart: Felder;
}

export interface TabellenOptionen {
	client: LeseSchreibClient;
	kind: Kind;
	id: string;
	saveController?: Planer;
	/** Aktueller lokaler Stand (gelesen erst beim Senden). */
	placements: () => Placements | null;
	/** Frische Antwort in die Karte. */
	uebernehmen: (a: PlacementsAntwort) => void;
	gemeldet?: (art: 'konflikt' | 'fehler', e: unknown) => void;
	/** #3305 Anlege-Modus: Entwurf für die Vorschau (gelesen erst beim Senden). Gesetzt = kein GET, kein PUT. */
	entwurf?: () => Record<string, unknown>;
	/** #3305: entprelltes Nachladen der Vorschau ist gescheitert. */
	vorschauFehler?: (e: unknown) => void;
}

export interface TabellenSpeicherung {
	/** Lokale Änderung ist geschehen: Speichern einplanen. */
	aenderung(): void;
	/** Frisches GET (übernommen nur nach den Reihenfolge-Regeln). */
	laden(): Promise<void>;
	/** Ein anderer Speicherweg des Hubs hat das Abo geschrieben: neu laden, wenn nichts ungespeichert ist. */
	nachFremdemSpeichern(): void;
	/** „−“/„+“/Vorlagenwechsel des Reiters: lokaler Stand geändert, OHNE eigenen PUT — der PUT des Reiters
	 *  trägt ihn mit (#3237 Runde 13). Ein eigener Tabellen-PUT verdrängte über den Besitzerwechsel des
	 *  Controllers die Entprellung des Reiters (zwei Gesten = zwei Schreibvorgänge) und lief bei veraltetem
	 *  Stempel vor dem Reiter-PUT in den 412. Ältere GETs werden trotzdem verworfen (Version zählt). */
	mitgefuehrt(): void;
	/** Der Reiter liest den Stand zum Mitsenden (nur bei gespeicherter Tabelle, sonst `undefined`). Das
	 *  gelieferte Objekt trägt die Versionsmarke seines Stands (#3237 Runde 14). */
	zumMitsenden(tabelleGespeichert: boolean): Placements | undefined;
	/** Der Reiter-PUT ist gespeichert. `gesendet` = das placements-Objekt, das dieser PUT wirklich trug:
	 *  nur dessen Stand gilt als gespeichert; danach neu laden, wenn nichts ungespeichert ist. */
	nachReiterSpeichern(gesendet?: unknown): void;
	/** #3305 Anlege-Modus: Metrikwechsel — Vorschau entprellt neu laden (mehrere Aufrufe = ein POST). */
	vorschauNachMetrik(): void;
	readonly ungespeichert: boolean;
}

/** #3305: Vorschau-Rumpf = Entwurf; ein lokaler Stand steht in `display_config.placements`. */
function vorschauRumpf(entwurf: Record<string, unknown>, p: Placements | null): Record<string, unknown> {
	if (!p) return entwurf;
	const dc = (entwurf.display_config ?? {}) as Record<string, unknown>;
	return { ...entwurf, display_config: { ...dc, placements: p } };
}

export function erstelleTabellenSpeicherung(o: TabellenOptionen): TabellenSpeicherung {
	const pfad = tabellenPfad(o.kind, o.id);
	let version = 0;
	let gespeichert = 0;
	let ausgegeben = 0;
	let uebernommen = 0;
	/** Versionsmarke je mitgesendetem placements-Objekt (#3237 Runde 14). */
	const marken = new WeakMap<object, number>();
	const anlegen = Boolean(o.entwurf);
	let vorschauUhr: ReturnType<typeof setTimeout> | undefined;
	const holen = (): Promise<PlacementsAntwort> =>
		o.entwurf
			? o.client.post!<PlacementsAntwort>(vorschauPfad(o.kind), vorschauRumpf(o.entwurf(), o.placements()))
			: o.client.get<PlacementsAntwort>(pfad);

	async function laden(): Promise<void> {
		const ticket = { nr: ++ausgegeben, version };
		const a = await holen();
		if (ticket.nr < uebernommen || ticket.version !== version) return;
		uebernommen = ticket.nr;
		o.uebernehmen(a);
	}
	const ladenStill = () => void laden().catch(() => {});

	const fn: SaveFn = async (init) => {
		if (version === gespeichert) return;
		const body = o.placements();
		if (!body) return;
		const gesendet = version;
		try {
			await o.client.put(pfad, body, init);
		} catch (e) {
			gespeichert = version;
			o.gemeldet?.((e as { status?: number })?.status === 412 ? 'konflikt' : 'fehler', e);
			ladenStill();
			throw e;
		}
		gespeichert = Math.max(gespeichert, gesendet);
		if (version === gesendet) ladenStill();
	};
	const vorgang = mitKonfliktSchluessel(fn, TABELLE_OWNER);

	return {
		aenderung() {
			version += 1;
			// #3305: im Anlegen kein PUT, kein Planen — der Stand geht mit dem Anlege-POST.
			if (anlegen) return;
			if (o.saveController) o.saveController.schedule(vorgang, 700, TABELLE_OWNER);
			else void vorgang().catch(() => {});
		},
		laden,
		nachFremdemSpeichern() {
			if (version === gespeichert) ladenStill();
		},
		mitgefuehrt() {
			version += 1;
		},
		zumMitsenden(tabelleGespeichert: boolean) {
			// #3305: im Anlegen gibt es nie eine gespeicherte Tabelle — der lokale Stand zählt immer.
			const p = tabelleGespeichert || anlegen ? o.placements() : null;
			if (!p) return undefined;
			// Eigene Identität je Auswertung: der Speicherer liest mehrfach, gespeichert gilt nur, was gesendet wurde.
			const objekt = { ...p };
			marken.set(objekt, version);
			return objekt;
		},
		nachReiterSpeichern(gesendet?: unknown) {
			const v = gesendet && typeof gesendet === 'object' ? marken.get(gesendet) : undefined;
			if (v !== undefined) gespeichert = Math.max(gespeichert, v);
			if (version === gespeichert) ladenStill();
		},
		vorschauNachMetrik() {
			if (!anlegen) return;
			clearTimeout(vorschauUhr);
			vorschauUhr = setTimeout(() => void laden().catch((e) => o.vorschauFehler?.(e)), VORSCHAU_MS);
		},
		get ungespeichert() {
			return version !== gespeichert;
		}
	};
}

// ── Schalter unter der Tabelle ────────────────────────────────────────────────

export interface Felder {
	show_stage_stats: boolean;
	show_yesterday_comparison: boolean;
	show_night_block: boolean;
	email_format: 'full' | 'compact';
	telegram_style: 'rich' | 'kurzform';
	hourly_enabled: boolean;
}
type Rumpf = Record<string, unknown>;

/** Startwerte der Schalter aus `blocks` der Antwort (fehlende Werte: Vorgaben des Python-Kerns). */
export function felderAusAntwort(a: Pick<PlacementsAntwort, 'blocks'>): Felder {
	const b = (a?.blocks ?? {}) as Record<string, unknown>;
	return {
		show_stage_stats: b.show_stage_stats !== false,
		show_yesterday_comparison: b.show_yesterday_comparison !== false,
		show_night_block: b.show_night_block !== false,
		email_format: b.email_format === 'compact' ? 'compact' : 'full',
		telegram_style: b.telegram_style === 'kurzform' ? 'kurzform' : 'rich',
		hourly_enabled: b.hourly !== false
	};
}

const geaendert = <K extends keyof Felder>(neu: Felder, alt: Felder, k: K) => neu[k] !== alt[k];
function nurGeaendert(neu: Felder, alt: Felder, keys: (keyof Felder)[]): Rumpf {
	return Object.fromEntries(keys.filter((k) => geaendert(neu, alt, k)).map((k) => [k, neu[k]]));
}
function zusammen(...teile: Rumpf[]): Rumpf {
	const aus: Rumpf = {};
	for (const t of teile) {
		for (const [k, v] of Object.entries(t)) {
			if (v && typeof v === 'object' && !Array.isArray(v)) {
				const innen = { ...((aus[k] as Rumpf) ?? {}), ...(v as Rumpf) };
				if (Object.keys(innen).length) aus[k] = innen;
			} else aus[k] = v;
		}
	}
	return aus;
}
/** Kurzstil wie im Übergangsblock (Trip `report_config.telegram_style`, Orte `display_config.telegram_style`). */
function kurzstil(kind: Kind, neu: Felder, alt: Felder): Rumpf {
	if (!geaendert(neu, alt, 'telegram_style')) return {};
	const s = { stil: neu.telegram_style, trendMorgen: false, trendAbend: false };
	return kanalStilNutzlast(kind, s, { ...s, stil: alt.telegram_style });
}

/** Teilfeld-Rumpf: nur, was sich gegenüber `alt` geändert hat. */
export function felderNutzlast(kind: Kind, neu: Felder, alt: Felder): Rumpf {
	if (kind === 'route') {
		const rc = nurGeaendert(neu, alt, ['show_stage_stats', 'show_yesterday_comparison', 'email_format']);
		const dc = nurGeaendert(neu, alt, ['show_night_block']);
		return zusammen(Object.keys(rc).length ? { report_config: rc } : {}, kurzstil(kind, neu, alt), Object.keys(dc).length ? { display_config: dc } : {});
	}
	// #3059: Orte tragen das E-Mail-Format in `display_config` (wie den Kurzstil); Teilfeld, der Server mischt
	// `display_config` feldweise (Read-Modify-Write) — `telegram_style` und alle übrigen Felder bleiben.
	const dc = nurGeaendert(neu, alt, ['email_format']);
	return zusammen(nurGeaendert(neu, alt, ['hourly_enabled']), kurzstil(kind, neu, alt), Object.keys(dc).length ? { display_config: dc } : {});
}

const FELDER_PFAD: Record<Kind, (id: string) => string> = {
	route: (id) => `/api/trips/${id}`,
	vergleich: (id) => `/api/compare/presets/${id}`
};

export function erstelleFelderSpeicherung(o: {
	client: PutClient;
	kind: Kind;
	id: string;
	saveController?: Planer;
	enqueueHubWrite?: <T>(fn: () => Promise<T>) => Promise<T>;
	start: Felder;
	onAntwort?: (antwort: unknown) => void;
	/** Fix-Loop F1: Speichern gescheitert -> Anzeige auf den gespeicherten Stand `stand` zurück (412 wie Fehler). */
	onFehler?: (e: unknown, stand: Felder) => void;
}): { melden(neu: Felder): void } {
	let aktuell: Felder = { ...o.start };
	let bezug: Felder = { ...o.start };
	const fn: SaveFn = async (init) => {
		const gesendet = { ...aktuell };
		const rumpf = felderNutzlast(o.kind, gesendet, bezug);
		if (!Object.keys(rumpf).length) return;
		const lauf = () =>
			baueSpeicherung<unknown>(o.client, FELDER_PFAD[o.kind](o.id), rumpf, (antwort) => {
				bezug = gesendet;
				o.onAntwort?.(antwort);
			})(init);
		try {
			await (o.enqueueHubWrite ? o.enqueueHubWrite(lauf) : lauf());
		} catch (e) {
			// Die gescheiterte Änderung fährt nicht still mit dem nächsten Schalter mit.
			aktuell = { ...bezug };
			o.onFehler?.(e, { ...bezug });
			throw e;
		}
	};
	const vorgang = mitKonfliktSchluessel(fn, FELDER_OWNER);
	return {
		melden(neu: Felder) {
			aktuell = { ...neu };
			if (o.saveController) o.saveController.schedule(vorgang, 700, FELDER_OWNER);
			else void vorgang().catch(() => {});
		}
	};
}
