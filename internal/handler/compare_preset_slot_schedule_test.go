package handler

// TDD (inline): Issue #1232 Scheibe 2a — ComparePreset-Zeitplan-Reshape,
// PUT nil-Preserve, Validierung, POST-Defaults.
//
// Spec: docs/specs/modules/compare_preset_zeitplan.md (AC-1, AC-2, AC-9)

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

// AC-1: PUT ohne die 5 Slot-Felder im Body darf zuvor gesetzte Werte NICHT
// nullen (Read-Modify-Write, Datenverlust-Schutz).
func TestUpdateComparePreset_SlotFieldsPreservedWhenBodyOmitsThem(t *testing.T) {
	s := newTestStore(t)

	trueVal, falseVal := true, false
	morningTime, eveningTime, endDate := "07:30:00", "19:00:00", "2026-09-30"
	original := model.ComparePreset{
		ID:             "cp-slot-rwm-1",
		Name:           "Slot-RWM-Test",
		UserID:         "user1",
		LocationIDs:    []string{"loc-a"},
		Schedule:       "manual",
		Profil:         "SUMMER_TREKKING",
		HourFrom:       8,
		HourTo:         17,
		Empfaenger:     []string{"a@example.com"},
		CreatedAt:      time.Now().UTC(),
		MorningEnabled: &trueVal,
		MorningTime:    &morningTime,
		EveningEnabled: &falseVal,
		EveningTime:    &eveningTime,
		EndDate:        &endDate,
	}
	if err := s.WithUser("user1").SaveComparePresets([]model.ComparePreset{original}); err != nil {
		t.Fatalf("SaveComparePresets: %v", err)
	}

	// PUT-Body OHNE die 5 Slot-Felder — nur der Name wird geändert.
	body := map[string]interface{}{
		"name":         "Slot-RWM-Test (umbenannt)",
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
	req := httptest.NewRequest(http.MethodPut, "/api/compare/presets/cp-slot-rwm-1", bytes.NewReader(buf))
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
	p := loaded[0]
	if p.MorningEnabled == nil || !*p.MorningEnabled {
		t.Errorf("MorningEnabled erased by PUT without field: expected true, got %v", p.MorningEnabled)
	}
	if p.MorningTime == nil || *p.MorningTime != "07:30:00" {
		t.Errorf("MorningTime erased by PUT without field: expected 07:30:00, got %v", p.MorningTime)
	}
	if p.EveningEnabled == nil || *p.EveningEnabled {
		t.Errorf("EveningEnabled erased by PUT without field: expected false, got %v", p.EveningEnabled)
	}
	if p.EveningTime == nil || *p.EveningTime != "19:00:00" {
		t.Errorf("EveningTime erased by PUT without field: expected 19:00:00, got %v", p.EveningTime)
	}
	if p.EndDate == nil || *p.EndDate != "2026-09-30" {
		t.Errorf("EndDate erased by PUT without field: expected 2026-09-30, got %v", p.EndDate)
	}
	if p.Name != "Slot-RWM-Test (umbenannt)" {
		t.Errorf("expected name to be updated, got %q", p.Name)
	}
}

// AC-9: PUT mit ungueltigem Zeit-Format ("9:5") wird mit 400 abgelehnt und
// das Preset bleibt UNVERAENDERT auf der Platte (kein Teil-Persist).
func TestUpdateComparePreset_InvalidMorningTimeRejectedWithoutPersisting(t *testing.T) {
	s := newTestStore(t)

	trueVal, falseVal := true, false
	morningTime, eveningTime := "07:00:00", "18:00:00"
	original := model.ComparePreset{
		ID:             "cp-slot-invalid-1",
		Name:           "Invalid-Time-Test",
		UserID:         "user1",
		LocationIDs:    []string{"loc-a"},
		Schedule:       "manual",
		Profil:         "SUMMER_TREKKING",
		HourFrom:       8,
		HourTo:         17,
		Empfaenger:     []string{"a@example.com"},
		CreatedAt:      time.Now().UTC(),
		MorningEnabled: &trueVal,
		MorningTime:    &morningTime,
		EveningEnabled: &falseVal,
		EveningTime:    &eveningTime,
	}
	if err := s.WithUser("user1").SaveComparePresets([]model.ComparePreset{original}); err != nil {
		t.Fatalf("SaveComparePresets: %v", err)
	}

	body := map[string]interface{}{
		"name":         "Invalid-Time-Test",
		"schedule":     "manual",
		"profil":       "SUMMER_TREKKING",
		"hour_from":    8,
		"hour_to":      17,
		"location_ids": []string{"loc-a"},
		"empfaenger":   []string{"a@example.com"},
		"morning_time": "9:5",
	}
	buf, _ := json.Marshal(body)

	r := chi.NewRouter()
	r.Put("/api/compare/presets/{id}", UpdateComparePresetHandler(s))
	req := httptest.NewRequest(http.MethodPut, "/api/compare/presets/cp-slot-invalid-1", bytes.NewReader(buf))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "user1")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Fatalf("expected 400 for invalid morning_time, got %d: %s", w.Code, w.Body.String())
	}

	loaded, err := s.WithUser("user1").LoadComparePresets()
	if err != nil {
		t.Fatalf("LoadComparePresets: %v", err)
	}
	if loaded[0].MorningTime == nil || *loaded[0].MorningTime != "07:00:00" {
		t.Errorf("preset must stay unchanged after rejected PUT, expected morning_time=07:00:00, got %v", loaded[0].MorningTime)
	}
	if loaded[0].Name != "Invalid-Time-Test" {
		t.Errorf("preset must stay unchanged after rejected PUT, name changed to %q", loaded[0].Name)
	}
}

// AC-9: PUT mit ungueltigem end_date ("31-09-2026") wird mit 400 abgelehnt.
func TestUpdateComparePreset_InvalidEndDateRejectedWithoutPersisting(t *testing.T) {
	s := newTestStore(t)

	original := model.ComparePreset{
		ID:          "cp-slot-invalid-date-1",
		Name:        "Invalid-Date-Test",
		UserID:      "user1",
		LocationIDs: []string{"loc-a"},
		Schedule:    "manual",
		Profil:      "SUMMER_TREKKING",
		HourFrom:    8,
		HourTo:      17,
		Empfaenger:  []string{"a@example.com"},
		CreatedAt:   time.Now().UTC(),
	}
	if err := s.WithUser("user1").SaveComparePresets([]model.ComparePreset{original}); err != nil {
		t.Fatalf("SaveComparePresets: %v", err)
	}

	body := map[string]interface{}{
		"name":         "Invalid-Date-Test",
		"schedule":     "manual",
		"profil":       "SUMMER_TREKKING",
		"hour_from":    8,
		"hour_to":      17,
		"location_ids": []string{"loc-a"},
		"empfaenger":   []string{"a@example.com"},
		"end_date":     "31-09-2026",
	}
	buf, _ := json.Marshal(body)

	r := chi.NewRouter()
	r.Put("/api/compare/presets/{id}", UpdateComparePresetHandler(s))
	req := httptest.NewRequest(http.MethodPut, "/api/compare/presets/cp-slot-invalid-date-1", bytes.NewReader(buf))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "user1")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Fatalf("expected 400 for invalid end_date, got %d: %s", w.Code, w.Body.String())
	}
}

// AC-2: POST ohne Slot-Felder bekommt die Neu-Preset-Defaults (Morgen an
// @07:00, Abend aus @18:00, unbegrenzte Laufzeit).
func TestCreateComparePreset_DefaultsSlotFieldsWhenOmitted(t *testing.T) {
	s := newTestStore(t)

	body := map[string]interface{}{
		"name":         "Neues Preset ohne Slots",
		"schedule":     "manual",
		"profil":       "SUMMER_TREKKING",
		"hour_from":    9,
		"hour_to":      16,
		"location_ids": []string{"loc-a"},
		"empfaenger":   []string{"a@example.com"},
	}
	buf, _ := json.Marshal(body)

	r := chi.NewRouter()
	r.Post("/api/compare/presets", CreateComparePresetHandler(s))
	req := httptest.NewRequest(http.MethodPost, "/api/compare/presets", bytes.NewReader(buf))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "user1")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusCreated {
		t.Fatalf("expected 201, got %d: %s", w.Code, w.Body.String())
	}

	var created model.ComparePreset
	if err := json.Unmarshal(w.Body.Bytes(), &created); err != nil {
		t.Fatalf("unmarshal response: %v", err)
	}

	if created.MorningEnabled == nil || !*created.MorningEnabled {
		t.Errorf("expected new preset MorningEnabled=true, got %v", created.MorningEnabled)
	}
	if created.MorningTime == nil || *created.MorningTime != "07:00:00" {
		t.Errorf("expected new preset MorningTime=07:00:00, got %v", created.MorningTime)
	}
	if created.EveningEnabled == nil || *created.EveningEnabled {
		t.Errorf("expected new preset EveningEnabled=false, got %v", created.EveningEnabled)
	}
	if created.EveningTime == nil || *created.EveningTime != "18:00:00" {
		t.Errorf("expected new preset EveningTime=18:00:00, got %v", created.EveningTime)
	}
	if created.EndDate != nil {
		t.Errorf("expected new preset EndDate=nil (unbegrenzt), got %v", *created.EndDate)
	}
}

// Mandanten-Pflicht (CLAUDE.md): Ein abgelehntes PUT von Nutzer A darf Nutzer
// B's unabhaengiges Preset nicht beruehren.
func TestUpdateComparePreset_RejectedInvalidTimeDoesNotAffectOtherUser(t *testing.T) {
	s := newTestStore(t)

	morningA := "07:00:00"
	presetA := model.ComparePreset{
		ID:          "cp-slot-usera",
		Name:        "Nutzer A",
		UserID:      "usera",
		LocationIDs: []string{"loc-a"},
		Schedule:    "manual",
		Profil:      "SUMMER_TREKKING",
		HourFrom:    8,
		HourTo:      17,
		Empfaenger:  []string{"a@example.com"},
		CreatedAt:   time.Now().UTC(),
		MorningTime: &morningA,
	}
	morningB := "08:00:00"
	presetB := model.ComparePreset{
		ID:          "cp-slot-userb",
		Name:        "Nutzer B",
		UserID:      "userb",
		LocationIDs: []string{"loc-b"},
		Schedule:    "manual",
		Profil:      "SUMMER_TREKKING",
		HourFrom:    9,
		HourTo:      16,
		Empfaenger:  []string{"b@example.com"},
		CreatedAt:   time.Now().UTC(),
		MorningTime: &morningB,
	}
	if err := s.WithUser("usera").SaveComparePresets([]model.ComparePreset{presetA}); err != nil {
		t.Fatalf("SaveComparePresets usera: %v", err)
	}
	if err := s.WithUser("userb").SaveComparePresets([]model.ComparePreset{presetB}); err != nil {
		t.Fatalf("SaveComparePresets userb: %v", err)
	}

	body := map[string]interface{}{
		"name":         "Nutzer A",
		"schedule":     "manual",
		"profil":       "SUMMER_TREKKING",
		"hour_from":    8,
		"hour_to":      17,
		"location_ids": []string{"loc-a"},
		"empfaenger":   []string{"a@example.com"},
		"morning_time": "not-a-time",
	}
	buf, _ := json.Marshal(body)

	r := chi.NewRouter()
	r.Put("/api/compare/presets/{id}", UpdateComparePresetHandler(s))
	req := httptest.NewRequest(http.MethodPut, "/api/compare/presets/cp-slot-usera", bytes.NewReader(buf))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "usera")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Fatalf("expected 400, got %d: %s", w.Code, w.Body.String())
	}

	loadedB, err := s.WithUser("userb").LoadComparePresets()
	if err != nil {
		t.Fatalf("LoadComparePresets userb: %v", err)
	}
	if loadedB[0].MorningTime == nil || *loadedB[0].MorningTime != "08:00:00" {
		t.Errorf("cross-user leak: userb's MorningTime changed, expected 08:00:00, got %v", loadedB[0].MorningTime)
	}
}
