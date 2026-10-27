// Issue #2521 S2 (AC-16) — Ziel des Aufruf-Knopfs fuer Ortsvergleiche: ohne
// angefangenen Vergleich die Anlege-Seite, sonst dessen Hub (Epic #1273 S3).
export function buildCompareCtaHref(firstIncomplete: { id: string } | null | undefined): string {
	return firstIncomplete ? `/compare/${firstIncomplete.id}` : '/compare/new';
}
