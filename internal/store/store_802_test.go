package store

// Issue #802 — Compute-on-Save: SaveTrip setzt arrival_calculated zentral.
//
// AC-1 (Go): SaveTrip eines fahrrad_20-Trips OHNE arrival_calculated →
// LoadTrip → alle Wegpunkte haben arrival_calculated mit Bike-Werten.
// KEINE Mocks — echter Store mit t.TempDir().

import (
	"testing"

	"github.com/henemm/gregor-api/internal/model"
)

func TestSaveTrip_802_ComputeOnSave_Fahrrad20(t *testing.T) {
	s := New(t.TempDir(), "u802")

	// Wegpunkte ohne arrival_calculated, gleiche lat/lon → nur Höhe zählt
	st := "08:00"
	trip := model.Trip{
		ID:       "trip-802",
		Name:     "Bike-Trip",
		Activity: "fahrrad_20",
		AlertRules: []model.AlertRule{},
		Stages: []model.Stage{
			{
				ID:        "S1",
				Name:      "Etappe 1",
				Date:      "2026-06-20",
				StartTime: &st,
				Waypoints: []model.Waypoint{
					{ID: "G1", Name: "Start", Lat: 47.0, Lon: 11.0, ElevationM: 500},
					{ID: "G2", Name: "Mitte", Lat: 47.0, Lon: 11.0, ElevationM: 1100},
					{ID: "G3", Name: "Plateau", Lat: 47.0, Lon: 11.0, ElevationM: 1100},
					{ID: "G4", Name: "Ziel", Lat: 47.0, Lon: 11.0, ElevationM: 500},
				},
			},
		},
	}

	if err := s.SaveTrip(&trip); err != nil {
		t.Fatalf("SaveTrip: %v", err)
	}

	loaded, err := s.LoadTrip("trip-802")
	if err != nil {
		t.Fatalf("LoadTrip: %v", err)
	}
	if loaded == nil {
		t.Fatal("LoadTrip returned nil")
	}

	wps := loaded.Stages[0].Waypoints
	if len(wps) != 4 {
		t.Fatalf("Waypoint-Count verändert: got %d, want 4", len(wps))
	}

	for _, wp := range wps {
		if wp.ArrivalCalculated == nil {
			t.Errorf("Waypoint %s: arrival_calculated ist nil", wp.ID)
		}
	}

	// Fixture A (AC-3 Wertekontrakt): fahrrad_20, [500,1100,1100,500] → ["08:00","09:00","09:00","09:36"]
	expected := []string{"08:00", "09:00", "09:00", "09:36"}
	for i, wp := range wps {
		if wp.ArrivalCalculated == nil {
			continue
		}
		if *wp.ArrivalCalculated != expected[i] {
			t.Errorf("wp[%d] (%s): arrival_calculated=%q, want %q",
				i, wp.ID, *wp.ArrivalCalculated, expected[i])
		}
	}
}

func TestSaveTrip_802_EmptyStage_NoArrival(t *testing.T) {
	// Eine Stage mit 0 Wegpunkten (Pausentag) darf nicht crashen.
	// Nota: store.go schreibt model.Trip, Stage muss >=1 WP haben (Go-Constraint
	// existiert nicht) — aber Python Stage hat __post_init__ Constraint; hier
	// testen wir nur, dass ComputeStageArrivals bei 0 WPs kein Panic produziert.
	s := New(t.TempDir(), "u802b")

	st := "08:00"
	trip := model.Trip{
		ID:         "trip-802-empty",
		Name:       "Empty",
		Activity:   "fahrrad_20",
		AlertRules: []model.AlertRule{},
		Stages: []model.Stage{
			{
				ID:        "S1",
				Name:      "Pause",
				Date:      "2026-06-20",
				StartTime: &st,
				Waypoints: []model.Waypoint{}, // 0 WPs
			},
		},
	}

	// Muss ohne Panic speichern
	if err := s.SaveTrip(&trip); err != nil {
		t.Fatalf("SaveTrip mit 0-WP-Stage: %v", err)
	}
}
