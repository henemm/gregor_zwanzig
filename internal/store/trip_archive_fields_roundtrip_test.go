package store

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

// TDD RED — Issue #583 AC-2 (Go-Seite).
// Erwartet: FAIL bis die additiven Felder `accuracy_pct` (*int) und
// `headline` (string, omitempty) im Trip-Modell existieren.
//
// AC-2: Trip mit accuracy_pct=92 und headline="Gewitter Tag 2..." →
// SaveTrip → LoadTrip → beide Felder erhalten.

func TestTripRoundTrip_PreservesAccuracyAndHeadline(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "test")

	tripDir := filepath.Join(tmpDir, "users", "test", "trips")
	if err := os.MkdirAll(tripDir, 0755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}

	tripJSON := `{
		"id": "ortler-2025",
		"name": "Ortler-Überquerung",
		"stages": [],
		"alert_rules": [],
		"accuracy_pct": 92,
		"headline": "Gewitter Tag 2 wie prognostiziert — Aufstieg vorgezogen"
	}`
	path := filepath.Join(tripDir, "ortler-2025.json")
	if err := os.WriteFile(path, []byte(tripJSON), 0644); err != nil {
		t.Fatalf("write trip: %v", err)
	}

	loaded, err := s.LoadTrip("ortler-2025")
	if err != nil {
		t.Fatalf("LoadTrip: %v", err)
	}

	if err := s.SaveTrip(*loaded); err != nil {
		t.Fatalf("SaveTrip: %v", err)
	}

	reloaded, err := s.LoadTrip("ortler-2025")
	if err != nil {
		t.Fatalf("re-LoadTrip: %v", err)
	}

	// Round-Trip preserved fields — via raw JSON re-marshal because
	// model fields exist nur wenn die Struct sie kennt.
	raw, err := json.Marshal(reloaded)
	if err != nil {
		t.Fatalf("marshal reloaded: %v", err)
	}

	var got map[string]any
	if err := json.Unmarshal(raw, &got); err != nil {
		t.Fatalf("unmarshal got: %v", err)
	}

	if v, ok := got["accuracy_pct"].(float64); !ok || int(v) != 92 {
		t.Errorf("AC-2 FAIL: expected accuracy_pct=92, got %v (type %T)",
			got["accuracy_pct"], got["accuracy_pct"])
	}

	headline, _ := got["headline"].(string)
	if headline != "Gewitter Tag 2 wie prognostiziert — Aufstieg vorgezogen" {
		t.Errorf("AC-2 FAIL: expected headline preserved, got %q", headline)
	}
}

// AC-2b: omitempty — Trip OHNE accuracy_pct/headline darf nach Round-Trip
// auch keine null-Werte einschleifen.
func TestTripRoundTrip_LegacyWithoutAccuracyHeadline(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "test")

	tripDir := filepath.Join(tmpDir, "users", "test", "trips")
	if err := os.MkdirAll(tripDir, 0755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}

	legacyJSON := `{
		"id": "legacy-trip",
		"name": "Legacy",
		"stages": [],
		"alert_rules": []
	}`
	path := filepath.Join(tripDir, "legacy-trip.json")
	if err := os.WriteFile(path, []byte(legacyJSON), 0644); err != nil {
		t.Fatalf("write legacy: %v", err)
	}

	loaded, err := s.LoadTrip("legacy-trip")
	if err != nil {
		t.Fatalf("LoadTrip: %v", err)
	}
	if err := s.SaveTrip(*loaded); err != nil {
		t.Fatalf("SaveTrip: %v", err)
	}

	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read back: %v", err)
	}

	var got map[string]any
	if err := json.Unmarshal(data, &got); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}

	// Beide Felder DÜRFEN NICHT im JSON erscheinen wenn nicht gesetzt
	// (omitempty + Pointer für int sorgt dafür).
	if _, exists := got["accuracy_pct"]; exists {
		t.Errorf("AC-2b FAIL: accuracy_pct should be omitted when nil, got %v", got["accuracy_pct"])
	}
	if v, exists := got["headline"]; exists && v != "" {
		t.Errorf("AC-2b FAIL: headline should be omitted when empty, got %q", v)
	}
}
