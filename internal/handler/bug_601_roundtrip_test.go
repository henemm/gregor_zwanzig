package handler

// TDD: Bug #601 — Round-Trip-Tests für CRUD-Handler
//
// Spec: docs/specs/modules/bug_601_round_trip_catchblocks.md
//
// AC-3: Location POST→GET→PUT    → 200
// AC-4: Trip POST→GET→PUT        → 200
//
// Issue #1250 Scheibe 0: AC-2/AC-5 (Subscription Round-Trip) entfernt —
// Legacy-Drittstack CompareSubscription stillgelegt (#1131), CreateSubscriptionHandler
// existiert nicht mehr.

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/go-chi/chi/v5"
)

// =============================================================================
// AC-3: Location Round-Trip (POST → GET → PUT → 200)
// =============================================================================

func TestLocation_RoundTrip_Basic(t *testing.T) {
	s := newTestStore(t)
	r := chi.NewRouter()
	r.Post("/api/locations", CreateLocationHandler(s))
	r.Get("/api/locations/{id}", LocationHandler(s))
	r.Put("/api/locations/{id}", UpdateLocationHandler(s))

	// 1. POST
	createBody := map[string]interface{}{
		"id":   "loc-rt-001",
		"name": "Round-Trip-Ort",
		"lat":  47.4,
		"lon":  11.2,
	}
	b, _ := json.Marshal(createBody)
	req := httptest.NewRequest("POST", "/api/locations", bytes.NewReader(b))
	req = addUserToContext(req, "user-rt")
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	if w.Code != http.StatusCreated {
		t.Fatalf("AC-3 POST: expected 201, got %d: %s", w.Code, w.Body.String())
	}

	// 2. GET
	req = httptest.NewRequest("GET", "/api/locations/loc-rt-001", nil)
	req = addUserToContext(req, "user-rt")
	w = httptest.NewRecorder()
	r.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("AC-3 GET: expected 200, got %d: %s", w.Code, w.Body.String())
	}
	gotBody := w.Body.Bytes()

	// 3. PUT mit exakt demselben Body
	req = httptest.NewRequest("PUT", "/api/locations/loc-rt-001", bytes.NewReader(gotBody))
	req = addUserToContext(req, "user-rt")
	req.Header.Set("Content-Type", "application/json")
	w = httptest.NewRecorder()
	r.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("AC-3 PUT (round-trip): expected 200, got %d: %s", w.Code, w.Body.String())
	}
}

// =============================================================================
// AC-4: Trip Round-Trip (POST → GET → PUT → 200)
// =============================================================================

func TestTrip_RoundTrip_Basic(t *testing.T) {
	s := newTestStore(t)
	r := chi.NewRouter()
	r.Post("/api/trips", CreateTripHandler(s))
	r.Get("/api/trips/{id}", TripHandler(s))
	r.Put("/api/trips/{id}", UpdateTripHandler(s))

	// 1. POST
	createBody := `{
		"id": "trip-rt-001",
		"name": "Round-Trip-Tour",
		"stages": [{
			"id": "s1",
			"name": "Tag 1",
			"date": "2026-08-01",
			"waypoints": [
				{"id": "w1", "name": "Start", "lat": 47.0, "lon": 11.0, "elevation_m": 800}
			]
		}]
	}`
	req := httptest.NewRequest("POST", "/api/trips", bytes.NewReader([]byte(createBody)))
	req = addUserToContext(req, "user-rt")
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	if w.Code != http.StatusCreated {
		t.Fatalf("AC-4 POST: expected 201, got %d: %s", w.Code, w.Body.String())
	}

	// 2. GET
	req = httptest.NewRequest("GET", "/api/trips/trip-rt-001", nil)
	req = addUserToContext(req, "user-rt")
	w = httptest.NewRecorder()
	r.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("AC-4 GET: expected 200, got %d: %s", w.Code, w.Body.String())
	}

	// 3. PUT — Trip-Update nimmt nur die veränderten Felder (Merge-Handler)
	// Wir schicken nur name + stages — das ist was das Frontend tut
	putBody := `{"name": "Round-Trip-Tour", "stages": [{"id": "s1", "name": "Tag 1", "date": "2026-08-01", "waypoints": [{"id": "w1", "name": "Start", "lat": 47.0, "lon": 11.0, "elevation_m": 800}]}]}`
	req = httptest.NewRequest("PUT", "/api/trips/trip-rt-001", bytes.NewReader([]byte(putBody)))
	req = addUserToContext(req, "user-rt")
	req.Header.Set("Content-Type", "application/json")
	w = httptest.NewRecorder()
	r.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("AC-4 PUT (round-trip): expected 200, got %d: %s", w.Code, w.Body.String())
	}
}
