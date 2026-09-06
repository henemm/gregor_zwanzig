// Raeumen beim Abmelden (Issue #2128, AC-11/AC-12).
// Spec: docs/specs/modules/pwa_installierbar_offline_start.md · ADR-0061
//
// Geraeumt wird ausschliesslich auf der ANMELDESEITE -- dort und nur dort ist
// der Zustand endgueltig: SvelteKit registriert den Worker auf jeder Seite neu,
// ein Raeumen davor wuerde durch den naechsten Seitenaufruf sofort wieder eine
// Registrierung und einen gefuellten Speicher erzeugen (gemessen, #2128).
//
// Das Abmelde-Merkmal hat deshalb ZWEI Traeger, weil die beiden Abmelde-Wege
// verschieden ankommen:
//   1. Seitenleiste: der Server leitet auf `/login?abgemeldet=1` -- das Merkmal
//      steht im Ziel.
//   2. „Auf allen Geraeten abmelden": gemessen ueberlebt das Ziel diesen Weg
//      NICHT -- der zentrale 401-Umleiter aus `$lib/api` kommt dazwischen und
//      ersetzt es durch `/login?expired=1&redirect=…`. Darum wird das Merkmal
//      dort zusaetzlich im Sitzungsspeicher des Tabs hinterlegt.
//
// Bedingungsloses Raeumen beim Betreten der Anmeldeseite ist ausdruecklich
// nicht zulaessig: dort landet auch, wessen Sitzung abgelaufen ist oder wer die
// Seite schlicht aufruft (AC-12).

/** Merkmal im Ziel der Abmelde-Weiterleitung. */
export const ABMELDE_MERKMAL = 'abgemeldet';

/** Traeger fuer Wege, deren Weiterleitungsziel unterwegs ersetzt wird. */
const ABMELDE_MERKER = 'gz-abgemeldet';

/**
 * Der Merker gilt nur unmittelbar (AC-20).
 *
 * Er wird VOR dem Abmelde-Aufruf gesetzt, weil das Weiterleitungsziel den Weg
 * sonst nicht ueberlebt. Bleibt die Weiterleitung aus -- Netzfehler,
 * Serverfehler, geschlossener Tab --, laege er andernfalls im Sitzungsspeicher
 * herum und machte den naechsten, voellig regulaeren Sitzungsablauf
 * (401 -> `/login?expired=1`) zu einer vermeintlichen Abmeldung: die
 * Anmeldeseite raeumte still Gerätespeicher und Worker und damit die
 * Offline-Faehigkeit (AC-12). Der Fehlerzweig raeumt den Merker selbst weg
 * (AC-19); dieses Fenster faengt zusaetzlich jeden Weg, auf dem die Navigation
 * ausbleibt, ohne dass wir sie alle kennen muessen. Ein echtes Abmelden
 * navigiert sofort und liegt weit innerhalb des Fensters.
 */
const MERKER_FENSTER_MS = 60_000;

/** Vor einer Weiterleitung setzen, deren Ziel nicht sicher ankommt. */
export function merkeAbmeldung(): void {
	sessionStorage.setItem(ABMELDE_MERKER, String(Date.now()));
}

/** Der Abmelde-Versuch ist gescheitert -- der Merker darf nicht liegen bleiben. */
export function vergissAbmeldung(): void {
	sessionStorage.removeItem(ABMELDE_MERKER);
}

/** Lag ein echter Abmelde-Vorgang vor? Verbraucht den Merker. */
export function abmeldungLiegtVor(url: URL): boolean {
	const roh = sessionStorage.getItem(ABMELDE_MERKER);
	// Bedingungslos verbrauchen: auch ein abgelaufener Merker darf beim
	// naechsten Aufruf der Anmeldeseite nicht erneut zur Debatte stehen.
	if (roh !== null) sessionStorage.removeItem(ABMELDE_MERKER);
	const gesetztUm = Number(roh);
	const ausMerker =
		roh !== null && Number.isFinite(gesetztUm) && Date.now() - gesetztUm < MERKER_FENSTER_MS;
	return url.searchParams.get(ABMELDE_MERKMAL) === '1' || ausMerker;
}

/** Alle Speicher loeschen und jede Worker-Registrierung entfernen. */
export async function raeumeGeraetespeicher(): Promise<void> {
	if ('serviceWorker' in navigator) {
		for (const reg of await navigator.serviceWorker.getRegistrations()) {
			await reg.unregister();
		}
	}
	if ('caches' in window) {
		for (const name of await caches.keys()) await caches.delete(name);
	}
}
