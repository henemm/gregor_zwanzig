package model

// Issue #802 — Compute-on-Save: Cross-Language-Konsistenz Python↔Go.
//
// Dieselben Fixtures wie tests/tdd/test_issue_802_fahrrad_segment_zeit.py::_CONTRACT.
// Alle Wegpunkte lat=47.0 lon=11.0 → Horizontaldistanz 0 → nur Höhe zählt.
// Start 08:00 bei allen Fixtures.
//
// Erwartete Werte (AC-3 Wertekontrakt):
//   A: fahrrad_20, [500,1100,1100,500] → ["08:00","09:00","09:00","09:36"]
//   B: fahrrad_20, [500,505]            → ["08:00","08:01"]
//   C: fahrrad_20, [500,10500]          → ["08:00","23:59"]
//   W: "",         [500,800,300]        → ["08:00","09:00","10:00"]

import "testing"

// fixture802Stage baut eine Stage mit Wegpunkten aller bei (47.0, 11.0).
func fixture802Stage(id, startTime, activity string, elevs []int) *Stage {
	wps := make([]Waypoint, len(elevs))
	for i, e := range elevs {
		wps[i] = Waypoint{
			ID:         "G" + string(rune('0'+i+1)),
			Name:       "P",
			Lat:        47.0,
			Lon:        11.0,
			ElevationM: e,
		}
	}
	st := startTime
	return &Stage{ID: id, Name: "E", Date: "2026-06-20", StartTime: &st, Waypoints: wps}
}

func arrivals802(stage *Stage) []string {
	result := make([]string, len(stage.Waypoints))
	for i, wp := range stage.Waypoints {
		if wp.ArrivalCalculated != nil {
			result[i] = *wp.ArrivalCalculated
		}
	}
	return result
}

func sliceEq(a, b []string) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}

// TestNaismith802_A: fahrrad_20, [500,1100,1100,500] → ["08:00","09:00","09:00","09:36"]
func TestNaismith802_A(t *testing.T) {
	stage := fixture802Stage("A", "08:00", "fahrrad_20", []int{500, 1100, 1100, 500})
	ComputeStageArrivals(stage, ActivitySpeed("fahrrad_20"))
	got := arrivals802(stage)
	want := []string{"08:00", "09:00", "09:00", "09:36"}
	if !sliceEq(got, want) {
		t.Fatalf("Fixture A: got %v, want %v", got, want)
	}
}

// TestNaismith802_B: fahrrad_20, [500,505] → ["08:00","08:01"] (Rundung half-up)
func TestNaismith802_B(t *testing.T) {
	stage := fixture802Stage("B", "08:00", "fahrrad_20", []int{500, 505})
	ComputeStageArrivals(stage, ActivitySpeed("fahrrad_20"))
	got := arrivals802(stage)
	want := []string{"08:00", "08:01"}
	if !sliceEq(got, want) {
		t.Fatalf("Fixture B: got %v, want %v", got, want)
	}
}

// TestNaismith802_C: fahrrad_20, [500,10500] → ["08:00","23:59"] (Clamp 23:59)
func TestNaismith802_C(t *testing.T) {
	stage := fixture802Stage("C", "08:00", "fahrrad_20", []int{500, 10500})
	ComputeStageArrivals(stage, ActivitySpeed("fahrrad_20"))
	got := arrivals802(stage)
	want := []string{"08:00", "23:59"}
	if !sliceEq(got, want) {
		t.Fatalf("Fixture C: got %v, want %v", got, want)
	}
}

// TestNaismith802_W: "", [500,800,300] → ["08:00","09:00","10:00"] (Wanderer-SUMME)
func TestNaismith802_W(t *testing.T) {
	stage := fixture802Stage("W", "08:00", "", []int{500, 800, 300})
	ComputeStageArrivals(stage, ActivitySpeed(""))
	got := arrivals802(stage)
	want := []string{"08:00", "09:00", "10:00"}
	if !sliceEq(got, want) {
		t.Fatalf("Fixture W: got %v, want %v", got, want)
	}
}
