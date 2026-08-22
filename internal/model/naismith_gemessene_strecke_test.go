package model

import (
	"testing"
)

// Spiegelbild zu tests/tdd/test_gehzeit_folgt_wegstrecke.py (#2042).
// Dieselben Eingaben, dieselben erwarteten Ankunftszeiten — weichen die beiden
// Seiten voneinander ab, ist die bit-genaue Spiegelung gebrochen (AC-5).

const (
	testLat  = 46.6500
	testLonA = 12.4000
	testLonB = 12.4300
)

func kmPtr(v float64) *float64 { return &v }

func stageWith(wps []Waypoint) *Stage {
	start := "08:00"
	return &Stage{ID: "T1", Name: "Pruefetappe", Date: "2026-08-25", Waypoints: wps, StartTime: &start}
}

func hikerSpeeds() ActivitySpeeds { return ActivitySpeed("") }

// AC-1: Liegt die gemessene Strecke vor, bestimmt sie die Gehzeit.
func TestArrivals_2042_MeasuredDistanceDrivesWalkingTime(t *testing.T) {
	luft := haversineKm(testLat, testLonA, testLat, testLonB)
	gemessen := luft * 2.0

	stage := stageWith([]Waypoint{
		{ID: "G1", Lat: testLat, Lon: testLonA, ElevationM: 1800, DistanceFromStartKm: kmPtr(0)},
		{ID: "G2", Lat: testLat, Lon: testLonB, ElevationM: 1800, DistanceFromStartKm: kmPtr(gemessen)},
	})
	ComputeStageArrivals(stage, hikerSpeeds())

	got := *stage.Waypoints[1].ArrivalCalculated
	wantMin := 480 + int(gemessen/hikerSpeeds().FlatKmh*60.0+0.5)
	if got != formatHHMM(wantMin) {
		t.Fatalf("gemessene Strecke muss die Gehzeit bestimmen: got %s, want %s", got, formatHHMM(wantMin))
	}
}

// AC-2: Ohne gemessene Strecke bleibt das Ergebnis wie im Bestand.
func TestArrivals_2042_UnmeasuredStageUnchanged(t *testing.T) {
	stage := stageWith([]Waypoint{
		{ID: "G1", Lat: testLat, Lon: testLonA, ElevationM: 1800},
		{ID: "G2", Lat: testLat, Lon: testLonB, ElevationM: 1800},
	})
	ComputeStageArrivals(stage, hikerSpeeds())

	luft := haversineKm(testLat, testLonA, testLat, testLonB)
	wantMin := 480 + int(luft/hikerSpeeds().FlatKmh*60.0+0.5)
	if got := *stage.Waypoints[1].ArrivalCalculated; got != formatHHMM(wantMin) {
		t.Fatalf("Bestandsetappe muss unveraendert rechnen: got %s, want %s", got, formatHHMM(wantMin))
	}
}

// AC-4: Eine absteigende Strecke darf die Gehzeit nicht verkuerzen.
func TestArrivals_2042_NegativeDeltaFallsBackToStraightLine(t *testing.T) {
	stage := stageWith([]Waypoint{
		{ID: "G1", Lat: testLat, Lon: testLonA, ElevationM: 1800, DistanceFromStartKm: kmPtr(12)},
		{ID: "G2", Lat: testLat, Lon: testLonB, ElevationM: 1800, DistanceFromStartKm: kmPtr(4)},
	})
	ComputeStageArrivals(stage, hikerSpeeds())

	luft := haversineKm(testLat, testLonA, testLat, testLonB)
	wantMin := 480 + int(luft/hikerSpeeds().FlatKmh*60.0+0.5)
	if got := *stage.Waypoints[1].ArrivalCalculated; got != formatHHMM(wantMin) {
		t.Fatalf("negative Differenz muss auf die Luftlinie zurueckfallen: got %s, want %s", got, formatHHMM(wantMin))
	}
}

// AC-5: feste Erwartungswerte, identisch zur Python-Seite.
func TestArrivals_2042_ParityWithPython(t *testing.T) {
	stage := stageWith([]Waypoint{
		{ID: "G1", Lat: testLat, Lon: testLonA, ElevationM: 1800, DistanceFromStartKm: kmPtr(0)},
		{ID: "G2", Lat: testLat, Lon: testLonB, ElevationM: 2100, DistanceFromStartKm: kmPtr(8)},
	})
	ComputeStageArrivals(stage, hikerSpeeds())

	// 8,0 km / 4 km/h = 120 min; 300 Hm / 300 m/h = 60 min => 180 min ab 08:00.
	if got := *stage.Waypoints[0].ArrivalCalculated; got != "08:00" {
		t.Fatalf("Startzeit: got %s, want 08:00", got)
	}
	if got := *stage.Waypoints[1].ArrivalCalculated; got != "11:00" {
		t.Fatalf("Paritaet zur Python-Seite gebrochen: got %s, want 11:00", got)
	}
}
