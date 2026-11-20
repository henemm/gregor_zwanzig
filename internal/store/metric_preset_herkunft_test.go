package store

// TDD RED — Issue #3189 AC-2: Store-Round-Trip ueber migrateMetricPreset.
// Spec: docs/specs/modules/feat_3189_vorlage_herkunft.md
//
// Given: metric_presets.json mit Altbestand ohne `herkunft` UND einer Vorlage
//        mit `herkunft {id,name}`.
// When:  LoadMetricPresets -> SaveMetricPresets -> LoadMetricPresets.
// Then:  Altbestand bleibt gueltig und ohne Feld, die Herkunft ueberlebt.
//
// Kein Mock: echter Store auf t.TempDir(). Gepruefte Wirkung ist die Datei auf
// der Platte (map-basiert), damit das Paket im RED-Stand kompiliert.

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

func herkunft3189Datei(t *testing.T, dataDir, user string) []map[string]interface{} {
	t.Helper()
	raw, err := os.ReadFile(filepath.Join(dataDir, "users", user, "metric_presets.json"))
	if err != nil {
		t.Fatalf("read: %v", err)
	}
	var out []map[string]interface{}
	if err := json.Unmarshal(raw, &out); err != nil {
		t.Fatalf("parse: %v", err)
	}
	return out
}

func TestHerkunft3189_AC2_StoreRoundTripAltbestandUndHerkunft(t *testing.T) {
	tmpDir := t.TempDir()
	writePresetsRaw(t, tmpDir, "anna", `[
		{"id":"alt","name":"Altbestand","kind":"route","is_default":false,
		 "metrics":[{"metric_id":"wind","enabled":true,"use_friendly_format":false}],
		 "created_at":"2026-01-01T00:00:00Z"},
		{"id":"neu","name":"Mallorca Frühling","kind":"vergleich","is_default":false,
		 "metrics":[{"metric_id":"wind","enabled":true,"use_friendly_format":false}],
		 "created_at":"2026-11-20T00:00:00Z",
		 "herkunft":{"id":"cmp-gr221","name":"GR221"}}
	]`)

	s := New(tmpDir, "").WithUser("anna")
	presets, err := s.LoadMetricPresets()
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if len(presets) != 2 {
		t.Fatalf("erwartet 2 Vorlagen, got %d", len(presets))
	}
	if err := s.SaveMetricPresets(presets); err != nil {
		t.Fatalf("Save: %v", err)
	}
	if _, err := s.LoadMetricPresets(); err != nil {
		t.Fatalf("Load nach Save: %v", err)
	}

	datei := herkunft3189Datei(t, tmpDir, "anna")
	byID := map[string]map[string]interface{}{}
	for _, p := range datei {
		id, _ := p["id"].(string)
		byID[id] = p
	}
	alt := byID["alt"]
	if alt == nil || alt["name"] != "Altbestand" || alt["kind"] != "route" {
		t.Fatalf("AC-2: Altbestand nicht gueltig erhalten: %v", alt)
	}
	if _, ok := alt["herkunft"]; ok {
		t.Fatalf("AC-2: Altbestand hat nach Save ein herkunft-Feld bekommen: %v", alt)
	}
	neu := byID["neu"]
	hk, ok := neu["herkunft"].(map[string]interface{})
	if !ok {
		t.Fatalf("AC-2: herkunft ging bei Load+Save verloren (migrateMetricPreset): %v", neu)
	}
	if hk["id"] != "cmp-gr221" || hk["name"] != "GR221" {
		t.Fatalf("AC-2: herkunft nach Round-Trip veraendert: %v", hk)
	}
}

// AC-2 / AC-3 Mandanten: Datei je Nutzer — Save von B beruehrt A's Herkunft nicht.
func TestHerkunft3189_AC2_RoundTripJeNutzerGetrennt(t *testing.T) {
	tmpDir := t.TempDir()
	writePresetsRaw(t, tmpDir, "anna", `[{"id":"a1","name":"A","kind":"route",
		"metrics":[],"created_at":"2026-11-20T00:00:00Z","herkunft":{"id":"gr221","name":"GR221"}}]`)
	writePresetsRaw(t, tmpDir, "bernd", `[{"id":"b1","name":"B","kind":"route",
		"metrics":[],"created_at":"2026-11-20T00:00:00Z","herkunft":{"id":"gr221","name":"Bernds"}}]`)

	for _, u := range []string{"anna", "bernd"} {
		s := New(tmpDir, "").WithUser(u)
		ps, err := s.LoadMetricPresets()
		if err != nil {
			t.Fatalf("Load %s: %v", u, err)
		}
		if err := s.SaveMetricPresets(ps); err != nil {
			t.Fatalf("Save %s: %v", u, err)
		}
	}
	want := map[string]string{"anna": "GR221", "bernd": "Bernds"}
	for u, name := range want {
		d := herkunft3189Datei(t, tmpDir, u)
		if len(d) != 1 {
			t.Fatalf("%s: erwartet 1 Vorlage, got %d", u, len(d))
		}
		hk, ok := d[0]["herkunft"].(map[string]interface{})
		if !ok || hk["name"] != name {
			t.Fatalf("AC-2/AC-3: %s herkunft nach Round-Trip falsch: %v", u, d[0])
		}
	}
}
