package store

// Issue #1244: SaveComparePresets muss pro Preset "corridors" NIE als JSON
// `null` persistieren -- analog zur Trip-Coercion (trip_nil_coercion_test.go).
// Spec: docs/specs/modules/fix_1244_null_list_fields.md, AC-4.
// Keine Mocks -- echter Filesystem-Roundtrip via t.TempDir().

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/henemm/gregor-api/internal/model"
)

func TestSaveComparePresets_NilCorridorsCoercedToEmptyArray(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "user1")

	presets := []model.ComparePreset{
		{
			ID:     "cp-nil-corridors",
			Name:   "Preset ohne Korridore",
			UserID: "user1",
			// Corridors absichtlich nicht gesetzt -> nil (wie beim
			// POST /api/compare-presets ohne "corridors" im Body).
		},
	}

	if err := s.SaveComparePresets(presets); err != nil {
		t.Fatalf("SaveComparePresets failed: %v", err)
	}

	// Issue #1250 Scheibe 7b: per-Datei-Persistenz — gelesen wird
	// briefings/<id>.json statt compare_presets.json.
	written, err := os.ReadFile(filepath.Join(tmpDir, "users", "user1", "briefings", "cp-nil-corridors.json"))
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

	reloaded, err := s.LoadComparePresets()
	if err != nil {
		t.Fatalf("LoadComparePresets failed: %v", err)
	}
	if len(reloaded) != 1 {
		t.Fatalf("expected 1 preset, got %d", len(reloaded))
	}
	if reloaded[0].Corridors == nil {
		t.Error("Erwartet [] statt nil nach Reload fuer Corridors")
	}
}
