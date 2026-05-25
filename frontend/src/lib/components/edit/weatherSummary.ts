// Issue #345 (Wetter-Editor-Konsolidierung, Touren-Teil) — AC-1.
// Spec: docs/specs/modules/issue_345_weather_editor_consolidation.md
//
// Reine Funktion ohne Svelte-Abhängigkeit, damit sie via node:test
// unit-getestet werden kann (siehe weatherSummary.test.ts). Liefert die
// read-only Wetter-Zusammenfassung für die Tour-Bearbeiten-Maske aus dem
// gespeicherten display_config.
//
// Bucket-Parsing ist KONSISTENT mit dem Loader in
// trip-detail/WeatherMetricsTab.svelte::initFromTrip (#360/#364):
// - primary  → Spalten
// - secondary → Detail
// - enabled ohne expliziten bucket → defensiv Detail (looseActive)
// - Altformat (kein bucket/order) → aktive gelten mangels Markierung als Spalte
// - off / enabled:false → zählt nirgends

// Shape einer gespeicherten Metrik in display_config.metrics[].
// Deckt sich mit BucketWeatherConfigMetric in trip-detail/metricsEditor.ts,
// hier minimal gehalten (nur die für die Zusammenfassung relevanten Felder).
interface SummaryMetric {
	metric_id: string;
	enabled: boolean;
	bucket?: 'primary' | 'secondary';
	order?: number;
}

export interface DisplayConfigLike {
	preset_name?: string | null;
	metrics?: SummaryMetric[];
}

export interface TripWeatherSummary {
	/** Profil-/Preset-Name aus display_config.preset_name; leer/fehlend → null. */
	presetName: string | null;
	/** Metriken im primary-Bucket bzw. (Altformat) als Spalte markiert. */
	spalten: number;
	/** Metriken im secondary-Bucket bzw. enabled ohne expliziten Bucket. */
	detail: number;
	/** Alle aktiven (nicht „off") Metriken = spalten + detail. */
	aktiv: number;
}

/**
 * Aggregiert die read-only Wetter-Zusammenfassung aus dem display_config.
 *
 * Fail-soft: undefiniertes/leeres display_config → alles 0, presetName null.
 */
export function summarizeTripWeather(
	displayConfig: DisplayConfigLike | undefined | null,
): TripWeatherSummary {
	const presetRaw = displayConfig?.preset_name;
	const presetName = presetRaw && presetRaw.trim() !== '' ? presetRaw : null;

	const metrics = displayConfig?.metrics;
	if (!Array.isArray(metrics) || metrics.length === 0) {
		return { presetName, spalten: 0, detail: 0, aktiv: 0 };
	}

	// Bucket-Format erkennen: irgendeine Metrik trägt bucket oder order
	// (deckt sich mit hasBuckets in WeatherMetricsTab::initFromTrip).
	const hasBuckets = metrics.some((m) => m.bucket || m.order !== undefined);

	let spalten = 0;
	let detail = 0;

	for (const m of metrics) {
		if (!m.enabled) continue;
		if (hasBuckets) {
			if (m.bucket === 'primary') {
				spalten++;
			} else {
				// secondary ODER enabled ohne expliziten bucket → Detail (looseActive).
				detail++;
			}
		} else {
			// Altformat: keine Bucket-Markierung → aktive gelten als Spalte.
			spalten++;
		}
	}

	return { presetName, spalten, detail, aktiv: spalten + detail };
}
