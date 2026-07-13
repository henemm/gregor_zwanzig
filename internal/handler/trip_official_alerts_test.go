package handler

// Issue #1087 (Epic #1073 Slice 3), AC-3 Go-Teil.
//
// Spec: docs/specs/modules/epic_1073_trip_official_alerts.md
//
// model.Trip bekommt ein additives Pointer-Feld OfficialAlertsEnabled
// (`json:"official_alerts_enabled,omitempty"`), analog zum #1040-Muster fuer
// ComparePreset. PUT /api/trips/{id} ohne das Feld im Body darf den zuvor
// gesetzten Wert `false` nicht auf den Default zuruecksetzen (Read-Modify-
// Write, BUG-DATALOSS-GR221) — geprueft fuer zwei unabhaengige Nutzer
// (Cross-User-Isolation, CLAUDE.md Multi-User-Pflicht).

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

func seedTripWithOfficialAlerts(t *testing.T, s *store.Store, id, name string, enabled *bool) {
	t.Helper()
	trip := model.Trip{
		ID:   id,
		Name: name,
		Stages: []model.Stage{{
			ID: "S1", Name: "D1", Date: "2026-05-01",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}},
		}},
		OfficialAlertsEnabled: enabled,
	}
	if err := s.SaveTrip(&trip); err != nil {
		t.Fatalf("SaveTrip: %v", err)
	}
}

func TestUpdateTripHandler_OfficialAlertsEnabledPreservedWhenBodyOmitsIt(t *testing.T) {
	s := newTestStore(t)
	falseVal := false
	seedTripWithOfficialAlerts(t, s, "trip-alerts-rwm-1", "Alerts-Toggle-Test", &falseVal)

	// PUT-Body OHNE official_alerts_enabled — nur "name" geaendert.
	body := map[string]interface{}{
		"name": "Alerts-Toggle-Test (umbenannt)",
	}
	buf, _ := json.Marshal(body)

	r := chi.NewRouter()
	r.Put("/api/trips/{id}", UpdateTripHandler(s))
	req := httptest.NewRequest(http.MethodPut, "/api/trips/trip-alerts-rwm-1", bytes.NewReader(buf))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "test")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	loaded, err := s.LoadTrip("trip-alerts-rwm-1")
	if err != nil {
		t.Fatalf("LoadTrip: %v", err)
	}
	if loaded.OfficialAlertsEnabled == nil || *loaded.OfficialAlertsEnabled != false {
		t.Errorf("OfficialAlertsEnabled erased by PUT without field: expected false, got %v", loaded.OfficialAlertsEnabled)
	}
	if loaded.Name != "Alerts-Toggle-Test (umbenannt)" {
		t.Errorf("expected name updated, got %q", loaded.Name)
	}
	if len(loaded.Stages) != 1 || loaded.Stages[0].ID != "S1" {
		t.Errorf("expected stages preserved unchanged, got %v", loaded.Stages)
	}
}

func TestUpdateTripHandler_OfficialAlertsEnabledCrossUserIsolation(t *testing.T) {
	baseDir := t.TempDir()
	sA := store.New(baseDir, "usera-1087")
	sB := store.New(baseDir, "userb-1087")

	falseVal := false
	trueVal := true
	seedTripWithOfficialAlerts(t, sA, "trip-alerts-usera", "Nutzer A Trip", &falseVal)
	seedTripWithOfficialAlerts(t, sB, "trip-alerts-userb", "Nutzer B Trip", &trueVal)

	body := map[string]interface{}{
		"name":                    "Nutzer A Trip (geaendert)",
		"official_alerts_enabled": true,
	}
	buf, _ := json.Marshal(body)

	r := chi.NewRouter()
	r.Put("/api/trips/{id}", UpdateTripHandler(sA))
	req := httptest.NewRequest(http.MethodPut, "/api/trips/trip-alerts-usera", bytes.NewReader(buf))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "usera-1087")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	loadedA, err := sA.LoadTrip("trip-alerts-usera")
	if err != nil {
		t.Fatalf("LoadTrip usera: %v", err)
	}
	if loadedA.OfficialAlertsEnabled == nil || *loadedA.OfficialAlertsEnabled != true {
		t.Errorf("expected usera OfficialAlertsEnabled=true after explicit PUT, got %v", loadedA.OfficialAlertsEnabled)
	}

	loadedB, err := sB.LoadTrip("trip-alerts-userb")
	if err != nil {
		t.Fatalf("LoadTrip userb: %v", err)
	}
	if loadedB.Name != "Nutzer B Trip" {
		t.Errorf("cross-user leak: userb's trip name changed to %q", loadedB.Name)
	}
	if loadedB.OfficialAlertsEnabled == nil || *loadedB.OfficialAlertsEnabled != true {
		t.Errorf("cross-user leak: userb's OfficialAlertsEnabled changed, expected true, got %v", loadedB.OfficialAlertsEnabled)
	}
}
