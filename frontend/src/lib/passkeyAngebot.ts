/**
 * Passkey-Angebot — Issue #2248 (#2199 Scheibe 3).
 *
 * Zwei reine Funktionen: die Anzeige-Entscheidung und das Anhaengen des
 * Anmelde-Markers. Beide lesen NICHTS selbst (kein `window`, kein Speicher,
 * kein Abruf) — nur so sind sie unter `node --test` pruefbar und liegen damit
 * in der CI-Ampel (Spec, Analyse-Entscheidung B).
 */

/**
 * Der Marker, den die Login-Aktion an die Weiterleitungs-Adresse haengt und den
 * das Layout dort wiederfindet. EINE Quelle fuer beide Seiten — zwei
 * Schreibweisen hiessen, dass das Layout nach einem Marker sucht, den niemand
 * schreibt.
 */
export const ANGEBOT_MARKER = 'passkey_angebot';

export interface AngebotLage {
	/** Der Anmelde-Marker steht in der Adresse. */
	marker: boolean;
	/** Der Nutzer hat bereits einen Passkey hinterlegt. */
	hasPasskey: boolean;
	/** Der Nutzer hat das Angebot abgewiesen (serverseitig gemerkt). */
	dismissed: boolean;
	/** Das Geraet kann WebAuthn ueberhaupt einloesen. */
	webauthnFaehig: boolean;
}

/**
 * Das Angebot ist nur faellig, wenn alle vier Bedingungen zugleich gelten:
 * frisch angemeldet, noch kein Passkey, nicht abgewiesen, Geraet faehig.
 */
export function passkeyAngebotFaellig({
	marker,
	hasPasskey,
	dismissed,
	webauthnFaehig
}: AngebotLage): boolean {
	return marker && !hasPasskey && !dismissed && webauthnFaehig;
}

/**
 * Issue #2961 (ADR-0115): Passkey hinzufuegen verlangt einen frischen Nachweis.
 * Scheitert das Einrichten aus dem Angebot daran, fuehrt das Layout zur
 * Passkey-Karte der Konto-Seite; dort oeffnet der Nachweis-Dialog von selbst
 * und danach der Anlegen-Dialog. Merkmal in der Adresse: `?passkey=einrichten`.
 */
export const KONTO_PASSKEY_EINRICHTEN = '/account?passkey=einrichten';

/** Steht das Merkmal „Passkey einrichten" in der Adresse der Konto-Seite? */
export function passkeyEinrichtenAngefordert(suche: URLSearchParams): boolean {
	return suche.get('passkey') === 'einrichten';
}

/** Was nach einem gescheiterten Einrichten aus dem Angebot geschieht. */
export type AngebotFehlerFolge = 'nachweis' | 'abgebrochen' | 'fehler';

/**
 * `nachweis`: der Server verlangt einen frischen Nachweis (zur Konto-Seite);
 * `abgebrochen`: Zeremonie abgebrochen/abgelaufen; `fehler`: alles andere.
 */
export function angebotFehlerFolge(e: unknown): AngebotFehlerFolge {
	if (e instanceof Error && e.message === 'reauth_required') return 'nachweis';
	const name = (e as { name?: string } | null)?.name;
	if (name === 'NotAllowedError' || name === 'AbortError' || name === 'TimeoutError') return 'abgebrochen';
	return 'fehler';
}

/**
 * Haengt den Anmelde-Marker als eigenstaendigen Query-Parameter an einen
 * relativen Pfad, der bereits eine Query tragen kann.
 *
 * Ein zweites `?` wuerde die bestehende Angabe verfaelschen
 * (`/trips?filter=aktiv?passkey_angebot=1` liest sich als
 * `filter="aktiv?passkey_angebot=1"`) — deshalb entscheidet das bereits
 * vorhandene `?` ueber das Trennzeichen.
 */
export function mitAngebotMarker(pfad: string): string {
	const trenner = pfad.includes('?') ? '&' : '?';
	return `${pfad}${trenner}${ANGEBOT_MARKER}=1`;
}
