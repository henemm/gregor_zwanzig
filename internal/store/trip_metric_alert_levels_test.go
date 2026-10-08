package store

// Issue #1981 AC-7 (Go): der Trip-Ladepfad (migrateMetricAlertLevels)
// uebersetzt neben snow_line (#959) auch die Summary-Alt-Schluessel; ein Trip
// ohne Alt-Schluessel bleibt unveraendert.
//
// Spec: docs/specs/modules/fix_1981_alarm_abwahl_alt_vokabular.md

import (
	"encoding/json"
	"os"
	"path/filepath"
	"reflect"
	"testing"
)

func loadTripLevels(t *testing.T, levels map[string]interface{}) map[string]interface{} {
	t.Helper()
	tmpDir := t.TempDir()
	s := New(tmpDir, "test")
	tripDir := filepath.Join(tmpDir, "users", "test", "briefings")
	if err := os.MkdirAll(tripDir, 0755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	raw, err := json.Marshal(map[string]interface{}{
		"id": "trip-1981", "name": "Trip 1981", "stages": []interface{}{},
		"display_config": map[string]interface{}{"metric_alert_levels": levels},
	})
	if err != nil {
		t.Fatalf("Marshal: %v", err)
	}
	if err := os.WriteFile(filepath.Join(tripDir, "trip-1981.json"), raw, 0644); err != nil {
		t.Fatalf("write: %v", err)
	}
	loaded, err := s.LoadTrip("trip-1981")
	if err != nil || loaded == nil {
		t.Fatalf("LoadTrip: %v", err)
	}
	return levelsOf(t, loaded.DisplayConfig)
}

func TestLoadTrip_UebersetztSummaryUndSnowLine(t *testing.T) {
	got := loadTripLevels(t, map[string]interface{}{
		"snow_line": "sensibel", "temp_max_c": "off",
	})
	want := map[string]interface{}{"freezing_level": "sensibel", "temperature_max": "off"}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("Erwartet %v, erhalten %v", want, got)
	}
}

// GUARD: ohne Alt-Schluessel bleibt die Map unveraendert.
func TestLoadTrip_OhneAltSchluesselUnveraendert(t *testing.T) {
	in := map[string]interface{}{
		"temperature_max": "off", "wind_gust": "sensibel", "zukunfts_metrik": "robust",
	}
	got := loadTripLevels(t, in)
	if !reflect.DeepEqual(got, in) {
		t.Fatalf("Erwartet unveraendert %v, erhalten %v", in, got)
	}
}

// AC-9 (Go, Trip-Pfad): dieselbe gemeinsame Fixture gilt auch beim Trip.
func TestLoadTrip_FaelleAusGemeinsamerFixture(t *testing.T) {
	for _, fall := range loadAltVokabularFaelle(t) {
		t.Run(fall.Name, func(t *testing.T) {
			got := loadTripLevels(t, fall.Eingabe)
			if !reflect.DeepEqual(got, fall.Erwartet) {
				t.Fatalf("Erwartet %v, erhalten %v", fall.Erwartet, got)
			}
		})
	}
}
