// Issue #2676 (i18n G2), AC-5 (Konto-Seite): Meldung beim Passwortwechsel.
// Die API liefert bei falschem aktuellen Passwort den Code wrong_password
// (Fehlerobjekt {code, message, error, detail}); die Seite prueft den code.
// Alle anderen Fehler zeigen den Text aus dem Feld error (= code), sonst
// den Standardsatz.

export function passwortAendernErrorMessage(e: unknown): string {
	const body = e as { error?: string; code?: string } | undefined;
	if (body?.code === 'wrong_password') {
		return 'Aktuelles Passwort ist falsch';
	}
	return body?.error ?? 'Passwort ändern fehlgeschlagen';
}
