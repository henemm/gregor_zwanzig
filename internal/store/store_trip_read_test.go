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

// AC-2: Existierende Rules für aktive alert-fähige Metriken werden NICHT überschrieben.
// Issue #809: display_config.metrics muss aktive alert-fähige Metriken enthalten,
// damit der Self-Heal die bestehenden Regeln preserved (SyncAlertRules Merge-Semantik).
// Nicht-alertable Metriken (thunder_level, wind_change als delta) werden durch
// SyncAlertRules korrekt herausgefiltert — das ist beabsichtigtes Verhalten seit #701.
func TestLoadTrip_PreservesExistingAlertRules(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "test")

	tripDir := filepath.Join(tmpDir, "users", "test", "trips")
	if err := os.MkdirAll(tripDir, 0755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	// display_config enthält wind_gust als aktive alert-fähige Metrik.
	// Die bestehende absolute wind_gust-Regel (threshold=50) muss erhalten bleiben.
	withRules := `{
		"id": "with-rules",
		"name": "Trip mit Rules",
		"stages": [],
		"display_config": {
			"metrics": [
				{"metric_id": "wind_gust", "enabled": true}
			]
		},
		"alert_rules": [
			{"id":"r1","kind":"absolute","metric":"wind_gust","threshold":50,"unit":"km/h","severity":"critical","enabled":true}
		]
	}`
	if err := os.WriteFile(filepath.Join(tripDir, "with-rules.json"), []byte(withRules), 0644); err != nil {
		t.Fatalf("write: %v", err)
	}

	loaded, err := s.LoadTrip("with-rules")
	if err != nil {
		t.Fatalf("LoadTrip: %v", err)
	}
	// Nach Self-Heal: genau 1 absolute wind_gust-Regel mit unverändertem Threshold.
	if len(loaded.AlertRules) != 1 {
		t.Fatalf("Erwartet 1 Rule (wind_gust), got %d: %+v", len(loaded.AlertRules), loaded.AlertRules)
	}
	if loaded.AlertRules[0].Metric != model.AlertMetricWindGust {
		t.Errorf("Rule 0 Metric falsch: %q", loaded.AlertRules[0].Metric)
	}
	if loaded.AlertRules[0].Threshold != 50 {
		t.Errorf("Rule 0 Threshold falsch (soll 50 bleiben): %v", loaded.AlertRules[0].Threshold)
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
