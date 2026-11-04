package model_test

// Issue #2792 S1a — eigene Vorlage (MetricPreset) traegt die Profil-Ampel samt
// alarm_ab (AC-14). Bestehende Vorlagen ohne Ampel laden unveraendert; die
// Ampel ueberlebt Laden und Speichern ueber den echten Store; zwei Nutzer
// bleiben getrennt. Echter Store im Temp-Verzeichnis, kein Mock.

import (
	"encoding/json"
	"os"
	"path/filepath"
	"reflect"
	"testing"

	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

const presetMitAmpel = `[{"id":"p-1","name":"Mein Gipfel","is_default":false,"created_at":"2026-11-01T10:00:00Z",
 "metrics":[{"metric_id":"wind","enabled":true,"use_friendly_format":false,"horizons":{"today":true,"tomorrow":true,"day_after":true}}],
 "ampel":{"template":"wandern","metrics":{"wind":{"enabled":true,"lower":{"red":null,"orange":null,"yellow":null},
  "upper":{"yellow":25,"orange":50,"red":70},"alarm_ab":"yellow"}},"thunder":{"mittel":"orange","hoch":"red"}}}]`

const presetOhneAmpel = `[{"id":"p-alt","name":"Alt","is_default":true,"created_at":"2026-01-01T10:00:00Z",
 "metrics":["temperature","wind"],"friendly_ids":["wind"]}]`

func schreibePresets(t *testing.T, s *store.Store, inhalt string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(s.PresetsFile()), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(s.PresetsFile(), []byte(inhalt), 0o644); err != nil {
		t.Fatal(err)
	}
}

func ampelAusDatei(t *testing.T, path string) interface{} {
	t.Helper()
	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	var liste []map[string]interface{}
	if err := json.Unmarshal(raw, &liste); err != nil {
		t.Fatal(err)
	}
	return liste[0]["ampel"]
}

func TestMetricPresetAmpel_JSONRoundtripBehaeltAmpelSamtAlarmAb(t *testing.T) {
	var presets []model.MetricPreset
	if err := json.Unmarshal([]byte(presetMitAmpel), &presets); err != nil {
		t.Fatal(err)
	}
	out, _ := json.Marshal(presets)
	var zurueck []map[string]interface{}
	_ = json.Unmarshal(out, &zurueck)
	var erwartet []map[string]interface{}
	_ = json.Unmarshal([]byte(presetMitAmpel), &erwartet)
	if !reflect.DeepEqual(zurueck[0]["ampel"], erwartet[0]["ampel"]) {
		t.Fatalf("Ampel nach Roundtrip = %v", zurueck[0]["ampel"])
	}
}

func TestMetricPresetAmpel_StoreLadenSpeichernZweiNutzerGetrennt(t *testing.T) {
	dir := t.TempDir()
	alice, bob := store.New(dir, "alice"), store.New(dir, "bob")
	schreibePresets(t, alice, presetMitAmpel)
	schreibePresets(t, bob, presetOhneAmpel)
	vorher := ampelAusDatei(t, alice.PresetsFile())

	presets, err := alice.LoadMetricPresets()
	if err != nil {
		t.Fatal(err)
	}
	if err := alice.SaveMetricPresets(presets); err != nil {
		t.Fatal(err)
	}
	if nachher := ampelAusDatei(t, alice.PresetsFile()); !reflect.DeepEqual(nachher, vorher) {
		t.Fatalf("Ampel nach Laden+Speichern = %v, erwartet %v", nachher, vorher)
	}

	// Bestehende Vorlage ohne Ampel laedt fehlerfrei und bekommt keine.
	alt, err := bob.LoadMetricPresets()
	if err != nil || len(alt) != 1 || alt[0].Name != "Alt" || len(alt[0].Metrics) != 2 {
		t.Fatalf("Alt-Vorlage laedt nicht unveraendert: %+v (%v)", alt, err)
	}
	if err := bob.SaveMetricPresets(alt); err != nil {
		t.Fatal(err)
	}
	if a := ampelAusDatei(t, bob.PresetsFile()); a != nil {
		t.Fatalf("bob bekommt eine Ampel, die er nie hatte: %v", a)
	}
}
