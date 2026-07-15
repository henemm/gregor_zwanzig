package store

// Issue #1244: SaveTrip muss "corridors"/"stages"/pro-Stage "waypoints" NIE
// als JSON `null` persistieren -- der Python-Loader crasht sonst beim naechsten
// Laden (TypeError: 'NoneType' object is not iterable) und der Trip
// verschwindet lautlos aus load_all_trips(). Analog zur bestehenden
// AlertRules-Coercion (Issue #205 F002, trip.go:100-104).
//
// Spec: docs/specs/modules/fix_1244_null_list_fields.md, AC-1/AC-2.
// Keine Mocks -- echter Filesystem-Roundtrip via t.TempDir(), rohe JSON-Datei
// wird nach dem Schreiben eingelesen und auf "[]" statt "null" geprueft.

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/henemm/gregor-api/internal/model"
)

func TestSaveTrip_NilCorridorsStagesWaypointsCoercedToEmptyArrays(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "test")

	// Trip wie er beim POST /api/trips ohne corridors/stages im Body
	// entsteht: alle drei Slice-Felder sind nil (Go-Zero-Value).
	trip := model.Trip{
		ID:   "nil-coercion-trip",
		Name: "Nil Coercion Trip",
		// Corridors, Stages absichtlich nicht gesetzt -> nil.
	}

	if err := s.SaveTrip(&trip); err != nil {
		t.Fatalf("SaveTrip failed: %v", err)
	}

	written, err := os.ReadFile(filepath.Join(tmpDir, "users", "test", "briefings", "nil-coercion-trip.json"))
	if err != nil {
		t.Fatalf("read written: %v", err)
	}
	raw := string(written)

	if !strings.Contains(raw, `"corridors": []`) {
		t.Errorf("Erwartet \"corridors\": [] im File, war: %s", raw)
	}
	if strings.Contains(raw, `"corridors": null`) {
		t.Errorf("corridors darf NICHT null sein, war: %s", raw)
	}
	if !strings.Contains(raw, `"stages": []`) {
		t.Errorf("Erwartet \"stages\": [] im File, war: %s", raw)
	}
	if strings.Contains(raw, `"stages": null`) {
		t.Errorf("stages darf NICHT null sein, war: %s", raw)
	}
}

func TestSaveTrip_NilWaypointsWithinStageCoercedToEmptyArray(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "test")

	trip := model.Trip{
		ID:   "nil-waypoints-trip",
		Name: "Nil Waypoints Trip",
		Stages: []model.Stage{
			// Waypoints absichtlich nicht gesetzt -> nil (wie bei einer
			// Stage, die per Request-Body ohne "waypoints"-Key ankommt).
			{ID: "S1", Name: "Etappe 1", Date: "2026-07-20"},
		},
	}

	if err := s.SaveTrip(&trip); err != nil {
		t.Fatalf("SaveTrip failed: %v", err)
	}

	written, err := os.ReadFile(filepath.Join(tmpDir, "users", "test", "briefings", "nil-waypoints-trip.json"))
	if err != nil {
		t.Fatalf("read written: %v", err)
	}
	raw := string(written)

	if !strings.Contains(raw, `"waypoints": []`) {
		t.Errorf("Erwartet \"waypoints\": [] im File, war: %s", raw)
	}
	if strings.Contains(raw, `"waypoints": null`) {
		t.Errorf("waypoints darf NICHT null sein, war: %s", raw)
	}

	loaded, err := s.LoadTrip("nil-waypoints-trip")
	if err != nil {
		t.Fatalf("LoadTrip failed: %v", err)
	}
	if loaded == nil {
		t.Fatal("expected trip, got nil")
	}
	if len(loaded.Stages) != 1 {
		t.Fatalf("expected 1 stage, got %d", len(loaded.Stages))
	}
	if loaded.Stages[0].Waypoints == nil {
		t.Error("Erwartet [] statt nil nach Reload fuer Waypoints")
	}
}
