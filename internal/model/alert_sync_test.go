package model

import "testing"

// Tests für SyncAlertRules und DefaultAlertThreshold.
// Issue #817: auf Δ-Semantik umgestellt. Superseded-Tests wurden an die neue
// Δ-Invariante angepasst (nicht gelöscht) und sind mit "SUPERSEDED #817" markiert.

// AC-3 (Issue #701 / SUPERSEDED #817): Neue Metriken aktiviert → Delta-Regeln werden angelegt
// Issue #817: SyncAlertRules erzeugt nun kind="delta" statt "absolute".
func TestSyncAlertRules_NewMetrics(t *testing.T) {
	result := SyncAlertRules(nil, []string{"wind_gust", "precipitation_sum"})
	if len(result) != 2 {
		t.Fatalf("want 2 rules, got %d", len(result))
	}
	found := map[AlertMetric]bool{}
	for _, r := range result {
		found[r.Metric] = true
		// SUPERSEDED #817: war "absolute", ist jetzt "delta"
		if r.Kind != AlertRuleKindDelta {
			t.Errorf("metric %s: want kind=delta (Issue #817), got %s", r.Metric, r.Kind)
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

// AC-4 (Issue #701 / SUPERSEDED #817): Absolut-Regel wird migriert zu Delta mit DefaultDeltaThreshold
// Issue #817: Absolute Regel mit custom threshold 70 → wird auf Delta-Default 20 gesetzt.
// Hintergrund: absolute Threshold war nie alert-wirksam (from_alert_rules ignorierte ihn).
// ID und Enabled bleiben erhalten (read-modify-write).
func TestSyncAlertRules_PreservesExistingThreshold(t *testing.T) {
	existing := []AlertRule{
		{ID: "abc", Kind: AlertRuleKindAbsolute, Metric: AlertMetricWindGust, Threshold: 70, Unit: "km/h", Enabled: true},
	}
	result := SyncAlertRules(existing, []string{"wind_gust"})
	if len(result) != 1 {
		t.Fatalf("want 1 rule, got %d", len(result))
	}
	// SUPERSEDED #817: war "threshold 70 preserved (absolute)", ist jetzt Delta-Default 20.
	// Der absolute Threshold war nie alert-wirksam → kein Verlust durch Migration.
	if result[0].Threshold != DefaultDeltaThreshold[AlertMetricWindGust].Threshold {
		t.Errorf("SUPERSEDED #817: want threshold=%v (DefaultDeltaThreshold[wind_gust]), got %f",
			DefaultDeltaThreshold[AlertMetricWindGust].Threshold, result[0].Threshold)
	}
	if result[0].ID != "abc" {
		t.Errorf("want original ID 'abc', got %s", result[0].ID)
	}
	if result[0].Kind != AlertRuleKindDelta {
		t.Errorf("SUPERSEDED #817: want kind=delta after migration, got %s", result[0].Kind)
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

// AC-2 (Issue #701 / SUPERSEDED #817): *_change-Metriken erhalten keine Regel;
// thunder_level bekommt jetzt eine Delta-Regel (Issue #817).
func TestSyncAlertRules_ExcludesDeltaOnlyMetrics(t *testing.T) {
	// *_change-Metriken sind konzeptionell redundant nach #817 (Folge-Issue pending)
	// aber noch in AlertableMetrics ausgeschlossen.
	result := SyncAlertRules(nil, []string{"temperature_change", "wind_change", "precipitation_change"})
	if len(result) != 0 {
		t.Errorf("want 0 rules for *_change metrics, got %d", len(result))
	}
	// SUPERSEDED #817: thunder_level ist jetzt alertable (Delta-Regel mit Threshold=1)
	resultWithThunder := SyncAlertRules(nil, []string{"thunder_level"})
	if len(resultWithThunder) != 1 {
		t.Errorf("SUPERSEDED #817: want 1 rule for thunder_level (delta), got %d", len(resultWithThunder))
	}
	if len(resultWithThunder) == 1 && resultWithThunder[0].Kind != AlertRuleKindDelta {
		t.Errorf("SUPERSEDED #817: thunder_level rule should be kind=delta, got %s", resultWithThunder[0].Kind)
	}
}

// AC-4 (Issue #701 / SUPERSEDED #817): Bestehende Delta-Regel wird NICHT entfernt;
// bei Duplikat (delta+absolute für gleiche Metrik) gewinnt die ERSTE gefundene Regel.
// Issue #817: Delta-Regeln werden erhalten (idempotent). Absolute → zu Delta migriert.
func TestSyncAlertRules_RemovesDeltaRules(t *testing.T) {
	// SUPERSEDED #817: früher "delta wird entfernt, absolute bleibt".
	// Jetzt: beide indexiert, ERSTE gewinnt (delta), Threshold erhalten.
	existing := []AlertRule{
		{ID: "d1", Kind: AlertRuleKindDelta, Metric: AlertMetricWindGust, Threshold: 10},
		{ID: "a1", Kind: AlertRuleKindAbsolute, Metric: AlertMetricWindGust, Threshold: 50},
	}
	result := SyncAlertRules(existing, []string{"wind_gust"})
	if len(result) != 1 {
		t.Fatalf("want 1 rule (first match wins), got %d", len(result))
	}
	// SUPERSEDED #817: war "absolute bleibt"; jetzt: erste Regel (delta d1) bleibt,
	// Threshold 10 erhalten (bereits delta → kein Reset).
	if result[0].Kind != AlertRuleKindDelta {
		t.Errorf("SUPERSEDED #817: want delta (first rule wins), got %s", result[0].Kind)
	}
	if result[0].ID != "d1" {
		t.Errorf("SUPERSEDED #817: want ID d1 (first rule wins), got %s", result[0].ID)
	}
	if result[0].Threshold != 10 {
		t.Errorf("SUPERSEDED #817: delta threshold 10 must be preserved (idempotent), got %f", result[0].Threshold)
	}
}

// Issue #812: ActiveAlertableMetricIDs dedupliziert Duplikat-metric_id
func TestActiveAlertableMetricIDsDeduplicated(t *testing.T) {
	displayConfig := map[string]interface{}{
		"metrics": []interface{}{
			map[string]interface{}{"metric_id": "wind_gust", "enabled": true},
			map[string]interface{}{"metric_id": "wind_gust", "enabled": true}, // Duplikat
			map[string]interface{}{"metric_id": "precipitation_sum", "enabled": true},
		},
	}
	ids := ActiveAlertableMetricIDs(displayConfig)
	if len(ids) != 2 {
		t.Fatalf("want 2 unique IDs, got %d: %v", len(ids), ids)
	}
	rules := SyncAlertRules(nil, ids)
	if len(rules) != 2 {
		t.Fatalf("want 2 rules (one per unique metric), got %d", len(rules))
	}
	found := map[AlertMetric]int{}
	for _, r := range rules {
		found[r.Metric]++
	}
	if found[AlertMetricWindGust] != 1 {
		t.Errorf("want exactly 1 wind_gust rule, got %d", found[AlertMetricWindGust])
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

// AC-2 (Issue #701 / SUPERSEDED #817): thunder_level ist jetzt alertable (delta).
// Issue #817: thunder_level wurde zu AlertableMetrics hinzugefügt.
func TestSyncAlertRules_ThunderLevelNotAlertable(t *testing.T) {
	// SUPERSEDED #817: thunder_level ist jetzt in AlertableMetrics → bekommt Delta-Regel.
	result := SyncAlertRules(nil, []string{"thunder_level", "wind_gust"})
	if len(result) != 2 {
		t.Fatalf("SUPERSEDED #817: want 2 rules (thunder_level + wind_gust, beide delta), got %d", len(result))
	}
	found := map[AlertMetric]bool{}
	for _, r := range result {
		found[r.Metric] = true
		if r.Kind != AlertRuleKindDelta {
			t.Errorf("SUPERSEDED #817: metric %s: want kind=delta, got %s", r.Metric, r.Kind)
		}
	}
	if !found[AlertMetricThunderLevel] {
		t.Error("SUPERSEDED #817: want thunder_level rule")
	}
	if !found[AlertMetricWindGust] {
		t.Error("want wind_gust rule")
	}
}

// AC-4 (Issue #701 / SUPERSEDED #817): Mehrere aktive Metriken — absolute Regel wird
// auf Delta-Default migriert, neue Metrik bekommt Delta-Default.
func TestSyncAlertRules_MixedMerge(t *testing.T) {
	existing := []AlertRule{
		{ID: "x1", Kind: AlertRuleKindAbsolute, Metric: AlertMetricWindGust, Threshold: 75, Enabled: true},
	}
	result := SyncAlertRules(existing, []string{"wind_gust", "snow_line"})
	if len(result) != 2 {
		t.Fatalf("want 2 rules, got %d", len(result))
	}
	for _, r := range result {
		if r.Metric == AlertMetricWindGust {
			// SUPERSEDED #817: war "threshold 75 preserved"; jetzt Delta-Default (20).
			// Absolute Threshold war nie wirksam → Migration auf Delta-Default kein Verlust.
			wantThreshold := DefaultDeltaThreshold[AlertMetricWindGust].Threshold
			if r.Threshold != wantThreshold {
				t.Errorf("SUPERSEDED #817: wind_gust: want threshold=%v (DefaultDeltaThreshold), got %f", wantThreshold, r.Threshold)
			}
			if r.Kind != AlertRuleKindDelta {
				t.Errorf("SUPERSEDED #817: wind_gust: want kind=delta, got %s", r.Kind)
			}
		}
		if r.Metric == AlertMetricSnowLine && r.Threshold == 0 {
			t.Error("snow_line should have non-zero default threshold")
		}
	}
}
