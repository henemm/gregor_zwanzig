// Issue #2794 S3a, Teil-PR 3 (Reiter Wetter), Stufe 3.2: der EINE Speicherer des Reiters (AC-38).
// Spec: docs/specs/modules/feat_2794_s3a_teil3_wetter.md, Datenfluss „Speichern" und „Konflikt".
//
//   Trip (`route`): ein Speichervorgang aus zwei disjunkten PUTs wie bisher (`tripSpeicherung.ts`):
//     PUT /api/trips/{id}/weather-config mit `ampel` + `metrics` (display_config-Teil), danach
//     PUT /api/trips/{id} mit `official_alerts_enabled`, `official_warnings`, `report_config`.
//   Orts-Briefing (`vergleich`): EIN Eintrag in der Hub-Schreibschlange (If-Match), nur die
//     Eigenfelder (display_config `ampel` + `active_metrics`, Warn-Felder, Radar, Tagesfenster);
//     der Server mergt display_config auf Ebene 1. Bei 412 laedt der Reiter Abo und Aufloesung neu (die
//     fremde Aenderung bleibt sichtbar und wird nicht still ueberschrieben) und meldet den Konflikt
//     an den Controller („Nochmal speichern" sendet danach den neu geladenen Stand).
//   Anlegen (`createMode`): kein Netz — der Stand geht als Nutzlast an die Anlege-Seite.
//
// Die Rumpf-Funktionen lesen Stand und Abo erst beim Senden (keine eingefrorene Kopie).
// Kein Browser-/SvelteKit-Import, lauffaehig unter node --experimental-strip-types.

import { getKnownEtag, setKnownEtag } from '../../../etagRegistry.ts';
import type { SaveFn, SaveStatus } from '../../../stores/saveStatusStore.svelte.ts';
import { baueWetterMetrikenSpeicherung, mitKonfliktSchluessel } from '../tripSpeicherung.ts';
import { eintragAusAbo, loeseAmpelnAuf, type Aufgeloest, type AufloesungClient } from './ampelAufloesung.ts';
import { tripSpeicherPayload, vergleichSpeicherPayload } from './ampelSchreiben.ts';
import type { AltSchluessel, VorlagenAmpeln } from './ampelModell.ts';
import type { WarnFelder } from './amtlicheWarnungen.ts';
import { vorlageImKontext, type AboSicht, type WetterStand } from './wetterZustand.ts';

/** Besitzer des Speicher-Platzes im Controller (nie die Reiterkennung `wetter`, s. Owner-Waechter). */
export const WETTER_OWNER = 'wetter-ampel';

export interface SchreibClient extends AufloesungClient {
	get<T>(path: string): Promise<T>;
	put<T>(path: string, body: unknown, init?: RequestInit): Promise<T>;
}

export type SpeicherOptionen = {
	client: SchreibClient;
	/** Aktueller Bearbeitungsstand (Getter: erst beim Senden gelesen). */
	stand: () => WetterStand;
	vorlagen: () => VorlagenAmpeln;
	/** Lebender Abo-Stand der Seite (Trip bzw. Vergleich). */
	abo: () => AboSicht;
	saveController?: SaveStatus;
	enqueueHubWrite?: <T>(fn: () => Promise<T>) => Promise<T>;
	/** Server-Antwort an die Seite (Trip bzw. Vergleich); `gesendet` = das placements-Objekt, das dieser
	 *  Speichervorgang wirklich gesendet hat (#3237 Runde 14), sonst `undefined`. */
	uebernehmen?: (antwort: unknown, gesendet?: unknown) => void;
	/** Vergleich: nach 412 neu geladenes Abo samt Aufloesung, der Reiter hydriert daraus neu (synchron). */
	neuGeladen?: (abo: AboSicht, aufgeloest: Aufgeloest) => void;
	/** Anlegen: Nutzlast an die Anlege-Seite statt PUT. */
	anlegen?: (nutzlast: unknown) => void;
	/** Vergleich: Auswertung je neu hinzugefuegter Metrik (Katalog der Vergleichs-Metriken). */
	aggregationFuer?: (id: string) => string;
	/** Vergleich: Altformat-Schluessel von `active_metrics` -> Groesse (Fix-Loop 3, C2). */
	altSchluessel?: AltSchluessel;
	/** #3122 B3b (Spec Nr. 13, AC-32): vollstaendiger Stand der Tabelle „Was steht wo“, wenn „−“/„+“ ihn
	 *  im selben Speichervorgang mitschreiben muss; `undefined` = nichts mitsenden (keine gespeicherte Tabelle). */
	placements?: () => unknown;
};

/** `placements` nur, wenn die Karte einen Stand zum Mitspeichern liefert (sonst bleibt der Schluessel weg). */
function mitPlacements(o: SpeicherOptionen): { placements?: unknown } {
	const p = o.placements?.();
	return p === undefined ? {} : { placements: p };
}

export type Speicherer = { melden(): void };

/** Trip-Nutzlast aus Stand und lebendem Abo (zwei disjunkte Teile). */
export function tripNutzlast(o: SpeicherOptionen) {
	const s = o.stand();
	const abo = o.abo();
	// #3193: gespeichert wird die Abweichung gegen die Vorlage im Kontext (wie der Zaehler).
	const basis = vorlageImKontext(s, o.vorlagen(), 'route', o.altSchluessel);
	const teile = tripSpeicherPayload({
		vorlage: basis.vorlage,
		aufgeloest: basis.aufgeloest,
		auswahl: s.auswahl,
		displayConfig: (abo.display_config ?? {}) as Parameters<typeof tripSpeicherPayload>[0]['displayConfig'],
		warnFelder: abo as WarnFelder,
		warnungenAn: s.warnungenAn,
		radarAn: s.radarAn,
		tagesfenster: s.tagesfenster
	});
	return { ...teile, weatherConfig: { ...teile.weatherConfig, ...mitPlacements(o) } };
}

/** Vergleichs-Nutzlast: nur Eigenfelder, display_config nur `ampel` + `active_metrics`. */
export function vergleichNutzlast(o: SpeicherOptionen) {
	const s = o.stand();
	const abo = o.abo();
	const basis = vorlageImKontext(s, o.vorlagen(), 'vergleich', o.altSchluessel);
	const voll = vergleichSpeicherPayload({
		vorlage: basis.vorlage,
		aufgeloest: basis.aufgeloest,
		auswahl: s.auswahl,
		displayConfig: (abo.display_config ?? {}) as Parameters<typeof vergleichSpeicherPayload>[0]['displayConfig'],
		aggregationFuer: o.aggregationFuer ?? (() => 'max'),
		altSchluessel: o.altSchluessel,
		warnFelder: abo as WarnFelder,
		warnungenAn: s.warnungenAn,
		radarAn: s.radarAn,
		tagesfenster: s.tagesfenster
	});
	const { ampel, active_metrics } = voll.display_config as { ampel: unknown; active_metrics?: unknown };
	// #3047 E1: ungesetzte Grundauswahl bleibt ungesetzt (kein Schluessel in der Nutzlast).
	return { ...voll, display_config: { ampel, ...(active_metrics === undefined ? {} : { active_metrics }), ...mitPlacements(o) } };
}

function tripSpeicherer(o: SpeicherOptionen): Speicherer {
	return {
		melden() {
			const id = String(o.abo().id);
			// #3237 Runde 14: der Rumpf wird mehrfach gelesen (Nutzlast-Merker, dann Senden); die LETZTE Lesung des
			// /weather-config-Teils ist die gesendete — nur deren placements gelten nach Erfolg als gespeichert.
			let gesendet: unknown;
			const wetter = () => {
				const w = tripNutzlast(o).weatherConfig as { placements?: unknown };
				gesendet = w.placements;
				return w;
			};
			const fn = baueWetterMetrikenSpeicherung<unknown>(
				o.client,
				id,
				wetter,
				() => tripNutzlast(o).tripFelder,
				(antwort) => o.uebernehmen?.(antwort, gesendet),
				WETTER_OWNER
			);
			o.saveController?.schedule(fn, 700, 'wetter-ampel');
		}
	};
}

/** Gemeldete Speichervorgaenge je Vergleichs-Kennung (Modulzustand wie die ETag-Registry: gilt ueber einen
 *  Reiterwechsel hinweg). Nur eine Meldung laeuft spaeter als Speichern nach. */
const meldungen = new Map<string, number>();
const meldungenVon = (id: string): number => meldungen.get(id) ?? 0;

/** Nach 412: Abo und Aufloesung holen, erst dann Seite und Reiter in einem Zug ersetzen; scheitert eines,
 *  bleibt der alte Stand. Dann gilt auch wieder der Stempel von vor dem GET (Muster `retryConflict`):
 *  mit dem frischen ginge die naechste Eingabe durch und ueberschriebe die fremde Aenderung still.
 *  Ebenso, wenn seit `bezug` ein weiteres Speichern gemeldet wurde (F005): es laeuft nach, trifft wieder auf
 *  412 und laedt neu (auch nach Zuruecknehmen). Eine Eingabe ohne Meldung (F008: gleicher Wert, gleiche
 *  Vorlage) laeuft nicht nach, dann wird geladen: massgeblich sind Meldungen, nicht das Stand-Objekt. */
async function nachKonfliktLaden(o: SpeicherOptionen, pfad: string, id: string, bezug: number): Promise<void> {
	const stempelVorGet = getKnownEtag(id);
	const frisch = await o.client.get<AboSicht>(pfad).catch(() => null);
	if (!frisch) return;
	const [aufgeloest] = await loeseAmpelnAuf(o.client, [eintragAusAbo(frisch)]).catch((): Aufgeloest[] => []);
	if (!aufgeloest || meldungenVon(id) !== bezug) {
		if (stempelVorGet !== undefined) setKnownEtag(id, stempelVorGet);
		return;
	}
	o.uebernehmen?.(frisch);
	o.neuGeladen?.(frisch, aufgeloest);
}

/** Ein Vergleichs-PUT in der Hub-Schlange; bei 412 neu laden, dann den Konflikt melden. */
function vergleichSaveFn(o: SpeicherOptionen): SaveFn {
	// Bezug beim ersten Lauf ist die eigene Meldung: jede spaetere hat einen eigenen, noch wartenden Vorgang
	// (auch wenn dieser PUT ihre Eingabe schon traegt). „Nochmal speichern" misst ab dem Senden.
	let gemeldet: number | undefined = meldungenVon(String(o.abo().id));
	const fn: SaveFn = async (init) => {
		const id = String(o.abo().id);
		const pfad = `/api/compare/presets/${id}`;
		const reihe = o.enqueueHubWrite ?? (<T>(f: () => Promise<T>) => f());
		await reihe(async () => {
			const bezug = gemeldet ?? meldungenVon(id);
			gemeldet = undefined;
			try {
				const nutzlast = vergleichNutzlast(o);
				const gesendet = (nutzlast.display_config as { placements?: unknown }).placements;
				o.uebernehmen?.(await o.client.put<unknown>(pfad, nutzlast, init), gesendet);
			} catch (e) {
				if ((e as { status?: number })?.status === 412) await nachKonfliktLaden(o, pfad, id, bezug);
				throw e;
			}
		});
	};
	return mitKonfliktSchluessel(fn, WETTER_OWNER);
}

function vergleichSpeicherer(o: SpeicherOptionen): Speicherer {
	return {
		melden() {
			const id = String(o.abo().id);
			meldungen.set(id, meldungenVon(id) + 1);
			o.saveController?.schedule(vergleichSaveFn(o), 700, 'wetter-ampel');
		}
	};
}

/** Anlegen: dieselbe Nutzlast wie beim Speichern, aber an die Anlege-Seite (kein PUT). */
const ANLEGE_NUTZLAST: Record<'route' | 'vergleich', (o: SpeicherOptionen) => unknown> = {
	route: tripNutzlast,
	vergleich: vergleichNutzlast
};

export function anlegeSpeicherer(o: SpeicherOptionen, kind: 'route' | 'vergleich'): Speicherer {
	return { melden: () => o.anlegen?.(ANLEGE_NUTZLAST[kind](o)) };
}

/** Der Speicherer je Kontext (Tabelle statt Kontext-Weiche). */
export const SPEICHERER: Record<'route' | 'vergleich', (o: SpeicherOptionen) => Speicherer> = {
	route: tripSpeicherer,
	vergleich: vergleichSpeicherer
};
