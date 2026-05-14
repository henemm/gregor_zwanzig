package store

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/henemm/gregor-api/internal/model"
)

// Issue #205 F002: Legacy-Trip-JSON ohne alert_rules-Feld darf nach
// LoadTrip → SaveTrip NICHT als "alert_rules":null im File landen,
// sonst triggert Python beim nächsten Load erneut Legacy-Migration.
func TestSaveTrip_LegacyAlertRulesCoercedToEmptyArray(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "test")

	tripDir := filepath.Join(tmpDir, "users", "test", "trips")
	if err := os.MkdirAll(tripDir, 0755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}

	// Legacy-JSON-File ohne alert_rules-Feld (wie Bestandsdaten)
	legacyJSON := `{"id":"legacy-1","name":"Legacy Trip","stages":[]}`
	if err := os.WriteFile(filepath.Join(tripDir, "legacy-1.json"), []byte(legacyJSON), 0644); err != nil {
		t.Fatalf("write legacy json: %v", err)
	}

	loaded, err := s.LoadTrip("legacy-1")
	if err != nil {
		t.Fatalf("LoadTrip: %v", err)
	}
	if loaded == nil {
		t.Fatal("expected trip, got nil")
	}
	if loaded.AlertRules != nil {
		t.Fatalf("Erwartet nil nach Load von legacy JSON, got %v", loaded.AlertRules)
	}

	if err := s.SaveTrip(*loaded); err != nil {
		t.Fatalf("SaveTrip: %v", err)
	}

	written, err := os.ReadFile(filepath.Join(tripDir, "legacy-1.json"))
	if err != nil {
		t.Fatalf("read written: %v", err)
	}
	s2 := string(written)
	if !strings.Contains(s2, `"alert_rules": []`) {
		t.Fatalf("Erwartet \"alert_rules\": [] im File, war: %s", s2)
	}
	if strings.Contains(s2, `"alert_rules": null`) {
		t.Fatalf("alert_rules darf NICHT null sein, war: %s", s2)
	}
}

func TestSaveTripAndLoad(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "test")

	trip := model.Trip{
		ID:   "save-test",
		Name: "Save Test Trip",
		Stages: []model.Stage{
			{
				ID: "S1", Name: "Day 1", Date: "2026-05-01",
				Waypoints: []model.Waypoint{
					{ID: "W1", Name: "Start", Lat: 47.0, Lon: 11.0, ElevationM: 500},
				},
			},
		},
	}

	if err := s.SaveTrip(trip); err != nil {
		t.Fatalf("SaveTrip failed: %v", err)
	}

	loaded, err := s.LoadTrip("save-test")
	if err != nil {
		t.Fatalf("LoadTrip failed: %v", err)
	}
	if loaded == nil {
		t.Fatal("expected trip, got nil")
	}
	if loaded.Name != "Save Test Trip" {
		t.Errorf("expected name 'Save Test Trip', got %s", loaded.Name)
	}
	if len(loaded.Stages) != 1 {
		t.Errorf("expected 1 stage, got %d", len(loaded.Stages))
	}
}

func TestDeleteTrip(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "test")

	trip := model.Trip{
		ID: "del-test", Name: "Delete Me",
		Stages: []model.Stage{{ID: "S1", Name: "D1", Date: "2026-05-01",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}},
		}},
	}
	s.SaveTrip(trip)

	if err := s.DeleteTrip("del-test"); err != nil {
		t.Fatalf("DeleteTrip failed: %v", err)
	}

	loaded, _ := s.LoadTrip("del-test")
	if loaded != nil {
		t.Error("expected nil after delete")
	}
}

func TestDeleteTripNotFound(t *testing.T) {
	tmpDir := t.TempDir()
	tripDir := filepath.Join(tmpDir, "users", "test", "trips")
	os.MkdirAll(tripDir, 0755)

	s := New(tmpDir, "test")
	err := s.DeleteTrip("nonexistent")
	if err != nil {
		t.Errorf("expected no error for nonexistent trip, got %v", err)
	}
}
