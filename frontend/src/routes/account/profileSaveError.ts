// Issue #2147 Scheibe B1 (AC-16): reine Uebersetzungsfunktion fuer
// Profil-Speicherfehler. `email_taken` bekommt einen verstaendlichen
// deutschen Satz statt eines rohen Fehlercodes; alle anderen Faelle behalten
// das bisherige Verhalten (account/+page.svelte:299).
// Spec: docs/specs/modules/adress_eindeutigkeit_schreibpfade.md §7, AC-16.

export function profileSaveErrorMessage(status: number, body: unknown): string {
	const b = (body ?? {}) as { detail?: string; error?: string };
	if (status === 409 && b.error === 'email_taken') {
		return 'Diese E-Mail-Adresse wird bereits von einem anderen Konto verwendet.';
	}
	return b.detail ?? b.error ?? 'Speichern fehlgeschlagen';
}
