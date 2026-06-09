package model

import "testing"

// TDD RED — Issue #674 Fahrradtour-Aktivitätstyp
//
// Spec: docs/specs/modules/issue_674_aktivitaetstyp_fahrrad.md
// Workflow: phase5_tdd_red — Tests MÜSSEN FEHLSCHLAGEN bis Phase 6.
//
// KEINE MOCKS — echte Structs, echte Berechnung.
//
// RED-Ursache: ActivitySpeed(string) gibt es nicht → Compile-Fehler.

// TestActivitySpeed_Fahrrad25 prüft AC-6: ActivitySpeed("fahrrad_25")
// liefert FlatKmh=25, AscentMh=600, DescentMh=1000.
func TestActivitySpeed_Fahrrad25(t *testing.T) {
	s := ActivitySpeed("fahrrad_25") // nicht vorhanden → Compile-Fehler = RED
	if s.FlatKmh != 25.0 {
		t.Fatalf("FlatKmh = %v, want 25.0", s.FlatKmh)
	}
	if s.AscentMh != 600.0 {
		t.Fatalf("AscentMh = %v, want 600.0", s.AscentMh)
	}
	if s.DescentMh != 1000.0 {
		t.Fatalf("DescentMh = %v, want 1000.0", s.DescentMh)
	}
}

// TestActivitySpeed_Fahrrad20 prüft AC-6 für fahrrad_20.
func TestActivitySpeed_Fahrrad20(t *testing.T) {
	s := ActivitySpeed("fahrrad_20")
	if s.FlatKmh != 20.0 {
		t.Fatalf("FlatKmh = %v, want 20.0", s.FlatKmh)
	}
	if s.AscentMh != 600.0 {
		t.Fatalf("AscentMh = %v, want 600.0", s.AscentMh)
	}
}

// TestActivitySpeed_Fahrrad15 prüft AC-6 für fahrrad_15.
func TestActivitySpeed_Fahrrad15(t *testing.T) {
	s := ActivitySpeed("fahrrad_15")
	if s.FlatKmh != 15.0 {
		t.Fatalf("FlatKmh = %v, want 15.0", s.FlatKmh)
	}
	if s.AscentMh != 600.0 {
		t.Fatalf("AscentMh = %v, want 600.0", s.AscentMh)
	}
}

// TestActivitySpeed_Default prüft AC-6: ActivitySpeed("") liefert Wanderer-Default
// (FlatKmh=4, AscentMh=300, DescentMh=500).
func TestActivitySpeed_Default(t *testing.T) {
	s := ActivitySpeed("")
	if s.FlatKmh != 4.0 {
		t.Fatalf("FlatKmh = %v, want 4.0 (Wanderer-Default)", s.FlatKmh)
	}
	if s.AscentMh != 300.0 {
		t.Fatalf("AscentMh = %v, want 300.0", s.AscentMh)
	}
	if s.DescentMh != 500.0 {
		t.Fatalf("DescentMh = %v, want 500.0", s.DescentMh)
	}
}

// TestActivitySpeed_UnknownActivity prüft: unbekannter Aktivitätswert → Wanderer-Default.
func TestActivitySpeed_UnknownActivity(t *testing.T) {
	s := ActivitySpeed("paragliding") // unbekannt → Default
	if s.FlatKmh != 4.0 {
		t.Fatalf("FlatKmh = %v, want 4.0 (Default für unbekannte Aktivität)", s.FlatKmh)
	}
}

// TestComputeStageArrivals_Fahrrad20_Flat prüft AC-1:
// Trip activity="fahrrad_20", 2 Wegpunkte ~20 km flach, start_time="08:00"
// → wp[1].ArrivalCalculated == "09:00" (20 km ÷ 20 km/h = 1 h).
//
// 0.17987° Lat ≈ 20 km bei ~42° N (5 × DELTA_4KM_LAT aus naismith_test.go).
func TestComputeStageArrivals_Fahrrad20_Flat(t *testing.T) {
	stage := &Stage{
		ID: "S674-1", Name: "Fahrrad-Etappe", Date: "2026-06-09",
		StartTime: strPtr("08:00"),
		Waypoints: []Waypoint{
			{ID: "W1", Name: "Start", Lat: 42.0, Lon: 9.0, ElevationM: 200},
			{ID: "W2", Name: "Ziel", Lat: 42.17987, Lon: 9.0, ElevationM: 200}, // ~20 km
		},
	}
	speeds := ActivitySpeed("fahrrad_20")
	ComputeStageArrivals(stage, speeds) // neue Signatur → Compile-Fehler = RED

	if stage.Waypoints[1].ArrivalCalculated == nil {
		t.Fatal("wp[1] ArrivalCalculated == nil, want gesetzt")
	}
	got := *stage.Waypoints[1].ArrivalCalculated
	if got != "09:00" {
		t.Fatalf("wp[1] arrival = %q, want 09:00 (20 km ÷ 20 km/h = 1 h)", got)
	}
}

// TestComputeStageArrivals_Fahrrad15_Ascent prüft AC-3:
// Trip activity="fahrrad_15", +600 m Aufstieg ~0 km Horizontal, start_time="08:00"
// → wp[1].ArrivalCalculated == "09:00" (600 m ÷ 600 Hm/h = 1 h).
func TestComputeStageArrivals_Fahrrad15_Ascent(t *testing.T) {
	stage := &Stage{
		ID: "S674-3", Name: "Berg-Etappe", Date: "2026-06-09",
		StartTime: strPtr("08:00"),
		Waypoints: []Waypoint{
			{ID: "W1", Name: "Tal", Lat: 42.0, Lon: 9.0, ElevationM: 200},
			{ID: "W2", Name: "Gipfel", Lat: 42.0, Lon: 9.0, ElevationM: 800}, // +600 m, ~0 km
		},
	}
	speeds := ActivitySpeed("fahrrad_15")
	ComputeStageArrivals(stage, speeds)

	if stage.Waypoints[1].ArrivalCalculated == nil {
		t.Fatal("wp[1] ArrivalCalculated == nil, want gesetzt")
	}
	got := *stage.Waypoints[1].ArrivalCalculated
	if got != "09:00" {
		t.Fatalf("wp[1] arrival = %q, want 09:00 (600 m ÷ 600 Hm/h = 1 h)", got)
	}
}

// TestComputeStageArrivals_WandererDefault_Unchanged prüft AC-2 + AC-8:
// Leere activity → Wanderer-Default 4 km/h → identische Ergebnisse wie vor Refaktorierung.
// 0.036° lat ≈ 4 km → wp[1] = "09:00" (4 km ÷ 4 km/h = 1 h).
func TestComputeStageArrivals_WandererDefault_Unchanged(t *testing.T) {
	stage := &Stage{
		ID: "S674-2", Name: "Wander-Etappe", Date: "2026-06-09",
		StartTime: strPtr("08:00"),
		Waypoints: []Waypoint{
			{ID: "W1", Name: "Start", Lat: 47.000, Lon: 11.0, ElevationM: 1000},
			{ID: "W2", Name: "Ziel", Lat: 47.036, Lon: 11.0, ElevationM: 1000},
		},
	}
	speeds := ActivitySpeed("") // leer → Wanderer-Default
	ComputeStageArrivals(stage, speeds)

	if stage.Waypoints[1].ArrivalCalculated == nil {
		t.Fatal("wp[1] ArrivalCalculated == nil, want gesetzt")
	}
	got := *stage.Waypoints[1].ArrivalCalculated
	if got != "09:00" {
		t.Fatalf("wp[1] arrival = %q, want 09:00 (Wanderer 4 km/h, 4 km ÷ 4 = 1 h)", got)
	}
}

// TestFahrrad20_FasterThanWanderer prüft AC-5 (Backend-Seite):
// Fahrradtour kommt früher an als Wanderer.
// Beide starten 08:00, flache 20 km. Wanderer: 5 h → 13:00. Fahrrad 20: 1 h → 09:00.
func TestFahrrad20_FasterThanWanderer(t *testing.T) {
	makeStage := func(id string) *Stage {
		return &Stage{
			ID: id, Name: id, Date: "2026-06-09",
			StartTime: strPtr("08:00"),
			Waypoints: []Waypoint{
				{ID: "W1", Name: "Start", Lat: 42.0, Lon: 9.0, ElevationM: 200},
				{ID: "W2", Name: "Ziel", Lat: 42.17987, Lon: 9.0, ElevationM: 200},
			},
		}
	}

	stageWander := makeStage("wander")
	stageFahrrad := makeStage("fahrrad")

	ComputeStageArrivals(stageWander, ActivitySpeed(""))
	ComputeStageArrivals(stageFahrrad, ActivitySpeed("fahrrad_20"))

	wander := *stageWander.Waypoints[1].ArrivalCalculated
	fahrrad := *stageFahrrad.Waypoints[1].ArrivalCalculated

	wMins := hhmmToMinutes(t, wander)
	fMins := hhmmToMinutes(t, fahrrad)

	if fMins >= wMins {
		t.Fatalf("Fahrrad (%q = %d min) soll früher als Wanderer (%q = %d min) ankommen",
			fahrrad, fMins, wander, wMins)
	}
}
