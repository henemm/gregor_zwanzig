package store

// Issue #2795 S3b Teil 1a — Viertelstunden-Raster beim LESEN (Read-Heilung).
// SPEC: docs/specs/modules/feat_2795_s3b_teil1_zustellung.md §4.1 „Lesen (Go)",
// AC-4 (06:45 bleibt), AC-7 (07:00/18:00 unveraendert).
//
// Bisher (#1280) kappt der Lesepfad (LoadTrip/LoadTrips/LoadComparePreset(s))
// jede Slot-Zeit auf die volle Stunde. Neu:
//   * rasterkonforme Werte (Minute 00/15/30/45) bleiben unveraendert,
//   * ein (theoretisch) nicht rasterkonformer Altwert wird auf die VORHERIGE
//     Viertelstunde abgerundet (07:20 -> 07:15), OHNE Rueckschreiben auf die
//     Platte (Datei bleibt byte-gleich).
//
// Keine Mocks — echter Filesystem-Roundtrip via t.TempDir(), Daten werden ROH
// (SaveTrip/SaveComparePresets normalisieren nicht) auf die Platte gelegt.
//
// Format-Toleranz: ob der Store "06:45" oder "06:45:00" liefert, ist nicht
// Teil der Zusicherung (Spec: „HH:MM“ oder „HH:MM:SS“, Sekunden :00); geprueft
// wird die Uhrzeit (clock2795).
//
// Ausfuehrung: go test ./internal/store -run 2795 -v

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/henemm/gregor-api/internal/model"
)

// clock2795 liefert "HH:MM" fuer "HH:MM" bzw. "HH:MM:00"; alles andere
// (Sekunden != 00, Nicht-String, nil) wird unveraendert als Fehlerwert
// zurueckgegeben, damit die Meldung den echten Wert zeigt.
func clock2795(v interface{}) string {
	s, ok := v.(string)
	if !ok {
		return "<kein String>"
	}
	if len(s) == 5 {
		return s
	}
	if len(s) == 8 && s[5:] == ":00" {
		return s[:5]
	}
	return s
}

func clockPtr2795(p *string) string {
	if p == nil {
		return "<nil>"
	}
	return clock2795(*p)
}

func seedTrip2795(t *testing.T, s *Store, id, morning, evening string) {
	t.Helper()
	trip := model.Trip{
		ID:   id,
		Name: "Trip " + id,
		Stages: []model.Stage{
			{ID: "S1", Name: "D1", Date: "2026-08-20",
				Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}}},
		},
		ReportConfig: map[string]interface{}{
			"enabled":      true,
			"send_email":   true,
			"morning_time": morning,
			"evening_time": evening,
		},
	}
	if err := s.SaveTrip(&trip); err != nil {
		t.Fatalf("SaveTrip: %v", err)
	}
}

func seedPreset2795(t *testing.T, s *Store, id, morning, evening string) {
	t.Helper()
	trueVal := true
	m, e := morning, evening
	p := model.ComparePreset{
		ID:             id,
		Name:           "Preset " + id,
		UserID:         s.UserID,
		LocationIDs:    []string{"loc-a"},
		Schedule:       "daily",
		Profil:         "ALLGEMEIN",
		HourFrom:       8,
		HourTo:         17,
		ForecastHours:  48,
		MorningEnabled: &trueVal,
		MorningTime:    &m,
		EveningEnabled: &trueVal,
		EveningTime:    &e,
	}
	if err := s.SaveComparePresets([]model.ComparePreset{p}); err != nil {
		t.Fatalf("SaveComparePresets: %v", err)
	}
}

// AC-4 (Lesen, Trip): 06:45 auf der Platte kommt als 06:45 zurueck — im
// verschachtelten report_config UND im abgeleiteten Flach-Feld.
// RED heute: Lesepfad kappt auf 06:00:00.
func TestLoadTrip_2795_ViertelstundeBleibt(t *testing.T) {
	s := New(t.TempDir(), "user-2795")
	seedTrip2795(t, s, "trip-2795-q", "06:45:00", "18:15:00")

	got, err := s.LoadTrip("trip-2795-q")
	if err != nil || got == nil {
		t.Fatalf("LoadTrip: err=%v got=%v", err, got)
	}
	if c := clock2795(got.ReportConfig["morning_time"]); c != "06:45" {
		t.Errorf("AC-4: report_config.morning_time gelesen als %q, erwartet 06:45 (kein Kappen auf die Stunde)", c)
	}
	if c := clockPtr2795(got.MorningTime); c != "06:45" {
		t.Errorf("AC-4: Flach-Feld morning_time gelesen als %q, erwartet 06:45", c)
	}
	if c := clock2795(got.ReportConfig["evening_time"]); c != "18:15" {
		t.Errorf("AC-4: report_config.evening_time gelesen als %q, erwartet 18:15", c)
	}
	if c := clockPtr2795(got.EveningTime); c != "18:15" {
		t.Errorf("AC-4: Flach-Feld evening_time gelesen als %q, erwartet 18:15", c)
	}
}

// AC-4 (Lesen, Orte): 06:45 im Preset kommt als 06:45 zurueck.
// RED heute: HealComparePresetSlotTimes kappt auf 06:00:00.
func TestLoadComparePresets_2795_ViertelstundeBleibt(t *testing.T) {
	s := New(t.TempDir(), "user-2795")
	seedPreset2795(t, s, "cp-2795-q", "06:45:00", "18:30:00")

	list, err := s.LoadComparePresets()
	if err != nil || len(list) != 1 {
		t.Fatalf("LoadComparePresets: err=%v n=%d", err, len(list))
	}
	if c := clockPtr2795(list[0].MorningTime); c != "06:45" {
		t.Errorf("AC-4: Preset morning_time gelesen als %q, erwartet 06:45", c)
	}
	if c := clockPtr2795(list[0].EveningTime); c != "18:30" {
		t.Errorf("AC-4: Preset evening_time gelesen als %q, erwartet 18:30", c)
	}
	one, err := s.LoadComparePreset("cp-2795-q")
	if err != nil || one == nil {
		t.Fatalf("LoadComparePreset: err=%v one=%v", err, one)
	}
	if c := clockPtr2795(one.MorningTime); c != "06:45" {
		t.Errorf("AC-4: LoadComparePreset morning_time %q, erwartet 06:45", c)
	}
}

// AC-7 (Regressionsschutz, heute gruen): 07:00/18:00 bleiben beim Lesen
// unveraendert — Trip und Preset.
func TestLoad_2795_VolleStundeUnveraendert(t *testing.T) {
	s := New(t.TempDir(), "user-2795")
	seedTrip2795(t, s, "trip-2795-h", "07:00:00", "18:00:00")
	seedPreset2795(t, s, "cp-2795-h", "07:00:00", "18:00:00")

	trip, err := s.LoadTrip("trip-2795-h")
	if err != nil || trip == nil {
		t.Fatalf("LoadTrip: %v", err)
	}
	if c := clock2795(trip.ReportConfig["morning_time"]); c != "07:00" {
		t.Errorf("AC-7: Trip morning_time %q, erwartet 07:00", c)
	}
	if c := clock2795(trip.ReportConfig["evening_time"]); c != "18:00" {
		t.Errorf("AC-7: Trip evening_time %q, erwartet 18:00", c)
	}
	p, err := s.LoadComparePreset("cp-2795-h")
	if err != nil || p == nil {
		t.Fatalf("LoadComparePreset: %v", err)
	}
	if c := clockPtr2795(p.MorningTime); c != "07:00" {
		t.Errorf("AC-7: Preset morning_time %q, erwartet 07:00", c)
	}
	if c := clockPtr2795(p.EveningTime); c != "18:00" {
		t.Errorf("AC-7: Preset evening_time %q, erwartet 18:00", c)
	}
}

// Spec §4.1 Lesen: ein nicht rasterkonformer Altwert wird beim Lesen auf die
// VORHERIGE Viertelstunde abgerundet (07:20 -> 07:15, 18:59 -> 18:45) und
// NICHT zurueckgeschrieben (Datei byte-gleich).
// RED heute: 07:20 -> 07:00, 18:59 -> 18:00.
func TestLoad_2795_AltwertAufViertelstundeAbgerundetOhneRueckschreiben(t *testing.T) {
	s := New(t.TempDir(), "user-2795")
	seedTrip2795(t, s, "trip-2795-alt", "07:20:00", "18:59:00")
	seedPreset2795(t, s, "cp-2795-alt", "07:20:00", "18:59:00")

	tripPfad := filepath.Join(s.BriefingsDir(), "trip-2795-alt.json")
	presetPfad := filepath.Join(s.BriefingsDir(), "cp-2795-alt.json")
	tripVorher, err := os.ReadFile(tripPfad)
	if err != nil {
		t.Fatalf("Trip-Datei lesen: %v", err)
	}
	presetVorher, err := os.ReadFile(presetPfad)
	if err != nil {
		t.Fatalf("Preset-Datei lesen: %v", err)
	}

	trip, err := s.LoadTrip("trip-2795-alt")
	if err != nil || trip == nil {
		t.Fatalf("LoadTrip: %v", err)
	}
	if c := clock2795(trip.ReportConfig["morning_time"]); c != "07:15" {
		t.Errorf("§4.1 Lesen: Trip-Altwert 07:20 gelesen als %q, erwartet 07:15 (vorherige Viertelstunde)", c)
	}
	if c := clockPtr2795(trip.MorningTime); c != "07:15" {
		t.Errorf("§4.1 Lesen: Trip-Flach-Feld 07:20 gelesen als %q, erwartet 07:15", c)
	}
	if c := clock2795(trip.ReportConfig["evening_time"]); c != "18:45" {
		t.Errorf("§4.1 Lesen: Trip-Altwert 18:59 gelesen als %q, erwartet 18:45", c)
	}
	p, err := s.LoadComparePreset("cp-2795-alt")
	if err != nil || p == nil {
		t.Fatalf("LoadComparePreset: %v", err)
	}
	if c := clockPtr2795(p.MorningTime); c != "07:15" {
		t.Errorf("§4.1 Lesen: Preset-Altwert 07:20 gelesen als %q, erwartet 07:15", c)
	}
	if c := clockPtr2795(p.EveningTime); c != "18:45" {
		t.Errorf("§4.1 Lesen: Preset-Altwert 18:59 gelesen als %q, erwartet 18:45", c)
	}

	// Kein Rueckschreiben: beide Dateien byte-gleich.
	tripNachher, _ := os.ReadFile(tripPfad)
	presetNachher, _ := os.ReadFile(presetPfad)
	if string(tripVorher) != string(tripNachher) {
		t.Errorf("§4.1 Lesen: Trip-Datei wurde beim Lesen veraendert (Rueckschreiben verboten)")
	}
	if string(presetVorher) != string(presetNachher) {
		t.Errorf("§4.1 Lesen: Preset-Datei wurde beim Lesen veraendert (Rueckschreiben verboten)")
	}
}
