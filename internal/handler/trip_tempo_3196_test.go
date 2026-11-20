package handler

// TDD RED: Issue #3196 (Workflow feat-3196-trip-tempo-etappen)
// Spec: docs/specs/modules/feat_3196_trip_tempo_etappen.md (AC-5, AC-8)
//
// Etappen-PUT (PUT /api/trips/{id}) mit Optional-Merge des Feldes "tempo":
// fehlt es, bleibt der Bestand; ist es gesetzt, wird nur dieses Feld
// ueberschrieben und arrival_calculated neu berechnet; ungueltige Werte -> 422.
// Zwei-Nutzer-Trennung: A aendert nur seinen Trip, nie den von B.
//
// Ausfuehrung: go test ./internal/handler/ -run 'TestTempo3196' -v

import (
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

func tempoF(v float64) *float64 { return &v }

func seedTempoTrip(t *testing.T, s *store.Store, user, id string) {
	t.Helper()
	trip := model.Trip{
		ID: id, Name: "Tempo-Trip", Region: "Korsika", Activity: "fahrrad_20",
		Tempo: &model.Tempo{Fortbewegung: "rad", GrundtempoKmh: 20},
		Stages: []model.Stage{{ID: "S1", Name: "D1", Date: "2026-07-01", Waypoints: []model.Waypoint{
			{ID: "A", Name: "A", Lat: 47, Lon: 11, ElevationM: 1000, DistanceFromStartKm: tempoF(0)},
			{ID: "B", Name: "B", Lat: 47, Lon: 11, ElevationM: 1000, DistanceFromStartKm: tempoF(10)},
		}}},
	}
	if err := s.WithUser(user).SaveTrip(&trip); err != nil {
		t.Fatalf("SaveTrip: %v", err)
	}
}

func ladeTempoTrip(t *testing.T, s *store.Store, user, id string) *model.Trip {
	t.Helper()
	tr, err := s.WithUser(user).LoadTrip(id)
	if err != nil || tr == nil {
		t.Fatalf("LoadTrip(%s/%s): %v", user, id, err)
	}
	return tr
}

// AC-5: PUT mit tempo setzt nur dieses Feld, rechnet Ankunftszeiten neu.
func TestTempo3196_PutMitTempoMergedNurDiesesFeld(t *testing.T) {
	s := newTestStore(t)
	seedTempoTrip(t, s, "userA", "t1")
	r := briefingVergleichEtagRouter(s)
	putOK(t, r, "/api/trips/t1", "userA", `{"tempo":{"fortbewegung":"fuss","grundtempo_kmh":5}}`)

	tr := ladeTempoTrip(t, s, "userA", "t1")
	if tr.Tempo == nil || tr.Tempo.Fortbewegung != "fuss" || tr.Tempo.GrundtempoKmh != 5 {
		t.Fatalf("tempo nicht uebernommen: %+v", tr.Tempo)
	}
	if tr.Name != "Tempo-Trip" || tr.Region != "Korsika" || tr.Activity != "fahrrad_20" || len(tr.Stages) != 1 {
		t.Errorf("andere Felder veraendert: name=%q region=%q activity=%q stages=%d",
			tr.Name, tr.Region, tr.Activity, len(tr.Stages))
	}
	// 10 km flach bei 5 km/h = 2:00 -> 10:00
	if got := *tr.Stages[0].Waypoints[1].ArrivalCalculated; got != "10:00" {
		t.Errorf("arrival_calculated nach PUT: erwartet 10:00, bekommen %s", got)
	}
}

// Fix-Loop 3, F-A2-2: der Anlege-POST prueft tempo wie der PUT. Ungueltig -> 422 und
// nichts gespeichert; fehlendes tempo bleibt erlaubt und wird aus activity abgeleitet.
func TestTempo3196_PostPrueftTempo(t *testing.T) {
	post := func(s *store.Store, body string) int {
		return doReq(CreateTripHandler(s), http.MethodPost, "/api/trips", body, "", "userA").Code
	}
	for _, tempo := range []string{
		`{"fortbewegung":"auto","grundtempo_kmh":4}`,
		`{"fortbewegung":"fuss","grundtempo_kmh":0}`,
		`{"fortbewegung":"fuss","grundtempo_kmh":0.4}`,
		`{"fortbewegung":"rad","grundtempo_kmh":61}`,
	} {
		t.Run(tempo, func(t *testing.T) {
			s := newTestStore(t)
			if code := post(s, `{"id":"neu","name":"Neu","tempo":`+tempo+`}`); code != http.StatusUnprocessableEntity {
				t.Fatalf("erwartet 422, bekommen %d", code)
			}
			if tr, _ := s.WithUser("userA").LoadTrip("neu"); tr != nil {
				t.Errorf("abgelehnter Trip trotzdem gespeichert: %+v", tr.Tempo)
			}
		})
	}
	s := newTestStore(t)
	if code := post(s, `{"id":"gut","name":"Gut","tempo":{"fortbewegung":"ski","grundtempo_kmh":2.5}}`); code != http.StatusCreated && code != http.StatusOK {
		t.Fatalf("gueltiges tempo: erwartet 201, bekommen %d", code)
	}
	if tr := ladeTempoTrip(t, s, "userA", "gut"); tr.Tempo == nil || tr.Tempo.Fortbewegung != "ski" || tr.Tempo.GrundtempoKmh != 2.5 {
		t.Errorf("gueltiges tempo nicht gespeichert: %+v", tr.Tempo)
	}
	if code := post(s, `{"id":"alt","name":"Alt","activity":"fahrrad_20"}`); code != http.StatusCreated && code != http.StatusOK {
		t.Fatalf("ohne tempo: erwartet 201, bekommen %d", code)
	}
	if tr := ladeTempoTrip(t, s, "userA", "alt"); tr.Tempo == nil || tr.Tempo.Fortbewegung != "rad" || tr.Tempo.GrundtempoKmh != 20 {
		t.Errorf("fehlendes tempo nicht aus activity abgeleitet: %+v", tr.Tempo)
	}
}

// Fix-Loop 2, F001: die Untergrenze 0.5 km/h selbst ist gueltig (Oberflaeche min=0.5).
func TestTempo3196_PutUntergrenzeGueltig(t *testing.T) {
	s := newTestStore(t)
	seedTempoTrip(t, s, "userA", "t1u")
	r := briefingVergleichEtagRouter(s)
	putOK(t, r, "/api/trips/t1u", "userA", `{"tempo":{"fortbewegung":"fuss","grundtempo_kmh":0.5}}`)
	tr := ladeTempoTrip(t, s, "userA", "t1u")
	if tr.Tempo == nil || tr.Tempo.GrundtempoKmh != 0.5 {
		t.Fatalf("0.5 km/h nicht uebernommen: %+v", tr.Tempo)
	}
}

// PUT ohne tempo laesst das gespeicherte tempo unveraendert.
func TestTempo3196_PutOhneTempoBehaeltBestand(t *testing.T) {
	for _, body := range []string{`{}`, `{"name":"Neu"}`, `{"activity":"wandern"}`} {
		t.Run(body, func(t *testing.T) {
			s := newTestStore(t)
			seedTempoTrip(t, s, "userA", "t2")
			r := briefingVergleichEtagRouter(s)
			putOK(t, r, "/api/trips/t2", "userA", body)
			tr := ladeTempoTrip(t, s, "userA", "t2")
			if tr.Tempo == nil || tr.Tempo.Fortbewegung != "rad" || tr.Tempo.GrundtempoKmh != 20 {
				t.Errorf("tempo nach %s veraendert: %+v", body, tr.Tempo)
			}
		})
	}
}

// Ungueltige Werte werden mit 422 abgelehnt, der Bestand bleibt.
func TestTempo3196_PutUngueltigesTempo422(t *testing.T) {
	bodies := []string{
		`{"tempo":{"fortbewegung":"auto","grundtempo_kmh":50}}`,
		`{"tempo":{"fortbewegung":"fuss","grundtempo_kmh":0}}`,
		`{"tempo":{"fortbewegung":"fuss","grundtempo_kmh":-3}}`,
		`{"tempo":{"fortbewegung":"rad","grundtempo_kmh":500}}`,
		`{"tempo":{"fortbewegung":"","grundtempo_kmh":4}}`,
		// Fix-Loop 2, F001: Untergrenze 0.5 km/h (sonst OverflowError im Python-Rechner).
		`{"tempo":{"fortbewegung":"fuss","grundtempo_kmh":0.4}}`,
		`{"tempo":{"fortbewegung":"ski","grundtempo_kmh":1e-320}}`,
	}
	for _, body := range bodies {
		t.Run(body, func(t *testing.T) {
			s := newTestStore(t)
			seedTempoTrip(t, s, "userA", "t3")
			r := briefingVergleichEtagRouter(s)
			w := doReq(r, http.MethodPut, "/api/trips/t3", body, "", "userA")
			if w.Code != http.StatusUnprocessableEntity {
				t.Errorf("erwartet 422, bekommen %d: %s", w.Code, w.Body.String())
			}
			tr := ladeTempoTrip(t, s, "userA", "t3")
			if tr.Tempo == nil || tr.Tempo.Fortbewegung != "rad" || tr.Tempo.GrundtempoKmh != 20 {
				t.Errorf("Bestand nach abgelehntem PUT veraendert: %+v", tr.Tempo)
			}
		})
	}
}

// AC-8: Zwei Nutzer -- A aendert sein tempo, B bleibt unveraendert; A kann
// den Trip von B nicht aendern; nie unter "default" gespeichert.
func TestTempo3196_ZweiNutzerGetrennt(t *testing.T) {
	dataDir := t.TempDir()
	s := store.New(dataDir, "test")
	seedTempoTrip(t, s, "userA", "gemeinsam")
	seedTempoTrip(t, s, "userB", "gemeinsam")
	seedTempoTrip(t, s, "userB", "nur-b")
	r := briefingVergleichEtagRouter(s)

	putOK(t, r, "/api/trips/gemeinsam", "userA", `{"tempo":{"fortbewegung":"mtb","grundtempo_kmh":12}}`)
	if tr := ladeTempoTrip(t, s, "userA", "gemeinsam"); tr.Tempo == nil || tr.Tempo.Fortbewegung != "mtb" {
		t.Fatalf("A: tempo nicht gesetzt: %+v", tr.Tempo)
	}
	if tr := ladeTempoTrip(t, s, "userB", "gemeinsam"); tr.Tempo == nil || tr.Tempo.Fortbewegung != "rad" || tr.Tempo.GrundtempoKmh != 20 {
		t.Errorf("B: gleichnamiger Trip von A-PUT veraendert: %+v", tr.Tempo)
	}

	w := doReq(r, http.MethodPut, "/api/trips/nur-b", `{"tempo":{"fortbewegung":"ski","grundtempo_kmh":3}}`, "", "userA")
	if w.Code == http.StatusOK {
		t.Errorf("A darf Trip von B nicht aendern, bekam 200: %s", w.Body.String())
	}
	if tr := ladeTempoTrip(t, s, "userB", "nur-b"); tr.Tempo == nil || tr.Tempo.Fortbewegung != "rad" {
		t.Errorf("B: Trip nur-b durch A veraendert: %+v", tr.Tempo)
	}

	defDir := filepath.Join(dataDir, "users", "default")
	if entries, err := os.ReadDir(defDir); err == nil {
		for _, e := range entries {
			if strings.Contains(e.Name(), "briefings") || strings.HasSuffix(e.Name(), ".json") {
				t.Errorf("unter users/default wurde geschrieben: %s", e.Name())
			}
		}
	}
}
