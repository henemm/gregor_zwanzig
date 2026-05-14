package store

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/henemm/gregor-api/internal/model"
)

// Issue #205 Follow-Up — Read-Path-Coercion.
// External Validator hat entdeckt, dass GET /api/trips Legacy-Trips mit
// "alert_rules":null zurueckliefert. LoadTrip() muss nil → []AlertRule{}
// coercen, damit Konsumenten konsistent ein Array sehen.

// AC-1: Legacy-JSON ohne alert_rules → LoadTrip liefert leeres Slice, nicht nil.
func TestLoadTrip_LegacyJSONCoercesNilAlertRulesToEmpty(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "test")

	tripDir := filepath.Join(tmpDir, "users", "test", "trips")
	if err := os.MkdirAll(tripDir, 0755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	legacyJSON := `{"id":"legacy-2","name":"Legacy ohne alert_rules","stages":[]}`
	if err := os.WriteFile(filepath.Join(tripDir, "legacy-2.json"), []byte(legacyJSON), 0644); err != nil {
		t.Fatalf("write: %v", err)
	}

	loaded, err := s.LoadTrip("legacy-2")
	if err != nil {
		t.Fatalf("LoadTrip: %v", err)
	}
	if loaded == nil {
		t.Fatal("expected trip, got nil")
	}
	if loaded.AlertRules == nil {
		t.Fatalf("Erwartet leeres Slice nach Load, got nil")
	}
	if len(loaded.AlertRules) != 0 {
		t.Fatalf("Erwartet len==0, got %d", len(loaded.AlertRules))
	}
}

// AC-2: Existierende Rules werden NICHT überschrieben.
func TestLoadTrip_PreservesExistingAlertRules(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "test")

	tripDir := filepath.Join(tmpDir, "users", "test", "trips")
	if err := os.MkdirAll(tripDir, 0755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	withRules := `{
		"id": "with-rules",
		"name": "Trip mit Rules",
		"stages": [],
		"alert_rules": [
			{"id":"r1","kind":"absolute","metric":"wind_gust","threshold":50,"unit":"km/h","severity":"critical","enabled":true},
			{"id":"r2","kind":"delta","metric":"wind_change","threshold":20,"unit":"km/h","severity":"warning","enabled":false},
			{"id":"r3","kind":"absolute","metric":"thunder_level","threshold":1,"severity":"info","enabled":true}
		]
	}`
	if err := os.WriteFile(filepath.Join(tripDir, "with-rules.json"), []byte(withRules), 0644); err != nil {
		t.Fatalf("write: %v", err)
	}

	loaded, err := s.LoadTrip("with-rules")
	if err != nil {
		t.Fatalf("LoadTrip: %v", err)
	}
	if len(loaded.AlertRules) != 3 {
		t.Fatalf("Erwartet 3 Rules, got %d", len(loaded.AlertRules))
	}
	if loaded.AlertRules[0].Metric != model.AlertMetricWindGust {
		t.Errorf("Rule 0 Metric falsch: %q", loaded.AlertRules[0].Metric)
	}
	if loaded.AlertRules[1].Threshold != 20 {
		t.Errorf("Rule 1 Threshold falsch: %v", loaded.AlertRules[1].Threshold)
	}
}

// AC-3: Nach LoadTrip serialisiert json.Marshal alert_rules als []  (niemals null).
func TestLoadTrip_MarshalAfterLoadProducesEmptyArrayNotNull(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "test")

	tripDir := filepath.Join(tmpDir, "users", "test", "trips")
	if err := os.MkdirAll(tripDir, 0755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	legacyJSON := `{"id":"legacy-3","name":"API-Response-Test","stages":[]}`
	if err := os.WriteFile(filepath.Join(tripDir, "legacy-3.json"), []byte(legacyJSON), 0644); err != nil {
		t.Fatalf("write: %v", err)
	}

	loaded, err := s.LoadTrip("legacy-3")
	if err != nil {
		t.Fatalf("LoadTrip: %v", err)
	}

	// Simuliere GET /api/trips/<id>: Handler marshalled trip ohne weitere Modifikation.
	b, err := json.Marshal(loaded)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	out := string(b)
	if !strings.Contains(out, `"alert_rules":[]`) {
		t.Fatalf("Erwartet \"alert_rules\":[] im API-Response, war: %s", out)
	}
	if strings.Contains(out, `"alert_rules":null`) {
		t.Fatalf("alert_rules darf NICHT null sein im API-Response, war: %s", out)
	}
}
