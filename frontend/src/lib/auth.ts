import { createHmac } from 'crypto';

/**
 * Lebensdauer des Anmelde-Cookies in Sekunden (Issue #2129). Muss mit
 * `SessionMaxAgeSeconds` in internal/middleware/auth.go übereinstimmen — 400
 * Tage, weil Browser persistente Cookies dort deckeln.
 */
export const SESSION_MAX_AGE_SECONDS = 400 * 24 * 60 * 60;

/**
 * Zweite Prüfstelle: der Frontend-Server prüft Format und Signatur des
 * Anmelde-Merkmals. Die Gästeliste kennt er NICHT — er hat keinen Zugriff auf
 * den Nutzer-Datenbestand. Nach einem Widerruf lädt die Seite deshalb noch
 * einmal und wirkt leer (jeder Datenabruf bekommt vom Go-Dienst 401), bis der
 * nächste Klick den harten Sprung auf die Anmelde-Seite auslöst. Das ist
 * dasselbe Verhalten wie mit der abgelösten Sperrliste, keine Umleitungsschleife.
 *
 * Zerlegt wird VON RECHTS, damit eine Nutzerkennung mit Punkt hier und im
 * Go-Dienst dieselbe Kennung ergibt.
 */
export function verifySession(cookie: string, secret: string): { userId: string } | null {
	const parts = cookie.split('.');
	if (parts.length < 4) return null;

	const sig = parts[parts.length - 1];
	const tsStr = parts[parts.length - 2];
	const sessionId = parts[parts.length - 3];
	const userId = parts.slice(0, parts.length - 3).join('.');
	if (!userId || !sessionId || !tsStr || !sig) return null;

	const ts = parseInt(tsStr, 10);
	if (isNaN(ts)) return null;

	const expected = createHmac('sha256', secret)
		.update(`${userId}:${sessionId}:${ts}`)
		.digest('hex');
	// Kein Ablauf: die Gästeliste des Go-Dienstes trägt die Gültigkeit,
	// nicht der Zeitstempel.
	return sig === expected ? { userId } : null;
}
