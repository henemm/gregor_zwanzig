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
// Issue #2653 (i18n F4): die Saetze stehen im Katalog (konto.fehler.<code>) und
// kommen in der aktuellen Sprache (tr liest `locale` beim Aufruf).
import { tr, type MessageKey } from '../../lib/i18n/index.ts';

const FEHLERTEXTE: Record<string, MessageKey> = {
	invalid_sms_number: 'konto.fehler.invalid_sms_number',
	invalid_code: 'konto.fehler.invalid_code',
	code_expired: 'konto.fehler.code_expired',
	sms_not_allowed: 'konto.fehler.sms_not_allowed',
	no_number: 'konto.fehler.no_number',
	rate_limit_exceeded: 'konto.fehler.rate_limit_exceeded'
};

export function profileSaveErrorMessage(status: number, body: unknown): string {
	const b = (body ?? {}) as { detail?: string; error?: string };
	if (status === 409 && b.error === 'email_taken') {
		return tr('konto.fehler.email_taken');
	}
	if (b.error && FEHLERTEXTE[b.error]) {
		return tr(FEHLERTEXTE[b.error]);
	}
	return b.detail ?? b.error ?? tr('konto.fehler.speichern_fehlgeschlagen');
}
