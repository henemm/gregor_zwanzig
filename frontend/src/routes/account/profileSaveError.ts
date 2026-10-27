// Issue #2147 Scheibe B1 (AC-16): reine Uebersetzungsfunktion fuer
// Profil-Speicherfehler. `email_taken` bekommt einen verstaendlichen
// deutschen Satz statt eines rohen Fehlercodes; alle anderen Faelle behalten
// das bisherige Verhalten (account/+page.svelte:299).
// Spec: docs/specs/modules/adress_eindeutigkeit_schreibpfade.md §7, AC-16.

// Issue #2406 (AC-13): die Fehlercodes des SMS-Bestaetigungsablaufs bekommen
// hier ihre deutschen Saetze — dieselbe, EINZIGE Uebersetzungsstelle der
// Kontoseite, kein zweites Modul daneben. Der Schluessel ist der Fehlercode,
// nicht der Status: `rate_limit_exceeded` kommt mit 429, die uebrigen mit 400,
// und diese Kenntnis muss nicht doppelt gepflegt werden.
const FEHLERTEXTE: Record<string, string> = {
	invalid_sms_number:
		'Die Handynummer muss im internationalen Format stehen, z. B. +49151234567.',
	invalid_code:
		'Der Code stimmt nicht. Gültig ist immer nur der zuletzt angeforderte Code — ältere verfallen, sobald du einen neuen anforderst oder die Nummer änderst.',
	code_expired: 'Der Bestätigungscode ist abgelaufen — bitte einen neuen anfordern.',
	sms_not_allowed: 'SMS gibt es ab Level Standard — bitte den Tarif prüfen.',
	no_number: 'Es ist keine Handynummer hinterlegt.',
	rate_limit_exceeded: 'Zu viele Anfragen — bitte später noch einmal versuchen.'
};

export function profileSaveErrorMessage(status: number, body: unknown): string {
	const b = (body ?? {}) as { detail?: string; error?: string };
	if (status === 409 && b.error === 'email_taken') {
		return 'Diese E-Mail-Adresse wird bereits von einem anderen Konto verwendet.';
	}
	if (b.error && FEHLERTEXTE[b.error]) {
		return FEHLERTEXTE[b.error];
	}
	return b.detail ?? b.error ?? 'Speichern fehlgeschlagen';
}
