package store

// Issue #1280 — Versandzeit-Eingabe auf volle Stunden begrenzen.
// Tech-Lead-Entscheidung (Adversary-Nachtrag F002-F005): Read-Heilung ist
// zentral im store-Paket (LoadTrip/LoadTrips/LoadComparePreset/
// LoadComparePresets) verankert, statt an jedem einzelnen Handler-
// Serialisierungspfad. Diese Store-Level-Tests seeden Bestandsdaten ROH
// (ohne Normalisierung, direkt via SaveTrip/SaveComparePresets) und pruefen,
// dass der Load-Pfad sie heilt — unabhaengig davon, welcher Handler sie
// spaeter encodiert.
//
// Keine Mocks — echter Filesystem-Roundtrip via t.TempDir().

import (
	"testing"

	"github.com/henemm/gregor-api/internal/model"
)

// Ein via SaveTrip ROH geseedeter Trip (krumme report_config.morning_time,
// keine Normalisierung) liefert bei LoadTrip sowohl das verschachtelte Feld
// ALS AUCH das daraus abgeleitete oberste Flach-Feld auf die volle Stunde
// gekappt zurueck.
func TestSaveTripThenLoadTrip_HealsMorningTimeInReportConfigAndFlatField(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "heal-user")

	trip := model.Trip{
		ID:   "trip-heal-store",
		Name: "Store-Level Heal Trip",
		Stages: []model.Stage{
			{ID: "S1", Name: "D1", Date: "2026-05-01",
				Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}}},
		},
		ReportConfig: map[string]interface{}{
			"enabled":      true,
			"morning_time": "07:30:00",
		},
	}
	// SaveTrip normalisiert die Slot-Zeit NICHT (nur der Handler-Schreibpfad
	// tut das) — die krumme Zeit landet roh auf der Platte.
	if err := s.SaveTrip(&trip); err != nil {
		t.Fatalf("SaveTrip failed: %v", err)
	}

	loaded, err := s.LoadTrip("trip-heal-store")
	if err != nil || loaded == nil {
		t.Fatalf("LoadTrip failed: err=%v loaded=%v", err, loaded)
	}

	if loaded.ReportConfig["morning_time"] != "07:00:00" {
		t.Errorf("report_config.morning_time: erwartet 07:00:00 (geheilt), got %v", loaded.ReportConfig["morning_time"])
	}
	if loaded.MorningTime == nil || *loaded.MorningTime != "07:00:00" {
		t.Errorf("oberstes Flach-Feld MorningTime: erwartet 07:00:00 (geheilt), got %v", loaded.MorningTime)
	}
}

// Ein via SaveComparePresets ROH geseedetes Preset (krumme morning_time)
// liefert bei LoadComparePresets den Wert auf die volle Stunde gekappt.
func TestSaveComparePresetsThenLoadComparePresets_HealsMorningTime(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "heal-user")

	trueVal := true
	morningTime := "07:30:00"
	preset := model.ComparePreset{
		ID:             "cp-heal-store",
		Name:           "Store-Level Heal Preset",
		UserID:         "heal-user",
		LocationIDs:    []string{"loc-a"},
		Schedule:       "manual",
		Profil:         "SUMMER_TREKKING",
		HourFrom:       8,
		HourTo:         17,
		Empfaenger:     []string{"a@example.com"},
		MorningEnabled: &trueVal,
		MorningTime:    &morningTime,
	}
	// SaveComparePresets (-> SaveComparePreset) normalisiert die Slot-Zeit
	// NICHT — die krumme Zeit landet roh auf der Platte.
	if err := s.SaveComparePresets([]model.ComparePreset{preset}); err != nil {
		t.Fatalf("SaveComparePresets failed: %v", err)
	}

	loaded, err := s.LoadComparePresets()
	if err != nil {
		t.Fatalf("LoadComparePresets failed: %v", err)
	}
	if len(loaded) != 1 {
		t.Fatalf("expected 1 preset, got %d", len(loaded))
	}
	if loaded[0].MorningTime == nil || *loaded[0].MorningTime != "07:00:00" {
		t.Errorf("morning_time: erwartet 07:00:00 (geheilt), got %v", loaded[0].MorningTime)
	}
}

// Epic #1319 Scheibe B AC-4: ein roh geseedetes ungueltiges Tagesfenster-Paar
// (start=20 >= end=10) wird beim Laden auf "nicht gesetzt" zurueckgesetzt --
// kein Crash, kein Absturz. Ein gueltiges Paar bleibt unangetastet.
func TestSaveTripThenLoadTrip_ClampsInvalidDayWindowPair(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "heal-user")

	trip := model.Trip{
		ID:   "trip-daywindow-clamp",
		Name: "Day-Window Clamp Trip",
		Stages: []model.Stage{
			{ID: "S1", Name: "D1", Date: "2026-05-01",
				Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}}},
		},
		ReportConfig: map[string]interface{}{
			"enabled":               true,
			"day_window_start_hour": 20,
			"day_window_end_hour":   10,
		},
	}
	if err := s.SaveTrip(&trip); err != nil {
		t.Fatalf("SaveTrip failed: %v", err)
	}

	loaded, err := s.LoadTrip("trip-daywindow-clamp")
	if err != nil || loaded == nil {
		t.Fatalf("LoadTrip failed: err=%v loaded=%v", err, loaded)
	}
	if _, ok := loaded.ReportConfig["day_window_start_hour"]; ok {
		t.Errorf("day_window_start_hour haette bei ungueltigem Paar entfernt werden muessen, got %v", loaded.ReportConfig["day_window_start_hour"])
	}
	if _, ok := loaded.ReportConfig["day_window_end_hour"]; ok {
		t.Errorf("day_window_end_hour haette bei ungueltigem Paar entfernt werden muessen, got %v", loaded.ReportConfig["day_window_end_hour"])
	}
}

// Ein gueltiges Tagesfenster-Paar (6-16) bleibt beim Laden unveraendert.
func TestSaveTripThenLoadTrip_KeepsValidDayWindowPair(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "heal-user")

	trip := model.Trip{
		ID:   "trip-daywindow-valid",
		Name: "Day-Window Valid Trip",
		Stages: []model.Stage{
			{ID: "S1", Name: "D1", Date: "2026-05-01",
				Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}}},
		},
		ReportConfig: map[string]interface{}{
			"enabled":               true,
			"day_window_start_hour": 6,
			"day_window_end_hour":   16,
		},
	}
	if err := s.SaveTrip(&trip); err != nil {
		t.Fatalf("SaveTrip failed: %v", err)
	}

	loaded, err := s.LoadTrip("trip-daywindow-valid")
	if err != nil || loaded == nil {
		t.Fatalf("LoadTrip failed: err=%v loaded=%v", err, loaded)
	}
	start, _ := toIntHour(loaded.ReportConfig["day_window_start_hour"])
	end, _ := toIntHour(loaded.ReportConfig["day_window_end_hour"])
	if start != 6 || end != 16 {
		t.Errorf("gueltiges Fenster-Paar haette erhalten bleiben muessen, got start=%v end=%v", start, end)
	}
}
