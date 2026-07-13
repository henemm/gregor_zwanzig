package handler

import (
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/go-chi/chi/v5"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

// Issue #1082 + #1103: Blind-Replace verursacht Datenverlust.
// TDD RED: co-located Handler-Tests gegen echten Store (Tempdir, keine Mocks).
// Muster wie location_write_test.go / trip_write_test.go.

// AC-1: POST /api/locations mit kollidierender ID (kebab-Ableitung aus Name)
// muss 409 liefern und die bestehende Datei byte-identisch belassen.
func TestCreateLocation_Collision_Returns409(t *testing.T) {
	s := newTestStore(t)

	region := "Haute-Savoie"
	existing := model.Location{ID: "chamonix", Name: "Chamonix (alt)", Lat: 45.9, Lon: 6.87, Region: &region}
	if err := s.SaveLocation(existing); err != nil {
		t.Fatalf("seed failed: %v", err)
	}

	path := filepath.Join(s.LocationsDir(), "chamonix.json")
	before, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("failed to read seeded file: %v", err)
	}

	body := `{"name":"Chamonix","lat":45.9,"lon":6.87}`
	h := CreateLocationHandler(s)
	req := httptest.NewRequest("POST", "/api/locations", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 409 {
		t.Fatalf("expected 409, got %d: %s", w.Code, w.Body.String())
	}

	after, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("failed to re-read file: %v", err)
	}
	if string(before) != string(after) {
		t.Fatalf("existing location file was overwritten\nbefore:\n%s\nafter:\n%s", before, after)
	}
}

// AC-2: Regression-Schutz — frischer POST ohne Kollision liefert weiterhin 201.
func TestCreateLocation_NoCollision_Returns201(t *testing.T) {
	s := newTestStore(t)

	body := `{"name":"Annecy","lat":45.9,"lon":6.12}`
	h := CreateLocationHandler(s)
	req := httptest.NewRequest("POST", "/api/locations", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 201 {
		t.Fatalf("expected 201, got %d: %s", w.Code, w.Body.String())
	}

	path := filepath.Join(s.LocationsDir(), "annecy.json")
	if _, err := os.Stat(path); os.IsNotExist(err) {
		t.Fatalf("expected location file to exist at %s", path)
	}
}

// AC-3: PUT /api/trips/{id} mit Teil-report_config muss die übrigen Keys
// (enabled, send_email) erhalten und nur email_format ändern (Feld-Level-Merge).
func TestUpdateTrip_PartialReportConfig_MergesFields(t *testing.T) {
	s := newTestStore(t)

	trip := model.Trip{
		ID: "merge-rc-1103", Name: "RC Trip",
		Stages: []model.Stage{{ID: "S1", Name: "D1", Date: "2026-05-01",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}},
		}},
		ReportConfig: map[string]interface{}{
			"enabled":      true,
			"email_format": "full",
			"send_email":   true,
		},
	}
	if err := s.SaveTrip(&trip); err != nil {
		t.Fatalf("seed failed: %v", err)
	}

	body := `{"report_config":{"email_format":"compact"}}`

	r := chi.NewRouter()
	r.Put("/api/trips/{id}", UpdateTripHandler(s))
	req := httptest.NewRequest("PUT", "/api/trips/merge-rc-1103", strings.NewReader(body))
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	got, err := s.LoadTrip("merge-rc-1103")
	if err != nil {
		t.Fatalf("LoadTrip failed: %v", err)
	}
	if got == nil {
		t.Fatal("trip not found after PUT")
	}
	if got.ReportConfig["enabled"] != true {
		t.Errorf("report_config.enabled lost/changed: got %v", got.ReportConfig["enabled"])
	}
	if got.ReportConfig["email_format"] != "compact" {
		t.Errorf("report_config.email_format: expected compact, got %v", got.ReportConfig["email_format"])
	}
	if got.ReportConfig["send_email"] != true {
		t.Errorf("report_config.send_email lost/changed: got %v", got.ReportConfig["send_email"])
	}
}

// AC-4: Existenzprüfung ist user-scoped — userB darf eine ID anlegen, die nur
// in userAs Store existiert (kein Cross-User-Datenleck, kein falsches 409).
func TestCreateLocation_Collision_UserScoped_NoCrossUser(t *testing.T) {
	tmpDir := t.TempDir()
	base := store.New(tmpDir, "default")

	userAStore := base.WithUser("userA")
	seedLocation(t, userAStore, "chamonix", "Chamonix (userA)")

	body := `{"name":"Chamonix","lat":45.9,"lon":6.87}`
	h := CreateLocationHandler(base)
	req := httptest.NewRequest("POST", "/api/locations", strings.NewReader(body))
	req = addUserToContext(req, "userB")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 201 {
		t.Fatalf("expected 201 (user-scoped, no cross-user collision), got %d: %s", w.Code, w.Body.String())
	}

	userAFile := filepath.Join(tmpDir, "users", "userA", "locations", "chamonix.json")
	if _, err := os.Stat(userAFile); os.IsNotExist(err) {
		t.Fatalf("userA's location file should still exist untouched at %s", userAFile)
	}
}
