package model

import "testing"

// Spiegelbild zu tests/tdd/test_gehzeit_etappenregel.py (#2082, AC-6).
// Dieselbe Geometrie, dieselben Faelle, dieselben Erwartungen -- weichen die
// beiden Seiten voneinander ab, ist die bit-genaue Spiegelung gebrochen.

const (
	testLat  = 46.6500
	testLonA = 12.4000
	testLonB = 12.4300
	testLonC = 12.4600
	testElev = 1800
)

func kmPtr(v float64) *float64 { return &v }

func hikerSpeeds() ActivitySpeeds { return ActivitySpeed("") }

func stageWith(wps []Waypoint) *Stage {
	start := "08:00"
	return &Stage{ID: "T1", Name: "Pruefetappe", Date: "2026-08-25", Waypoints: wps, StartTime: &start}
}

func wp(id string, lon float64, km *float64) Waypoint {
	return Waypoint{ID: id, Name: id, Lat: testLat, Lon: lon, ElevationM: testElev, DistanceFromStartKm: km}
}

// luftlinienAnkunft liefert die erwartete Ankunft, wenn ALLE Abschnitte auf
// Luftlinie rechnen (gleiche Hoehe => nur der Distanzanteil wirkt).
func luftlinienAnkunft(lons ...float64) string {
	cur := 480.0
	for i := 0; i < len(lons)-1; i++ {
		cur += haversineKm(testLat, lons[i], testLat, lons[i+1]) / hikerSpeeds().FlatKmh * 60.0
	}
	return formatHHMM(int(cur + 0.5))
}

// AC-1: Ein Abschnitt kuerzer als die Luftlinie entwertet die GANZE Etappe.
func TestArrivals_2082_ImplausibleSegmentInvalidatesWholeStage(t *testing.T) {
	luftAB := haversineKm(testLat, testLonA, testLat, testLonB)
	luftBC := haversineKm(testLat, testLonB, testLat, testLonC)

	stage := stageWith([]Waypoint{
		wp("G1", testLonA, kmPtr(0)),
		wp("G2", testLonB, kmPtr(luftAB*2.0)),            // plausibel
		wp("G3", testLonC, kmPtr(luftAB*2.0+luftBC*0.3)), // unplausibel kurz
	})
	ComputeStageArrivals(stage, hikerSpeeds())

	if got, want := *stage.Waypoints[1].ArrivalCalculated, luftlinienAnkunft(testLonA, testLonB); got != want {
		t.Fatalf("auch der plausible Abschnitt muss zurueckfallen: got %s, want %s", got, want)
	}
	if got, want := *stage.Waypoints[2].ArrivalCalculated, luftlinienAnkunft(testLonA, testLonB, testLonC); got != want {
		t.Fatalf("Etappenende: got %s, want %s", got, want)
	}
}

// AC-2: Nicht strikt steigende Werte -> ganze Etappe Luftlinie.
//
// Der "gleich"-Fall braucht zwei Wegpunkte am SELBEN Ort: sonst faengt die
// Plausibilitaetspruefung (span < Luftlinie) den Fall ab, bevor die
// Monotonie-Regel gefragt ist, und der Test bestuende aus dem falschen Grund.
// Die Mutation `span <= 0` -> `span < 0` blieb genau daran unentdeckt.
func TestArrivals_2082_NonMonotonicFallsBack(t *testing.T) {
	t.Run("kleiner", func(t *testing.T) {
		stage := stageWith([]Waypoint{
			wp("G1", testLonA, kmPtr(5.0)),
			wp("G2", testLonB, kmPtr(4.0)),
		})
		ComputeStageArrivals(stage, hikerSpeeds())

		if got, want := *stage.Waypoints[1].ArrivalCalculated, luftlinienAnkunft(testLonA, testLonB); got != want {
			t.Fatalf("got %s, want %s", got, want)
		}
	})

	t.Run("gleich", func(t *testing.T) {
		// G1 und G2 am selben Ort (Luftlinie 0) mit gleichem Messwert: nur die
		// Monotonie-Regel kann das verwerfen. G3 traegt einen grossen Wert --
		// wird die Etappe faelschlich als vermessen gefuehrt, rechnet der
		// zweite Abschnitt damit statt auf Luftlinie.
		stage := stageWith([]Waypoint{
			wp("G1", testLonA, kmPtr(5.0)),
			wp("G2", testLonA, kmPtr(5.0)),
			wp("G3", testLonB, kmPtr(25.0)),
		})
		ComputeStageArrivals(stage, hikerSpeeds())

		if got, want := *stage.Waypoints[2].ArrivalCalculated, luftlinienAnkunft(testLonA, testLonA, testLonB); got != want {
			t.Fatalf("gleiche Werte sind nicht strikt steigend: got %s, want %s", got, want)
		}
	})
}

// AC-3: Ein fehlender Messwert entwertet die GANZE Etappe.
func TestArrivals_2082_MissingValueInvalidatesWholeStage(t *testing.T) {
	luftAB := haversineKm(testLat, testLonA, testLat, testLonB)
	stage := stageWith([]Waypoint{
		wp("G1", testLonA, kmPtr(0)),
		wp("G2", testLonB, nil), // Luecke
		wp("G3", testLonC, kmPtr(luftAB*2.0+5.0)),
	})
	ComputeStageArrivals(stage, hikerSpeeds())

	if got, want := *stage.Waypoints[2].ArrivalCalculated, luftlinienAnkunft(testLonA, testLonB, testLonC); got != want {
		t.Fatalf("eine Luecke darf keine teilweise vermessene Etappe hinterlassen: got %s, want %s", got, want)
	}
}

// AC-4: Vermessene, plausible Etappe rechnet gemessen (Waechter fuer #2042).
func TestArrivals_2082_MeasuredPlausibleStageUsesMeasured(t *testing.T) {
	luftAB := haversineKm(testLat, testLonA, testLat, testLonB)
	gemessen := luftAB * 2.0
	stage := stageWith([]Waypoint{
		wp("G1", testLonA, kmPtr(0)),
		wp("G2", testLonB, kmPtr(gemessen)),
	})
	ComputeStageArrivals(stage, hikerSpeeds())

	want := formatHHMM(int(480.0 + gemessen/hikerSpeeds().FlatKmh*60.0 + 0.5))
	if got := *stage.Waypoints[1].ArrivalCalculated; got != want {
		t.Fatalf("gemessene Strecke muss die Gehzeit bestimmen: got %s, want %s", got, want)
	}
}

// AC-7: Etappe ohne Messwerte bleibt beim Bestandsverhalten.
func TestArrivals_2082_UnmeasuredStageUnchanged(t *testing.T) {
	stage := stageWith([]Waypoint{
		wp("G1", testLonA, nil),
		wp("G2", testLonB, nil),
	})
	ComputeStageArrivals(stage, hikerSpeeds())

	if got, want := *stage.Waypoints[1].ArrivalCalculated, luftlinienAnkunft(testLonA, testLonB); got != want {
		t.Fatalf("got %s, want %s", got, want)
	}
}

// Fester Paritaets-Anker: identische Erwartungswerte auf beiden Seiten.
// 8,0 km / 4 km/h = 120 min; 300 Hm / 300 m/h = 60 min => 180 min ab 08:00.
func TestArrivals_2082_ParityAnchor(t *testing.T) {
	stage := stageWith([]Waypoint{
		{ID: "G1", Lat: testLat, Lon: testLonA, ElevationM: 1800, DistanceFromStartKm: kmPtr(0)},
		{ID: "G2", Lat: testLat, Lon: testLonB, ElevationM: 2100, DistanceFromStartKm: kmPtr(8)},
	})
	ComputeStageArrivals(stage, hikerSpeeds())

	if got := *stage.Waypoints[0].ArrivalCalculated; got != "08:00" {
		t.Fatalf("Startzeit: got %s, want 08:00", got)
	}
	if got := *stage.Waypoints[1].ArrivalCalculated; got != "11:00" {
		t.Fatalf("Paritaet gebrochen: got %s, want 11:00", got)
	}
}
