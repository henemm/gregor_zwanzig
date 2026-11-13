// Issue #2961 (ADR-0115): Adresswechsel und Passkey-Aenderungen verlangen einen
// frischen Nachweis (Passwort oder Code per E-Mail). Der Server antwortet ohne
// ihn mit 403 `reauth_required`; die Konto-Seite oeffnet dann den Nachweis-
// Dialog (derselbe Dialog wie beim Konto-Loeschen) und wiederholt danach die
// Aenderung.
import { tr, type MessageKey } from '../../lib/i18n/index.ts';

export const NACHWEIS_FEHLT = 'reauth_required';

/** Verlangt die Antwort einen frischen Nachweis? (API-Fehlerobjekt oder Error aus $lib/passkey) */
export function brauchtNachweis(e: unknown): boolean {
	if (e instanceof Error) return e.message === NACHWEIS_FEHLT;
	const body = e as { status?: number; error?: string; code?: string } | null;
	return body?.status === 403 && (body.error === NACHWEIS_FEHLT || body.code === NACHWEIS_FEHLT);
}

const NACHWEIS_FEHLER_TEXT: Record<string, MessageKey> = {
	reauth_required: 'konto.nachweis.fehlt',
	wrong_password: 'konto.fehler.wrong_password',
	invalid_code: 'konto.fehler.loeschcode_ungueltig',
	rate_limit_exceeded: 'konto.fehler.zu_viele_versuche',
	mail_failed: 'konto.fehler.mail_failed'
};

/** Fehlertext im Nachweis-Dialog: bekannter Code -> eigener Satz, sonst Server-Text, sonst Ersatz. */
export function nachweisFehlerText(e: unknown, fallback: string): string {
	const body = e as { detail?: string; error?: string } | null;
	const key = body?.error ? NACHWEIS_FEHLER_TEXT[body.error] : undefined;
	return (key && tr(key)) || body?.detail || body?.error || fallback;
}
