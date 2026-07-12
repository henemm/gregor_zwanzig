package model

import (
	"encoding/json"
	"testing"
)

// TDD — Issue #1231, Slice 1: Corridor-Datenmodell (additiv neben AlertRules).
// Roundtrip mit einseitig offener Range-Seite (null) + Erhalt von AlertRules.

func f64(v float64) *float64 { return &v }

func TestCorridor_RoundtripWithOpenRangeSide(t *testing.T) {
	in := Trip{
		ID:   "t1",
		Name: "Korridor-Test",
		AlertRules: []AlertRule{
			{ID: "r1", Kind: AlertRuleKindDelta, Metric: AlertMetricWindGust, Threshold: 20.0, Severity: AlertSeverityWarning, Enabled: true},
		},
		Corridors: []Corridor{
			{Metric: "wind_gust", Range: [2]*float64{nil, f64(45.0)}, Notify: true, Mark: false},
		},
	}

	b, err := json.Marshal(in)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}

	var out Trip
	if err := json.Unmarshal(b, &out); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}

	// AlertRules bleibt unberührt (Additiv-Kontrakt).
	if len(out.AlertRules) != 1 || out.AlertRules[0].ID != "r1" {
		t.Fatalf("AlertRules muss erhalten bleiben, got %+v", out.AlertRules)
	}

	if len(out.Corridors) != 1 {
		t.Fatalf("expected 1 Corridor, got %d", len(out.Corridors))
	}
	c := out.Corridors[0]
	if c.Metric != "wind_gust" {
		t.Fatalf("expected metric=wind_gust, got %q", c.Metric)
	}
	if c.Range[0] != nil {
		t.Fatalf("expected Range[0]=nil (offene Untergrenze), got %v", *c.Range[0])
	}
	if c.Range[1] == nil || *c.Range[1] != 45.0 {
		t.Fatalf("expected Range[1]=45.0, got %v", c.Range[1])
	}
	if !c.Notify || c.Mark {
		t.Fatalf("expected Notify=true, Mark=false, got Notify=%v Mark=%v", c.Notify, c.Mark)
	}
}

// Corridors verhaelt sich beim Marshal von Zero-Value-Slices bewusst
// IDENTISCH zu AlertRules (beide ohne omitempty -> "null" bei nil-Slice,
// "[]" bei explizit leerem Slice) — konsistent zum bestehenden Muster,
// die tatsaechliche Immer-Nicht-null-Garantie liefert die Store-Schicht
// (internal/store), nicht der reine json.Marshal-Zero-Value-Fall.
func TestCorridor_EmptySliceEmitsEmptyArrayLikeAlertRules(t *testing.T) {
	in := Trip{ID: "t2", Name: "Ohne Korridore", AlertRules: []AlertRule{}, Corridors: []Corridor{}}
	b, err := json.Marshal(in)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	var raw map[string]interface{}
	if err := json.Unmarshal(b, &raw); err != nil {
		t.Fatalf("unmarshal raw: %v", err)
	}
	corridors, ok := raw["corridors"].([]interface{})
	if !ok {
		t.Fatalf("expected corridors als [] bei explizit leerem Slice, got %v", raw["corridors"])
	}
	if len(corridors) != 0 {
		t.Fatalf("expected leeres corridors-Array, got %v", corridors)
	}
}

func TestComparePreset_CorridorsField(t *testing.T) {
	in := ComparePreset{
		ID: "p1", Name: "Preset",
		Corridors: []Corridor{
			{Metric: "temp_max_c", Range: [2]*float64{f64(-5.0), f64(25.0)}, Notify: false, Mark: true},
		},
	}
	b, err := json.Marshal(in)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	var out ComparePreset
	if err := json.Unmarshal(b, &out); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if len(out.Corridors) != 1 || out.Corridors[0].Metric != "temp_max_c" {
		t.Fatalf("expected 1 Corridor mit metric=temp_max_c, got %+v", out.Corridors)
	}
}
