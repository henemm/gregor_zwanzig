package model

import (
	"testing"
)

// TDD RED — Issue #296-BE Naismith-Ankunftszeiten.
// Erwartet: FAIL (Compile-Fehler) bis naismithHours, ComputeStageArrivals und
// Waypoint.ArrivalCalculated in internal/model/naismith.go bzw. trip.go existieren.
//
// Spec: docs/specs/modules/issue_296_be_naismith_arrival.md
//
// KEINE MOCKS — echte Structs, echte Berechnung.

const arrivalEps = 1e-9

// strPtr ist ein lokaler Helper für *string-Felder (StartTime).
func strPtr(s string) *string { return &s }

// TestNaismithHours prüft die angepasste Naismith-Formel als SUMME (nicht max!).
// AC-3 / AC-6: dist/4 + ascent/300 + descent/500.
func TestNaismithHours(t *testing.T) {
	sp := ActivitySpeed("") // Wanderer-Default
	cases := []struct {
		name                       string
		distKm, ascentM, descentM float64
		want                       float64
	}{
		{"flat_4km", 4, 0, 0, 1.0},       // 4 km ÷ 4 km/h = 1 h
		{"ascent_300m", 0, 300, 0, 1.0},  // 300 m ÷ 300 m/h = 1 h
		{"descent_500m", 0, 0, 500, 1.0}, // 500 m ÷ 500 m/h = 1 h
		{"summe", 4, 300, 500, 3.0},      // Summe, NICHT max() (max wäre 1.0)
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			got := naismithHours(c.distKm, c.ascentM, c.descentM, sp)
			if diff := got - c.want; diff > arrivalEps || diff < -arrivalEps {
				t.Fatalf("naismithHours(%v,%v,%v) = %v, want %v",
					c.distKm, c.ascentM, c.descentM, got, c.want)
			}
		})
	}
}

// TestComputeStageArrivals_Flat prüft AC-1: Stage start_time "08:00",
// 2 Wegpunkte 4 km auseinander, gleiche Höhe → wp[1] == "09:00".
// 0.036° Breitendifferenz ≈ 4.0 km.
func TestComputeStageArrivals_Flat(t *testing.T) {
	stage := &Stage{
		ID: "S1", Name: "Tag 1", Date: "2026-05-23",
		StartTime: strPtr("08:00"),
		Waypoints: []Waypoint{
			{ID: "W1", Name: "Start", Lat: 47.000, Lon: 11.0, ElevationM: 1000},
			{ID: "W2", Name: "Ziel", Lat: 47.036, Lon: 11.0, ElevationM: 1000},
		},
	}
	ComputeStageArrivals(stage, ActivitySpeed(""))

	if stage.Waypoints[0].ArrivalCalculated == nil ||
		*stage.Waypoints[0].ArrivalCalculated != "08:00" {
		t.Fatalf("wp[0] arrival = %v, want 08:00", stage.Waypoints[0].ArrivalCalculated)
	}
	if stage.Waypoints[1].ArrivalCalculated == nil {
		t.Fatal("wp[1] ArrivalCalculated == nil, want gesetzt")
	}
	if got := *stage.Waypoints[1].ArrivalCalculated; got != "09:00" {
		t.Fatalf("wp[1] arrival = %q, want 09:00 (4 km ÷ 4 km/h = 1 h)", got)
	}
}

// TestComputeStageArrivals_DefaultStart prüft AC-2: Stage OHNE start_time →
// wp[0] == "08:00".
func TestComputeStageArrivals_DefaultStart(t *testing.T) {
	stage := &Stage{
		ID: "S1", Name: "Tag 1", Date: "2026-05-23",
		Waypoints: []Waypoint{
			{ID: "W1", Name: "Start", Lat: 47.0, Lon: 11.0, ElevationM: 1000},
		},
	}
	ComputeStageArrivals(stage, ActivitySpeed(""))

	if stage.Waypoints[0].ArrivalCalculated == nil {
		t.Fatal("wp[0] ArrivalCalculated == nil, want Default 08:00")
	}
	if got := *stage.Waypoints[0].ArrivalCalculated; got != "08:00" {
		t.Fatalf("wp[0] arrival = %q, want 08:00 (Default-Startzeit)", got)
	}
}

// TestComputeStageArrivals_Ascent prüft AC-3: +300 m Höhe, ~0 km Distanz →
// Inkrement 1 h. Beweist den Höhenterm in der Summe.
func TestComputeStageArrivals_Ascent(t *testing.T) {
	stage := &Stage{
		ID: "S1", Name: "Tag 1", Date: "2026-05-23",
		StartTime: strPtr("08:00"),
		Waypoints: []Waypoint{
			{ID: "W1", Name: "Start", Lat: 47.0, Lon: 11.0, ElevationM: 1000},
			{ID: "W2", Name: "Gipfel", Lat: 47.0, Lon: 11.0, ElevationM: 1300},
		},
	}
	ComputeStageArrivals(stage, ActivitySpeed(""))

	if stage.Waypoints[1].ArrivalCalculated == nil {
		t.Fatal("wp[1] ArrivalCalculated == nil, want gesetzt")
	}
	if got := *stage.Waypoints[1].ArrivalCalculated; got != "09:00" {
		t.Fatalf("wp[1] arrival = %q, want 09:00 (300 m ÷ 300 m/h = 1 h)", got)
	}
}

// TestComputeStageArrivals_Pause prüft AC-7: Pausentag (0 Wegpunkte) → kein
// Panic, keine Arrival gesetzt.
func TestComputeStageArrivals_Pause(t *testing.T) {
	stage := &Stage{
		ID: "S1", Name: "Pause", Date: "2026-05-23",
		Waypoints: []Waypoint{},
	}
	// Darf nicht paniken.
	ComputeStageArrivals(stage, ActivitySpeed(""))

	if len(stage.Waypoints) != 0 {
		t.Fatalf("Pausentag soll 0 Wegpunkte behalten, hat %d", len(stage.Waypoints))
	}
}

// TestComputeStageArrivals_Monotonic prüft AC-8: 3 Wegpunkte
// (flach→Aufstieg→flach) → ArrivalCalculated streng monoton steigend,
// Format "HH:MM".
func TestComputeStageArrivals_Monotonic(t *testing.T) {
	stage := &Stage{
		ID: "S1", Name: "Tag 1", Date: "2026-05-23",
		StartTime: strPtr("08:00"),
		Waypoints: []Waypoint{
			{ID: "W1", Name: "Start", Lat: 47.000, Lon: 11.0, ElevationM: 1000},
			{ID: "W2", Name: "Gipfel", Lat: 47.036, Lon: 11.0, ElevationM: 1300},
			{ID: "W3", Name: "Ziel", Lat: 47.072, Lon: 11.0, ElevationM: 1300},
		},
	}
	ComputeStageArrivals(stage, ActivitySpeed(""))

	prev := -1
	for i, wp := range stage.Waypoints {
		if wp.ArrivalCalculated == nil {
			t.Fatalf("wp[%d] ArrivalCalculated == nil", i)
		}
		v := *wp.ArrivalCalculated
		// Format "HH:MM" prüfen.
		if len(v) != 5 || v[2] != ':' {
			t.Fatalf("wp[%d] arrival %q nicht im Format HH:MM", i, v)
		}
		mins := hhmmToMinutes(t, v)
		if mins <= prev {
			t.Fatalf("Ankunftszeiten nicht streng monoton: wp[%d]=%q (%d min) <= prev %d min",
				i, v, mins, prev)
		}
		prev = mins
	}
}

// TestFormatHHMM_ClampsOverflow prüft F001: kumulierte Zeit >= 24 h darf nie
// einen Stunden-Teil >23 ausgeben, sondern wird auf "23:59" geclamped. Grund:
// Python `_parse_hhmm` kann ">23h" nicht lesen und fällt sonst still auf die
// divergente Interpolation zurück. ~100 km flach ÷ 4 km/h = 25 h → würde
// ungeclamped "33:00" ergeben.
func TestFormatHHMM_ClampsOverflow(t *testing.T) {
	// 0.036° lat ≈ 4 km; 0.9° lat ≈ 100 km → 25 h ab 08:00 = 33:00 ungeclamped.
	stage := &Stage{
		ID: "S1", Name: "Mega-Etappe", Date: "2026-05-23",
		StartTime: strPtr("08:00"),
		Waypoints: []Waypoint{
			{ID: "W1", Name: "Start", Lat: 47.0, Lon: 11.0, ElevationM: 1000},
			{ID: "W2", Name: "Fern", Lat: 47.9, Lon: 11.0, ElevationM: 1000},
		},
	}
	ComputeStageArrivals(stage, ActivitySpeed(""))

	if stage.Waypoints[1].ArrivalCalculated == nil {
		t.Fatal("wp[1] ArrivalCalculated == nil, want geclampten Wert")
	}
	got := *stage.Waypoints[1].ArrivalCalculated
	if got != "23:59" {
		t.Fatalf("wp[1] arrival = %q, want 23:59 (Clamp >=24h)", got)
	}
	// Stunden-Teil muss <= 23 sein (cross-layer mit Python `_parse_hhmm`).
	h := hhmmToMinutes(t, got) / 60
	if h > 23 {
		t.Fatalf("Stunden-Teil %d > 23 — Python `_parse_hhmm` kann das nicht lesen", h)
	}
}

// TestParseStartMinutes_RejectsNonsense prüft F002: eine unsinnige start_time
// (Stunde >23 ODER Minute >59) fällt auf die Default-Startzeit "08:00" zurück
// statt den Unsinn zu übernehmen.
func TestParseStartMinutes_RejectsNonsense(t *testing.T) {
	stage := &Stage{
		ID: "S1", Name: "Tag 1", Date: "2026-05-23",
		StartTime: strPtr("99:99"),
		Waypoints: []Waypoint{
			{ID: "W1", Name: "Start", Lat: 47.0, Lon: 11.0, ElevationM: 1000},
		},
	}
	ComputeStageArrivals(stage, ActivitySpeed(""))

	if stage.Waypoints[0].ArrivalCalculated == nil {
		t.Fatal("wp[0] ArrivalCalculated == nil, want Default 08:00")
	}
	if got := *stage.Waypoints[0].ArrivalCalculated; got != "08:00" {
		t.Fatalf("wp[0] arrival = %q, want 08:00 (Fallback bei Unsinns-Startzeit)", got)
	}
}

// hhmmToMinutes parst "HH:MM" in Minuten ab Mitternacht (Test-Helper).
func hhmmToMinutes(t *testing.T, s string) int {
	t.Helper()
	if len(s) != 5 || s[2] != ':' {
		t.Fatalf("ungültiges HH:MM: %q", s)
	}
	h := int(s[0]-'0')*10 + int(s[1]-'0')
	m := int(s[3]-'0')*10 + int(s[4]-'0')
	return h*60 + m
}
