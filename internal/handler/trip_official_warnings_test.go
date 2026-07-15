package handler

// Issue #1258 Scheibe S1 (AC-4/AC-5) — official_warnings-Pointer-Feld auf
// Trip: Neuanlage-Default via POST, Read-Modify-Write-Preserve via PUT
// (Datenverlust-Schutz BUG-DATALOSS-GR221), Zwei-Nutzer-Isolation
// (CLAUDE.md Multi-User-Pflicht).
//
// Spec: docs/specs/modules/issue_1258_alarme_tab_official_warnings.md AC-4/AC-5.

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/go-chi/chi/v5"

	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

// AC-4: POST /api/trips ohne official_warnings im Body setzt enabled=false
// (bewusster Verhaltenswechsel NUR fuer Neuanlagen).
func TestCreateTripHandler_OfficialWarningsDefaultsDisabled(t *testing.T) {
	s := newTestStore(t)

	body := map[string]interface{}{
		"id":   "trip-1258-create",
		"name": "Neuanlage",
		"stages": []map[string]interface{}{{
			"id": "S1", "name": "D1", "date": "2026-07-15",
			"waypoints": []map[string]interface{}{{
				"id": "W1", "name": "P", "lat": 47.0, "lon": 11.0, "elevation_m": 500,
			}},
		}},
	}
	buf, _ := json.Marshal(body)

	r := chi.NewRouter()
	r.Post("/api/trips", CreateTripHandler(s))
	req := httptest.NewRequest(http.MethodPost, "/api/trips", bytes.NewReader(buf))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "test")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusCreated {
		t.Fatalf("expected 201, got %d: %s", w.Code, w.Body.String())
	}

	var resp model.Trip
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if resp.OfficialWarnings == nil || resp.OfficialWarnings.Enabled != false {
		t.Fatalf("expected official_warnings.enabled=false in response, got %+v", resp.OfficialWarnings)
	}

	loaded, err := s.LoadTrip("trip-1258-create")
	if err != nil {
		t.Fatalf("LoadTrip: %v", err)
	}
	if loaded.OfficialWarnings == nil || loaded.OfficialWarnings.Enabled != false {
		t.Fatalf("expected persisted official_warnings.enabled=false, got %+v", loaded.OfficialWarnings)
	}
}

// RMW-Preserve: PUT ohne official_warnings im Body darf einen zuvor
// gesetzten Wert nicht auf den Default zuruecksetzen (BUG-DATALOSS-GR221).
func TestUpdateTripHandler_OfficialWarningsPreservedWhenBodyOmitsIt(t *testing.T) {
	s := newTestStore(t)
	trip := model.Trip{
		ID:   "trip-1258-rmw",
		Name: "RMW-Test",
		Stages: []model.Stage{{
			ID: "S1", Name: "D1", Date: "2026-07-15",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}},
		}},
		OfficialWarnings: &model.OfficialWarningsConfig{Enabled: true, Sources: []string{"meteofrance_vigilance"}},
	}
	if err := s.SaveTrip(&trip); err != nil {
		t.Fatalf("SaveTrip: %v", err)
	}

	// PUT-Body OHNE official_warnings — nur "name" geaendert.
	body := map[string]interface{}{"name": "RMW-Test (umbenannt)"}
	buf, _ := json.Marshal(body)

	r := chi.NewRouter()
	r.Put("/api/trips/{id}", UpdateTripHandler(s))
	req := httptest.NewRequest(http.MethodPut, "/api/trips/trip-1258-rmw", bytes.NewReader(buf))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "test")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	loaded, err := s.LoadTrip("trip-1258-rmw")
	if err != nil {
		t.Fatalf("LoadTrip: %v", err)
	}
	if loaded.OfficialWarnings == nil || loaded.OfficialWarnings.Enabled != true ||
		len(loaded.OfficialWarnings.Sources) != 1 || loaded.OfficialWarnings.Sources[0] != "meteofrance_vigilance" {
		t.Errorf("official_warnings erased by PUT without field: expected {enabled:true, sources:[meteofrance_vigilance]}, got %+v", loaded.OfficialWarnings)
	}
	if loaded.Name != "RMW-Test (umbenannt)" {
		t.Errorf("expected name updated, got %q", loaded.Name)
	}
}

// AC-5: Nutzer A aendert official_warnings seines Trips — der gleichnamige
// Trip von Nutzer B bleibt unveraendert (Isolation ueber user_id, kein
// Cross-User-Leck, PFLICHT-Test lt. CLAUDE.md).
func TestUpdateTripHandler_OfficialWarningsCrossUserIsolation(t *testing.T) {
	baseDir := t.TempDir()
	sA := store.New(baseDir, "usera-1258")
	sB := store.New(baseDir, "userb-1258")

	tripA := model.Trip{
		ID: "trip-1258-shared", Name: "Nutzer A Trip",
		Stages: []model.Stage{{
			ID: "S1", Name: "D1", Date: "2026-07-15",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}},
		}},
		OfficialWarnings: &model.OfficialWarningsConfig{Enabled: true},
	}
	tripB := model.Trip{
		ID: "trip-1258-shared", Name: "Nutzer B Trip",
		Stages: []model.Stage{{
			ID: "S1", Name: "D1", Date: "2026-07-15",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}},
		}},
		OfficialWarnings: &model.OfficialWarningsConfig{Enabled: false},
	}
	if err := sA.SaveTrip(&tripA); err != nil {
		t.Fatalf("SaveTrip A: %v", err)
	}
	if err := sB.SaveTrip(&tripB); err != nil {
		t.Fatalf("SaveTrip B: %v", err)
	}

	body := map[string]interface{}{
		"official_warnings": map[string]interface{}{"enabled": false},
	}
	buf, _ := json.Marshal(body)

	r := chi.NewRouter()
	r.Put("/api/trips/{id}", UpdateTripHandler(sA))
	req := httptest.NewRequest(http.MethodPut, "/api/trips/trip-1258-shared", bytes.NewReader(buf))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "usera-1258")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	loadedA, err := sA.LoadTrip("trip-1258-shared")
	if err != nil {
		t.Fatalf("LoadTrip usera: %v", err)
	}
	if loadedA.OfficialWarnings == nil || loadedA.OfficialWarnings.Enabled != false {
		t.Errorf("expected usera official_warnings.enabled=false after PUT, got %+v", loadedA.OfficialWarnings)
	}

	loadedB, err := sB.LoadTrip("trip-1258-shared")
	if err != nil {
		t.Fatalf("LoadTrip userb: %v", err)
	}
	if loadedB.Name != "Nutzer B Trip" {
		t.Errorf("cross-user leak: userb's trip name changed to %q", loadedB.Name)
	}
	if loadedB.OfficialWarnings == nil || loadedB.OfficialWarnings.Enabled != false {
		t.Errorf("userb's official_warnings unexpectedly changed, expected enabled=false (unveraendert seit Anlage), got %+v", loadedB.OfficialWarnings)
	}
}

// Fix-Loop F002: PUT mit official_warnings={"enabled":false} OHNE "sources"
// darf zuvor gesetzte Sources nicht loeschen — RMW griff bisher nur auf
// Objekt-Ebene, nicht auf Feld-Ebene innerhalb official_warnings.
func TestUpdateTripHandler_OfficialWarningsEnabledOnlyPreservesSources(t *testing.T) {
	s := newTestStore(t)
	trip := model.Trip{
		ID:   "trip-1258-f002-preserve",
		Name: "F002-Preserve-Test",
		Stages: []model.Stage{{
			ID: "S1", Name: "D1", Date: "2026-07-15",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}},
		}},
		OfficialWarnings: &model.OfficialWarningsConfig{Enabled: true, Sources: []string{"meteofrance_vigilance"}},
	}
	if err := s.SaveTrip(&trip); err != nil {
		t.Fatalf("SaveTrip: %v", err)
	}

	// PUT setzt nur enabled:false, "sources" fehlt im Body komplett.
	body := map[string]interface{}{
		"official_warnings": map[string]interface{}{"enabled": false},
	}
	buf, _ := json.Marshal(body)

	r := chi.NewRouter()
	r.Put("/api/trips/{id}", UpdateTripHandler(s))
	req := httptest.NewRequest(http.MethodPut, "/api/trips/trip-1258-f002-preserve", bytes.NewReader(buf))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "test")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	loaded, err := s.LoadTrip("trip-1258-f002-preserve")
	if err != nil {
		t.Fatalf("LoadTrip: %v", err)
	}
	if loaded.OfficialWarnings == nil || loaded.OfficialWarnings.Enabled != false {
		t.Fatalf("expected enabled=false applied, got %+v", loaded.OfficialWarnings)
	}
	if len(loaded.OfficialWarnings.Sources) != 1 || loaded.OfficialWarnings.Sources[0] != "meteofrance_vigilance" {
		t.Errorf("F002: sources erased by enabled-only PUT, expected [meteofrance_vigilance], got %+v", loaded.OfficialWarnings.Sources)
	}
}

// Gegenprobe zu F002: ein PUT mit explizit leerem "sources":[] MUSS weiterhin
// leeren — nur das komplette Fehlen des Keys bedeutet "unveraendert".
func TestUpdateTripHandler_OfficialWarningsExplicitEmptySourcesClears(t *testing.T) {
	s := newTestStore(t)
	trip := model.Trip{
		ID:   "trip-1258-f002-clear",
		Name: "F002-Clear-Test",
		Stages: []model.Stage{{
			ID: "S1", Name: "D1", Date: "2026-07-15",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}},
		}},
		OfficialWarnings: &model.OfficialWarningsConfig{Enabled: true, Sources: []string{"meteofrance_vigilance"}},
	}
	if err := s.SaveTrip(&trip); err != nil {
		t.Fatalf("SaveTrip: %v", err)
	}

	body := map[string]interface{}{
		"official_warnings": map[string]interface{}{"enabled": true, "sources": []string{}},
	}
	buf, _ := json.Marshal(body)

	r := chi.NewRouter()
	r.Put("/api/trips/{id}", UpdateTripHandler(s))
	req := httptest.NewRequest(http.MethodPut, "/api/trips/trip-1258-f002-clear", bytes.NewReader(buf))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "test")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	loaded, err := s.LoadTrip("trip-1258-f002-clear")
	if err != nil {
		t.Fatalf("LoadTrip: %v", err)
	}
	if len(loaded.OfficialWarnings.Sources) != 0 {
		t.Errorf("explicit empty sources must clear, got %+v", loaded.OfficialWarnings.Sources)
	}
}
