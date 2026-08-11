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

func boolPtr(b bool) *bool { return &b }

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
		loaded.AlertChannels.Email == nil || *loaded.AlertChannels.Email != false ||
		loaded.AlertChannels.Telegram == nil || *loaded.AlertChannels.Telegram != true ||
		loaded.AlertChannels.Sms == nil || *loaded.AlertChannels.Sms != false {
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
		AlertChannels: &model.AlertChannelsConfig{
			Email: boolPtr(false), Telegram: boolPtr(true), Sms: boolPtr(false),
		},
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
	if loaded.AlertChannels == nil ||
		loaded.AlertChannels.Email == nil || *loaded.AlertChannels.Email != false ||
		loaded.AlertChannels.Telegram == nil || *loaded.AlertChannels.Telegram != true ||
		loaded.AlertChannels.Sms == nil || *loaded.AlertChannels.Sms != false {
		t.Errorf("alert_channels erased by PUT without field: expected {email:false,telegram:true,sms:false}, got %+v", loaded.AlertChannels)
	}
	if loaded.Name != "AlertChannels-Preserve-Test (umbenannt)" {
		t.Errorf("expected name updated, got %q", loaded.Name)
	}
}

// AC-7 (#1701 S2b): PUT eines aelteren Frontend-Builds ohne das vierte Feld
// "premium_sms" darf einen zuvor gesetzten Premium-SMS-Wert NICHT auf false
// zuruecksetzen -- Feld-Level-Merge INNERHALB von AlertChannelsConfig
// (Muster AlertChannelThresholds, D3 der Spec). Zwei aufeinanderfolgende
// PUTs: der erste setzt alle vier Felder, der zweite schickt nur drei.
func TestUpdateTripHandler_AlertChannels_FourthFieldMissingInBody_PreservesExistingValue(t *testing.T) {
	s := newTestStore(t)
	trip := model.Trip{
		ID:   "trip-1701-ac7",
		Name: "AC7-1701-Test",
		Stages: []model.Stage{{
			ID: "S1", Name: "D1", Date: "2026-07-15",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}},
		}},
	}
	if err := s.SaveTrip(&trip); err != nil {
		t.Fatalf("SaveTrip: %v", err)
	}

	r := chi.NewRouter()
	r.Put("/api/trips/{id}", UpdateTripHandler(s))

	// Erster PUT: alle vier Felder explizit gesetzt, inkl. premium_sms=true.
	firstBody := map[string]interface{}{
		"alert_channels": map[string]interface{}{
			"email": true, "telegram": false, "sms": true, "premium_sms": true,
		},
	}
	firstBuf, _ := json.Marshal(firstBody)
	firstReq := httptest.NewRequest(http.MethodPut, "/api/trips/trip-1701-ac7", bytes.NewReader(firstBuf))
	firstReq.Header.Set("Content-Type", "application/json")
	firstReq = addUserToContext(firstReq, "test")
	firstW := httptest.NewRecorder()
	r.ServeHTTP(firstW, firstReq)
	if firstW.Code != http.StatusOK {
		t.Fatalf("expected 200 on first PUT, got %d: %s", firstW.Code, firstW.Body.String())
	}

	afterFirst, err := s.LoadTrip("trip-1701-ac7")
	if err != nil {
		t.Fatalf("LoadTrip after first PUT: %v", err)
	}
	if afterFirst.AlertChannels == nil || afterFirst.AlertChannels.PremiumSms == nil ||
		*afterFirst.AlertChannels.PremiumSms != true {
		t.Fatalf("expected premium_sms=true after first PUT, got %+v", afterFirst.AlertChannels)
	}

	// Zweiter PUT: wie ein aelteres Frontend-Build — nur drei Felder, kein
	// premium_sms im Body.
	secondBody := map[string]interface{}{
		"alert_channels": map[string]interface{}{
			"email": false, "telegram": true, "sms": false,
		},
	}
	secondBuf, _ := json.Marshal(secondBody)
	secondReq := httptest.NewRequest(http.MethodPut, "/api/trips/trip-1701-ac7", bytes.NewReader(secondBuf))
	secondReq.Header.Set("Content-Type", "application/json")
	secondReq = addUserToContext(secondReq, "test")
	secondW := httptest.NewRecorder()
	r.ServeHTTP(secondW, secondReq)
	if secondW.Code != http.StatusOK {
		t.Fatalf("expected 200 on second PUT, got %d: %s", secondW.Code, secondW.Body.String())
	}

	loaded, err := s.LoadTrip("trip-1701-ac7")
	if err != nil {
		t.Fatalf("LoadTrip after second PUT: %v", err)
	}
	// Die drei explizit gesendeten Felder wurden uebernommen.
	if loaded.AlertChannels == nil ||
		loaded.AlertChannels.Email == nil || *loaded.AlertChannels.Email != false ||
		loaded.AlertChannels.Telegram == nil || *loaded.AlertChannels.Telegram != true ||
		loaded.AlertChannels.Sms == nil || *loaded.AlertChannels.Sms != false {
		t.Fatalf("expected the three explicitly sent fields applied, got %+v", loaded.AlertChannels)
	}
	// AC-7: premium_sms fehlte im zweiten Body -- der Bestandswert (true)
	// MUSS erhalten bleiben, NICHT still auf false zurueckgesetzt werden.
	if loaded.AlertChannels.PremiumSms == nil || *loaded.AlertChannels.PremiumSms != true {
		t.Errorf(
			"AC-7: premium_sms erased by a PUT that omitted the fourth field "+
				"(simulating an older frontend build) -- expected true (unangetastet), got %+v",
			loaded.AlertChannels.PremiumSms,
		)
	}
}
