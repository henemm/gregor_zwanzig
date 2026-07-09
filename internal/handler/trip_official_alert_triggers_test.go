package handler

// Issue #1088 (Epic #1073 Slice 4), AC-3 Go-Teil (Adversary Finding F002).
//
// Spec: docs/specs/modules/issue_1088_alert_official_warnings.md
//
// model.Trip bekommt ein additives Pointer-Feld OfficialAlertTriggersEnabled
// (`json:"official_alert_triggers_enabled,omitempty"`), gleiches Muster wie
// OfficialAlertsEnabled (#1087, trip_official_alerts_test.go). PUT
// /api/trips/{id} ohne das Feld im Body darf den zuvor gesetzten Wert
// `false` nicht auf den Default zuruecksetzen (Read-Modify-Write,
// BUG-DATALOSS-GR221) — geprueft fuer zwei unabhaengige Nutzer
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

func seedTripWithOfficialAlertTriggers(t *testing.T, s *store.Store, id, name string, enabled *bool) {
	t.Helper()
	trip := model.Trip{
		ID:   id,
		Name: name,
		Stages: []model.Stage{{
			ID: "S1", Name: "D1", Date: "2026-05-01",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}},
		}},
		OfficialAlertTriggersEnabled: enabled,
	}
	if err := s.SaveTrip(trip); err != nil {
		t.Fatalf("SaveTrip: %v", err)
	}
}

func TestUpdateTripHandler_OfficialAlertTriggersEnabledPreservedWhenBodyOmitsIt(t *testing.T) {
	s := newTestStore(t)
	falseVal := false
	seedTripWithOfficialAlertTriggers(t, s, "trip-triggers-rwm-1", "Trigger-Toggle-Test", &falseVal)

	// PUT-Body OHNE official_alert_triggers_enabled — nur "name" geaendert.
	body := map[string]interface{}{
		"name": "Trigger-Toggle-Test (umbenannt)",
	}
	buf, _ := json.Marshal(body)

	r := chi.NewRouter()
	r.Put("/api/trips/{id}", UpdateTripHandler(s))
	req := httptest.NewRequest(http.MethodPut, "/api/trips/trip-triggers-rwm-1", bytes.NewReader(buf))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "test")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	loaded, err := s.LoadTrip("trip-triggers-rwm-1")
	if err != nil {
		t.Fatalf("LoadTrip: %v", err)
	}
	if loaded.OfficialAlertTriggersEnabled == nil || *loaded.OfficialAlertTriggersEnabled != false {
		t.Errorf("OfficialAlertTriggersEnabled erased by PUT without field: expected false, got %v", loaded.OfficialAlertTriggersEnabled)
	}
	if loaded.Name != "Trigger-Toggle-Test (umbenannt)" {
		t.Errorf("expected name updated, got %q", loaded.Name)
	}
	if len(loaded.Stages) != 1 || loaded.Stages[0].ID != "S1" {
		t.Errorf("expected stages preserved unchanged, got %v", loaded.Stages)
	}
}

func TestUpdateTripHandler_OfficialAlertTriggersEnabledCrossUserIsolation(t *testing.T) {
	baseDir := t.TempDir()
	sA := store.New(baseDir, "usera-1088")
	sB := store.New(baseDir, "userb-1088")

	falseVal := false
	trueVal := true
	seedTripWithOfficialAlertTriggers(t, sA, "trip-triggers-usera", "Nutzer A Trip", &falseVal)
	seedTripWithOfficialAlertTriggers(t, sB, "trip-triggers-userb", "Nutzer B Trip", &trueVal)

	body := map[string]interface{}{
		"name": "Nutzer A Trip (geaendert)",
		"official_alert_triggers_enabled": true,
	}
	buf, _ := json.Marshal(body)

	r := chi.NewRouter()
	r.Put("/api/trips/{id}", UpdateTripHandler(sA))
	req := httptest.NewRequest(http.MethodPut, "/api/trips/trip-triggers-usera", bytes.NewReader(buf))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "usera-1088")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	loadedA, err := sA.LoadTrip("trip-triggers-usera")
	if err != nil {
		t.Fatalf("LoadTrip usera: %v", err)
	}
	if loadedA.OfficialAlertTriggersEnabled == nil || *loadedA.OfficialAlertTriggersEnabled != true {
		t.Errorf("expected usera OfficialAlertTriggersEnabled=true after explicit PUT, got %v", loadedA.OfficialAlertTriggersEnabled)
	}

	loadedB, err := sB.LoadTrip("trip-triggers-userb")
	if err != nil {
		t.Fatalf("LoadTrip userb: %v", err)
	}
	if loadedB.Name != "Nutzer B Trip" {
		t.Errorf("cross-user leak: userb's trip name changed to %q", loadedB.Name)
	}
	if loadedB.OfficialAlertTriggersEnabled == nil || *loadedB.OfficialAlertTriggersEnabled != true {
		t.Errorf("cross-user leak: userb's OfficialAlertTriggersEnabled changed, expected true, got %v", loadedB.OfficialAlertTriggersEnabled)
	}
}
