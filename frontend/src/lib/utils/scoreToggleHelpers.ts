// frontend/src/lib/utils/scoreToggleHelpers.ts
// Issue #362 — Score-Toggle-Helpers: buildScoreMap + extractScoreMemberFilter.

type MetricEntry = { id: string; default_enabled?: boolean };
type MetricCatalog = Record<string, MetricEntry[]>;
type SavedMetric = { metric_id: string; score_member?: boolean };

/**
 * Baut scoreMap aus gespeicherter Config.
 * Default: true (im Score) wenn score_member fehlt.
 */
export function buildScoreMap(
	catalog: MetricCatalog,
	config: Record<string, unknown> | undefined,
): Record<string, boolean> {
	const map: Record<string, boolean> = {};
	// Alle Einträge aus Catalog: Default true
	for (const metrics of Object.values(catalog)) {
		for (const m of metrics) {
			map[m.id] = true;
		}
	}
	// Override aus gespeicherter Config
	if (config && Array.isArray(config.metrics)) {
		for (const entry of config.metrics as SavedMetric[]) {
			map[entry.metric_id] = entry.score_member ?? true;
		}
	}
	return map;
}

/**
 * Liefert Set der Metrik-IDs die im Score sind.
 * Returns null wenn alle true (kein Filtering nötig — Fallback auf volles Profil-Scoring).
 */
export function extractScoreMemberFilter(
	scoreMap: Record<string, boolean>,
): Set<string> | null {
	const active = new Set<string>();
	for (const [id, inScore] of Object.entries(scoreMap)) {
		if (inScore) active.add(id);
	}
	// Wenn alle true oder alle false: null (kein Filtering / Fallback)
	if (active.size === 0 || active.size === Object.keys(scoreMap).length) {
		return null;
	}
	return active;
}
