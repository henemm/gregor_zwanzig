package handler

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/go-chi/chi/v5"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

func newTestStore(t *testing.T) *store.Store {
	return store.New(t.TempDir(), "test")
}

func seedTrip(t *testing.T, s *store.Store, id, name string) {
	trip := model.Trip{
		ID: id, Name: name,
		Stages: []model.Stage{{ID: "S1", Name: "D1", Date: "2026-05-01",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}},
		}},
	}
	s.SaveTrip(trip)
}

func TestCreateTripHandler(t *testing.T) {
	s := newTestStore(t)

	body := `{"id":"new-trip","name":"New Trip","stages":[{"id":"S1","name":"Day 1","date":"2026-05-01","waypoints":[{"id":"W1","name":"Start","lat":47.0,"lon":11.0,"elevation_m":500}]}]}`

	h := CreateTripHandler(s)
	req := httptest.NewRequest("POST", "/api/trips", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 201 {
		t.Fatalf("expected 201, got %d: %s", w.Code, w.Body.String())
	}

	var resp map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &resp)
	if resp["id"] != "new-trip" {
		t.Errorf("expected id new-trip, got %v", resp["id"])
	}
}

func TestCreateTripHandlerInvalid(t *testing.T) {
	s := newTestStore(t)

	body := `{"id":"no-name","stages":[]}`

	h := CreateTripHandler(s)
	req := httptest.NewRequest("POST", "/api/trips", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 400 {
		t.Fatalf("expected 400, got %d", w.Code)
	}
}

func TestCreateTripHandlerZeroCoords(t *testing.T) {
	s := newTestStore(t)

	body := `{"id":"zero","name":"Zero","stages":[{"id":"S1","name":"D1","date":"2026-05-01","waypoints":[{"id":"W1","name":"P","lat":0,"lon":0,"elevation_m":0}]}]}`

	h := CreateTripHandler(s)
	req := httptest.NewRequest("POST", "/api/trips", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 400 {
		t.Fatalf("expected 400 for zero coords, got %d", w.Code)
	}
}

func TestUpdateTripHandler(t *testing.T) {
	s := newTestStore(t)
	seedTrip(t, s, "existing", "Old Name")

	body := `{"id":"existing","name":"Updated Name","stages":[{"id":"S1","name":"Day 1","date":"2026-05-01","waypoints":[{"id":"W1","name":"Start","lat":47.0,"lon":11.0,"elevation_m":500}]}]}`

	r := chi.NewRouter()
	r.Put("/api/trips/{id}", UpdateTripHandler(s))

	req := httptest.NewRequest("PUT", "/api/trips/existing", strings.NewReader(body))
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
}

func TestUpdateTripHandlerNotFound(t *testing.T) {
	s := newTestStore(t)

	body := `{"id":"ghost","name":"Ghost","stages":[{"id":"S1","name":"D1","date":"2026-05-01","waypoints":[{"id":"W1","name":"P","lat":47.0,"lon":11.0,"elevation_m":500}]}]}`

	r := chi.NewRouter()
	r.Put("/api/trips/{id}", UpdateTripHandler(s))

	req := httptest.NewRequest("PUT", "/api/trips/ghost", strings.NewReader(body))
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 404 {
		t.Fatalf("expected 404, got %d", w.Code)
	}
}

func TestDeleteTripHandler(t *testing.T) {
	s := newTestStore(t)
	seedTrip(t, s, "to-delete", "Delete Me")

	r := chi.NewRouter()
	r.Delete("/api/trips/{id}", DeleteTripHandler(s))

	req := httptest.NewRequest("DELETE", "/api/trips/to-delete", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusNoContent {
		t.Fatalf("expected 204, got %d", w.Code)
	}
}
