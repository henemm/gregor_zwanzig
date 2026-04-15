package handler

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/go-chi/chi/v5"
	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

// TDD RED: Tests for user-scoped handlers — must FAIL until handlers
// extract userId from context via s.WithUser().

// addUserToContext simulates what AuthMiddleware does: inject userId into context.
// Uses middleware.ContextWithUserID which must be exported for test support.
func addUserToContext(r *http.Request, userId string) *http.Request {
	ctx := middleware.ContextWithUserID(r.Context(), userId)
	return r.WithContext(ctx)
}

func TestLocationsHandlerUsesContextUserId(t *testing.T) {
	// GIVEN: Store with data for two users
	tmpDir := t.TempDir()
	s := store.New(tmpDir, "default")

	// Seed location for "alice"
	aliceDir := filepath.Join(tmpDir, "users", "alice", "locations")
	os.MkdirAll(aliceDir, 0755)
	os.WriteFile(filepath.Join(aliceDir, "a.json"),
		[]byte(`{"id":"a","name":"Alice Spot","lat":47.0,"lon":11.0}`), 0644)

	// Seed location for "bob"
	bobDir := filepath.Join(tmpDir, "users", "bob", "locations")
	os.MkdirAll(bobDir, 0755)
	os.WriteFile(filepath.Join(bobDir, "b.json"),
		[]byte(`{"id":"b","name":"Bob Spot","lat":48.0,"lon":12.0}`), 0644)

	h := LocationsHandler(s)

	// WHEN: Alice requests her locations
	req := httptest.NewRequest("GET", "/api/locations", nil)
	req = addUserToContext(req, "alice")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	// THEN: Only Alice's locations are returned
	if w.Code != 200 {
		t.Fatalf("expected 200, got %d", w.Code)
	}
	var locations []model.Location
	json.Unmarshal(w.Body.Bytes(), &locations)

	if len(locations) != 1 {
		t.Fatalf("expected 1 location for alice, got %d", len(locations))
	}
	if locations[0].Name != "Alice Spot" {
		t.Errorf("expected 'Alice Spot', got '%s'", locations[0].Name)
	}
}

func TestCreateLocationHandlerWritesToUserDir(t *testing.T) {
	// GIVEN: Store initialized with "default"
	tmpDir := t.TempDir()
	s := store.New(tmpDir, "default")

	// Create alice's directory structure
	os.MkdirAll(filepath.Join(tmpDir, "users", "alice", "locations"), 0755)

	h := CreateLocationHandler(s)

	// WHEN: Alice creates a location
	body := `{"id":"alice-loc","name":"Alice New","lat":47.5,"lon":11.5}`
	req := httptest.NewRequest("POST", "/api/locations", strings.NewReader(body))
	req = addUserToContext(req, "alice")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	// THEN: Location is saved in alice's directory, NOT default's
	if w.Code != 201 {
		t.Fatalf("expected 201, got %d: %s", w.Code, w.Body.String())
	}

	aliceFile := filepath.Join(tmpDir, "users", "alice", "locations", "alice-loc.json")
	defaultFile := filepath.Join(tmpDir, "users", "default", "locations", "alice-loc.json")

	if _, err := os.Stat(aliceFile); os.IsNotExist(err) {
		t.Error("location should be saved in alice's directory")
	}
	if _, err := os.Stat(defaultFile); !os.IsNotExist(err) {
		t.Error("location should NOT be saved in default's directory")
	}
}

func TestTripsHandlerUsesContextUserId(t *testing.T) {
	// GIVEN: Store with trip data for "charlie"
	tmpDir := t.TempDir()
	s := store.New(tmpDir, "default")

	charlieDir := filepath.Join(tmpDir, "users", "charlie", "trips")
	os.MkdirAll(charlieDir, 0755)
	trip := model.Trip{ID: "trip1", Name: "Charlie's Trip"}
	data, _ := json.Marshal(trip)
	os.WriteFile(filepath.Join(charlieDir, "trip1.json"), data, 0644)

	h := TripsHandler(s)

	// WHEN: Charlie requests trips
	req := httptest.NewRequest("GET", "/api/trips", nil)
	req = addUserToContext(req, "charlie")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	// THEN: Returns Charlie's trips
	if w.Code != 200 {
		t.Fatalf("expected 200, got %d", w.Code)
	}
	var trips []model.Trip
	json.Unmarshal(w.Body.Bytes(), &trips)

	if len(trips) != 1 {
		t.Fatalf("expected 1 trip for charlie, got %d", len(trips))
	}
	if trips[0].Name != "Charlie's Trip" {
		t.Errorf("expected 'Charlie's Trip', got '%s'", trips[0].Name)
	}
}

func TestDeleteTripHandlerUsesContextUserId(t *testing.T) {
	// GIVEN: Trips for two users
	tmpDir := t.TempDir()
	s := store.New(tmpDir, "default")

	// Alice has a trip
	aliceDir := filepath.Join(tmpDir, "users", "alice", "trips")
	os.MkdirAll(aliceDir, 0755)
	os.WriteFile(filepath.Join(aliceDir, "trip1.json"),
		[]byte(`{"id":"trip1","name":"Alice Trip"}`), 0644)

	// Bob has the same trip ID
	bobDir := filepath.Join(tmpDir, "users", "bob", "trips")
	os.MkdirAll(bobDir, 0755)
	os.WriteFile(filepath.Join(bobDir, "trip1.json"),
		[]byte(`{"id":"trip1","name":"Bob Trip"}`), 0644)

	r := chi.NewRouter()
	r.Delete("/api/trips/{id}", DeleteTripHandler(s))

	// WHEN: Alice deletes trip1
	req := httptest.NewRequest("DELETE", "/api/trips/trip1", nil)
	req = addUserToContext(req, "alice")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	// THEN: Only Alice's trip is deleted, Bob's remains
	if w.Code != 204 {
		t.Fatalf("expected 204, got %d", w.Code)
	}

	if _, err := os.Stat(filepath.Join(aliceDir, "trip1.json")); !os.IsNotExist(err) {
		t.Error("alice's trip should be deleted")
	}
	if _, err := os.Stat(filepath.Join(bobDir, "trip1.json")); os.IsNotExist(err) {
		t.Error("bob's trip should still exist")
	}
}
