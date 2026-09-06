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

/**
 * Der Merker hat seinen Zweck verloren -- der Abmelde-Versuch ist gescheitert
 * (AC-19), das Fenster ist abgelaufen (AC-20) oder das Raeumen ist gelungen
 * (AC-24). In allen drei Faellen darf er nicht liegen bleiben.
 */
export function vergissAbmeldung(): void {
	sessionStorage.removeItem(ABMELDE_MERKER);
}

/**
 * Gilt der hinterlegte Merker gerade? (AC-20, AC-23)
 *
 * Ein Alter ausserhalb `[0, MERKER_FENSTER_MS)` ist unplausibel und zaehlt
 * NICHT. Negativ wird das Alter, wenn die Geraeteuhr nach dem Setzen
 * zurueckspringt (Zeitzonenwechsel, NTP-Korrektur) -- ohne diese Schranke waere
 * jede negative Zahl kleiner als das Fenster, ein zufaellig liegen gebliebener
 * Merker wuerde also als "gerade eben gesetzt" gelesen und die Anmeldeseite
 * raeumte. Unlesbare Zeitstempel (`NaN`) fallen ueber `Number.isFinite`
 * genauso heraus. Bei Zweifeln gilt immer die sichere Seite: nicht raeumen --
 * ein stehen gebliebener Speicher ist ein Schoenheitsfehler, ein faelschlich
 * geleerter kostet die Offline-Faehigkeit.
 */
function merkerGiltNoch(): boolean {
	const roh = sessionStorage.getItem(ABMELDE_MERKER);
	if (roh === null) return false;
	const alter = Date.now() - Number(roh);
	return Number.isFinite(alter) && alter >= 0 && alter < MERKER_FENSTER_MS;
}

/**
 * Lag ein echter Abmelde-Vorgang vor?
 *
 * Ein Merker, der NICHT (mehr) gilt, wird hier verbraucht -- er darf beim
 * naechsten Aufruf der Anmeldeseite nicht erneut zur Debatte stehen. Ein
 * geltender Merker bleibt dagegen stehen, bis das Raeumen nachweislich gelungen
 * ist (AC-24, `vergissAbmeldung` beim Aufrufer): scheitert eine
 * Speicher-Schnittstelle, findet ihn so der naechste Versuch. Dauerhaft
 * haengen bleibt er dabei nicht -- nach Ablauf des Fensters raeumt ihn dieser
 * Zweig weg.
 */
export function abmeldungLiegtVor(url: URL): boolean {
	const ausMerker = merkerGiltNoch();
	if (!ausMerker) vergissAbmeldung();
	return url.searchParams.get(ABMELDE_MERKMAL) === '1' || ausMerker;
}

/**
 * Alle Speicher loeschen und jede Worker-Registrierung entfernen.
 *
 * Meldet, ob das VOLLSTAENDIG gelungen ist. Jeder Eintrag wird einzeln
 * versucht: verweigert der Browser eine Speicher-Schnittstelle (iOS Safari
 * unter Speicherdruck, privater Modus), soll das nicht die uebrigen Eintraege
 * mitreissen. Ein Teilerfolg -- Speicher geraeumt, Worker-Abmeldung gescheitert
 * oder umgekehrt -- gilt als Fehlschlag, damit ein zweiter Versuch folgt.
 */
export async function raeumeGeraetespeicher(): Promise<boolean> {
	let vollstaendig = true;
	const versuche = async (schritt: () => Promise<boolean>): Promise<void> => {
		try {
			if (!(await schritt())) vollstaendig = false;
		} catch {
			vollstaendig = false;
		}
	};

	if ('serviceWorker' in navigator) {
		try {
			for (const reg of await navigator.serviceWorker.getRegistrations()) {
				await versuche(() => reg.unregister());
			}
		} catch {
			vollstaendig = false;
		}
	}
	if ('caches' in window) {
		try {
			for (const name of await caches.keys()) await versuche(() => caches.delete(name));
		} catch {
			vollstaendig = false;
		}
	}
	return vollstaendig;
}
