// Issue #2281 — Versand-Historie (geteilt von Trip und Ortsvergleich).
// Spec: docs/specs/modules/feat_2281_vergleich_versand_historie.md

export type BriefingHistoryKind = 'route' | 'vergleich';

export interface BriefingHistoryEntry {
	sent_at: string;
	kind: string;
	channels: string[];
	on_demand?: boolean;
}

/** Kind-neutraler Endpunkt der Versand-Historie (Go: briefing_history.go). */
export function briefingHistoryUrl(id: string, kind: BriefingHistoryKind): string {
	return `/api/briefings/${encodeURIComponent(id)}/briefing-history?kind=${kind}`;
}
