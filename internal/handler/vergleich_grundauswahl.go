package handler

import "github.com/henemm/gregor-api/internal/model"

// vergleichAggregation — Issue #3047 E1: Auswertung je Groesse fuer
// `active_metrics` eines Orts-Briefings, wie der Editor sie schreibt (erster
// Eintrag des Vergleichs-Katalogs je Groesse, GET /api/compare/metrics).
// Groessen ausserhalb des Vergleichs-Katalogs (z. B. temperature_night) fehlen
// bewusst: die Mail wuerde sie verwerfen. Drift-Waechter gegen Python:
// TestF3047E1_AggregationstabelleGleichPythonKatalog.
var vergleichAggregation = map[string]string{
	"snow_depth": "max", "fresh_snow": "sum", "sunshine": "sum", "wind": "max",
	"cloud_total": "avg", "visibility": "min", "precipitation": "sum", "uv_index": "max",
	"temperature": "max", "thunder": "max", "gust": "max", "freezing_level": "min",
	"rain_probability": "max", "wind_direction": "avg", "wind_chill": "min", "humidity": "avg",
	"dewpoint": "avg", "snowfall_limit": "min", "precip_type": "max", "cloud_low": "avg",
	"cloud_mid": "avg", "cloud_high": "avg", "pressure": "avg",
}

// vergleichDisplayConfigAusVorlage baut die display_config eines neuen
// Orts-Briefings aus der Orts-Standardvorlage: Ampel wie bisher und
// (Issue #3047 E1) die Grundauswahl ausdruecklich als `active_metrics` in der
// Folge der Vorlage — sonst zeigte die Mail alle Zeilen, der Editor die Vorlage.
// Ohne waehlbare Groesse bleibt es beim Bestandsverhalten (nur Ampel).
func vergleichDisplayConfigAusVorlage(p *model.MetricPreset) map[string]interface{} {
	dc := displayConfigAusVorlage(p, false)
	if p == nil {
		return dc
	}
	aktiv := []interface{}{}
	gesehen := map[string]bool{}
	for _, m := range p.Metrics {
		agg, ok := vergleichAggregation[m.MetricID]
		if !m.Enabled || !ok || gesehen[m.MetricID] {
			continue
		}
		gesehen[m.MetricID] = true
		aktiv = append(aktiv, map[string]interface{}{"metric_id": m.MetricID, "aggregation": agg})
	}
	if len(aktiv) == 0 {
		return dc
	}
	if dc == nil {
		dc = map[string]interface{}{}
	}
	dc["active_metrics"] = aktiv
	return dc
}
