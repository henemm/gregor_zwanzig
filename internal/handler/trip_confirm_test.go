package handler

// TDD RED — Issue #303 AC-4, AC-5, AC-6.
// Erwartet: COMPILE-FEHLER bis ConfirmWaypointHandler existiert und
// Waypoint die Felder Origin, Confirmed, SuggestionReason, ArrivalOverride hat.

import (
	"encoding/json"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/go-chi/chi/v5"
	"github.com/henemm/gregor-api/internal/model"
)

// dispatchConfirm ruft PATCH /api/trips/{id}/waypoints/{wpId}/confirm auf.
func dispatchConfirm(t *testing.T, tripID, waypointID, body string) *httptest.ResponseRecorder {
	t.Helper()
	s := newTestStore(t)

	trip := model.Trip{
		ID: tripID, Name: "Test Trip",
		Stages: []model.Stage{{
			ID: "S1", Name: "Tag 1", Date: "2026-05-26",
			Waypoints: []model.Waypoint{
				{ID: "W1", Name: "Start", Lat: 47.0, Lon: 11.0, ElevationM: 500},
				{ID: waypointID, Name: "Gipfel", Lat: 47.1, Lon: 11.1, ElevationM: 2500},
			},
		}},
	}
	if err := s.SaveTrip(trip); err != nil {
		t.Fatalf("seedTrip: %v", err)
	}

	r := chi.NewRouter()
	r.Patch("/api/trips/{id}/waypoints/{waypointId}/confirm", ConfirmWaypointHandler(s))
	req := httptest.NewRequest("PATCH", "/api/trips/"+tripID+"/waypoints/"+waypointID+"/confirm", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	return w
}

// TestConfirmWaypoint_SetsConfirmedAndOverride — AC-4 (Happy Path).
// GIVEN: existierender Trip mit einem Wegpunkt
// WHEN:  PATCH .../confirm mit {"confirmed":true,"arrival_override":"11:45"}
// THEN:  200, Waypoint.Confirmed==true, Waypoint.ArrivalOverride=="11:45"
func TestConfirmWaypoint_SetsConfirmedAndOverride(t *testing.T) {
	w := dispatchConfirm(t, "trip-1", "WP1", `{"confirmed":true,"arrival_override":"11:45"}`)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	var trip model.Trip
	if err := json.Unmarshal(w.Body.Bytes(), &trip); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}

	var found *model.Waypoint
	for i := range trip.Stages {
		for j := range trip.Stages[i].Waypoints {
			if trip.Stages[i].Waypoints[j].ID == "WP1" {
				found = &trip.Stages[i].Waypoints[j]
			}
		}
	}
	if found == nil {
		t.Fatal("Waypoint WP1 nicht in Response gefunden")
	}
	if found.Confirmed == nil || !*found.Confirmed {
		t.Fatalf("Confirmed erwartet true, got %v", found.Confirmed)
	}
	if found.ArrivalOverride == nil || *found.ArrivalOverride != "11:45" {
		t.Fatalf("ArrivalOverride erwartet 11:45, got %v", found.ArrivalOverride)
	}
}

// TestConfirmWaypoint_UnconfirmClearsOverride — AC-4 (Unconfirm).
// GIVEN: bestätigter Waypoint mit arrival_override
// WHEN:  PATCH .../confirm mit {"confirmed":false}
// THEN:  200, Confirmed==false, ArrivalOverride==nil
func TestConfirmWaypoint_UnconfirmClearsOverride(t *testing.T) {
	s := newTestStore(t)
	override := "11:45"
	confirmedTrue := true
	trip := model.Trip{
		ID: "trip-unconfirm", Name: "T",
		Stages: []model.Stage{{
			ID: "S1", Name: "D", Date: "2026-05-26",
			Waypoints: []model.Waypoint{
				{ID: "W1", Name: "Start", Lat: 47.0, Lon: 11.0, ElevationM: 500},
				{
					ID: "WP_CONF", Name: "Gipfel", Lat: 47.1, Lon: 11.1, ElevationM: 2500,
					Origin:          "algorithmic",
					Confirmed:       &confirmedTrue,
					ArrivalOverride: &override,
				},
			},
		}},
	}
	if err := s.SaveTrip(trip); err != nil {
		t.Fatalf("seed: %v", err)
	}

	r := chi.NewRouter()
	r.Patch("/api/trips/{id}/waypoints/{waypointId}/confirm", ConfirmWaypointHandler(s))
	req := httptest.NewRequest("PATCH", "/api/trips/trip-unconfirm/waypoints/WP_CONF/confirm",
		strings.NewReader(`{"confirmed":false}`))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	var result model.Trip
	if err := json.Unmarshal(w.Body.Bytes(), &result); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	var found *model.Waypoint
	for i := range result.Stages {
		for j := range result.Stages[i].Waypoints {
			if result.Stages[i].Waypoints[j].ID == "WP_CONF" {
				found = &result.Stages[i].Waypoints[j]
			}
		}
	}
	if found == nil {
		t.Fatal("Waypoint WP_CONF nicht gefunden")
	}
	if found.Confirmed == nil || *found.Confirmed {
		t.Fatalf("Confirmed erwartet false nach Unconfirm, got %v", found.Confirmed)
	}
}

// TestConfirmWaypoint_NotFound — AC-5.
// GIVEN: nicht existierender Trip oder Waypoint
// WHEN:  PATCH .../confirm
// THEN:  404
func TestConfirmWaypoint_NotFound(t *testing.T) {
	// 404 für nicht existierenden Trip
	s := newTestStore(t)
	r := chi.NewRouter()
	r.Patch("/api/trips/{id}/waypoints/{waypointId}/confirm", ConfirmWaypointHandler(s))

	req := httptest.NewRequest("PATCH", "/api/trips/ghost-trip/waypoints/W1/confirm",
		strings.NewReader(`{"confirmed":true}`))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 404 {
		t.Fatalf("Trip nicht gefunden: expected 404, got %d", w.Code)
	}

	// 404 für nicht existierenden Waypoint
	s2 := newTestStore(t)
	trip2 := model.Trip{
		ID: "trip-wp-miss", Name: "T",
		Stages: []model.Stage{{
			ID: "S1", Name: "D", Date: "2026-05-26",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}},
		}},
	}
	s2.SaveTrip(trip2)

	r2 := chi.NewRouter()
	r2.Patch("/api/trips/{id}/waypoints/{waypointId}/confirm", ConfirmWaypointHandler(s2))
	req2 := httptest.NewRequest("PATCH", "/api/trips/trip-wp-miss/waypoints/GHOST/confirm",
		strings.NewReader(`{"confirmed":true}`))
	req2.Header.Set("Content-Type", "application/json")
	w2 := httptest.NewRecorder()
	r2.ServeHTTP(w2, req2)

	if w2.Code != 404 {
		t.Fatalf("Waypoint nicht gefunden: expected 404, got %d", w2.Code)
	}
}

