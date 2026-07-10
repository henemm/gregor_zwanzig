package handler

// Issue #1041 Slice 1b — RadarAlertEnabled RMW-Merge (Datenverlust-Schutz,
// CLAUDE.md). Muster: compare_preset_hourly_enabled_test.go.
//
// Spec: docs/specs/modules/issue_1041b_compare_radar_alert_service.md

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/go-chi/chi/v5"

	"github.com/henemm/gregor-api/internal/model"
)

// PUT ohne radar_alert_enabled im Body darf das Feld NICHT auf nil/false
// zurücksetzen. Beweist Read-Modify-Write für RadarAlertEnabled im
// UpdateComparePresetHandler.
func TestUpdateComparePreset_RadarAlertEnabledPreservedWhenBodyOmitsIt(t *testing.T) {
	s := newTestStore(t)

	trueVal := true
	original := model.ComparePreset{
		ID:                "cp-radar-rwm-1",
		Name:              "Radar-Alarm-Test",
		UserID:            "user1",
		LocationIDs:       []string{"loc-a"},
		Schedule:          "manual",
		RadarAlertEnabled: &trueVal,
		Profil:            "SUMMER_TREKKING",
		HourFrom:          8,
		HourTo:            17,
		Empfaenger:        []string{"a@example.com"},
		CreatedAt:         time.Now().UTC(),
	}
	if err := s.WithUser("user1").SaveComparePresets([]model.ComparePreset{original}); err != nil {
		t.Fatalf("SaveComparePresets: %v", err)
	}

	// PUT-Body OHNE radar_alert_enabled (wie ein Client der das Feld nicht
	// kennt). Nur "name" wird geändert.
	body := map[string]interface{}{
		"name":         "Radar-Alarm-Test (umbenannt)",
		"schedule":     "manual",
		"profil":       "SUMMER_TREKKING",
		"hour_from":    8,
		"hour_to":      17,
		"location_ids": []string{"loc-a"},
		"empfaenger":   []string{"a@example.com"},
	}
	buf, _ := json.Marshal(body)

	r := chi.NewRouter()
	r.Put("/api/compare/presets/{id}", UpdateComparePresetHandler(s))
	req := httptest.NewRequest(http.MethodPut, "/api/compare/presets/cp-radar-rwm-1", bytes.NewReader(buf))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "user1")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	loaded, err := s.WithUser("user1").LoadComparePresets()
	if err != nil {
		t.Fatalf("LoadComparePresets: %v", err)
	}
	if len(loaded) != 1 {
		t.Fatalf("expected 1 preset, got %d", len(loaded))
	}
	if loaded[0].RadarAlertEnabled == nil || *loaded[0].RadarAlertEnabled != true {
		t.Errorf("RadarAlertEnabled erased by PUT without field: expected true, got %v", loaded[0].RadarAlertEnabled)
	}
	if loaded[0].Name != "Radar-Alarm-Test (umbenannt)" {
		t.Errorf("expected name to be updated to the new value, got %q", loaded[0].Name)
	}
}
