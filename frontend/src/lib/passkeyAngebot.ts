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
