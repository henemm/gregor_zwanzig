package store

// TDD RED: Issue #3197 (Workflow feat-3197-tempo-je-etappe)
// Spec: docs/specs/modules/feat_3197_tempo_je_etappe.md (AC-2, AC-5, AC-8, AC-9)
//
// SaveTrip loest das Tempo je Etappe auf (ResolveStageTempo), bevor
// ComputeStageArrivals rechnet. Ein ungueltiger gespeicherter Etappenwert
// wird beim Rechnen ignoriert (Trip-Tempo). Erwartungen aus
// tests/fixtures/naismith_dav_paritaet.json "etappen_ueberschreibung".
//
// Ausfuehrung: go test ./internal/store/ -run 'TestStageTempo3197' -v

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/henemm/gregor-api/internal/model"
)

type etappenFall3197 struct {
	Tempo    model.Tempo   `json:"tempo"`
	Stages   []model.Stage `json:"stages"`
	Erwartet map[string]struct {
		Ankuenfte []string `json:"ankuenfte"`
	} `json:"erwartet"`
}

func ladeFall3197(t *testing.T) etappenFall3197 {
	t.Helper()
	raw, err := os.ReadFile(filepath.Join("..", "..", "tests", "fixtures", "naismith_dav_paritaet.json"))
	if err != nil {
		t.Fatal(err)
	}
	var tab struct {
		Fall etappenFall3197 `json:"etappen_ueberschreibung"`
	}
	if err := json.Unmarshal(raw, &tab); err != nil {
		t.Fatal(err)
	}
	if len(tab.Fall.Stages) != 2 {
		t.Fatalf("Abschnitt etappen_ueberschreibung fehlt")
	}
	return tab.Fall
}

func ankuenfte3197(st model.Stage) []string {
	out := make([]string, len(st.Waypoints))
	for i, wp := range st.Waypoints {
		if wp.ArrivalCalculated != nil {
			out[i] = *wp.ArrivalCalculated
		}
	}
	return out
}

func gleich3197(a, b []string) bool {
	return strings.Join(a, ",") == strings.Join(b, ",")
}

// AC-2/AC-5: SaveTrip rechnet S2 mit 3 km/h, S1 mit dem Trip-Tempo; Feld bleibt nach Reload.
func TestStageTempo3197_SaveTripRechnetJeEtappe(t *testing.T) {
	f := ladeFall3197(t)
	dir := t.TempDir()
	s := New(dir, "u1")
	tempo := f.Tempo
	trip := model.Trip{ID: "t3197", Name: "T", Tempo: &tempo, Stages: f.Stages}
	if err := s.SaveTrip(&trip); err != nil {
		t.Fatal(err)
	}
	tr, err := s.LoadTrip("t3197")
	if err != nil || tr == nil {
		t.Fatalf("LoadTrip: %v", err)
	}
	for _, st := range tr.Stages {
		if got, want := ankuenfte3197(st), f.Erwartet[st.ID].Ankuenfte; !gleich3197(got, want) {
			t.Errorf("%s: erwartet %v, bekommen %v", st.ID, want, got)
		}
	}
	if tr.Stages[1].GrundtempoKmh == nil || *tr.Stages[1].GrundtempoKmh != 3 {
		t.Errorf("S2: grundtempo_kmh nach Reload verloren: %v", tr.Stages[1].GrundtempoKmh)
	}
	if tr.Stages[0].GrundtempoKmh != nil {
		t.Errorf("S1: grundtempo_kmh darf nicht entstehen: %v", *tr.Stages[0].GrundtempoKmh)
	}
}

// AC-8: ungueltiger Wert in einer gespeicherten Datei -> Laden klappt, Rechnen
// ignoriert ihn (S2 wie S1); Laden schreibt die Datei nicht um.
func TestStageTempo3197_UngueltigerDateiwertIgnoriert(t *testing.T) {
	f := ladeFall3197(t)
	for _, wert := range []string{"0", "0.4", "61", "-3"} {
		t.Run(wert, func(t *testing.T) {
			dir := t.TempDir()
			stages, _ := json.Marshal(f.Stages)
			body := strings.Replace(string(stages), `"grundtempo_kmh":3`, `"grundtempo_kmh":`+wert, 1)
			pfad := schreibeTripDatei(t, dir, "u1", "alt",
				`{"id":"alt","name":"Alt","kind":"route","tempo":{"fortbewegung":"fuss","grundtempo_kmh":4},"stages":`+body+`}`)
			vorher, _ := os.ReadFile(pfad)
			s := New(dir, "u1")
			tr, err := s.LoadTrip("alt")
			if err != nil || tr == nil {
				t.Fatalf("LoadTrip mit ungueltigem Etappenwert: %v", err)
			}
			if nachher, _ := os.ReadFile(pfad); string(nachher) != string(vorher) {
				t.Errorf("Laden hat die Datei umgeschrieben")
			}
			if err := s.SaveTrip(tr); err != nil {
				t.Fatal(err)
			}
			tr, _ = s.LoadTrip("alt")
			if got, want := ankuenfte3197(tr.Stages[1]), f.Erwartet["S1"].Ankuenfte; !gleich3197(got, want) {
				t.Errorf("Etappenwert %s: erwartet Trip-Tempo %v, bekommen %v", wert, want, got)
			}
		})
	}
}

// AC-9: Bestandsdatei ohne Etappenwert -> Ankuenfte wie vor #3197, kein neues Feld.
func TestStageTempo3197_BestandUnveraendert(t *testing.T) {
	f := ladeFall3197(t)
	dir := t.TempDir()
	s := New(dir, "u1")
	stages := f.Stages
	stages[1].GrundtempoKmh = nil
	tempo := f.Tempo
	trip := model.Trip{ID: "bestand", Name: "B", Tempo: &tempo, Stages: stages}
	if err := s.SaveTrip(&trip); err != nil {
		t.Fatal(err)
	}
	raw, _ := os.ReadFile(filepath.Join(dir, "users", "u1", "briefings", "bestand.json"))
	if strings.Contains(string(raw), "grundtempo_kmh\":3") || strings.Count(string(raw), "grundtempo_kmh") != 1 {
		t.Errorf("Bestand: grundtempo_kmh nur im Trip-Tempo erwartet: %s", raw)
	}
	tr, _ := s.LoadTrip("bestand")
	for _, st := range tr.Stages {
		if got := ankuenfte3197(st); !gleich3197(got, f.Erwartet["S1"].Ankuenfte) {
			t.Errorf("%s: Bestand rechnet anders: %v", st.ID, got)
		}
	}
}
