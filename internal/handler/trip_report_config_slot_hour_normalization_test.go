package handler

// Issue #1280 — Versandzeit-Eingabe auf volle Stunden begrenzen (Trip-Pfad).
// Spec: docs/specs/modules/fix_1280_versandzeit_stunden_raster.md (AC-2, AC-3)
//
// Co-located Handler-Tests gegen echten Store (t.TempDir, keine Mocks), Muster
// wie fix_go_rmw_merge_1082_1103_test.go.

import (
	"encoding/json"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/go-chi/chi/v5"

	"github.com/henemm/gregor-api/internal/model"
)

// AC-2: PUT /api/trips/{id} mit report_config.morning_time=18:45 kappt den Wert
// auf die volle Stunde (18:00) UND laesst die uebrigen report_config-Keys
// (enabled, send_email) unberuehrt (RMW-Merge, kein Replace).
func TestUpdateTripHandler_ReportConfigMorningTimeTruncatedToFullHourOnWrite(t *testing.T) {
	s := newTestStore(t)

	trip := model.Trip{
		ID: "trip-1280-write", Name: "RC Truncate Trip",
		Stages: []model.Stage{{ID: "S1", Name: "D1", Date: "2026-05-01",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}},
		}},
		ReportConfig: map[string]interface{}{
			"enabled":    true,
			"send_email": true,
		},
	}
	if err := s.SaveTrip(&trip); err != nil {
		t.Fatalf("seed failed: %v", err)
	}

	body := `{"report_config":{"morning_time":"18:45:00"}}`

	r := chi.NewRouter()
	r.Put("/api/trips/{id}", UpdateTripHandler(s))
	req := httptest.NewRequest("PUT", "/api/trips/trip-1280-write", strings.NewReader(body))
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	got, err := s.LoadTrip("trip-1280-write")
	if err != nil || got == nil {
		t.Fatalf("LoadTrip failed: %v", err)
	}
	if got.ReportConfig["morning_time"] != "18:00:00" {
		t.Errorf("report_config.morning_time: erwartet 18:00:00 (gekappt), got %v", got.ReportConfig["morning_time"])
	}
	// RMW-Merge: die anderen Keys ueberleben.
	if got.ReportConfig["enabled"] != true {
		t.Errorf("report_config.enabled verloren/geaendert: got %v", got.ReportConfig["enabled"])
	}
	if got.ReportConfig["send_email"] != true {
		t.Errorf("report_config.send_email verloren/geaendert: got %v", got.ReportConfig["send_email"])
	}
}

// AC-3 (Trip): Ein direkt via SaveTrip (unter Umgehung der Handler-Write-
// Normalisierung) mit krummer evening_time (19:30) geseedeter Trip wird beim GET
// mit auf volle Stunde geheiltem Wert (19:00) ausgeliefert.
func TestTripHandler_ReadHealsReportConfigEveningTime(t *testing.T) {
	s := newTestStore(t)

	trip := model.Trip{
		ID: "trip-1280-heal", Name: "RC Heal Trip",
		Stages: []model.Stage{{ID: "S1", Name: "D1", Date: "2026-05-01",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}},
		}},
		ReportConfig: map[string]interface{}{
			"enabled":      true,
			"evening_time": "19:30:00",
		},
	}
	if err := s.SaveTrip(&trip); err != nil {
		t.Fatalf("seed failed: %v", err)
	}

	r := chi.NewRouter()
	r.Get("/api/trips/{id}", TripHandler(s))
	req := httptest.NewRequest("GET", "/api/trips/trip-1280-heal", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	var got model.Trip
	if err := json.Unmarshal(w.Body.Bytes(), &got); err != nil {
		t.Fatalf("unmarshal response: %v", err)
	}
	if got.ReportConfig["evening_time"] != "19:00:00" {
		t.Errorf("GET report_config.evening_time: erwartet 19:00:00 (geheilt), got %v", got.ReportConfig["evening_time"])
	}
	// Adversary F001: das oberste, aus report_config ABGELEITETE Flach-Feld
	// (trip.evening_time) muss ebenfalls geheilt sein — sonst widerspricht die
	// Response sich selbst (verschachtelt 19:00, oben noch 19:30).
	if got.EveningTime == nil || *got.EveningTime != "19:00:00" {
		t.Errorf("GET oberstes evening_time-Flach-Feld: erwartet 19:00:00 (geheilt), got %v", got.EveningTime)
	}
}

// AC-3 (Trip, Liste): Orchestrierer-Nachtrag — die Home-Kachel laedt Trips
// ausschliesslich ueber die LISTE (GET /api/trips, TripsHandler), nicht ueber
// den Einzel-Endpoint. Ein direkt via SaveTrip mit krummer morning_time
// (07:30) geseedeter Trip muss auch in der Liste geheilt (07:00) ankommen —
// symmetrisch zu ListComparePresetsHandler und dem Einzel-TripHandler.
func TestTripsHandler_ReadHealsReportConfigMorningTimeInList(t *testing.T) {
	s := newTestStore(t)

	trip := model.Trip{
		ID: "trip-1280-list-heal", Name: "RC List-Heal Trip",
		Stages: []model.Stage{{ID: "S1", Name: "D1", Date: "2026-05-01",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}},
		}},
		ReportConfig: map[string]interface{}{
			"enabled":      true,
			"morning_time": "07:30:00",
		},
	}
	if err := s.SaveTrip(&trip); err != nil {
		t.Fatalf("seed failed: %v", err)
	}

	r := chi.NewRouter()
	r.Get("/api/trips", TripsHandler(s))
	req := httptest.NewRequest("GET", "/api/trips", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	var got []model.Trip
	if err := json.Unmarshal(w.Body.Bytes(), &got); err != nil {
		t.Fatalf("unmarshal response: %v", err)
	}
	var found *model.Trip
	for i := range got {
		if got[i].ID == "trip-1280-list-heal" {
			found = &got[i]
		}
	}
	if found == nil {
		t.Fatalf("trip-1280-list-heal not found in list response")
	}
	if found.ReportConfig["morning_time"] != "07:00:00" {
		t.Errorf("GET-Liste report_config.morning_time: erwartet 07:00:00 (geheilt), got %v", found.ReportConfig["morning_time"])
	}
	// Adversary F001: das oberste Flach-Feld muss ebenfalls geheilt sein.
	if found.MorningTime == nil || *found.MorningTime != "07:00:00" {
		t.Errorf("GET-Liste oberstes morning_time-Flach-Feld: erwartet 07:00:00 (geheilt), got %v", found.MorningTime)
	}
}

// AC-2 (Adversary F002 CRITICAL): POST /api/trips (Anlege-Wizard) mit
// report_config.morning_time=07:30 kappt den Wert auf die volle Stunde (07:00)
// — sowohl in der Response als auch persistiert. Der Anlege-Wizard
// (TripNewEditor.svelte) POSTet direkt an diesen Endpoint; ohne
// Write-Normalisierung im Anlege-Pfad wuerde eine krumme Versandzeit
// unnormalisiert gespeichert.
func TestCreateTripHandler_ReportConfigMorningTimeTruncatedToFullHourOnWrite(t *testing.T) {
	s := newTestStore(t)

	body := `{"id":"trip-1280-create","name":"Create Truncate Trip",` +
		`"stages":[{"id":"S1","name":"D1","date":"2026-05-01",` +
		`"waypoints":[{"id":"W1","name":"P","lat":47.0,"lon":11.0,"elevation_m":500}]}],` +
		`"report_config":{"enabled":true,"morning_time":"07:30:00"}}`

	h := CreateTripHandler(s)
	req := httptest.NewRequest("POST", "/api/trips", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 201 {
		t.Fatalf("expected 201, got %d: %s", w.Code, w.Body.String())
	}

	var resp model.Trip
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("unmarshal response: %v", err)
	}
	if resp.ReportConfig["morning_time"] != "07:00:00" {
		t.Errorf("Response report_config.morning_time: erwartet 07:00:00 (gekappt), got %v", resp.ReportConfig["morning_time"])
	}

	got, err := s.LoadTrip("trip-1280-create")
	if err != nil || got == nil {
		t.Fatalf("LoadTrip failed: %v", err)
	}
	if got.ReportConfig["morning_time"] != "07:00:00" {
		t.Errorf("Persistiert report_config.morning_time: erwartet 07:00:00 (gekappt), got %v", got.ReportConfig["morning_time"])
	}
}

// Adversary-Nachtrag F005: PATCH /api/trips/{id}/state (Pause/Archivieren) war
// zuvor ein ungeheilter Encode-Pfad — der Handler laedt existing per LoadTrip,
// mutiert nur PausedAt/ArchivedAt und encodiert existing direkt, ohne jemals
// einen Heal-Call auszufuehren. Seit die Read-Heilung zentral in LoadTrip
// sitzt, ist dieser Pfad automatisch mitgeheilt — kein Handler-Code-Aenderung
// noetig, dieser Test beweist es.
func TestUpdateTripStateHandler_ResponseCarriesHealedReportConfigAndFlatField(t *testing.T) {
	s := newTestStore(t)

	trip := model.Trip{
		ID: "trip-1280-state-heal", Name: "State Heal Trip",
		Stages: []model.Stage{{ID: "S1", Name: "D1", Date: "2026-05-01",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}},
		}},
		ReportConfig: map[string]interface{}{
			"enabled":      true,
			"morning_time": "07:30:00",
		},
	}
	// SaveTrip normalisiert die Slot-Zeit NICHT — roh geseedete Bestandsdaten.
	if err := s.SaveTrip(&trip); err != nil {
		t.Fatalf("seed failed: %v", err)
	}

	body := `{"paused":true}`

	r := chi.NewRouter()
	r.Patch("/api/trips/{id}/state", UpdateTripStateHandler(s))
	req := httptest.NewRequest("PATCH", "/api/trips/trip-1280-state-heal/state", strings.NewReader(body))
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	var got model.Trip
	if err := json.Unmarshal(w.Body.Bytes(), &got); err != nil {
		t.Fatalf("unmarshal response: %v", err)
	}
	if got.ReportConfig["morning_time"] != "07:00:00" {
		t.Errorf("PATCH-state Response report_config.morning_time: erwartet 07:00:00 (geheilt), got %v", got.ReportConfig["morning_time"])
	}
	if got.MorningTime == nil || *got.MorningTime != "07:00:00" {
		t.Errorf("PATCH-state Response oberstes MorningTime-Flach-Feld: erwartet 07:00:00 (geheilt), got %v", got.MorningTime)
	}
}
