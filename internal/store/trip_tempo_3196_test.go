package store

// TDD RED: Issue #3196 (Workflow feat-3196-trip-tempo-etappen)
// Spec: docs/specs/modules/feat_3196_trip_tempo_etappen.md (AC-2, AC-5, AC-12)
//
// Lazy-Ableitung in normalizeTrip (Laden einer Datei OHNE tempo) und
// Compute-on-Save mit dem gespeicherten Tempo nach DAV.
//
// Ausfuehrung: go test ./internal/store/ -run 'TestTempo3196' -v

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	"github.com/henemm/gregor-api/internal/model"
)

func schreibeTripDatei(t *testing.T, dir, user, id, body string) string {
	t.Helper()
	p := filepath.Join(dir, "users", user, "briefings")
	if err := os.MkdirAll(p, 0755); err != nil {
		t.Fatal(err)
	}
	f := filepath.Join(p, id+".json")
	if err := os.WriteFile(f, []byte(body), 0644); err != nil {
		t.Fatal(err)
	}
	return f
}

// AC-2/AC-12: Bestandsdatei ohne tempo -> tempo wird beim Lesen abgeleitet.
func TestTempo3196_LoadTripLeitetTempoAb(t *testing.T) {
	faelle := map[string]model.Tempo{
		"fahrrad_20": {Fortbewegung: "rad", GrundtempoKmh: 20},
		"fahrrad_15": {Fortbewegung: "rad", GrundtempoKmh: 15},
		"hochtour":   {Fortbewegung: "fuss", GrundtempoKmh: 4},
		"skitour":    {Fortbewegung: "fuss", GrundtempoKmh: 4},
		"mtb":        {Fortbewegung: "fuss", GrundtempoKmh: 4},
		"":           {Fortbewegung: "fuss", GrundtempoKmh: 4},
	}
	for act, want := range faelle {
		t.Run("activity="+act, func(t *testing.T) {
			dir := t.TempDir()
			actJSON := ""
			if act != "" {
				actJSON = `,"activity":"` + act + `"`
			}
			schreibeTripDatei(t, dir, "u1", "alt", `{"id":"alt","name":"Alt","kind":"route","stages":[]`+actJSON+`}`)
			tr, err := New(dir, "u1").LoadTrip("alt")
			if err != nil || tr == nil {
				t.Fatalf("LoadTrip: %v", err)
			}
			if tr.Tempo == nil {
				t.Fatalf("tempo fehlt nach Laden (activity=%q)", act)
			}
			if *tr.Tempo != want {
				t.Errorf("activity=%q: erwartet %+v, bekommen %+v", act, want, *tr.Tempo)
			}
			if tr.Activity != act {
				t.Errorf("activity darf beim Laden nicht veraendert werden: %q -> %q", act, tr.Activity)
			}
		})
	}
}

// Gespeichertes tempo wird nie durch die Ableitung ueberschrieben.
func TestTempo3196_LoadTripBehaeltGespeichertesTempo(t *testing.T) {
	dir := t.TempDir()
	schreibeTripDatei(t, dir, "u1", "neu", `{"id":"neu","name":"Neu","kind":"route","stages":[],"activity":"fahrrad_20","tempo":{"fortbewegung":"ski","grundtempo_kmh":2.5}}`)
	tr, err := New(dir, "u1").LoadTrip("neu")
	if err != nil || tr == nil {
		t.Fatalf("LoadTrip: %v", err)
	}
	if tr.Tempo == nil || tr.Tempo.Fortbewegung != "ski" || tr.Tempo.GrundtempoKmh != 2.5 {
		t.Errorf("gespeichertes tempo verloren: %+v", tr.Tempo)
	}
}

// AC-5/AC-12: SaveTrip rechnet arrival_calculated mit dem tempo nach DAV,
// schreibt tempo auf die Platte und laesst activity stehen.
func TestTempo3196_SaveTripRechnetMitTempo(t *testing.T) {
	dir := t.TempDir()
	s := New(dir, "u1")
	d := func(v float64) *float64 { return &v }
	trip := model.Trip{
		ID: "t", Name: "T", Activity: "fahrrad_20",
		Tempo: &model.Tempo{Fortbewegung: "fuss", GrundtempoKmh: 5},
		Stages: []model.Stage{{ID: "S1", Name: "D1", Date: "2026-07-01", Waypoints: []model.Waypoint{
			{ID: "A", Lat: 47, Lon: 11, ElevationM: 1000, DistanceFromStartKm: d(0)},
			{ID: "B", Lat: 47, Lon: 11, ElevationM: 1000, DistanceFromStartKm: d(10)},
		}}},
	}
	if err := s.SaveTrip(&trip); err != nil {
		t.Fatal(err)
	}
	raw, err := os.ReadFile(filepath.Join(dir, "users", "u1", "briefings", "t.json"))
	if err != nil {
		t.Fatal(err)
	}
	var disk map[string]interface{}
	if err := json.Unmarshal(raw, &disk); err != nil {
		t.Fatal(err)
	}
	tm, ok := disk["tempo"].(map[string]interface{})
	if !ok || tm["fortbewegung"] != "fuss" || tm["grundtempo_kmh"] != 5.0 {
		t.Errorf("tempo nicht auf der Platte: %v", disk["tempo"])
	}
	if disk["activity"] != "fahrrad_20" {
		t.Errorf("activity muss stehen bleiben, bekommen %v", disk["activity"])
	}
	// 10 km flach bei 5 km/h = 2:00 -> 10:00 (alt mit fahrrad_20 waere 08:30).
	tr, _ := s.LoadTrip("t")
	got := *tr.Stages[0].Waypoints[1].ArrivalCalculated
	if got != "10:00" {
		t.Errorf("arrival_calculated: erwartet 10:00 (fuss 5 km/h), bekommen %s", got)
	}
}
