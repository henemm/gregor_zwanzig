package model

import "testing"

// Golden-Mapping Issue #1257: ActiveAlertableMetricIDs mit ECHTEN Katalog-IDs.

func displayCfg(catalogIDs []string) map[string]interface{} {
	metrics := make([]interface{}, 0, len(catalogIDs))
	for _, id := range catalogIDs {
		metrics = append(metrics, map[string]interface{}{"metric_id": id, "enabled": true})
	}
	return map[string]interface{}{"metrics": metrics}
}

// AC-2: alle sechs Katalog-Metriken aktiv → jede Größe hat ≥1 Regel.
func TestActiveAlertableMetricIDs_AllSixCatalogMetrics(t *testing.T) {
	cfg := displayCfg([]string{"gust", "precipitation", "thunder", "temperature", "snowfall_limit", "freezing_level"})
	rules := SyncAlertRules(nil, ActiveAlertableMetricIDs(cfg))
	want := []AlertMetric{AlertMetricWindGust, AlertMetricPrecipitationSum, AlertMetricThunderLevel,
		AlertMetricTemperatureMin, AlertMetricTemperatureMax, AlertMetricSnowLine}
	got := map[AlertMetric]bool{}
	for _, r := range rules {
		got[r.Metric] = true
	}
	if len(rules) != len(want) {
		t.Fatalf("AC-2: want %d rules, got %d: %+v", len(want), len(rules), rules)
	}
	for _, w := range want {
		if !got[w] {
			t.Errorf("AC-2: missing rule for %s", w)
		}
	}
}

// AC-3: nur "temperature" aktiv → genau zwei Regeln (min UND max).
func TestActiveAlertableMetricIDs_TemperatureOnlyYieldsBothMinAndMax(t *testing.T) {
	rules := SyncAlertRules(nil, ActiveAlertableMetricIDs(displayCfg([]string{"temperature"})))
	found := map[AlertMetric]bool{}
	for _, r := range rules {
		found[r.Metric] = true
	}
	if len(rules) != 2 || !found[AlertMetricTemperatureMin] || !found[AlertMetricTemperatureMax] {
		t.Fatalf("AC-3: want 2 rules (min+max), got %+v", rules)
	}
}

// AC-4: "snowfall_limit" + "freezing_level" aktiv → genau EINE snow_line-Regel.
func TestActiveAlertableMetricIDs_SnowfallLimitAndFreezingLevelDedup(t *testing.T) {
	rules := SyncAlertRules(nil, ActiveAlertableMetricIDs(displayCfg([]string{"snowfall_limit", "freezing_level"})))
	if len(rules) != 1 || rules[0].Metric != AlertMetricSnowLine {
		t.Fatalf("AC-4: want exactly 1 snow_line rule (dedup), got %+v", rules)
	}
}
