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

	"github.com/henemm/gregor-api/internal/model"
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

// Rework #3020 R1, AC-17 (Store-Teil): Warnungswerte und Ausblick eines Trips gehen mit zwei
// Nutzern unter derselben Trip-ID getrennt durch Speichern und Laden; der Ladepfad laesst neue
// Schluessel und `placements.outlook_reports` unveraendert und erfindet kein Altfeld
// (`show_outlook`, `multi_day_trend_reports`). Der Teil-Update-Merge ueber den Handler steht in
// trip_display_config_felderhalt_test.go (externes Testpaket, braucht internal/handler).
func TestRework3020_WarnungswerteUndAusblickJeNutzerGetrennt(t *testing.T) {
	basis := New(t.TempDir(), "basis-ohne-daten")
	dc := func(stufe string, ausblick []interface{}) map[string]interface{} {
		return map[string]interface{}{
			"metric_alert_levels": map[string]interface{}{"wind": stufe, "wind_gust": "robust"},
			"placements":          map[string]interface{}{"version": float64(1), "rows": []interface{}{}, "outlook_reports": ausblick},
			"metrics":             []interface{}{map[string]interface{}{"metric_id": "wind", "morning_enabled": true, "evening_enabled": false, "format_mode": "raw"}},
		}
	}
	for nutzer, d := range map[string]map[string]interface{}{
		"nutzer-a-3020": dc("sensibel", []interface{}{"morning"}),
		"nutzer-b-3020": dc("entspannt", []interface{}{"evening"}),
	} {
		trip := model.Trip{ID: "trip-3020", Name: "Trip " + nutzer, Stages: []model.Stage{}, DisplayConfig: d}
		if err := basis.WithUser(nutzer).SaveTrip(&trip); err != nil {
			t.Fatalf("SaveTrip %s: %v", nutzer, err)
		}
	}
	for nutzer, erwartet := range map[string][2]interface{}{
		"nutzer-a-3020": {"sensibel", []interface{}{"morning"}},
		"nutzer-b-3020": {"entspannt", []interface{}{"evening"}},
	} {
		geladen, err := basis.WithUser(nutzer).LoadTrip("trip-3020")
		if err != nil || geladen == nil {
			t.Fatalf("LoadTrip %s: %v", nutzer, err)
		}
		levels := levelsOf(t, geladen.DisplayConfig)
		if !reflect.DeepEqual(levels, map[string]interface{}{"wind": erwartet[0], "wind_gust": "robust"}) {
			t.Errorf("%s: metric_alert_levels = %v, erwartet wind=%v", nutzer, levels, erwartet[0])
		}
		pl, _ := geladen.DisplayConfig["placements"].(map[string]interface{})
		if !reflect.DeepEqual(pl["outlook_reports"], erwartet[1]) {
			t.Errorf("%s: placements.outlook_reports = %v, erwartet %v", nutzer, pl["outlook_reports"], erwartet[1])
		}
		for _, alt := range []string{"show_outlook", "multi_day_trend_reports"} {
			if _, da := geladen.DisplayConfig[alt]; da {
				t.Errorf("%s: Altfeld display_config.%s nach dem Laden", nutzer, alt)
			}
			if _, da := geladen.ReportConfig[alt]; da {
				t.Errorf("%s: Altfeld report_config.%s nach dem Laden", nutzer, alt)
			}
		}
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
