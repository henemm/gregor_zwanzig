// Issue #2482 — Mengen-Quoten je Tier auf /account ("x von N").
// Spec: docs/specs/modules/mengen_quoten_je_tier.md (AC-13, AC-15)
//
// Pure Funktionen (Muster smsDailyUsageHelpers.ts); +page.svelte verdrahtet sie
// nur. Die Grenzen kommen aus dem Profil (`quota`, null = unbegrenzt).

/** Zaehlt nur nicht archivierte Eintraege — dieselbe Regel wie der Server. */
export function countActive(list: Array<{ archived_at?: string | null }> | null | undefined): number {
	if (!Array.isArray(list)) return 0;
	return list.filter((item) => !item.archived_at).length;
}

/** "x von N"; ohne Grenze (null/undefined = unbegrenzt) nur "x". */
export function formatQuotaUsage(count: number, limit: number | null | undefined): string {
	if (typeof limit !== 'number') return String(count);
	return `${count} von ${limit}`;
}
