package handler

// Issue #1258 Scheibe S3 (AC-26) — alert_channels-Pointer-Feld auf Trip:
// Read-Modify-Write-Merge (Datenverlust-Schutz BUG-DATALOSS-GR221) analog
// OfficialWarnings (trip_official_warnings_test.go).
//
// Spec: docs/specs/modules/issue_1258_alarme_tab_official_warnings.md AC-26.

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/go-chi/chi/v5"

	"github.com/henemm/gregor-api/internal/model"
)

// AC-26: PUT nur mit alert_channels persistiert das Feld UND laesst uebrige
// Trip-Felder (Name, Stages, ReportConfig, Corridors) unangetastet.
func TestUpdateTripHandler_AlertChannelsRMW(t *testing.T) {
	s := newTestStore(t)
	trip := model.Trip{
		ID:   "trip-1258-s3-alertchannels-rmw",
		Name: "AlertChannels-RMW-Test",
		Stages: []model.Stage{{
			ID: "S1", Name: "D1", Date: "2026-07-15",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}},
		}},
		ReportConfig: map[string]interface{}{"send_email": true},
		Corridors: []model.Corridor{{
			Metric: "wind_gust", Range: [2]*float64{nil, nil}, Notify: true,
		}},
	}
	if err := s.SaveTrip(&trip); err != nil {
		t.Fatalf("SaveTrip: %v", err)
	}

	// PUT-Body enthaelt NUR alert_channels — keine anderen Felder.
	body := map[string]interface{}{
		"alert_channels": map[string]interface{}{"email": false, "telegram": true, "sms": false},
	}
	buf, _ := json.Marshal(body)

	r := chi.NewRouter()
	r.Put("/api/trips/{id}", UpdateTripHandler(s))
	req := httptest.NewRequest(http.MethodPut, "/api/trips/trip-1258-s3-alertchannels-rmw", bytes.NewReader(buf))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "test")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	loaded, err := s.LoadTrip("trip-1258-s3-alertchannels-rmw")
	if err != nil {
		t.Fatalf("LoadTrip: %v", err)
	}

	if loaded.AlertChannels == nil ||
		loaded.AlertChannels.Email != false ||
		loaded.AlertChannels.Telegram != true ||
		loaded.AlertChannels.Sms != false {
		t.Fatalf("expected alert_channels={email:false,telegram:true,sms:false}, got %+v", loaded.AlertChannels)
	}

	// Uebrige Felder unangetastet (BUG-DATALOSS-GR221).
	if loaded.Name != "AlertChannels-RMW-Test" {
		t.Errorf("expected name unchanged, got %q", loaded.Name)
	}
	if len(loaded.Stages) != 1 || loaded.Stages[0].ID != "S1" {
		t.Errorf("expected stages unchanged, got %+v", loaded.Stages)
	}
	if sendEmail, _ := loaded.ReportConfig["send_email"].(bool); !sendEmail {
		t.Errorf("expected report_config.send_email unchanged (true), got %+v", loaded.ReportConfig)
	}
	if len(loaded.Corridors) != 1 || !loaded.Corridors[0].Notify {
		t.Errorf("expected corridors unchanged, got %+v", loaded.Corridors)
	}
}

// RMW-Preserve: PUT ohne alert_channels im Body darf einen zuvor gesetzten
// Wert nicht auf nil zuruecksetzen (BUG-DATALOSS-GR221).
func TestUpdateTripHandler_AlertChannelsPreservedWhenBodyOmitsIt(t *testing.T) {
	s := newTestStore(t)
	trip := model.Trip{
		ID:   "trip-1258-s3-alertchannels-preserve",
		Name: "AlertChannels-Preserve-Test",
		Stages: []model.Stage{{
			ID: "S1", Name: "D1", Date: "2026-07-15",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}},
		}},
		AlertChannels: &model.AlertChannelsConfig{Email: false, Telegram: true, Sms: false},
	}
	if err := s.SaveTrip(&trip); err != nil {
		t.Fatalf("SaveTrip: %v", err)
	}

	body := map[string]interface{}{"name": "AlertChannels-Preserve-Test (umbenannt)"}
	buf, _ := json.Marshal(body)

	r := chi.NewRouter()
	r.Put("/api/trips/{id}", UpdateTripHandler(s))
	req := httptest.NewRequest(http.MethodPut, "/api/trips/trip-1258-s3-alertchannels-preserve", bytes.NewReader(buf))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "test")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	loaded, err := s.LoadTrip("trip-1258-s3-alertchannels-preserve")
	if err != nil {
		t.Fatalf("LoadTrip: %v", err)
	}
	if loaded.AlertChannels == nil || loaded.AlertChannels.Email != false ||
		loaded.AlertChannels.Telegram != true || loaded.AlertChannels.Sms != false {
		t.Errorf("alert_channels erased by PUT without field: expected {email:false,telegram:true,sms:false}, got %+v", loaded.AlertChannels)
	}
	if loaded.Name != "AlertChannels-Preserve-Test (umbenannt)" {
		t.Errorf("expected name updated, got %q", loaded.Name)
	}
}
