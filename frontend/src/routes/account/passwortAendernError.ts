// Issue #2676 (i18n G2), AC-5 (Konto-Seite): Meldung beim Passwortwechsel.
// Die API liefert bei falschem aktuellen Passwort den Code wrong_password
// (Fehlerobjekt {code, message, error, detail}); die Seite prueft den code.
// Alle anderen Fehler zeigen den Text aus dem Feld error (= code), sonst
// den Standardsatz. Issue #2653 (i18n F4): Saetze aus dem Katalog (konto.passwort.*).
import { tr } from '../../lib/i18n/index.ts';

export function passwortAendernErrorMessage(e: unknown): string {
	const body = e as { error?: string; code?: string } | undefined;
	if (body?.code === 'wrong_password') {
		return tr('konto.passwort.falsch');
	}
	return body?.error ?? tr('konto.passwort.fehlgeschlagen');
}
