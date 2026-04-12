package handler

import (
	"encoding/json"
	"net/http/httptest"
	"testing"

	"github.com/go-chi/chi/v5"
	"github.com/henemm/gregor-api/internal/store"
)

func TestTripsHandler(t *testing.T) {
	s := store.New("../../data", "default")

	h := TripsHandler(s)
	req := httptest.NewRequest("GET", "/api/trips", nil)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d", w.Code)
	}

	var trips []map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &trips); err != nil {
		t.Fatalf("expected JSON array, got error: %v", err)
	}
	if len(trips) == 0 {
		t.Error("expected at least one trip")
	}

	ct := w.Header().Get("Content-Type")
	if ct != "application/json" {
		t.Errorf("expected Content-Type application/json, got %s", ct)
	}
}

func TestTripHandlerFound(t *testing.T) {
	s := store.New("../../data", "default")

	r := chi.NewRouter()
	r.Get("/api/trips/{id}", TripHandler(s))

	req := httptest.NewRequest("GET", "/api/trips/e2e-test-story3", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d", w.Code)
	}

	var trip map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &trip); err != nil {
		t.Fatalf("expected JSON object, got error: %v", err)
	}
	if trip["id"] != "e2e-test-story3" {
		t.Errorf("expected id e2e-test-story3, got %v", trip["id"])
	}
}

func TestTripHandlerNotFound(t *testing.T) {
	s := store.New("../../data", "default")

	r := chi.NewRouter()
	r.Get("/api/trips/{id}", TripHandler(s))

	req := httptest.NewRequest("GET", "/api/trips/nonexistent-trip", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 404 {
		t.Fatalf("expected 404, got %d", w.Code)
	}

	var body map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &body)
	if body["error"] != "not_found" {
		t.Errorf("expected error not_found, got %v", body["error"])
	}
}
