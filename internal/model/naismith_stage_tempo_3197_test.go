package model

// TDD RED: Issue #3197 (Workflow feat-3197-tempo-je-etappe)
// Spec: docs/specs/modules/feat_3197_tempo_je_etappe.md (AC-2, AC-8, AC-9)
//
// Grundtempo je Etappe (ADR-0108): ResolveStageTempo(trip, stage) nimmt die
// Fortbewegung immer vom Trip, das Grundtempo von der Etappe, falls gueltig
// (0.5..60), sonst vom Trip. Erwartungen aus der gemeinsamen Falltabelle
// tests/fixtures/naismith_dav_paritaet.json, Abschnitt
// "etappen_ueberschreibung" -- dieselbe lesen Python und TS.
//
// Ausfuehrung: go test ./internal/model/ -run 'TestStageTempo3197' -v

import (
	"encoding/json"
	"math"
	"os"
	"path/filepath"
	"testing"
)

type etappenFall struct {
	Tempo    Tempo   `json:"tempo"`
	Stages   []Stage `json:"stages"`
	Erwartet map[string]struct {
		FlatKmh    float64  `json:"flat_kmh"`
		RAuf       float64  `json:"r_auf"`
		RAb        float64  `json:"r_ab"`
		GehzeitMin float64  `json:"gehzeit_min"`
		Ankuenfte  []string `json:"ankuenfte"`
	} `json:"erwartet"`
	UngueltigeWerte []float64 `json:"ungueltige_werte"`
}

func ladeEtappenFall(t *testing.T) etappenFall {
	t.Helper()
	raw, err := os.ReadFile(filepath.Join("..", "..", "tests", "fixtures", "naismith_dav_paritaet.json"))
	if err != nil {
		t.Fatalf("Falltabelle nicht lesbar: %v", err)
	}
	var tab struct {
		Fall *etappenFall `json:"etappen_ueberschreibung"`
	}
	if err := json.Unmarshal(raw, &tab); err != nil {
		t.Fatalf("Falltabelle kaputt: %v", err)
	}
	if tab.Fall == nil || len(tab.Fall.Stages) != 2 || len(tab.Fall.UngueltigeWerte) < 5 {
		t.Fatalf("Abschnitt etappen_ueberschreibung fehlt/unvollstaendig")
	}
	return *tab.Fall
}

func fallTrip(f etappenFall) *Trip {
	tempo := f.Tempo
	stages := make([]Stage, len(f.Stages))
	copy(stages, f.Stages)
	return &Trip{ID: "t3197", Name: "Etappen-Tempo", Tempo: &tempo, Stages: stages}
}

func ankuenfte(st *Stage) []string {
	out := make([]string, len(st.Waypoints))
	for i, wp := range st.Waypoints {
		if wp.ArrivalCalculated != nil {
			out[i] = *wp.ArrivalCalculated
		}
	}
	return out
}

func gleich(a, b []string) bool {
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

// AC-2: S2 rechnet mit 3 km/h, S1 mit dem Trip-Tempo -- Raten und Ankuenfte.
func TestStageTempo3197_FalltabelleJeEtappe(t *testing.T) {
	f := ladeEtappenFall(t)
	trip := fallTrip(f)
	if trip.Stages[1].GrundtempoKmh == nil || *trip.Stages[1].GrundtempoKmh != 3 {
		t.Fatalf("S2 traegt kein grundtempo_kmh=3 nach dem Dekodieren: %+v", trip.Stages[1].GrundtempoKmh)
	}
	if trip.Stages[0].GrundtempoKmh != nil {
		t.Fatalf("S1 darf kein grundtempo_kmh tragen")
	}
	for i := range trip.Stages {
		st := &trip.Stages[i]
		want := f.Erwartet[st.ID]
		sp := ResolveStageTempo(trip, st)
		if math.Abs(sp.FlatKmh-want.FlatKmh) > 1e-9 || math.Abs(sp.AscentMh-want.RAuf) > 1e-9 ||
			math.Abs(sp.DescentMh-want.RAb) > 1e-9 {
			t.Errorf("%s: erwartet %.2f/%.2f/%.2f, bekommen %.2f/%.2f/%.2f",
				st.ID, want.FlatKmh, want.RAuf, want.RAb, sp.FlatKmh, sp.AscentMh, sp.DescentMh)
		}
		ComputeStageArrivals(st, sp)
		if got := ankuenfte(st); !gleich(got, want.Ankuenfte) {
			t.Errorf("%s: Ankuenfte erwartet %v, bekommen %v", st.ID, want.Ankuenfte, got)
		}
	}
}

// AC-8: ungueltiger Etappenwert -> Trip-Tempo (S2 rechnet wie S1).
func TestStageTempo3197_UngueltigerWertIgnoriert(t *testing.T) {
	f := ladeEtappenFall(t)
	for _, v := range f.UngueltigeWerte {
		v := v
		t.Run("", func(t *testing.T) {
			trip := fallTrip(f)
			trip.Stages[1].GrundtempoKmh = &v
			sp := ResolveStageTempo(trip, &trip.Stages[1])
			ref := ResolveTempo(trip)
			if sp != ref {
				t.Errorf("Etappenwert %g: erwartet Trip-Tempo %+v, bekommen %+v", v, ref, sp)
			}
		})
	}
}

// AC-9: ohne Etappenwert ist ResolveStageTempo identisch zu ResolveTempo,
// auch fuer Bestandstrips ohne gespeichertes Tempo (Ableitung aus activity).
func TestStageTempo3197_OhneUeberschreibungWieTrip(t *testing.T) {
	for _, trip := range []*Trip{
		{Tempo: &Tempo{Fortbewegung: "rad", GrundtempoKmh: 20}, Stages: []Stage{{ID: "S1"}}},
		{Activity: "fahrrad_15", Stages: []Stage{{ID: "S1"}}},
		{Stages: []Stage{{ID: "S1"}}},
	} {
		if got, want := ResolveStageTempo(trip, &trip.Stages[0]), ResolveTempo(trip); got != want {
			t.Errorf("ohne Ueberschreibung: erwartet %+v, bekommen %+v", want, got)
		}
	}
}

// ADR-0108: die Fortbewegung bleibt trip-weit; die Etappe skaliert nur das
// Grundtempo innerhalb der Fortbewegung des Trips (Rad 10 km/h: R 300/500).
func TestStageTempo3197_FortbewegungVomTrip(t *testing.T) {
	v := 10.0
	trip := &Trip{Tempo: &Tempo{Fortbewegung: "rad", GrundtempoKmh: 20},
		Stages: []Stage{{ID: "S1", GrundtempoKmh: &v}}}
	sp := ResolveStageTempo(trip, &trip.Stages[0])
	if sp.FlatKmh != 10 || math.Abs(sp.AscentMh-300) > 1e-9 || math.Abs(sp.DescentMh-500) > 1e-9 {
		t.Errorf("Rad mit Etappe 10 km/h: erwartet 10/300/500, bekommen %+v", sp)
	}
}

// AC-5: JSON-Roundtrip -- Feld nur geschrieben, wenn gesetzt (omitempty).
func TestStageTempo3197_JSONOmitempty(t *testing.T) {
	v := 3.0
	out, err := json.Marshal([]Stage{{ID: "S1"}, {ID: "S2", GrundtempoKmh: &v}})
	if err != nil {
		t.Fatal(err)
	}
	var back []map[string]interface{}
	if err := json.Unmarshal(out, &back); err != nil {
		t.Fatal(err)
	}
	if _, ok := back[0]["grundtempo_kmh"]; ok {
		t.Errorf("S1 ohne Wert darf kein grundtempo_kmh schreiben: %s", out)
	}
	if back[1]["grundtempo_kmh"] != 3.0 {
		t.Errorf("S2: grundtempo_kmh=3 erwartet: %s", out)
	}
}
