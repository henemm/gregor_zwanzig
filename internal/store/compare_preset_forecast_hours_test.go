package store

// TDD RED: Issue #764 — LoadComparePresets forecast_hours-Default (AC-4).
//
// Spec: docs/specs/modules/issue_764_compare_forecast_hours.md §AC-4
//
// Prüft: Ein Legacy-Preset in compare_presets.json OHNE forecast_hours-Feld
//        wird beim Laden via LoadComparePresets() auf 48 defaultet (kein
//        ungültiges Go-Zero-Value 0 — "0 h Horizont" gibt es nicht).
//
// RED: Dieser Test kompiliert AKTUELL NICHT, weil das Feld ForecastHours
// im model.ComparePreset-Struct noch nicht existiert (presets[0].ForecastHours
// ist ein undefiniertes Feld). Das ist ein gültiges RED — der Compile-Fehler
// beweist, dass das Feature fehlt. Nach /5-implement (Feld + Load-Default)
// muss der Test grün sein.
//
// KEINE Mocks: echter Datei-Roundtrip gegen eine temporäre
// compare_presets.json — reales Store-Verhalten.

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

// =============================================================================
// AC-4: LoadComparePresets — forecast_hours-Default für Legacy-Presets
// =============================================================================

func TestLoadComparePresets_LegacyPresetGetsDefaultForecastHours(t *testing.T) {
	// GIVEN: compare_presets.json mit einem Preset OHNE forecast_hours-Feld (Altdaten)
	tmpDir := t.TempDir()
	s := New(tmpDir, "user1")

	rawJSON := `[{
		"id": "cp-legacy-no-horizon",
		"name": "Legacy Preset ohne Horizont",
		"user_id": "user1",
		"location_ids": ["loc-a"],
		"schedule": "daily",
		"profil": "SUMMER_TREKKING",
		"hour_from": 9,
		"hour_to": 16,
		"empfaenger": ["test@example.com"],
		"created_at": "2026-01-01T00:00:00Z"
	}]`
	// forecast_hours-Feld fehlt bewusst → JSON-Unmarshal liefert Zero-Value 0

	userDir := filepath.Join(tmpDir, "users", "user1")
	if err := os.MkdirAll(userDir, 0755); err != nil {
		t.Fatalf("MkdirAll: %v", err)
	}
	presetFile := filepath.Join(userDir, "compare_presets.json")
	if err := os.WriteFile(presetFile, []byte(rawJSON), 0644); err != nil {
		t.Fatalf("WriteFile: %v", err)
	}

	// WHEN: LoadComparePresets() aufgerufen
	presets, err := s.LoadComparePresets()
	if err != nil {
		t.Fatalf("LoadComparePresets failed: %v", err)
	}
	if len(presets) != 1 {
		t.Fatalf("expected 1 preset, got %d", len(presets))
	}

	// THEN: ForecastHours == 48 (Default für Legacy ohne Feld)
	// RED: scheitert/kompiliert nicht, weil das Feld noch nicht existiert
	// bzw. der Load-Default 0 → 48 noch nicht angewandt wird.
	if presets[0].ForecastHours != 48 {
		t.Errorf(
			"expected ForecastHours=48 (Default) für Legacy-Preset ohne forecast_hours-Feld, got %d — "+
				"LoadComparePresets() wendet noch keinen forecast_hours-Default an (RED)",
			presets[0].ForecastHours,
		)
	}
}

func TestLoadComparePresets_ExplicitForecastHoursPreserved(t *testing.T) {
	// GIVEN: Preset MIT explizitem forecast_hours=72 (gültiger Horizont)
	// THEN: forecast_hours=72 bleibt erhalten (Default nur bei 0)
	tmpDir := t.TempDir()
	s := New(tmpDir, "user1")

	rawJSON := `[{
		"id": "cp-explicit-72",
		"name": "72h Preset",
		"user_id": "user1",
		"location_ids": ["loc-a"],
		"schedule": "daily",
		"forecast_hours": 72,
		"profil": "SUMMER_TREKKING",
		"hour_from": 9,
		"hour_to": 16,
		"empfaenger": ["test@example.com"],
		"created_at": "2026-01-01T00:00:00Z"
	}]`

	userDir := filepath.Join(tmpDir, "users", "user1")
	if err := os.MkdirAll(userDir, 0755); err != nil {
		t.Fatalf("MkdirAll: %v", err)
	}
	if err := os.WriteFile(filepath.Join(userDir, "compare_presets.json"), []byte(rawJSON), 0644); err != nil {
		t.Fatalf("WriteFile: %v", err)
	}

	presets, err := s.LoadComparePresets()
	if err != nil {
		t.Fatalf("LoadComparePresets failed: %v", err)
	}
	if len(presets) != 1 {
		t.Fatalf("expected 1 preset, got %d", len(presets))
	}

	// Expliziter Horizont 72 muss erhalten bleiben (NICHT auf 48 überschrieben)
	if presets[0].ForecastHours != 72 {
		t.Errorf("expected ForecastHours=72 (explicitly set) preserved, got %d", presets[0].ForecastHours)
	}

	// JSON-Roundtrip: das Feld muss im Marshal-Output unter "forecast_hours" stehen
	data, _ := json.Marshal(presets[0])
	var m map[string]interface{}
	if err := json.Unmarshal(data, &m); err != nil {
		t.Fatalf("re-unmarshal: %v", err)
	}
	if _, ok := m["forecast_hours"]; !ok {
		t.Error("expected 'forecast_hours' field in JSON output — field missing in model (RED)")
	}
}
