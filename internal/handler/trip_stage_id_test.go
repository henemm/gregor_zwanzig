package handler

// Issue #243: Stage-IDs dürfen nie leer im Store landen.
// TDD RED — alle Tests schlagen fehl, bis ensureStageIDs implementiert ist.

import (
	"encoding/json"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/go-chi/chi/v5"
	"github.com/henemm/gregor-api/internal/model"
)

// AC-3: POST mit leerer Stage-ID → gespeicherte Stage hat nicht-leere ID.
func TestCreateTrip_EmptyStageID_AutoGenerates(t *testing.T) {
	s := newTestStore(t)

	body := `{"id":"khw-test","name":"KHW","stages":[{"id":"","name":"Tag 1","date":"2026-05-04","waypoints":[{"id":"W1","name":"Start","lat":47.1,"lon":13.2,"elevation_m":800}]}]}`

	h := CreateTripHandler(s)
	req := httptest.NewRequest("POST", "/api/trips", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 201 {
		t.Fatalf("expected 201, got %d: %s", w.Code, w.Body.String())
	}

	got, err := s.LoadTrip("khw-test")
	if err != nil || got == nil {
		t.Fatalf("trip nicht gefunden: %v", err)
	}
	if len(got.Stages) != 1 {
		t.Fatalf("expected 1 stage, got %d", len(got.Stages))
	}
	if got.Stages[0].ID == "" {
		t.Errorf("AC-3 FAIL: Stage.ID ist leer — Backend muss leere IDs auto-generieren")
	}
}

// AC-3: PUT mit leerer Stage-ID → gespeicherte Stage hat nicht-leere ID.
func TestUpdateTrip_EmptyStageID_AutoGenerates(t *testing.T) {
	s := newTestStore(t)
	seedTrip(t, s, "khw-update", "KHW")

	body := `{"stages":[{"id":"","name":"Tag 1","date":"2026-05-04","waypoints":[{"id":"W1","name":"Start","lat":47.1,"lon":13.2,"elevation_m":800}]}]}`

	r := chi.NewRouter()
	r.Put("/api/trips/{id}", UpdateTripHandler(s))
	req := httptest.NewRequest("PUT", "/api/trips/khw-update", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	got, err := s.LoadTrip("khw-update")
	if err != nil || got == nil {
		t.Fatalf("trip nicht gefunden: %v", err)
	}
	if len(got.Stages) != 1 {
		t.Fatalf("expected 1 stage, got %d", len(got.Stages))
	}
	if got.Stages[0].ID == "" {
		t.Errorf("AC-3 FAIL: Stage.ID ist leer nach PUT — Backend muss leere IDs auto-generieren")
	}
}

// AC-3: PUT mit 13 Stages alle id:"" → alle IDs sind eindeutig und nicht leer.
// Reproduziert exakt den Zustand von Trip 5f534011 (KHW 403).
func TestUpdateTrip_MultipleEmptyStageIDs_AllUnique(t *testing.T) {
	s := newTestStore(t)
	seedTrip(t, s, "khw-403", "KHW 403")

	// 13 Stages, alle mit id:"" — wie in 5f534011.json
	stages := make([]map[string]interface{}, 13)
	for i := range stages {
		stages[i] = map[string]interface{}{
			"id":   "",
			"name": "KHW Stage",
			"date": "2026-05-04",
			"waypoints": []map[string]interface{}{
				{"id": "W1", "name": "Start", "lat": 47.1, "lon": 13.2, "elevation_m": 800},
			},
		}
	}
	payload, _ := json.Marshal(map[string]interface{}{"stages": stages})

	r := chi.NewRouter()
	r.Put("/api/trips/{id}", UpdateTripHandler(s))
	req := httptest.NewRequest("PUT", "/api/trips/khw-403", strings.NewReader(string(payload)))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	got, err := s.LoadTrip("khw-403")
	if err != nil || got == nil {
		t.Fatalf("trip nicht gefunden: %v", err)
	}
	if len(got.Stages) != 13 {
		t.Fatalf("expected 13 stages, got %d", len(got.Stages))
	}

	seen := map[string]bool{}
	for i, stage := range got.Stages {
		if stage.ID == "" {
			t.Errorf("Stage %d hat leere ID — each_key_duplicate-Fehler im Frontend wäre die Folge", i)
		}
		if seen[stage.ID] {
			t.Errorf("Stage %d hat doppelte ID %q — each_key_duplicate-Fehler im Frontend wäre die Folge", i, stage.ID)
		}
		seen[stage.ID] = true
	}
}

// AC-3: Response-Body des PUT muss bereits die generierten IDs enthalten.
func TestUpdateTrip_EmptyStageID_ResponseContainsGeneratedID(t *testing.T) {
	s := newTestStore(t)
	seedTrip(t, s, "khw-resp", "KHW")

	body := `{"stages":[{"id":"","name":"Tag 1","date":"2026-05-04","waypoints":[{"id":"W1","name":"Start","lat":47.1,"lon":13.2,"elevation_m":800}]}]}`

	r := chi.NewRouter()
	r.Put("/api/trips/{id}", UpdateTripHandler(s))
	req := httptest.NewRequest("PUT", "/api/trips/khw-resp", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	var resp model.Trip
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("response ist kein valides Trip-JSON: %v", err)
	}
	if len(resp.Stages) != 1 {
		t.Fatalf("expected 1 stage in response, got %d", len(resp.Stages))
	}
	if resp.Stages[0].ID == "" {
		t.Errorf("AC-3 FAIL: Response-Body enthält leere Stage-ID — Frontend kann Key nicht ableiten")
	}
}
