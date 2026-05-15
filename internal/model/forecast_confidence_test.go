package model

import (
	"encoding/json"
	"strings"
	"testing"
	"time"
)

// TDD RED — Issue #121 / AC-2: ForecastDataPoint backward-compat for ensemble fields.
// Expected: FAIL until ConfidencePct, SpreadT2mK, SpreadPrecipMm fields exist.

// AC-2: A JSON payload without the three new fields must unmarshal cleanly,
// leaving the new fields as nil. New code can marshal them with omitempty.
func TestForecastDataPoint_ConfidenceFieldsBackwardCompat(t *testing.T) {
	// Old JSON without confidence/spread fields.
	old := `{"ts":"2026-05-15T08:00:00Z","t2m_c":20.0,"pop_pct":40}`

	var dp ForecastDataPoint
	if err := json.Unmarshal([]byte(old), &dp); err != nil {
		t.Fatalf("unmarshal old payload: %v", err)
	}
	if dp.ConfidencePct != nil {
		t.Errorf("ConfidencePct expected nil, got %v", *dp.ConfidencePct)
	}
	if dp.SpreadT2mK != nil {
		t.Errorf("SpreadT2mK expected nil, got %v", *dp.SpreadT2mK)
	}
	if dp.SpreadPrecipMm != nil {
		t.Errorf("SpreadPrecipMm expected nil, got %v", *dp.SpreadPrecipMm)
	}
}

func TestForecastDataPoint_ConfidenceFieldsRoundtrip(t *testing.T) {
	conf := 85
	spreadT := 1.5
	spreadP := 0.4
	ts, _ := time.Parse(time.RFC3339, "2026-05-15T08:00:00Z")

	in := ForecastDataPoint{
		Time:           UTCTime{Time: ts},
		ConfidencePct:  &conf,
		SpreadT2mK:     &spreadT,
		SpreadPrecipMm: &spreadP,
	}
	b, err := json.Marshal(in)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	for _, want := range []string{
		`"confidence_pct":85`,
		`"spread_t2m_k":1.5`,
		`"spread_precip_mm":0.4`,
	} {
		if !strings.Contains(string(b), want) {
			t.Errorf("marshaled JSON missing %q in %s", want, string(b))
		}
	}

	// Roundtrip
	var out ForecastDataPoint
	if err := json.Unmarshal(b, &out); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if out.ConfidencePct == nil || *out.ConfidencePct != 85 {
		t.Errorf("ConfidencePct roundtrip failed: %+v", out.ConfidencePct)
	}
	if out.SpreadT2mK == nil || *out.SpreadT2mK != 1.5 {
		t.Errorf("SpreadT2mK roundtrip failed: %+v", out.SpreadT2mK)
	}
	if out.SpreadPrecipMm == nil || *out.SpreadPrecipMm != 0.4 {
		t.Errorf("SpreadPrecipMm roundtrip failed: %+v", out.SpreadPrecipMm)
	}
}

func TestForecastDataPoint_ConfidenceFieldsOmitEmpty(t *testing.T) {
	// Without the new fields set, marshaled JSON must NOT contain the keys.
	ts, _ := time.Parse(time.RFC3339, "2026-05-15T08:00:00Z")
	dp := ForecastDataPoint{Time: UTCTime{Time: ts}}
	b, err := json.Marshal(dp)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	for _, key := range []string{`"confidence_pct"`, `"spread_t2m_k"`, `"spread_precip_mm"`} {
		if strings.Contains(string(b), key) {
			t.Errorf("expected key %s to be omitted, got: %s", key, string(b))
		}
	}
}
