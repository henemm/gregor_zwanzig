package model

import (
	"encoding/json"
	"reflect"
	"strings"
	"testing"
)

// TDD RED — Tests für Issue #205 AlertRule Datenmodell.
// Erwartet: FAIL bis AlertRule-Struct und Trip.AlertRules in trip.go ergänzt sind.

// AC-7 Vorbedingung: AlertRule Roundtrip via JSON.
func TestAlertRule_JSONRoundtrip(t *testing.T) {
	in := AlertRule{
		ID:        "abc-123",
		Kind:      AlertRuleKindDelta,
		Metric:    AlertMetricWindChange,
		Threshold: 20.0,
		Unit:      "km/h",
		Severity:  AlertSeverityWarning,
		Enabled:   true,
	}
	b, err := json.Marshal(in)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	for _, want := range []string{
		`"id":"abc-123"`,
		`"kind":"delta"`,
		`"metric":"wind_change"`,
		`"threshold":20`,
		`"unit":"km/h"`,
		`"severity":"warning"`,
		`"enabled":true`,
	} {
		if !strings.Contains(string(b), want) {
			t.Errorf("JSON fehlt %q, war: %s", want, string(b))
		}
	}

	var out AlertRule
	if err := json.Unmarshal(b, &out); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if !reflect.DeepEqual(out, in) {
		t.Fatalf("Roundtrip nicht identisch:\n in: %+v\nout: %+v", in, out)
	}
}

// AC-7: Leere AlertRules-Liste serialisiert als [], nicht null oder fehlend.
func TestTrip_AlertRulesEmptySerializesAsArray(t *testing.T) {
	in := Trip{
		ID:         "t1",
		Name:       "Trip ohne Rules",
		AlertRules: []AlertRule{},
	}
	b, err := json.Marshal(in)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	s := string(b)

	if !strings.Contains(s, `"alert_rules":[]`) {
		t.Fatalf("Erwartet leeres Array \"alert_rules\":[], war: %s", s)
	}
	if strings.Contains(s, `"alert_rules":null`) {
		t.Fatalf("AlertRules darf nicht als null serialisieren, war: %s", s)
	}
}

// AC-7 (F002 fix): Legacy-JSON ohne alert_rules-Feld → nach Unmarshal ist
// AlertRules nil. Vor dem nächsten Marshal MUSS nil zu []AlertRule{} coerced
// werden, sonst landet "alert_rules":null im File und triggert beim
// nächsten Python-Load erneut die Legacy-Migration.
func TestTrip_AlertRulesNilSerializesAsArray(t *testing.T) {
	legacyJSON := `{"id":"t1","name":"Legacy Trip"}`
	var trip Trip
	if err := json.Unmarshal([]byte(legacyJSON), &trip); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if trip.AlertRules != nil {
		t.Fatalf("Erwartet nil nach Unmarshal von legacy JSON, got %v", trip.AlertRules)
	}
	// SaveTrip in internal/store/store.go führt diese Coercion durch.
	if trip.AlertRules == nil {
		trip.AlertRules = []AlertRule{}
	}
	b, err := json.Marshal(trip)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	if !strings.Contains(string(b), `"alert_rules":[]`) {
		t.Fatalf("Nach nil-Coercion erwartet \"alert_rules\":[], war: %s", string(b))
	}
	if strings.Contains(string(b), `"alert_rules":null`) {
		t.Fatalf("alert_rules darf NICHT als null serialisieren, war: %s", string(b))
	}
}

// Zusatz: Trip mit AlertRules Roundtrip-Test (verstärkt AC-7).
func TestTrip_AlertRulesRoundtrip(t *testing.T) {
	in := Trip{
		ID:   "t1",
		Name: "Trip mit Rules",
		AlertRules: []AlertRule{
			{
				ID:        "r1",
				Kind:      AlertRuleKindAbsolute,
				Metric:    AlertMetricWindGust,
				Threshold: 50.0,
				Unit:      "km/h",
				Severity:  AlertSeverityCritical,
				Enabled:   true,
			},
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
	if len(out.AlertRules) != 1 {
		t.Fatalf("Erwartet 1 Rule nach Roundtrip, got %d", len(out.AlertRules))
	}
	if out.AlertRules[0].Metric != AlertMetricWindGust {
		t.Fatalf("Metric verloren beim Roundtrip: got %q", out.AlertRules[0].Metric)
	}
}
