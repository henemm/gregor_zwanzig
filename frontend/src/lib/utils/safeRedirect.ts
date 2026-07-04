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
