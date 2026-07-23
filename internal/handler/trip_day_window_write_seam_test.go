package handler

// Fix-Loop nach Adversary-Verdict BROKEN — Issue #1319 Scheibe B+C, F001.
// Spec: docs/specs/modules/daywindow_configurable_window.md (AC-4/AC-5)
//
// Adversary-Befund: ein ungueltiges day_window_start_hour/_end_hour-Paar
// (start>=end oder ausserhalb 0-23) wurde bisher NUR auf dem Lesepfad
// (healTripSlotTimes -> ClampReportConfigDayWindow) geklemmt, nie auf den
// Schreib-Seams (UpdateTripHandler/CreateTripHandler) — es landete ungeklemmt
// auf der Platte und die PUT/POST-Response echote den kaputten Wert direkt
// zurueck (existing wird ohne erneutes Load geantwortet). Fix: beide
// Schreib-Seams rufen jetzt zusaetzlich store.ClampReportConfigDayWindow auf,
// analog store.NormalizeReportConfigSlotTimes (Issue #1280-Muster).
//
// Co-located Handler-Tests gegen echten Store (t.TempDir, keine Mocks).

import (
	"encoding/json"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/go-chi/chi/v5"

	"github.com/henemm/gregor-api/internal/model"
)

// AC-4/AC-5 (Write-Seam): PUT /api/trips/{id} mit einem ungueltigen Paar
// (start=19, end=19, start>=end) darf das Paar weder persistieren noch in der
// PUT-Response zurueckechoen — beide Keys werden entfernt (-> Default 4/19).
func TestUpdateTripHandler_ClampsInvalidDayWindowPairOnWrite(t *testing.T) {
	s := newTestStore(t)

	trip := model.Trip{
		ID: "trip-1319-daywindow-write", Name: "DayWindow Write Clamp Trip",
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

	body := `{"report_config":{"day_window_start_hour":19,"day_window_end_hour":19}}`

	r := chi.NewRouter()
	r.Put("/api/trips/{id}", UpdateTripHandler(s))
	req := httptest.NewRequest("PUT", "/api/trips/trip-1319-daywindow-write", strings.NewReader(body))
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	var resp model.Trip
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("unmarshal response: %v", err)
	}
	if _, ok := resp.ReportConfig["day_window_start_hour"]; ok {
		t.Errorf("PUT-Response darf day_window_start_hour nicht ungeklemmt zurueckgeben, got %v", resp.ReportConfig["day_window_start_hour"])
	}
	if _, ok := resp.ReportConfig["day_window_end_hour"]; ok {
		t.Errorf("PUT-Response darf day_window_end_hour nicht ungeklemmt zurueckgeben, got %v", resp.ReportConfig["day_window_end_hour"])
	}
	// RMW-Merge: andere Keys bleiben erhalten.
	if resp.ReportConfig["send_email"] != true {
		t.Errorf("report_config.send_email verloren/geaendert: got %v", resp.ReportConfig["send_email"])
	}

	got, err := s.LoadTrip("trip-1319-daywindow-write")
	if err != nil || got == nil {
		t.Fatalf("LoadTrip failed: %v", err)
	}
	if _, ok := got.ReportConfig["day_window_start_hour"]; ok {
		t.Errorf("Persistiert darf day_window_start_hour nicht ungeklemmt vorliegen, got %v", got.ReportConfig["day_window_start_hour"])
	}
}

// AC-3/AC-5 (Write-Seam, gegenprobe): ein gueltiges Paar (06-16) bleibt
// unangetastet — die Klemmung darf keine korrekten Eingaben verwerfen.
func TestUpdateTripHandler_KeepsValidDayWindowPairOnWrite(t *testing.T) {
	s := newTestStore(t)

	trip := model.Trip{
		ID: "trip-1319-daywindow-valid", Name: "DayWindow Valid Trip",
		Stages: []model.Stage{{ID: "S1", Name: "D1", Date: "2026-05-01",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}},
		}},
		ReportConfig: map[string]interface{}{"enabled": true},
	}
	if err := s.SaveTrip(&trip); err != nil {
		t.Fatalf("seed failed: %v", err)
	}

	body := `{"report_config":{"day_window_start_hour":6,"day_window_end_hour":16}}`

	r := chi.NewRouter()
	r.Put("/api/trips/{id}", UpdateTripHandler(s))
	req := httptest.NewRequest("PUT", "/api/trips/trip-1319-daywindow-valid", strings.NewReader(body))
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	got, err := s.LoadTrip("trip-1319-daywindow-valid")
	if err != nil || got == nil {
		t.Fatalf("LoadTrip failed: %v", err)
	}
	if got.ReportConfig["day_window_start_hour"] != float64(6) {
		t.Errorf("day_window_start_hour: erwartet 6, got %v", got.ReportConfig["day_window_start_hour"])
	}
	if got.ReportConfig["day_window_end_hour"] != float64(16) {
		t.Errorf("day_window_end_hour: erwartet 16, got %v", got.ReportConfig["day_window_end_hour"])
	}
}

// AC-4 (Write-Seam, Anlege-Pfad): POST /api/trips mit einem ungueltigen Paar
// darf das Paar ebenfalls nicht persistieren (analog Issue #1280 F002-Fix fuer
// morning_time/evening_time).
func TestCreateTripHandler_ClampsInvalidDayWindowPairOnWrite(t *testing.T) {
	s := newTestStore(t)

	body := `{"id":"trip-1319-daywindow-create","name":"Create DayWindow Clamp Trip",` +
		`"stages":[{"id":"S1","name":"D1","date":"2026-05-01",` +
		`"waypoints":[{"id":"W1","name":"P","lat":47.0,"lon":11.0,"elevation_m":500}]}],` +
		`"report_config":{"enabled":true,"day_window_start_hour":20,"day_window_end_hour":10}}`

	h := CreateTripHandler(s)
	req := httptest.NewRequest("POST", "/api/trips", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 201 {
		t.Fatalf("expected 201, got %d: %s", w.Code, w.Body.String())
	}

	got, err := s.LoadTrip("trip-1319-daywindow-create")
	if err != nil || got == nil {
		t.Fatalf("LoadTrip failed: %v", err)
	}
	if _, ok := got.ReportConfig["day_window_start_hour"]; ok {
		t.Errorf("Persistiert darf day_window_start_hour nicht ungeklemmt vorliegen, got %v", got.ReportConfig["day_window_start_hour"])
	}
}
