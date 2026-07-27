// Issue #1395 S3 — ETag-Registry und Schreib-Warteschlange je Tour.
// Spec: docs/specs/modules/issue_1395_s3_etag_registry.md
// Server-Vertrag: docs/specs/modules/issue_1395_s2_etag_ifmatch.md · ADR-0036
//
// Bewusst ein Modul-Singleton (anders als saveStatusStore.svelte.ts, das eine
// Instanz je Editor-Oberflaeche verlangt): der Stempel ist ein Frischezustand
// der RESSOURCE (der Tour), nicht der Editor-Instanz. Genau das braucht der
// Kernfall — die zwei aufeinanderfolgenden Schreibvorgaenge des Wetter-Reiters
// und der unabhaengige Auto-Save des Alarme-Reiters auf derselben Tour muessen
// denselben Stand sehen. Zwei Browser-Tabs sind ohnehin getrennte JS-Realms mit
// je eigener Registry; der Schutz zwischen ihnen kommt vollstaendig vom Server.

const knownEtags = new Map<string, string>();
const writeQueues = new Map<string, Promise<unknown>>();

/**
 * F001 — zaehlt JEDE Veraenderung des Eintrags einer Tour (Setzen wie Verwerfen).
 * Ein Vorgang ausserhalb der Warteschlange (Lesevorgang, Entlade-Flush) erkennt
 * damit beim Eintreffen, ob inzwischen ein juengerer Stand hinterlegt wurde, und
 * verwirft seinen eigenen, dann veralteten Stempel. Ohne das ueberschreibt eine
 * langsam zurueckkommende Leseantwort den frischeren Stand — und der naechste
 * Schreibvorgang bekommt `412`, obwohl niemand sonst etwas geaendert hat.
 */
const etagVersions = new Map<string, number>();

function bumpVersion(tripId: string): void {
	etagVersions.set(tripId, (etagVersions.get(tripId) ?? 0) + 1);
}

/** Aktueller Aenderungszaehler dieser Tour (0 = noch nie beruehrt). */
export function etagVersion(tripId: string): number {
	return etagVersions.get(tripId) ?? 0;
}

/**
 * Nur exakt `/api/trips/{id}` und `/api/trips/{id}/weather-config` tragen laut
 * S2 einen ETag. `/state`, `/waypoints/{wp}/confirm` und alle uebrigen
 * Unterpfade matchen bewusst NICHT — dort prueft der Server kein `If-Match`
 * (S2 AC-15) und liefert keinen Stempel.
 */
const TRIP_PATH_RE = /^\/api\/trips\/([^/?#]+)(?:\/weather-config)?(?:[?#]|$)/;

/** Tour-Kennung eines Pfades, oder `null` fuer alle uebrigen Pfade. */
export function extractTripId(path: string): string | null {
	const match = TRIP_PATH_RE.exec(path);
	if (!match) return null;
	try {
		return decodeURIComponent(match[1]);
	} catch {
		return match[1];
	}
}

/** Zuletzt vom Server erhaltener Stand dieser Tour, oder `undefined`. */
export function getKnownEtag(tripId: string): string | undefined {
	return knownEtags.get(tripId);
}

/** Uebernimmt den vom Server gelieferten Stempel (Wert 1:1, inkl. Anfuehrungszeichen). */
export function setKnownEtag(tripId: string, etag: string): void {
	knownEtags.set(tripId, etag);
	bumpVersion(tripId);
}

/**
 * Uebernimmt den Stempel NUR, wenn der Eintrag seit `seenVersion` unberuehrt
 * blieb. Fuer alles, was nicht durch die Warteschlange serialisiert ist: sein
 * Stempel beschreibt den Stand zum Zeitpunkt SEINER Anfrage — verspaetet
 * eingetroffen waere er ein Rueckschritt. Nicht zu uebernehmen ist die sichere
 * Richtung: schlimmstenfalls laeuft der naechste Schreibvorgang ohne
 * Vorbedingung (Verhalten wie vor S3), statt faelschlich blockiert zu werden.
 */
export function setKnownEtagIfUnchanged(tripId: string, etag: string, seenVersion: number): boolean {
	if (etagVersion(tripId) !== seenVersion) return false;
	setKnownEtag(tripId, etag);
	return true;
}

/**
 * Stempel aus dem Seitenaufbau (Server-Naht) — nur, wenn diese Tour in dieser
 * Sitzung noch nie einen gefuehrt hat. Auch der Seitenaufbau ist ein
 * Lesevorgang, und sein Startzeitpunkt ist im Browser nicht greifbar: laeuft
 * `load()` erneut (Invalidierung), waehrend ein Speichervorgang unterwegs ist,
 * beschreibt sein Stempel den Stand VOR dem Speichern — derselbe Rueckschritt
 * wie F001. Ist schon etwas bekannt, ist der bekannte Wert mindestens so jung.
 */
export function adoptEtagFromPageLoad(tripId: string, etag: string): boolean {
	return setKnownEtagIfUnchanged(tripId, etag, 0);
}

/**
 * Verwirft den gemerkten Stand. Noetig nach jedem Vorgang, der die Tourdatei
 * veraendert, ohne einen neuen Stempel zu liefern (`PATCH /state`), und nach
 * einer `412`-Ablehnung — die traegt laut S2 bewusst keinen neuen Stempel.
 * Ohne Verwerfen scheiterte jeder weitere Versuch endlos am selben Wert.
 */
export function discardEtag(tripId: string): void {
	knownEtags.delete(tripId);
	bumpVersion(tripId);
}

/**
 * Setzt Registry, Warteschlangen und Zaehler zurueck — **ausschliesslich fuer
 * die Testisolation**. Im Produktivcode gibt es bewusst keinen Aufrufer.
 *
 * NICHT zur Laufzeit aufrufen, solange noch Anfragen unterwegs sein koennen:
 * der Zaehlerstand faengt danach wieder bei 0 an und wird also wiederverwendet.
 * Ein Nachzuegler, der sich vorher Stand 2 gemerkt hat, findet nach zwei
 * beliebigen weiteren Aenderungen an derselben Tour erneut Stand 2 vor — die
 * Pruefung in `setKnownEtagIfUnchanged` kann ihn dann nicht mehr von einem
 * frischen Vorgang unterscheiden und uebernimmt seinen laengst veralteten
 * Stempel (F001 durch die Hintertuer).
 *
 * Wer ein Zuruecksetzen bei Nutzerwechsel braucht, muss den Zaehler monoton
 * lassen (nur `knownEtags` leeren, `etagVersions` weiterlaufen lassen) ODER
 * laufende Anfragen ungueltig machen, etwa ueber eine Sitzungskennung, die in
 * `setKnownEtagIfUnchanged` mitgeprueft wird.
 */
export function clearEtagRegistry(): void {
	knownEtags.clear();
	writeQueues.clear();
	etagVersions.clear();
}

/**
 * Reiht einen Schreibvorgang hinter jeden bereits laufenden Schreibvorgang auf
 * DIESELBE Tour ein — unabhaengig davon, welche Komponente ihn ausgeloest hat.
 * Verschiedene Touren laufen weiterhin nebeneinander. Ein fehlgeschlagener
 * Vorgaenger bricht die Kette NICHT ab (kein Domino).
 */
export function enqueueTripWrite<T>(tripId: string, fn: () => Promise<T>): Promise<T> {
	// `previous` ist immer ein Kettenschwanz (siehe `tail` unten) und scheitert
	// daher per Konstruktion nie — ein eigener Fehlerzweig hier waere toter Code.
	// Der Schutz gegen den Dominoeffekt sitzt ausschliesslich in `tail`: was
	// gespeichert wird, ist die um den Fehler bereinigte Fassung, sodass ein
	// gescheiterter Vorgaenger den Nachfolger nicht mitreisst.
	const previous = writeQueues.get(tripId) ?? Promise.resolve();
	const run = previous.then(fn);
	const tail = run.then(
		() => undefined,
		() => undefined
	);
	writeQueues.set(tripId, tail);
	void tail.then(() => {
		if (writeQueues.get(tripId) === tail) writeQueues.delete(tripId);
	});
	return run;
}
