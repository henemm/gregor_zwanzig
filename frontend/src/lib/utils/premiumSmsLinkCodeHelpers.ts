// Issue #2154 Scheibe B — Pure-Logik der Premium-SMS-Verknuepfungscode-Karte
// auf /account.
// Spec: docs/specs/modules/fix_2154_s2_premium_sms_link_code_ui.md
//
// Reine Funktionen — keine Svelte-Imports, damit `node --experimental-strip-types
// --test` die Test-Datei laden kann. `+page.svelte`/`PremiumSmsLinkCard.svelte`
// verdrahten diese Funktionen nur.

import type { UserTier } from '../types.ts';

/** Sichtbarkeit der Karte — ausschliesslich fuer Tier "premium" (AC-8). */
export function shouldShowPremiumSmsLinkCard(tier: UserTier | undefined): boolean {
	return tier === 'premium';
}

/** "Code erneuern" braucht eine Bestaetigung, "Code erzeugen" nicht (AC-3/AC-4). */
export function needsRenewConfirmation(exists: boolean): boolean {
	return exists === true;
}

/** Klickpfad des Erzeugen/Erneuern-Buttons (AC-2/AC-4/AC-11). */
export function resolveGenerateClick(
	exists: boolean,
	busy: boolean
): 'call-post' | 'confirm-dialog' | 'noop' {
	if (busy) return 'noop';
	return exists ? 'confirm-dialog' : 'call-post';
}

/** Klickpfad des Bestaetigungsdialogs (AC-5/AC-6). */
export function resolveDialogAction(action: 'confirm' | 'cancel'): 'call-post' | 'none' {
	return action === 'confirm' ? 'call-post' : 'none';
}

/** Fail-closed: alles ausser explizit {exists:false} gilt als vorhanden (AC-10). */
export function deriveLinkCodeExists(resp: { exists?: boolean } | null | undefined): boolean {
	if (resp && resp.exists === false) return false;
	return true;
}

/**
 * Verstaendliche Fehlermeldung statt Rohtext/Absturz (AC-9). Reihenfolge:
 * `.detail` (echter Servertext) -> `Error.message` (Netzfehler, $lib/api.ts)
 * -> fester Fallback. `.error` (z.B. "HTTP 500" aus $lib/api.ts:134) wird
 * bewusst NIE als Nachricht verwendet.
 */
export function errorMessageFrom(err: unknown, fallback: string): string {
	const detail = (err as { detail?: unknown } | null | undefined)?.detail;
	if (typeof detail === 'string') return detail;
	if (err instanceof Error) return err.message;
	return fallback;
}
