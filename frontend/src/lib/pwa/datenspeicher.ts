// Inhaltsspeicher (`gz-daten-<mandant>`) des Service Workers — Mandantentrennung,
// Hoechstalter und Raeumen. Issue #2131 (Ablage), Issue #2961 (Haertung).
// Spec: docs/specs/modules/pwa_offline_ansicht_letzter_stand.md · ADR-0063
//       docs/specs/modules/security_haertung_2026_11_frontend.md
//
// Ausgelagert aus `service-worker.ts`, damit die Regeln ohne Worker-Umgebung
// pruefbar sind: jede Funktion bekommt den Gerätespeicher (`CacheStorage`)
// bzw. einen einzelnen Speicher (`Cache`) uebergeben.
//
// Drei Zusicherungen:
//   1. Jede Antwort mit Mandantenkennung raeumt fremde Inhaltsspeicher — nicht
//      erst die Ablage einer Positivlisten-Ansicht (ADR-0063 §4).
//   2. Gelesen wird nur aus dem Inhaltsspeicher des zuletzt angemeldeten
//      Mandanten. Weil (1) bei jeder angemeldeten Antwort greift, ist das der
//      einzige verbliebene; liegen ausnahmsweise mehrere, wird keiner benutzt.
//   3. Nichts Vorgehaltenes ist aelter als HOECHSTALTER_MS; Aelteres wird beim
//      Zugriff und beim Aktivieren des Workers entfernt.

import { DATEN_ENDUNG } from './ansicht.ts';
import type { OfflineEintrag } from './standDokument.ts';

/** Namenspraefix der Inhaltsspeicher, getrennt vom Programm-Speicher `gz-<version>`. */
export const DATEN_PRAEFIX = 'gz-daten-';

/** Kennung des Mandanten, gesetzt von `hooks.server.ts`. */
export const MANDANT_HEADER = 'x-gz-mandant';

/** Ablagezeitpunkt (ISO), den der Worker jeder abgelegten Antwort mitgibt. */
export const ABLAGE_HEADER = 'x-gz-abgelegt';

/** Buchfuehrung ueber die vorgehaltenen Ansichten (Verdraengung + Uebersicht). */
export const INDEX_SCHLUESSEL = '/__gz-offline-index';

/** Hoechstalter einer vorgehaltenen Ansicht: 30 Tage. */
export const HOECHSTALTER_MS = 30 * 24 * 60 * 60 * 1000;

type Speicher = Pick<CacheStorage, 'keys' | 'open' | 'delete'>;

/** Namen aller Inhaltsspeicher. */
export async function datenSpeicherNamen(speicher: Speicher): Promise<string[]> {
	return (await speicher.keys()).filter((name) => name.startsWith(DATEN_PRAEFIX));
}

/** Loescht jeden Inhaltsspeicher ausser `eigener`. */
export async function fremdeDatenspeicherLoeschen(speicher: Speicher, eigener: string): Promise<void> {
	for (const name of await datenSpeicherNamen(speicher)) {
		if (name !== eigener) await speicher.delete(name);
	}
}

/**
 * Traegt die Antwort eine Mandantenkennung, faellt jeder fremde Inhaltsspeicher
 * — gleich, ob die Antwort selbst abgelegt wird. Ohne Kennung: nichts.
 */
export async function nachMandantRaeumen(speicher: Speicher, antwort: Response): Promise<void> {
	const mandant = antwort.headers.get(MANDANT_HEADER);
	if (!mandant) return;
	await fremdeDatenspeicherLoeschen(speicher, DATEN_PRAEFIX + mandant);
}

/** Loescht alle Inhaltsspeicher; der Programm-Speicher bleibt. */
export async function datenspeicherLoeschen(speicher: Speicher): Promise<void> {
	for (const name of await datenSpeicherNamen(speicher)) await speicher.delete(name);
}

/**
 * Der Inhaltsspeicher des zuletzt angemeldeten Mandanten — oder `null`, wenn
 * keiner oder (fail-closed) mehr als einer vorliegt.
 */
export async function aktuellerDatenspeicher(speicher: Speicher): Promise<Cache | null> {
	const namen = await datenSpeicherNamen(speicher);
	if (namen.length !== 1) return null;
	return speicher.open(namen[0]);
}

/**
 * Erlaubte Abweichung in die Zukunft (Uhrkorrektur des Geraets). Ein
 * Ablagezeitpunkt weiter in der Zukunft ist unplausibel und gilt als
 * abgelaufen — sonst hielte er eine Ansicht beliebig lange frisch.
 */
export const ZUKUNFT_TOLERANZ_MS = 5 * 60 * 1000;

/** Ist ein Ablagezeitpunkt aelter als das Hoechstalter, unplausibel neu oder unlesbar? */
export function istAbgelaufen(stand: string | null | undefined, jetzt: number): boolean {
	if (!stand) return true;
	const zeit = Date.parse(stand);
	if (!Number.isFinite(zeit)) return true;
	if (zeit - jetzt > ZUKUNFT_TOLERANZ_MS) return true;
	return jetzt - zeit > HOECHSTALTER_MS;
}

/** Buchfuehrung eines Inhaltsspeichers; unlesbar = leer. */
export async function indexLesen(cache: Cache): Promise<OfflineEintrag[]> {
	const treffer = await cache.match(INDEX_SCHLUESSEL);
	if (!treffer) return [];
	try {
		const roh = (await treffer.json()) as unknown;
		return Array.isArray(roh) ? (roh as OfflineEintrag[]) : [];
	} catch {
		return [];
	}
}

/** Schreibt die Buchfuehrung zurueck. */
export async function indexSchreiben(cache: Cache, eintraege: OfflineEintrag[]): Promise<void> {
	await cache.put(
		INDEX_SCHLUESSEL,
		new Response(JSON.stringify(eintraege), { headers: { 'content-type': 'application/json' } })
	);
}

/** Pfad der Ansicht zu einem Speicher-Schluessel (Seite oder `__data.json`). */
function ansichtZu(pfad: string): string {
	return pfad.endsWith(DATEN_ENDUNG) ? pfad.slice(0, -DATEN_ENDUNG.length) : pfad;
}

/**
 * Entfernt alles, was aelter als das Hoechstalter ist: Eintraege der
 * Buchfuehrung samt Seite und `__data.json`, dazu jede abgelegte Antwort, deren
 * eigener Ablagezeitpunkt (oder ersatzweise der ihrer Ansicht) zu alt ist.
 */
export async function abgelaufeneEntfernen(cache: Cache, jetzt: number): Promise<void> {
	const eintraege = await indexLesen(cache);
	const behalten = eintraege.filter((e) => !istAbgelaufen(e.stand, jetzt));
	for (const alt of eintraege.filter((e) => istAbgelaufen(e.stand, jetzt))) {
		await cache.delete(alt.pfad);
		await cache.delete(alt.pfad + DATEN_ENDUNG);
	}
	if (behalten.length !== eintraege.length) await indexSchreiben(cache, behalten);

	const standJeAnsicht = new Map(behalten.map((e) => [e.pfad, e.stand]));
	for (const anfrage of await cache.keys()) {
		const pfad = new URL(anfrage.url).pathname;
		if (pfad === INDEX_SCHLUESSEL) continue;
		const antwort = await cache.match(anfrage);
		const stand = antwort?.headers.get(ABLAGE_HEADER) ?? standJeAnsicht.get(ansichtZu(pfad));
		if (istAbgelaufen(stand, jetzt)) await cache.delete(anfrage);
	}
}

/** Entfernt Abgelaufenes aus allen Inhaltsspeichern (Aktivieren des Workers). */
export async function alleAbgelaufenenEntfernen(speicher: Speicher, jetzt: number): Promise<void> {
	for (const name of await datenSpeicherNamen(speicher)) {
		await abgelaufeneEntfernen(await speicher.open(name), jetzt);
	}
}

/**
 * Eine vorgehaltene Antwort fuer `schluessel` — nur aus dem Speicher des
 * zuletzt angemeldeten Mandanten und nur, wenn sie das Hoechstalter nicht
 * ueberschritten hat.
 */
export async function vorgehalteneAntwort(
	speicher: Speicher,
	schluessel: string,
	jetzt: number
): Promise<Response | undefined> {
	const cache = await aktuellerDatenspeicher(speicher);
	if (!cache) return undefined;
	await abgelaufeneEntfernen(cache, jetzt);
	return (await cache.match(schluessel)) ?? undefined;
}

/** Buchfuehrung des zuletzt angemeldeten Mandanten, ohne Abgelaufenes. */
export async function vorgehalteneAnsichten(speicher: Speicher, jetzt: number): Promise<OfflineEintrag[]> {
	const cache = await aktuellerDatenspeicher(speicher);
	if (!cache) return [];
	await abgelaufeneEntfernen(cache, jetzt);
	return indexLesen(cache);
}
