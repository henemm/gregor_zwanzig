package model

import "testing"

// TDD RED — Issue #701: SyncAlertRules + DefaultAlertThreshold noch nicht implementiert.
// Alle Tests schlagen mit "undefined: SyncAlertRules" fehl bis trip.go ergänzt ist.

// AC-3: Neue Metriken aktiviert → Default-Regeln werden angelegt
func TestSyncAlertRules_NewMetrics(t *testing.T) {
	result := SyncAlertRules(nil, []string{"wind_gust", "precipitation_sum"})
	if len(result) != 2 {
		t.Fatalf("want 2 rules, got %d", len(result))
	}
	found := map[AlertMetric]bool{}
	for _, r := range result {
		found[r.Metric] = true
		if r.Kind != AlertRuleKindAbsolute {
			t.Errorf("metric %s: want kind=absolute, got %s", r.Metric, r.Kind)
		}
		if !r.Enabled {
			t.Errorf("metric %s: want enabled=true", r.Metric)
		}
		if r.ID == "" {
			t.Errorf("metric %s: want non-empty ID", r.Metric)
		}
	}
	if !found[AlertMetricWindGust] {
		t.Error("want wind_gust rule")
	}
	if !found[AlertMetricPrecipitationSum] {
		t.Error("want precipitation_sum rule")
	}
}

// AC-4: Bestehender Threshold bleibt erhalten (kein Überschreiben durch Default)
func TestSyncAlertRules_PreservesExistingThreshold(t *testing.T) {
	existing := []AlertRule{
		{ID: "abc", Kind: AlertRuleKindAbsolute, Metric: AlertMetricWindGust, Threshold: 70, Unit: "km/h", Enabled: true},
	}
	result := SyncAlertRules(existing, []string{"wind_gust"})
	if len(result) != 1 {
		t.Fatalf("want 1 rule, got %d", len(result))
	}
	if result[0].Threshold != 70 {
		t.Errorf("want threshold 70 (preserved), got %f", result[0].Threshold)
	}
	if result[0].ID != "abc" {
		t.Errorf("want original ID 'abc', got %s", result[0].ID)
	}
}

// AC-1: Inaktive Metriken verlieren ihre Regel
func TestSyncAlertRules_RemovesInactiveMetric(t *testing.T) {
	existing := []AlertRule{
		{ID: "r1", Kind: AlertRuleKindAbsolute, Metric: AlertMetricWindGust, Threshold: 50},
		{ID: "r2", Kind: AlertRuleKindAbsolute, Metric: AlertMetricPrecipitationSum, Threshold: 20},
	}
	result := SyncAlertRules(existing, []string{"wind_gust"})
	if len(result) != 1 {
		t.Fatalf("want 1 rule (precipitation_sum removed), got %d", len(result))
	}
	if result[0].Metric != AlertMetricWindGust {
		t.Errorf("want wind_gust in result, got %s", result[0].Metric)
	}
}

// AC-2: Delta-only-Metriken erhalten keine absolute Regel
func TestSyncAlertRules_ExcludesDeltaOnlyMetrics(t *testing.T) {
	result := SyncAlertRules(nil, []string{"temperature_change", "wind_change", "precipitation_change", "thunder_level"})
	if len(result) != 0 {
		t.Errorf("want 0 rules for delta-only metrics, got %d", len(result))
	}
}

// AC-4: Bestehende Delta-Regeln werden beim Sync entfernt, absolute bleibt
func TestSyncAlertRules_RemovesDeltaRules(t *testing.T) {
	existing := []AlertRule{
		{ID: "d1", Kind: AlertRuleKindDelta, Metric: AlertMetricWindGust, Threshold: 10},
		{ID: "a1", Kind: AlertRuleKindAbsolute, Metric: AlertMetricWindGust, Threshold: 50},
	}
	result := SyncAlertRules(existing, []string{"wind_gust"})
	if len(result) != 1 {
		t.Fatalf("want 1 rule (delta removed), got %d", len(result))
	}
	if result[0].Kind != AlertRuleKindAbsolute {
		t.Errorf("want absolute, got %s", result[0].Kind)
	}
	if result[0].ID != "a1" {
		t.Errorf("want existing absolute ID 'a1', got %s", result[0].ID)
	}
}

// AC-3: Default-Thresholds korrekt definiert
func TestDefaultAlertThresholds_Coverage(t *testing.T) {
	cases := []struct {
		metric    AlertMetric
		threshold float64
	}{
		{AlertMetricWindGust, 50},
		{AlertMetricPrecipitationSum, 20},
		{AlertMetricTemperatureMin, -5},
		{AlertMetricTemperatureMax, 35},
		{AlertMetricSnowLine, 1500},
	}
	for _, tc := range cases {
		d, ok := DefaultAlertThreshold[tc.metric]
		if !ok {
			t.Errorf("no default threshold for %s", tc.metric)
			continue
		}
		if d.Threshold != tc.threshold {
			t.Errorf("%s: want threshold %f, got %f", tc.metric, tc.threshold, d.Threshold)
		}
		if d.Unit == "" {
			t.Errorf("%s: want non-empty unit", tc.metric)
		}
	}
}

// AC-2: Nicht-alertable Metriken (thunder_level) werden nie aufgenommen
func TestSyncAlertRules_ThunderLevelNotAlertable(t *testing.T) {
	result := SyncAlertRules(nil, []string{"thunder_level", "wind_gust"})
	if len(result) != 1 {
		t.Fatalf("want 1 rule (only wind_gust), got %d", len(result))
	}
	if result[0].Metric != AlertMetricWindGust {
		t.Errorf("want wind_gust, got %s", result[0].Metric)
	}
}

// AC-4: Mehrere aktive Metriken — unveränderte Metriken bleiben, neue bekommen Default
func TestSyncAlertRules_MixedMerge(t *testing.T) {
	existing := []AlertRule{
		{ID: "x1", Kind: AlertRuleKindAbsolute, Metric: AlertMetricWindGust, Threshold: 75, Enabled: true},
	}
	result := SyncAlertRules(existing, []string{"wind_gust", "snow_line"})
	if len(result) != 2 {
		t.Fatalf("want 2 rules, got %d", len(result))
	}
	for _, r := range result {
		if r.Metric == AlertMetricWindGust && r.Threshold != 75 {
			t.Errorf("wind_gust threshold should be preserved at 75, got %f", r.Threshold)
		}
		if r.Metric == AlertMetricSnowLine && r.Threshold == 0 {
			t.Error("snow_line should have non-zero default threshold")
		}
	}
}
