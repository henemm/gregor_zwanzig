package store

import (
	"os"
	"path/filepath"
	"testing"
)

func TestLoadLocationsFromRealData(t *testing.T) {
	// GIVEN: Real location files in data/users/default/locations/
	// Find the repo root (two levels up from internal/store/)
	repoRoot := filepath.Join("..", "..")
	dataDir := filepath.Join(repoRoot, "data")

	s := New(dataDir, "default")

	// WHEN: Loading locations
	locations, err := s.LoadLocations()

	// THEN: Locations are loaded from real files
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(locations) == 0 {
		t.Fatal("expected at least 1 location from data/users/default/locations/")
	}

	// Verify structure of first location
	loc := locations[0]
	if loc.ID == "" {
		t.Error("expected location to have an ID")
	}
	if loc.Name == "" {
		t.Error("expected location to have a name")
	}
	if loc.Lat == 0 && loc.Lon == 0 {
		t.Error("expected location to have coordinates")
	}
}

func TestLoadLocationsEmptyDir(t *testing.T) {
	// GIVEN: An empty directory
	tmpDir := t.TempDir()
	locDir := filepath.Join(tmpDir, "users", "test", "locations")
	os.MkdirAll(locDir, 0755)

	s := New(tmpDir, "test")

	// WHEN: Loading locations from empty dir
	locations, err := s.LoadLocations()

	// THEN: Returns empty slice, no error
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(locations) != 0 {
		t.Errorf("expected empty slice, got %d locations", len(locations))
	}
}

func TestLoadLocationsDirNotExist(t *testing.T) {
	// GIVEN: A non-existent directory
	s := New("/tmp/nonexistent-gregor-test", "nobody")

	// WHEN: Loading locations
	locations, err := s.LoadLocations()

	// THEN: Returns empty slice, no error
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(locations) != 0 {
		t.Errorf("expected empty slice, got %d locations", len(locations))
	}
}

func TestLoadLocationsSkipsBadJSON(t *testing.T) {
	// GIVEN: A directory with one valid and one invalid JSON
	tmpDir := t.TempDir()
	locDir := filepath.Join(tmpDir, "users", "test", "locations")
	os.MkdirAll(locDir, 0755)

	// Valid location
	os.WriteFile(filepath.Join(locDir, "good.json"), []byte(`{
		"id": "good", "name": "Good Place", "lat": 47.0, "lon": 11.0
	}`), 0644)

	// Invalid JSON
	os.WriteFile(filepath.Join(locDir, "bad.json"), []byte(`{not valid json`), 0644)

	s := New(tmpDir, "test")

	// WHEN: Loading locations
	locations, err := s.LoadLocations()

	// THEN: Only the valid location is returned
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(locations) != 1 {
		t.Fatalf("expected 1 location (bad skipped), got %d", len(locations))
	}
	if locations[0].ID != "good" {
		t.Errorf("expected id 'good', got %s", locations[0].ID)
	}
}

func TestLoadLocationsSortedByName(t *testing.T) {
	// GIVEN: Multiple locations
	tmpDir := t.TempDir()
	locDir := filepath.Join(tmpDir, "users", "test", "locations")
	os.MkdirAll(locDir, 0755)

	os.WriteFile(filepath.Join(locDir, "z.json"), []byte(`{"id":"z","name":"Zillertal","lat":47.1,"lon":11.8}`), 0644)
	os.WriteFile(filepath.Join(locDir, "a.json"), []byte(`{"id":"a","name":"Aberg","lat":47.3,"lon":13.1}`), 0644)

	s := New(tmpDir, "test")

	// WHEN: Loading locations
	locations, err := s.LoadLocations()

	// THEN: Sorted alphabetically by name
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(locations) != 2 {
		t.Fatalf("expected 2 locations, got %d", len(locations))
	}
	if locations[0].Name != "Aberg" {
		t.Errorf("expected first location Aberg, got %s", locations[0].Name)
	}
	if locations[1].Name != "Zillertal" {
		t.Errorf("expected second location Zillertal, got %s", locations[1].Name)
	}
}
