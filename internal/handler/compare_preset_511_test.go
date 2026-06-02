package handler

// TDD RED: Issue #511 — Weekly-Preset weekday-Validation (AC-4).
//
// Spec: docs/specs/modules/issue_511_weekly_scheduler.md
//
// Tests prüfen:
//   - weekday=7 bei schedule='weekly' → 400 Bad Request
//   - weekday=4 bei schedule='weekly' → 201 Created (gültig)
//   - weekday=-1 bei schedule='weekly' → 400 Bad Request
//
// RED: TestCreateComparePreset_WeeklyInvalidWeekday schlägt fehl,
// weil validateComparePreset() aktuell kein weekday-Feld prüft.

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/go-chi/chi/v5"
)

// =============================================================================
// AC-4: POST — weekly mit weekday=7 (ungültig) → 400
// =============================================================================

func TestCreateComparePreset_WeeklyInvalidWeekday(t *testing.T) {
	// GIVEN: Create-Request für weekly-Preset mit weekday=7 (ungültig, muss 0-6 sein)
	s := newTestStore(t)
	r := chi.NewRouter()
	r.Post("/api/compare/presets", CreateComparePresetHandler(s))

	body := validPresetBody()
	body["schedule"] = "weekly"
	body["weekday"] = 7 // ungültig

	req := httptest.NewRequest("POST", "/api/compare/presets", jsonBody(t, body))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "user1")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	// WHEN: POST /api/compare/presets
	// THEN: 400 Bad Request mit "weekday" in der Fehlermeldung
	// RED: aktuell liefert der Handler 201, weil weekday nicht validiert wird
	if w.Code != http.StatusBadRequest {
		t.Fatalf(
			"expected 400 Bad Request for weekly preset with weekday=7, got %d: %s",
			w.Code, w.Body.String(),
		)
	}
	if !strings.Contains(w.Body.String(), "weekday") {
		t.Errorf(
			"expected error message to contain 'weekday', got: %s",
			w.Body.String(),
		)
	}
}

func TestCreateComparePreset_WeeklyInvalidWeekdayNegative(t *testing.T) {
	// GIVEN: Create-Request für weekly-Preset mit weekday=-1 (ungültig)
	s := newTestStore(t)
	r := chi.NewRouter()
	r.Post("/api/compare/presets", CreateComparePresetHandler(s))

	body := validPresetBody()
	body["schedule"] = "weekly"
	body["weekday"] = -1 // ungültig

	req := httptest.NewRequest("POST", "/api/compare/presets", jsonBody(t, body))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "user1")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	// THEN: 400 Bad Request
	if w.Code != http.StatusBadRequest {
		t.Fatalf(
			"expected 400 Bad Request for weekly preset with weekday=-1, got %d: %s",
			w.Code, w.Body.String(),
		)
	}
}

func TestCreateComparePreset_WeeklyValidWeekday(t *testing.T) {
	// GIVEN: Create-Request für weekly-Preset mit weekday=4 (Freitag, gültig)
	s := newTestStore(t)
	r := chi.NewRouter()
	r.Post("/api/compare/presets", CreateComparePresetHandler(s))

	body := validPresetBody()
	body["schedule"] = "weekly"
	body["weekday"] = 4 // Freitag, gültig

	req := httptest.NewRequest("POST", "/api/compare/presets", jsonBody(t, body))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "user1")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	// THEN: 201 Created
	// Dieser Test ist auch aktuell rot, weil das Weekday-Feld im Modell fehlt
	// und somit das gespeicherte Preset weekday=0 enthält statt weekday=4.
	if w.Code != http.StatusCreated {
		t.Fatalf(
			"expected 201 Created for weekly preset with weekday=4, got %d: %s",
			w.Code, w.Body.String(),
		)
	}
	// Weekday muss im Response-Body korrekt reflektiert sein
	var resp map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("unmarshal response: %v", err)
	}
	weekdayVal, ok := resp["weekday"]
	if !ok {
		t.Fatal("expected 'weekday' field in response body — field missing in model (RED)")
	}
	if weekdayVal != float64(4) {
		t.Errorf("expected weekday=4 in response, got %v", weekdayVal)
	}
}

func TestUpdateComparePreset_WeeklyInvalidWeekday(t *testing.T) {
	// GIVEN: Existierendes Preset, Update-Request mit weekday=8 (ungültig)
	s := newTestStore(t)
	r := chi.NewRouter()
	r.Post("/api/compare/presets", CreateComparePresetHandler(s))
	r.Put("/api/compare/presets/{id}", UpdateComparePresetHandler(s))

	// Erst erstellen
	createBody := validPresetBody()
	createBody["schedule"] = "weekly"
	createBody["weekday"] = 4

	createReq := httptest.NewRequest("POST", "/api/compare/presets", jsonBody(t, createBody))
	createReq.Header.Set("Content-Type", "application/json")
	createReq = addUserToContext(createReq, "user1")
	createW := httptest.NewRecorder()
	r.ServeHTTP(createW, createReq)

	if createW.Code != http.StatusCreated {
		t.Skipf("Create failed (%d), skipping Update test", createW.Code)
	}

	var created map[string]interface{}
	json.Unmarshal(createW.Body.Bytes(), &created)
	presetID, _ := created["id"].(string)

	// Jetzt Update mit ungültigem weekday
	updateBody := validPresetBody()
	updateBody["schedule"] = "weekly"
	updateBody["weekday"] = 8 // ungültig

	updateReq := httptest.NewRequest(
		"PUT",
		"/api/compare/presets/"+presetID,
		jsonBody(t, updateBody),
	)
	updateReq.Header.Set("Content-Type", "application/json")
	updateReq = addUserToContext(updateReq, "user1")
	updateW := httptest.NewRecorder()
	r.ServeHTTP(updateW, updateReq)

	// THEN: 400 Bad Request
	if updateW.Code != http.StatusBadRequest {
		t.Fatalf(
			"expected 400 Bad Request for PUT weekly preset with weekday=8, got %d: %s",
			updateW.Code, updateW.Body.String(),
		)
	}
}
