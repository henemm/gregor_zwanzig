// Issue #2412 S4b — Sichtbarkeit der SMS-Kontingent-Zeilen auf /account.
// Spec: docs/specs/modules/sms_daily_usage_anzeige.md

/** Eine Kontingent-Zeile erscheint genau dann, wenn der Tarif ein Limit > 0 hat (AC-2/AC-7). */
export function shouldShowSmsUsageRow(limit: number | undefined): boolean {
	return typeof limit === 'number' && limit > 0;
}
