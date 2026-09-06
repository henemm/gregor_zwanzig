import { createHmac } from 'crypto';

/**
 * Lebensdauer des Anmelde-Cookies in Sekunden (Issue #2129). Muss mit
 * `SessionMaxAgeSeconds` in internal/middleware/auth.go übereinstimmen — 400
 * Tage, weil Browser persistente Cookies dort deckeln.
 */
export const SESSION_MAX_AGE_SECONDS = 400 * 24 * 60 * 60;

/**
 * Ablauffrist des ALTEN dreiteiligen Merkmals. Bleibt scharf, damit der
 * Altbestand binnen 24 Stunden nach dem Deploy von selbst verschwindet.
 */
const LEGACY_MAX_AGE_SECONDS = 86400;

export function signSession(userId: string, secret: string): string {
	const ts = Math.floor(Date.now() / 1000);
	const sig = createHmac('sha256', secret).update(`${userId}:${ts}`).digest('hex');
	return `${userId}.${ts}.${sig}`;
}

/**
 * Zweite Prüfstelle: der Frontend-Server prüft Format und Signatur des
 * Anmelde-Merkmals. Die Gästeliste kennt er NICHT — er hat keinen Zugriff auf
 * den Nutzer-Datenbestand. Nach einem Widerruf lädt die Seite deshalb noch
 * einmal und wirkt leer (jeder Datenabruf bekommt vom Go-Dienst 401), bis der
 * nächste Klick den harten Sprung auf die Anmelde-Seite auslöst. Das ist
 * dasselbe Verhalten wie mit der abgelösten Sperrliste, keine Umleitungsschleife.
 *
 * Beide Formate werden VON RECHTS zerlegt, damit eine Nutzerkennung mit Punkt
 * hier und im Go-Dienst dieselbe Kennung ergibt. Die Segmentzahl allein
 * unterscheidet die Formate nicht eindeutig — ein Alt-Merkmal für
 * `alice.smith` hat ebenfalls vier Segmente —, deshalb entscheidet die
 * Signatur: erst das neue Format versuchen, dann das alte.
 */
export function verifySession(
	cookie: string,
	secret: string,
	maxAge = LEGACY_MAX_AGE_SECONDS
): { userId: string } | null {
	const parts = cookie.split('.');

	if (parts.length >= 4) {
		const sig = parts[parts.length - 1];
		const tsStr = parts[parts.length - 2];
		const sessionId = parts[parts.length - 3];
		const userId = parts.slice(0, parts.length - 3).join('.');
		if (userId && sessionId && tsStr && sig) {
			const ts = parseInt(tsStr, 10);
			if (!isNaN(ts)) {
				const expected = createHmac('sha256', secret)
					.update(`${userId}:${sessionId}:${ts}`)
					.digest('hex');
				// Kein Ablauf: beim neuen Format trägt die Gästeliste des
				// Go-Dienstes die Gültigkeit, nicht der Zeitstempel.
				if (sig === expected) return { userId };
			}
		}
	}

	if (parts.length >= 3) {
		const sig = parts[parts.length - 1];
		const tsStr = parts[parts.length - 2];
		const userId = parts.slice(0, parts.length - 2).join('.');
		if (!userId || !tsStr || !sig) return null;

		const ts = parseInt(tsStr, 10);
		if (isNaN(ts)) return null;
		if (Date.now() / 1000 - ts > maxAge) return null;

		const expected = createHmac('sha256', secret).update(`${userId}:${ts}`).digest('hex');
		if (sig === expected) return { userId };
	}

	return null;
}
