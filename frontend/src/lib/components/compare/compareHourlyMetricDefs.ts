// Issue #1106 — Katalog der waehlbaren Stundenverlauf-Metriken (Compare-Mail).
// Spec: docs/specs/modules/issue_1106_hourly_metrics_config.md
//
// IDs muessen 1:1 mit den Keys aus FRONTEND_TO_HOURLY_METRIC_ID in
// src/output/renderers/compare_hourly_metric_ids.py uebereinstimmen -- sonst
// verwirft der Resolver die Auswahl (unbekannte IDs -> None -> Default "alle").
// Eigenstaendiges Vokabular, kein Reuse von compareMetricDefs.ts (Rohwerte pro
// Stunde != Aggregate der Uebersichtstabelle).

export interface HourlyMetricDef {
	key: string;
	label: string;
}

// Anzeige-Reihenfolge der Checkboxen im Editor -- NICHT die Spaltenreihenfolge
// in der Mail (die ist im Renderer kanonisch fest verdrahtet, s. HOUR_METRICS
// in compare_html.py).
export const ALL_HOURLY_METRICS: HourlyMetricDef[] = [
	{ key: 'temp_c', label: 'Temperatur' },
	{ key: 'wind_chill_c', label: 'Gefühlte Temperatur' },
	{ key: 'wind_kmh', label: 'Wind' },
	{ key: 'gust_kmh', label: 'Böen' },
	{ key: 'precip_mm', label: 'Niederschlag' },
	{ key: 'uv_index', label: 'UV-Index' },
	{ key: 'thunder_level', label: 'Gewitter-Risiko' },
	{ key: 'pop_pct', label: 'Regenwahrscheinlichkeit' },
	{ key: 'visibility_m', label: 'Sicht' }
];
