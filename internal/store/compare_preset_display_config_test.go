package store

// Issue #582 — Roundtrip-Test: ComparePreset.DisplayConfig additiv (Backend-Gap).
//
// Beweist:
//   (a) Preset MIT display_config → Save → Load → display_config identisch erhalten.
//   (b) Preset OHNE display_config (Altdaten-JSON) → Load → DisplayConfig == nil,
//       kein Fehler; Save schreibt kein leeres display_config (omitempty-Garantie).
//
// Spec: docs/specs/modules/issue_582_compare_list_fidelity.md
// Keine Mocks — echter Filesystem-Roundtrip via t.TempDir().

import (
	"encoding/json"
	"os"
	"path/filepath"
	"reflect"
	"testing"
)

func TestComparePresetDisplayConfig_RoundtripWithData(t *testing.T) {
	// GIVEN: Preset mit display_config {"region":"Tirol","ideal_ranges":{"wind":{"max":30}}}
	tmpDir := t.TempDir()
	s := New(tmpDir, "user1")

	rawJSON := `[{
		"id": "cp-display-1",
		"name": "Tirol Vergleich",
		"user_id": "user1",
		"location_ids": ["loc-a", "loc-b"],
		"schedule": "daily",
		"profil": "wintersport",
		"hour_from": 6,
		"hour_to": 9,
		"empfaenger": ["test@example.com"],
		"created_at": "2026-01-01T00:00:00Z",
		"display_config": {
			"region": "Tirol",
			"ideal_ranges": {"wind": {"max": 30}},
			"channel_layouts": {"telegram": {}}
		}
	}]`

	writeComparePresetsJSON(t, tmpDir, "user1", rawJSON)

	// WHEN: LoadComparePresets
	presets, err := s.LoadComparePresets()
	if err != nil {
		t.Fatalf("LoadComparePresets failed: %v", err)
	}
	if len(presets) != 1 {
		t.Fatalf("expected 1 preset, got %d", len(presets))
	}

	p := presets[0]

	// THEN: DisplayConfig nicht nil
	if p.DisplayConfig == nil {
		t.Fatal("DisplayConfig must not be nil after loading JSON with display_config")
	}
	if p.DisplayConfig["region"] != "Tirol" {
		t.Errorf("expected region=Tirol, got %v", p.DisplayConfig["region"])
	}

	// AND: SaveComparePresets → erneut LoadComparePresets → display_config identisch
	if err := s.SaveComparePresets(presets); err != nil {
		t.Fatalf("SaveComparePresets failed: %v", err)
	}
	reloaded, err := s.LoadComparePresets()
	if err != nil {
		t.Fatalf("second LoadComparePresets failed: %v", err)
	}
	if len(reloaded) != 1 {
		t.Fatalf("expected 1 preset after re-load, got %d", len(reloaded))
	}
	if !reflect.DeepEqual(p.DisplayConfig, reloaded[0].DisplayConfig) {
		t.Errorf("display_config changed after roundtrip:\n  before: %v\n  after:  %v",
			p.DisplayConfig, reloaded[0].DisplayConfig)
	}
}

func TestComparePresetDisplayConfig_RoundtripAltdatenOhneField(t *testing.T) {
	// GIVEN: Altdaten-JSON OHNE display_config (Legacy-Preset)
	tmpDir := t.TempDir()
	s := New(tmpDir, "user1")

	rawJSON := `[{
		"id": "cp-legacy-1",
		"name": "Legacy Preset",
		"user_id": "user1",
		"location_ids": ["loc-a"],
		"schedule": "daily",
		"profil": "wandern",
		"hour_from": 7,
		"hour_to": 10,
		"empfaenger": ["alt@example.com"],
		"created_at": "2025-06-01T00:00:00Z"
	}]`

	writeComparePresetsJSON(t, tmpDir, "user1", rawJSON)

	// WHEN: Load
	presets, err := s.LoadComparePresets()
	if err != nil {
		t.Fatalf("LoadComparePresets failed: %v", err)
	}
	if len(presets) != 1 {
		t.Fatalf("expected 1 preset, got %d", len(presets))
	}

	// THEN: DisplayConfig ist nil (kein Default, kein Fehler)
	if presets[0].DisplayConfig != nil {
		t.Errorf("DisplayConfig must be nil for legacy preset without field, got: %v", presets[0].DisplayConfig)
	}

	// AND: SaveComparePresets → per-Datei-JSON enthält KEIN display_config
	// (omitempty). Issue #1250 Scheibe 7b: gelesen wird die Einzeldatei
	// briefings/<id>.json (ein Objekt), nicht mehr das Array compare_presets.json.
	if err := s.SaveComparePresets(presets); err != nil {
		t.Fatalf("SaveComparePresets failed: %v", err)
	}
	raw, err := os.ReadFile(filepath.Join(tmpDir, "users", "user1", "briefings", "cp-legacy-1.json"))
	if err != nil {
		t.Fatalf("ReadFile after save: %v", err)
	}
	var written map[string]interface{}
	if err := json.Unmarshal(raw, &written); err != nil {
		t.Fatalf("Unmarshal saved JSON: %v", err)
	}
	if _, exists := written["display_config"]; exists {
		t.Error("omitempty broken: display_config must not appear in JSON for nil DisplayConfig")
	}
}
