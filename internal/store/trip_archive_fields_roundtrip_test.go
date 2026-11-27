package store

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

// Issue #611 — die #583-Felder (accuracy_pct/headline/briefings_count/
// alerts_count) wurden aus dem Trip-Modell entfernt. Dieser Test sichert ab,
// dass:
//   1. Altdaten, die diese Felder noch enthalten, weiterhin fehlerfrei laden
//      (unbekannte JSON-Felder werden ignoriert, kein Datenverlust bei
//      restlichen Feldern).
//   2. Round-Trip über Go bewahrt die Altfelder unverändert in der Datei
//      (ADR-0101, #3092), das geladene Modell enthält sie nicht.

func TestTripRoundTrip_LegacyAnalyticsFieldsPreservedNotExposed(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "test")

	tripDir := filepath.Join(tmpDir, "users", "test", "briefings")
	if err := os.MkdirAll(tripDir, 0755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}

	// Altdaten mit den entfernten #583-Feldern + einem realen Feld (name),
	// das erhalten bleiben muss.
	legacyJSON := `{
		"id": "ortler-2025",
		"name": "Ortler-Überquerung",
		"stages": [],
		"alert_rules": [],
		"accuracy_pct": 92,
		"headline": "Gewitter Tag 2",
		"briefings_count": 5,
		"alerts_count": 2
	}`
	path := filepath.Join(tripDir, "ortler-2025.json")
	if err := os.WriteFile(path, []byte(legacyJSON), 0644); err != nil {
		t.Fatalf("write trip: %v", err)
	}

	loaded, err := s.LoadTrip("ortler-2025")
	if err != nil {
		t.Fatalf("LoadTrip (legacy with removed fields must not fail): %v", err)
	}
	if loaded.Name != "Ortler-Überquerung" {
		t.Fatalf("real field lost: name=%q", loaded.Name)
	}

	if err := s.SaveTrip(loaded); err != nil {
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
	want := map[string]any{
		"accuracy_pct":    float64(92),
		"headline":        "Gewitter Tag 2",
		"briefings_count": float64(5),
		"alerts_count":    float64(2),
	}
	for f, w := range want {
		if got[f] != w {
			t.Errorf("legacy field %q must stay unchanged in file (ADR-0101), got %v, want %v", f, got[f], w)
		}
	}

	exposed, err := json.Marshal(loaded)
	if err != nil {
		t.Fatalf("marshal loaded: %v", err)
	}
	var model map[string]any
	if err := json.Unmarshal(exposed, &model); err != nil {
		t.Fatalf("unmarshal loaded: %v", err)
	}
	for f := range want {
		if _, exists := model[f]; exists {
			t.Errorf("legacy field %q must not be exposed by the loaded model", f)
		}
	}
}
