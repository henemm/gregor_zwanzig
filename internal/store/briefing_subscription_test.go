package store

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

// TestBriefingSubscriptionRoundTrip_Lossless verifies ADR-0023's core claim
// (Issue #1250 Scheibe 5): a briefings/<id>.json with many fields, incl. one
// unmodeled field, survives Load->Save field-identical (as maps, key order
// irrelevant) -- the raw catch-all in model.BriefingSubscription must not
// drop anything (BUG-DATALOSS-GR221-Muster).
func TestBriefingSubscriptionRoundTrip_Lossless(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "user-a")

	dir := filepath.Join(tmpDir, "users", "user-a", "briefings")
	if err := os.MkdirAll(dir, 0755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}

	original := `{
		"id": "brief-1",
		"kind": "route",
		"name": "Stubaier Skitour",
		"stages": [{"id": "s1", "name": "Etappe 1", "date": "2026-08-01", "waypoints": []}],
		"location_ids": ["loc-a", "loc-b"],
		"empfaenger": ["gregor-test@henemm.com"],
		"schedule": "manual",
		"some_unknown_field": "keep-me",
		"nested": {"a": 1, "b": [1, 2, 3]}
	}`
	path := filepath.Join(dir, "brief-1.json")
	if err := os.WriteFile(path, []byte(original), 0644); err != nil {
		t.Fatalf("write fixture: %v", err)
	}

	loaded, err := s.LoadBriefing("brief-1")
	if err != nil {
		t.Fatalf("LoadBriefing: %v", err)
	}
	if loaded == nil {
		t.Fatal("LoadBriefing returned nil for existing file")
	}
	if loaded.ID != "brief-1" || loaded.Kind != "route" {
		t.Fatalf("typed fields not extracted: id=%q kind=%q", loaded.ID, loaded.Kind)
	}

	if err := s.SaveBriefing(loaded); err != nil {
		t.Fatalf("SaveBriefing: %v", err)
	}

	rewritten, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read back: %v", err)
	}

	var before, after map[string]any
	if err := json.Unmarshal([]byte(original), &before); err != nil {
		t.Fatalf("unmarshal original: %v", err)
	}
	if err := json.Unmarshal(rewritten, &after); err != nil {
		t.Fatalf("unmarshal rewritten: %v", err)
	}

	// json.Marshal on a map[string]any sorts keys alphabetically -- makes the
	// comparison independent of original key order (only content matters).
	beforeJSON, _ := json.Marshal(before)
	afterJSON, _ := json.Marshal(after)
	if string(beforeJSON) != string(afterJSON) {
		t.Fatalf("round-trip lost/changed fields:\nbefore: %s\nafter:  %s", beforeJSON, afterJSON)
	}
	if _, ok := after["some_unknown_field"]; !ok {
		t.Fatal("unmodeled field 'some_unknown_field' lost in round-trip")
	}
}

// TestLoadBriefing_MissingReturnsNil mirrors LoadTrip's not-found contract.
func TestLoadBriefing_MissingReturnsNil(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "user-a")

	loaded, err := s.LoadBriefing("does-not-exist")
	if err != nil {
		t.Fatalf("LoadBriefing: unexpected error: %v", err)
	}
	if loaded != nil {
		t.Fatalf("expected nil for missing briefing, got %+v", loaded)
	}
}
