// Issue #2160 (ADR-0081): Fehlertexte beim Konto-Loeschen (Passwort oder
// Loesch-Code). Bekannter Code -> eigener Satz; sonst Server-Text
// (detail, dann error), zuletzt der Ersatztext des Aufrufers.
// Issue #2653 (i18n F4): Saetze aus dem Katalog (konto.fehler.*), Sprache beim Aufruf.
import { tr, type MessageKey } from '../../lib/i18n/index.ts';

const DELETE_ERROR_TEXT: Record<string, MessageKey> = {
	reauth_required: 'konto.fehler.reauth_required',
	wrong_password: 'konto.fehler.wrong_password',
	invalid_code: 'konto.fehler.loeschcode_ungueltig',
	rate_limit_exceeded: 'konto.fehler.zu_viele_versuche',
	mail_failed: 'konto.fehler.mail_failed'
};

export function deleteErrorText(e: unknown, fallback: string): string {
	const body = e as { detail?: string; error?: string };
	const key = body?.error ? DELETE_ERROR_TEXT[body.error] : undefined;
	return (key && tr(key)) || body?.detail || body?.error || fallback;
}
