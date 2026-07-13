package handler

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/go-chi/chi/v5"
	"github.com/henemm/gregor-api/internal/model"
)

// ============================================================================
// Trip Weather Config
// ============================================================================

func TestGetTripWeatherConfigFound(t *testing.T) {
	s := newTestStore(t)
	seedTrip(t, s, "e2e-test-story3", "Story3")

	r := chi.NewRouter()
	r.Get("/api/trips/{id}/weather-config", GetTripWeatherConfigHandler(s))

	req := httptest.NewRequest("GET", "/api/trips/e2e-test-story3/weather-config", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d", w.Code)
	}
}

func TestGetTripWeatherConfigNotFound(t *testing.T) {
	s := newTestStore(t)

	r := chi.NewRouter()
	r.Get("/api/trips/{id}/weather-config", GetTripWeatherConfigHandler(s))

	req := httptest.NewRequest("GET", "/api/trips/nonexistent/weather-config", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 404 {
		t.Fatalf("expected 404, got %d", w.Code)
	}
}

func TestPutTripWeatherConfig(t *testing.T) {
	s := newTestStore(t)
	seedTrip(t, s, "cfg-trip", "Config Trip")

	r := chi.NewRouter()
	r.Put("/api/trips/{id}/weather-config", PutTripWeatherConfigHandler(s))

	body := `{"trip_id":"cfg-trip","metrics":[{"metric_id":"temperature","enabled":true}]}`
	req := httptest.NewRequest("PUT", "/api/trips/cfg-trip/weather-config", strings.NewReader(body))
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	// Verify config was saved
	trip, _ := s.LoadTrip("cfg-trip")
	if trip.DisplayConfig == nil {
		t.Fatal("expected display_config to be set after PUT")
	}
}

func TestPutTripWeatherConfigNotFound(t *testing.T) {
	s := newTestStore(t)

	r := chi.NewRouter()
	r.Put("/api/trips/{id}/weather-config", PutTripWeatherConfigHandler(s))

	req := httptest.NewRequest("PUT", "/api/trips/ghost/weather-config", strings.NewReader(`{}`))
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 404 {
		t.Fatalf("expected 404, got %d", w.Code)
	}
}

func TestPutTripWeatherConfigBadJSON(t *testing.T) {
	s := newTestStore(t)
	seedTrip(t, s, "bad-json", "Bad JSON Trip")

	r := chi.NewRouter()
	r.Put("/api/trips/{id}/weather-config", PutTripWeatherConfigHandler(s))

	req := httptest.NewRequest("PUT", "/api/trips/bad-json/weather-config", strings.NewReader(`not json`))
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 400 {
		t.Fatalf("expected 400, got %d", w.Code)
	}
}

// ============================================================================
// Location Weather Config
// ============================================================================

func TestGetLocationWeatherConfigNotFound(t *testing.T) {
	s := newTestStore(t)

	r := chi.NewRouter()
	r.Get("/api/locations/{id}/weather-config", GetLocationWeatherConfigHandler(s))

	req := httptest.NewRequest("GET", "/api/locations/nonexistent/weather-config", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 404 {
		t.Fatalf("expected 404, got %d", w.Code)
	}
}

func TestPutLocationWeatherConfig(t *testing.T) {
	s := newTestStore(t)
	// Seed a location
	loc := model.Location{ID: "test-loc", Name: "Test", Lat: 47.0, Lon: 11.0}
	s.SaveLocation(loc)

	r := chi.NewRouter()
	r.Put("/api/locations/{id}/weather-config", PutLocationWeatherConfigHandler(s))

	body := `{"metrics":[{"metric_id":"wind","enabled":true}]}`
	req := httptest.NewRequest("PUT", "/api/locations/test-loc/weather-config", strings.NewReader(body))
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	updated, _ := s.LoadLocation("test-loc")
	if updated.DisplayConfig == nil {
		t.Fatal("expected display_config to be set after PUT")
	}
}

// Issue #1250 Scheibe 0: Subscription Weather Config Tests entfernt —
// Legacy-Drittstack CompareSubscription stillgelegt (#1131),
// GetSubscriptionWeatherConfigHandler/PutSubscriptionWeatherConfigHandler
// existieren nicht mehr.

// Suppress unused import warning
var _ = json.Unmarshal
var _ = http.StatusOK
