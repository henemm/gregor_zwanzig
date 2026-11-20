package model

// TDD RED: Issue #3196 (Workflow feat-3196-trip-tempo-etappen)
// Spec: docs/specs/modules/feat_3196_trip_tempo_etappen.md (AC-2, AC-3, AC-6, AC-12)
//
// Gehzeit nach DAV (DIN 33466) statt Summenformel, Tempo als eigenes
// Trip-Feld (Fortbewegung + Grundtempo). Die Erwartungen kommen aus der
// gemeinsamen Falltabelle tests/fixtures/naismith_dav_paritaet.json, die
// Python- und TS-Rechner ebenfalls lesen (AC-6: Aenderung nur eines Rechners
// macht einen Test rot).
//
// Ausfuehrung: go test ./internal/model/ -run 'TestDAV3196' -v

import (
	"encoding/json"
	"math"
	"os"
	"path/filepath"
	"testing"
)

type davFall struct {
	Name          string  `json:"name"`
	Fortbewegung  string  `json:"fortbewegung"`
	GrundtempoKmh float64 `json:"grundtempo_kmh"`
	Km            float64 `json:"km"`
	HmAuf         float64 `json:"hm_auf"`
	HmAb          float64 `json:"hm_ab"`
	Minuten       float64 `json:"minuten"`
}

type davTabelle struct {
	Referenz map[string]struct {
		VorschlagKmh float64 `json:"vorschlag_kmh"`
		RAuf         float64 `json:"r_auf"`
		RAb          float64 `json:"r_ab"`
	} `json:"referenz"`
	Ableitung map[string]struct {
		Fortbewegung  string  `json:"fortbewegung"`
		GrundtempoKmh float64 `json:"grundtempo_kmh"`
	} `json:"ableitung_activity"`
	Faelle      []davFall `json:"faelle"`
	Gueltigkeit []struct {
		Fortbewegung  string  `json:"fortbewegung"`
		GrundtempoKmh float64 `json:"grundtempo_kmh"`
		Gueltig       bool    `json:"gueltig"`
	} `json:"gueltigkeit"`
}

// Fix-Loop 2, F001: Grenzen eines plausiblen Grundtempos (0.5 <= v <= 60)
// aus der gemeinsamen Falltabelle -- dieselbe lesen Python und TS.
func TestDAV3196_ValidTempoGrenzen(t *testing.T) {
	tab := ladeDAVTabelle(t)
	if len(tab.Gueltigkeit) < 8 {
		t.Fatalf("Gueltigkeitstabelle fehlt/zu klein: %d", len(tab.Gueltigkeit))
	}
	for _, g := range tab.Gueltigkeit {
		got := ValidTempo(Tempo{Fortbewegung: g.Fortbewegung, GrundtempoKmh: g.GrundtempoKmh})
		if got != g.Gueltig {
			t.Errorf("ValidTempo(%s, %g): erwartet %v, bekommen %v", g.Fortbewegung, g.GrundtempoKmh, g.Gueltig, got)
		}
	}
}

func ladeDAVTabelle(t *testing.T) davTabelle {
	t.Helper()
	raw, err := os.ReadFile(filepath.Join("..", "..", "tests", "fixtures", "naismith_dav_paritaet.json"))
	if err != nil {
		t.Fatalf("Falltabelle nicht lesbar: %v", err)
	}
	var tab davTabelle
	if err := json.Unmarshal(raw, &tab); err != nil {
		t.Fatalf("Falltabelle kaputt: %v", err)
	}
	if len(tab.Faelle) < 8 {
		t.Fatalf("Falltabelle zu klein: %d Faelle", len(tab.Faelle))
	}
	return tab
}

// AC-6/AC-3: DAV-Formel je Fortbewegung gegen die Falltabelle.
func TestDAV3196_FalltabelleDAVHours(t *testing.T) {
	tab := ladeDAVTabelle(t)
	for _, f := range tab.Faelle {
		t.Run(f.Name, func(t *testing.T) {
			trip := &Trip{Tempo: &Tempo{Fortbewegung: f.Fortbewegung, GrundtempoKmh: f.GrundtempoKmh}}
			sp := ResolveTempo(trip)
			got := DAVHours(f.Km, f.HmAuf, f.HmAb, sp) * 60.0
			if math.Abs(got-f.Minuten) > 1e-6 {
				t.Errorf("%s: erwartet %.4f min, bekommen %.4f min", f.Name, f.Minuten, got)
			}
		})
	}
}

// Raten folgen dem Grundtempo im festen Verhaeltnis je Fortbewegung.
func TestDAV3196_ResolveTempoRatenSkaliert(t *testing.T) {
	tab := ladeDAVTabelle(t)
	for name, ref := range tab.Referenz {
		for _, faktor := range []float64{1.0, 1.25, 0.5} {
			v := ref.VorschlagKmh * faktor
			sp := ResolveTempo(&Trip{Tempo: &Tempo{Fortbewegung: name, GrundtempoKmh: v}})
			if math.Abs(sp.FlatKmh-v) > 1e-9 ||
				math.Abs(sp.AscentMh-ref.RAuf*faktor) > 1e-9 ||
				math.Abs(sp.DescentMh-ref.RAb*faktor) > 1e-9 {
				t.Errorf("%s bei %.2f km/h: erwartet %.2f/%.2f/%.2f, bekommen %.2f/%.2f/%.2f",
					name, v, v, ref.RAuf*faktor, ref.RAb*faktor, sp.FlatKmh, sp.AscentMh, sp.DescentMh)
			}
		}
	}
}

// AC-2/AC-12: Lazy-Ableitung aller Altwerte; nie MTB oder Ski.
func TestDAV3196_DeriveTempoAusActivity(t *testing.T) {
	tab := ladeDAVTabelle(t)
	if len(tab.Ableitung) < 11 {
		t.Fatalf("Ableitungstabelle unvollstaendig: %d", len(tab.Ableitung))
	}
	for act, want := range tab.Ableitung {
		got := DeriveTempo(act)
		if got.Fortbewegung != want.Fortbewegung || got.GrundtempoKmh != want.GrundtempoKmh {
			t.Errorf("DeriveTempo(%q): erwartet %s/%.0f, bekommen %s/%.0f",
				act, want.Fortbewegung, want.GrundtempoKmh, got.Fortbewegung, got.GrundtempoKmh)
		}
	}
}

// AC-12: ResolveTempo ohne gespeichertes Tempo leitet aus Activity ab.
func TestDAV3196_ResolveTempoOhneTempoNutztActivity(t *testing.T) {
	sp := ResolveTempo(&Trip{Activity: "fahrrad_20"})
	if sp.FlatKmh != 20 || sp.AscentMh != 600 || sp.DescentMh != 1000 {
		t.Errorf("fahrrad_20 ohne tempo: erwartet 20/600/1000, bekommen %v", sp)
	}
	sp = ResolveTempo(&Trip{})
	if sp.FlatKmh != 4 || sp.AscentMh != 300 || sp.DescentMh != 500 {
		t.Errorf("leerer Trip: erwartet 4/300/500, bekommen %v", sp)
	}
	// Gespeichertes Tempo hat Vorrang vor dem Altfeld.
	sp = ResolveTempo(&Trip{Activity: "fahrrad_20", Tempo: &Tempo{Fortbewegung: "fuss", GrundtempoKmh: 5}})
	if sp.FlatKmh != 5 || sp.AscentMh != 375 {
		t.Errorf("tempo fuss/5 vor activity fahrrad_20: erwartet 5/375, bekommen %v", sp)
	}
}

// AC-3: gespeicherte Ankunftszeit folgt DAV. Etappe 8 km / ↑600 / ↓600 bei
// zu Fuss 4 km/h: 08:00 Start, Gipfel nach 4 km ↑600 (2:30 = 10:30), Ziel
// nach weiteren 4 km ↓600 (1:42 = 12:12). Gesamt 4:12 statt 5:12 (alt).
func TestDAV3196_ComputeStageArrivalsDAV(t *testing.T) {
	d := func(v float64) *float64 { return &v }
	stage := Stage{ID: "S1", Waypoints: []Waypoint{
		{ID: "A", Lat: 47.0, Lon: 11.0, ElevationM: 1000, DistanceFromStartKm: d(0)},
		{ID: "B", Lat: 47.0, Lon: 11.0, ElevationM: 1600, DistanceFromStartKm: d(4)},
		{ID: "C", Lat: 47.0, Lon: 11.0, ElevationM: 1000, DistanceFromStartKm: d(8)},
	}}
	ComputeStageArrivals(&stage, ResolveTempo(&Trip{Tempo: &Tempo{Fortbewegung: "fuss", GrundtempoKmh: 4}}))
	got := []string{
		*stage.Waypoints[0].ArrivalCalculated,
		*stage.Waypoints[1].ArrivalCalculated,
		*stage.Waypoints[2].ArrivalCalculated,
	}
	want := []string{"08:00", "10:30", "12:12"}
	for i := range want {
		if got[i] != want[i] {
			t.Errorf("Wegpunkt %d: erwartet %s, bekommen %s", i, want[i], got[i])
		}
	}
}

// JSON-Feld "tempo" ueberlebt Go-Roundtrip (sonst verwirft Go es).
func TestDAV3196_TempoJSONRoundtrip(t *testing.T) {
	in := []byte(`{"id":"t","name":"n","stages":[],"alert_rules":[],"corridors":[],"tempo":{"fortbewegung":"rad","grundtempo_kmh":18}}`)
	var tr Trip
	if err := json.Unmarshal(in, &tr); err != nil {
		t.Fatal(err)
	}
	if tr.Tempo == nil || tr.Tempo.Fortbewegung != "rad" || tr.Tempo.GrundtempoKmh != 18 {
		t.Fatalf("tempo nicht gelesen: %+v", tr.Tempo)
	}
	out, _ := json.Marshal(tr)
	var back map[string]interface{}
	_ = json.Unmarshal(out, &back)
	tm, ok := back["tempo"].(map[string]interface{})
	if !ok || tm["fortbewegung"] != "rad" || tm["grundtempo_kmh"] != 18.0 {
		t.Errorf("tempo nicht geschrieben: %s", out)
	}
}
