package handler

// TDD: Bug #601 — Round-Trip-Tests für CRUD-Handler
//
// Spec: docs/specs/modules/bug_601_round_trip_catchblocks.md
//
// AC-2: Subscription POST→GET→PUT → 200
// AC-3: Location POST→GET→PUT    → 200
// AC-4: Trip POST→GET→PUT        → 200
// AC-5: validateSubscription akzeptiert lowercase activity_profile ("allgemein")

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/go-chi/chi/v5"
)

// =============================================================================
// AC-2: Subscription Round-Trip (POST → GET → PUT → 200)
// =============================================================================

func TestSubscription_RoundTrip_Basic(t *testing.T) {
	s := newTestStore(t)
	r := chi.NewRouter()
	r.Post("/api/subscriptions", CreateSubscriptionHandler(s))
	r.Get("/api/subscriptions/{id}", SubscriptionHandler(s))
	r.Put("/api/subscriptions/{id}", UpdateSubscriptionHandler(s))

	// 1. POST — valide Subscription anlegen
	createBody := map[string]interface{}{
		"id":                "sub-rt-001",
		"name":              "Round-Trip-Test Subscription",
		"enabled":           true,
		"locations":         []string{"ort-1", "ort-2"},
		"forecast_hours":    24,
		"schedule":          "daily_morning",
		"time_window_start": 6,
		"time_window_end":   18,
		"top_n":             3,
		"weekday":           1,
		"send_email":        true,
		"send_telegram":     false,
	}
	b, _ := json.Marshal(createBody)
	req := httptest.NewRequest("POST", "/api/subscriptions", bytes.NewReader(b))
	req = addUserToContext(req, "user-rt")
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	if w.Code != http.StatusCreated {
		t.Fatalf("AC-2 POST: expected 201, got %d: %s", w.Code, w.Body.String())
	}

	// 2. GET — Subscription abrufen
	req = httptest.NewRequest("GET", "/api/subscriptions/sub-rt-001", nil)
	req = addUserToContext(req, "user-rt")
	w = httptest.NewRecorder()
	r.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("AC-2 GET: expected 200, got %d: %s", w.Code, w.Body.String())
	}
	gotBody := w.Body.Bytes()

	// 3. PUT — exakt dasselbe was GET zurückgab, zurückschicken
	req = httptest.NewRequest("PUT", "/api/subscriptions/sub-rt-001", bytes.NewReader(gotBody))
	req = addUserToContext(req, "user-rt")
	req.Header.Set("Content-Type", "application/json")
	w = httptest.NewRecorder()
	r.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("AC-2 PUT (round-trip): expected 200, got %d: %s", w.Code, w.Body.String())
	}
}

// AC-5: validateSubscription akzeptiert lowercase activity_profile
func TestSubscription_RoundTrip_LowercaseActivityProfile(t *testing.T) {
	s := newTestStore(t)
	r := chi.NewRouter()
	r.Post("/api/subscriptions", CreateSubscriptionHandler(s))
	r.Get("/api/subscriptions/{id}", SubscriptionHandler(s))
	r.Put("/api/subscriptions/{id}", UpdateSubscriptionHandler(s))

	profile := "allgemein"
	createBody := map[string]interface{}{
		"id":                "sub-rt-profile",
		"name":              "Profil Round-Trip",
		"enabled":           false,
		"locations":         []string{"ort-a"},
		"forecast_hours":    48,
		"schedule":          "daily_evening",
		"time_window_start": 5,
		"time_window_end":   9,
		"top_n":             5,
		"weekday":           0,
		"send_email":        false,
		"send_telegram":     false,
		"activity_profile":  profile,
	}
	b, _ := json.Marshal(createBody)
	req := httptest.NewRequest("POST", "/api/subscriptions", bytes.NewReader(b))
	req = addUserToContext(req, "user-rt")
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	if w.Code != http.StatusCreated {
		t.Fatalf("AC-5 POST mit activity_profile=%q: expected 201, got %d: %s", profile, w.Code, w.Body.String())
	}

	// GET → PUT round-trip
	req = httptest.NewRequest("GET", "/api/subscriptions/sub-rt-profile", nil)
	req = addUserToContext(req, "user-rt")
	w = httptest.NewRecorder()
	r.ServeHTTP(w, req)
	gotBody := w.Body.Bytes()

	req = httptest.NewRequest("PUT", "/api/subscriptions/sub-rt-profile", bytes.NewReader(gotBody))
	req = addUserToContext(req, "user-rt")
	req.Header.Set("Content-Type", "application/json")
	w = httptest.NewRecorder()
	r.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("AC-5 PUT round-trip mit activity_profile=%q: expected 200, got %d: %s", profile, w.Code, w.Body.String())
	}
}

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
