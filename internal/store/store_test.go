package store

import (
	"encoding/json"
	"os"
	"path/filepath"
	"reflect"
	"testing"

	"github.com/henemm/gregor-api/internal/model"
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

// =============================================================================
// Issue #342 — Schema-Migration für MetricPreset
// Spec: docs/specs/modules/issue_342_pro_metrik_horizon_backend.md §3, AC-4, AC-6
//
// Diese Tests scheitern absichtlich (RED), weil der neue
// model.DisplayMetric-Typ + die Legacy-Migration in LoadMetricPresets() noch
// nicht existieren. Bei `go test` → Compile-Error / falsche Strukturwerte.
// =============================================================================

// writePresetsRaw schreibt rohen JSON-Inhalt in
// data/users/{user}/metric_presets.json — bewusst ohne Struct, damit Legacy-
// und Misch-Layouts möglich sind.
func writePresetsRaw(t *testing.T, dataDir, user, raw string) {
	t.Helper()
	dir := filepath.Join(dataDir, "users", user)
	if err := os.MkdirAll(dir, 0755); err != nil {
		t.Fatalf("mkdir failed: %v", err)
	}
	if err := os.WriteFile(filepath.Join(dir, "metric_presets.json"),
		[]byte(raw), 0644); err != nil {
		t.Fatalf("write failed: %v", err)
	}
}

// TestLoadMetricPresets_LegacyDefaulting (AC-4)
//
// Given: metric_presets.json mit Legacy-Schema (Metrics als []string,
//        FriendlyIDs separater []string, kein horizons).
// When:  LoadMetricPresets() wird aufgerufen.
// Then:  Preset hat strukturierte Metrics[]DisplayMetric mit
//        UseFriendlyFormat aus friendly_ids und Horizons={true,true,true}.
func TestLoadMetricPresets_LegacyDefaulting(t *testing.T) {
	tmpDir := t.TempDir()
	writePresetsRaw(t, tmpDir, "admin", `[
		{
			"id":"p1",
			"name":"Legacy",
			"metrics":["wind","temperature"],
			"friendly_ids":["wind"],
			"is_default":false,
			"created_at":"2026-01-01T00:00:00Z"
		}
	]`)

	s := New(tmpDir, "").WithUser("admin")
	presets, err := s.LoadMetricPresets()
	if err != nil {
		t.Fatalf("LoadMetricPresets: %v", err)
	}
	if len(presets) != 1 {
		t.Fatalf("expected 1 preset, got %d", len(presets))
	}

	p := presets[0]
	if p.ID != "p1" || p.Name != "Legacy" {
		t.Errorf("basic fields wrong: id=%q name=%q", p.ID, p.Name)
	}
	if len(p.Metrics) != 2 {
		t.Fatalf("expected 2 metrics after migration, got %d", len(p.Metrics))
	}

	wantAllTrue := model.Horizons{Today: true, Tomorrow: true, DayAfter: true}

	wind := p.Metrics[0]
	if wind.MetricID != "wind" {
		t.Errorf("first metric_id should be wind, got %q", wind.MetricID)
	}
	if !wind.Enabled {
		t.Errorf("wind should be enabled after migration")
	}
	if !wind.UseFriendlyFormat {
		t.Errorf("wind should have UseFriendlyFormat=true (from friendly_ids)")
	}
	if wind.Horizons != wantAllTrue {
		t.Errorf("wind.Horizons = %+v, want %+v", wind.Horizons, wantAllTrue)
	}

	temp := p.Metrics[1]
	if temp.MetricID != "temperature" {
		t.Errorf("second metric_id should be temperature, got %q", temp.MetricID)
	}
	if !temp.Enabled {
		t.Errorf("temperature should be enabled after migration")
	}
	if temp.UseFriendlyFormat {
		t.Errorf("temperature should have UseFriendlyFormat=false (not in friendly_ids)")
	}
	if temp.Horizons != wantAllTrue {
		t.Errorf("temperature.Horizons = %+v, want %+v", temp.Horizons, wantAllTrue)
	}
}

// TestLoadMetricPresets_RoundtripStability (AC-6)
//
// Mischung aus Legacy- und Neu-Schema-Presets.
// Load → Save → Load liefert byte-identische Strukturen.
func TestLoadMetricPresets_RoundtripStability(t *testing.T) {
	tmpDir := t.TempDir()

	// Drei Presets:
	// - p1: Legacy (Metrics []string + friendly_ids)
	// - p2: Neu-Schema mit expliziten horizons
	// - p3: Mischform (Neu-Schema ohne horizons-Feld → Default greift)
	writePresetsRaw(t, tmpDir, "u", `[
		{
			"id":"p1","name":"Legacy",
			"metrics":["wind","temperature"],
			"friendly_ids":["wind"],
			"is_default":false,
			"created_at":"2026-01-01T00:00:00Z"
		},
		{
			"id":"p2","name":"New",
			"metrics":[
				{"metric_id":"wind","enabled":true,"use_friendly_format":false,
				 "horizons":{"today":true,"tomorrow":false,"day_after":true}}
			],
			"is_default":false,
			"created_at":"2026-02-01T00:00:00Z"
		},
		{
			"id":"p3","name":"Mixed",
			"metrics":[
				{"metric_id":"thunder","enabled":true,"use_friendly_format":true}
			],
			"is_default":false,
			"created_at":"2026-03-01T00:00:00Z"
		}
	]`)

	s := New(tmpDir, "").WithUser("u")

	first, err := s.LoadMetricPresets()
	if err != nil {
		t.Fatalf("first load: %v", err)
	}
	if len(first) != 3 {
		t.Fatalf("expected 3 presets, got %d", len(first))
	}
	if err := s.SaveMetricPresets(first); err != nil {
		t.Fatalf("save: %v", err)
	}
	second, err := s.LoadMetricPresets()
	if err != nil {
		t.Fatalf("second load: %v", err)
	}

	if !reflect.DeepEqual(first, second) {
		// Helpful diff: marshal both and print side-by-side.
		a, _ := json.MarshalIndent(first, "", "  ")
		b, _ := json.MarshalIndent(second, "", "  ")
		t.Fatalf("roundtrip differs:\nfirst:\n%s\n\nsecond:\n%s", a, b)
	}
}

// TestLoadMetricPresets_NewSchemaHorizonsDefault
//
// Neu-Schema-Preset ohne horizons-Feld → Default {true,true,true} greift.
func TestLoadMetricPresets_NewSchemaHorizonsDefault(t *testing.T) {
	tmpDir := t.TempDir()
	writePresetsRaw(t, tmpDir, "u", `[
		{
			"id":"p1","name":"NoHorizons",
			"metrics":[
				{"metric_id":"wind","enabled":true,"use_friendly_format":false}
			],
			"is_default":false,
			"created_at":"2026-01-01T00:00:00Z"
		}
	]`)

	s := New(tmpDir, "").WithUser("u")
	presets, err := s.LoadMetricPresets()
	if err != nil {
		t.Fatalf("LoadMetricPresets: %v", err)
	}
	if len(presets) != 1 || len(presets[0].Metrics) != 1 {
		t.Fatalf("unexpected shape: %+v", presets)
	}

	wantAllTrue := model.Horizons{Today: true, Tomorrow: true, DayAfter: true}
	got := presets[0].Metrics[0].Horizons
	if got != wantAllTrue {
		t.Errorf("Horizons default wrong: got %+v, want %+v", got, wantAllTrue)
	}
}

// =============================================================================
// Bug #350 — LoadMetricPresets darf korruptes JSON nicht wie leere Datei behandeln.
// Adversary-Finding F002 aus #342. RED: aktuell gibt LoadMetricPresets bei
// ungültigem JSON ([], nil) zurück (store.go:349) statt einen Fehler.
// =============================================================================

// TestLoadMetricPresets_CorruptJSONReturnsError (AC-1)
//
// Given: metric_presets.json mit ungültigem JSON-Inhalt.
// When:  LoadMetricPresets() wird aufgerufen.
// Then:  Es kommt ein Fehler (err != nil) und NICHT ([], nil) — sonst ist eine
//        korrupte Datei nicht von einem leeren Zustand zu unterscheiden.
func TestLoadMetricPresets_CorruptJSONReturnsError(t *testing.T) {
	tmpDir := t.TempDir()
	writePresetsRaw(t, tmpDir, "u", `{kaputtes-json ohne abschluss`)

	s := New(tmpDir, "").WithUser("u")
	presets, err := s.LoadMetricPresets()
	if err == nil {
		t.Fatalf("expected error for corrupt JSON, got nil (presets=%+v) — "+
			"silent failure überschreibt sonst beim nächsten Save alle Presets", presets)
	}
}

// TestLoadMetricPresets_MissingFileReturnsEmpty (AC-2)
//
// Given: keine metric_presets.json (Erst-Aufruf).
// When:  LoadMetricPresets() wird aufgerufen.
// Then:  ([]MetricPreset{}, nil) — der legitime Leer-Zustand bleibt fehlerfrei.
func TestLoadMetricPresets_MissingFileReturnsEmpty(t *testing.T) {
	tmpDir := t.TempDir()

	s := New(tmpDir, "").WithUser("u")
	presets, err := s.LoadMetricPresets()
	if err != nil {
		t.Fatalf("missing file must not error, got: %v", err)
	}
	if presets == nil {
		t.Fatal("missing file must return non-nil empty slice")
	}
	if len(presets) != 0 {
		t.Fatalf("missing file must return empty slice, got %d presets", len(presets))
	}
}
