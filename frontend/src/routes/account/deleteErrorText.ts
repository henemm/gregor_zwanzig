// Issue #2160 (ADR-0081): Fehlertexte beim Konto-Loeschen (Passwort oder
// Loesch-Code). Bekannter Code -> eigener Satz; sonst Server-Text
// (detail, dann error), zuletzt der Ersatztext des Aufrufers.
const DELETE_ERROR_TEXT: Record<string, string> = {
	reauth_required: 'Bitte Passwort oder Lösch-Code eingeben.',
	wrong_password: 'Das Passwort ist falsch.',
	invalid_code: 'Der Code ist falsch, abgelaufen oder bereits benutzt.',
	rate_limit_exceeded: 'Zu viele Versuche. Bitte warte einige Minuten.',
	mail_failed: 'Der Code konnte nicht verschickt werden. Bitte später erneut versuchen.',
};

export function deleteErrorText(e: unknown, fallback: string): string {
	const body = e as { detail?: string; error?: string };
	return (body?.error && DELETE_ERROR_TEXT[body.error]) || body?.detail || body?.error || fallback;
}
