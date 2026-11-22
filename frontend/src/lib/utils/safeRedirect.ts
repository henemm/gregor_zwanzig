// Issue #1006 — Login-Rückleitung: nur relative Pfade akzeptieren (kein Open-Redirect).
// Adversary-Finding F001 im Bündel #1010/#1006 (2026-07-04): Blacklist auf '//' reichte nicht — Browser lösen
// Pfade wie '/\evil.com' per WHATWG-URL-Normalisierung zu 'https://evil.com/' auf.
// Deshalb Whitelist: genau EIN führender Slash, danach weder Slash noch Backslash,
// und im gesamten Wert kein Backslash/Steuerzeichen (legitime interne Pfade haben das nie).
const SINGLE_LEADING_SLASH = /^\/(?![\/\\])/;
const HAS_BACKSLASH_OR_CONTROL_CHAR = /[\\\x00-\x1f\x7f]/;

export function safeRedirectPath(raw: string | null | undefined, fallback = '/'): string {
	if (typeof raw !== 'string' || raw === '') return fallback;
	if (!SINGLE_LEADING_SLASH.test(raw)) return fallback;
	if (HAS_BACKSLASH_OR_CONTROL_CHAR.test(raw)) return fallback;
	return raw;
}

/**
 * Issue #3281 — Ziel des Anmeldeformulars. `action="?/login"` ersetzt die
 * Abfrage der Seite; ein `redirect` der Seitenadresse (z. B. Rücksprung zur
 * Autorisierung des MCP-Konnektors) muss deshalb ausdrücklich mitreisen. Nur
 * ein Wert, den `safeRedirectPath` akzeptiert, wird übernommen.
 */
export function loginFormAktion(raw: string | null | undefined): string {
	const ziel = safeRedirectPath(raw, '');
	return ziel ? `?/login&redirect=${encodeURIComponent(ziel)}` : '?/login';
}

/**
 * Issue #3281 — Link zu einem anderen Anmeldeweg (Google, Code-Anmeldung), der
 * den erlaubten Rücksprung als `?redirect=` mitnimmt; sonst `pfad` unverändert.
 */
export function mitRuecksprung(pfad: string, raw: string | null | undefined): string {
	const ziel = safeRedirectPath(raw, '');
	return ziel ? `${pfad}?redirect=${encodeURIComponent(ziel)}` : pfad;
}

/**
 * Issue #3281 — Ziel nach einer Anmeldung im Browser (Passkey): der erlaubte
 * `redirect` aus der Abfrage der Seite (`location.search`), sonst `/`.
 */
export function zielNachAnmeldung(search: string): string {
	return safeRedirectPath(new URLSearchParams(search).get('redirect'));
}
