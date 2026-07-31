// Feature #1435 Etappe E1a-2: welche Alarm-Zeilen der Alarme-Reiter im
// Ortsvergleich zeigt, entscheidet das zentrale Wetter-Namensregister
// (Katalog-Feld `alertMetric`, live seit E1a-1) — nicht mehr eine eigene,
// handgepflegte Frontend-Liste. Ersetzt compareMetricMapping.ts.
// Spec: docs/specs/modules/feat_1435_e1a2_alarme_reiter_register.md
import { ALERTABLE_METRICS } from '$lib/components/alerts-tab/alertMetricTable';
import type { AlertMetric } from '$lib/types';
import type { CompareSelectionEntry } from '../weather-metrics-tab/compareMetricSelection.ts';

/**
 * Aktive Compare-Auswahl-Schluessel -> Alarm-Identitaeten, gelesen aus dem
 * UEBERGEBENEN Katalog. Kein Modul-Getter, kein internes Gedaechtnis: das
 * Ergebnis haengt allein an den Argumenten, damit ein `$derived` beim
 * Aktualisieren der Katalog-Prop neu rechnet (AC-5, Fehlerklasse #1320).
 *
 * Reihenfolge und Filter laufen weiterhin ueber `ALERTABLE_METRICS` —
 * unveraendert zum bisherigen Verhalten von `deriveActiveAlertMetrics()`.
 */
export function deriveActiveAlertMetricsFromCatalog(
	activeMetricKeys: string[],
	catalog: CompareSelectionEntry[]
): AlertMetric[] {
	const byKey = new Map((catalog ?? []).map((e) => [e.metric, e]));
	const seen = new Set<AlertMetric>();
	for (const key of activeMetricKeys ?? []) {
		const alertMetric = byKey.get(key)?.alertMetric;
		if (alertMetric) seen.add(alertMetric as AlertMetric);
	}
	return ALERTABLE_METRICS.filter((m) => seen.has(m));
}
