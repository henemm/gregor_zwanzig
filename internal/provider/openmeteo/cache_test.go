package openmeteo

import (
	"os"
	"path/filepath"
	"testing"
)

// =============================================================================
// Tests 10-12: Availability Cache
// =============================================================================

func TestLoadAvailabilityCache_MissingFile_ReturnsNil(t *testing.T) {
	// GIVEN: Kein Cache-File im Verzeichnis
	// WHEN: LoadAvailabilityCache aufgerufen
	// THEN: nil, nil (kein Fehler, kein Cache)
	tmpDir := t.TempDir()
	path := filepath.Join(tmpDir, "model_availability.json")

	cache, err := LoadAvailabilityCache(path)
	if err != nil {
		t.Fatalf("expected nil error, got: %v", err)
	}
	if cache != nil {
		t.Errorf("expected nil cache for missing file, got: %+v", cache)
	}
}

func TestSaveAndLoadAvailabilityCache_Roundtrip(t *testing.T) {
	// GIVEN: Ein gueltiger AvailabilityCache
	// WHEN: Save + Load hintereinander
	// THEN: Daten sind identisch
	tmpDir := t.TempDir()
	path := filepath.Join(tmpDir, "model_availability.json")

	original := &AvailabilityCache{
		ProbeDate: "2026-04-13",
		Models: map[string]ModelAvailability{
			"meteofrance_arome": {
				Available:   []string{"temperature_2m", "wind_speed_10m"},
				Unavailable: []string{"visibility"},
			},
		},
	}

	err := SaveAvailabilityCache(path, original)
	if err != nil {
		t.Fatalf("save failed: %v", err)
	}

	loaded, err := LoadAvailabilityCache(path)
	if err != nil {
		t.Fatalf("load failed: %v", err)
	}
	if loaded == nil {
		t.Fatal("expected non-nil cache after roundtrip")
	}
	if loaded.ProbeDate != original.ProbeDate {
		t.Errorf("probe_date mismatch: %s != %s", loaded.ProbeDate, original.ProbeDate)
	}
	aromeData, ok := loaded.Models["meteofrance_arome"]
	if !ok {
		t.Fatal("expected meteofrance_arome in loaded cache")
	}
	if len(aromeData.Available) != 2 {
		t.Errorf("expected 2 available params, got %d", len(aromeData.Available))
	}
}

func TestLoadAvailabilityCache_ExpiredCache_ReturnsNil(t *testing.T) {
	// GIVEN: Ein Cache-File mit probe_date aelter als 7 Tage
	// WHEN: LoadAvailabilityCache aufgerufen
	// THEN: nil, nil (abgelaufen)
	tmpDir := t.TempDir()
	path := filepath.Join(tmpDir, "model_availability.json")

	expiredJSON := `{"probe_date":"2020-01-01","models":{"ecmwf_ifs04":{"available":["temperature_2m"],"unavailable":[]}}}`
	os.WriteFile(path, []byte(expiredJSON), 0644)

	cache, err := LoadAvailabilityCache(path)
	if err != nil {
		t.Fatalf("expected nil error for expired cache, got: %v", err)
	}
	if cache != nil {
		t.Errorf("expected nil for expired cache (>7 days), got: %+v", cache)
	}
}
