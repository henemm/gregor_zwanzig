// Issue #1258 Scheibe S2 — geteilter Alarme-Organism (ungewired).
// Compare-Metrik-Mapping fuer den metric-levels-Abschnitt (vergleich-Zweig).
// Extrahiert aus CompareAlarmSection.svelte (Issue #1170) als Vorbild — jene
// Datei bleibt in dieser Scheibe UNVERAENDERT (Abloesung erst S4).
import { ALERTABLE_METRICS } from '$lib/components/alerts-tab/alertMetricTable';
import type { AlertMetric } from '$lib/types';

// Compare nutzt einen eigenen Metrik-Namensraum (compareMetricDefs.ts, z.B.
// "wind_max_kmh"), nicht identisch mit AlertMetric ("wind_gust").
export const COMPARE_TO_ALERT_METRIC: Record<string, AlertMetric> = {
	wind_max_kmh: 'wind_gust',
	precip_sum_mm: 'precipitation_sum',
	temp_max_c: 'temperature_max',
	thunder_level_max: 'thunder_level',
	snow_new_sum_cm: 'fresh_snow',
	visibility_min_m: 'visibility'
};

export function deriveActiveAlertMetrics(activeMetricKeys: string[]): AlertMetric[] {
	const seen = new Set<AlertMetric>();
	for (const key of activeMetricKeys) {
		const mapped = COMPARE_TO_ALERT_METRIC[key];
		if (mapped) seen.add(mapped);
	}
	return ALERTABLE_METRICS.filter((m) => seen.has(m));
}
