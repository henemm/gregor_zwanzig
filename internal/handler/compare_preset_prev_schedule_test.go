package handler

// TDD RED — Issue #631: Wochen-Rhythmus beim Reaktivieren erhalten.
//
// Spec: docs/specs/modules/issue_627_631_compare_send_rhythm.md (AC-8)
//
// SOLL-Verhalten nach Fix:
//   - model.ComparePreset bekommt ein additives Feld PreviousSchedule
//     (`json:"previous_schedule,omitempty"`), das den vorherigen Rhythmus
//     (z.B. "weekly") über ein Pausieren hinweg konserviert.
//   - Store-Roundtrip: speichern → laden erhält das Feld.
//   - Altdaten OHNE previous_schedule laden fehlerfrei ("" als Default),
//     alle anderen Felder bleiben unverändert (kein Datenverlust).
//
// RED-Erwartung (vor Fix): COMPILE-FEHLER, weil model.ComparePreset.PreviousSchedule
//   noch nicht existiert. Ein Compile-Fehler zählt als gültiges RED.

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/go-chi/chi/v5"

	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

// AC-8: PreviousSchedule überlebt einen Store-Roundtrip (save → load).
func TestComparePreset_PreviousScheduleRoundtrip(t *testing.T) {
	tmpDir := t.TempDir()
	s := store.New(tmpDir, "user1")

	weekday := 4
	original := model.ComparePreset{
		ID:               "cp-weekly-1",
		Name:             "Wöchentlicher Vergleich",
		UserID:           "user1",
		LocationIDs:      []string{"loc-a", "loc-b"},
		Schedule:         "manual",
		PreviousSchedule: "weekly", // RED: Feld existiert im Modell noch nicht
		Profil:           "SUMMER_TREKKING",
		HourFrom:         9,
		HourTo:           16,
		Weekday:          &weekday,
		Empfaenger:       []string{"a@example.com"},
	}

	if err := s.SaveComparePresets([]model.ComparePreset{original}); err != nil {
		t.Fatalf("SaveComparePresets: %v", err)
	}

	loaded, err := s.LoadComparePresets()
	if err != nil {
		t.Fatalf("LoadComparePresets: %v", err)
	}
	if len(loaded) != 1 {
		t.Fatalf("expected 1 preset, got %d", len(loaded))
	}
	if loaded[0].PreviousSchedule != "weekly" {
		t.Errorf("expected PreviousSchedule='weekly' to survive roundtrip, got %q", loaded[0].PreviousSchedule)
	}
	if loaded[0].Schedule != "manual" {
		t.Errorf("expected Schedule='manual' preserved, got %q", loaded[0].Schedule)
	}
}

// AC-8: Altdaten-JSON OHNE previous_schedule-Feld laden fehlerfrei; alle anderen
// Felder bleiben intakt (additives Feld → "" Default, kein Datenverlust).
func TestComparePreset_LegacyWithoutPreviousScheduleLoads(t *testing.T) {
	tmpDir := t.TempDir()
	s := store.New(tmpDir, "user1")

	// Direktes Alt-JSON ohne previous_schedule-Feld.
	rawJSON := `[{
		"id": "cp-legacy",
		"name": "Legacy Preset",
		"user_id": "user1",
		"location_ids": ["loc-a", "loc-b"],
		"schedule": "weekly",
		"weekday": 2,
		"profil": "SUMMER_TREKKING",
		"hour_from": 8,
		"hour_to": 17,
		"empfaenger": ["x@example.com", "y@example.com"],
		"created_at": "2026-01-01T00:00:00Z"
	}]`

	writeComparePresetBriefingFixture(t, tmpDir, "user1", rawJSON)

	loaded, err := s.LoadComparePresets()
	if err != nil {
		t.Fatalf("LoadComparePresets on legacy data: %v", err)
	}
	if len(loaded) != 1 {
		t.Fatalf("expected 1 preset, got %d", len(loaded))
	}
	p := loaded[0]
	// previous_schedule fehlte → "" (kein Fehler, additiv)
	if p.PreviousSchedule != "" {
		t.Errorf("expected empty PreviousSchedule for legacy data, got %q", p.PreviousSchedule)
	}
	// Alle anderen Felder unverändert
	if p.Schedule != "weekly" {
		t.Errorf("expected Schedule='weekly' preserved, got %q", p.Schedule)
	}
	if p.Weekday == nil || *p.Weekday != 2 {
		t.Errorf("expected Weekday=2 preserved on legacy load")
	}
	if len(p.Empfaenger) != 2 {
		t.Errorf("expected 2 empfaenger preserved, got %d", len(p.Empfaenger))
	}
	if len(p.LocationIDs) != 2 {
		t.Errorf("expected 2 location_ids preserved, got %d", len(p.LocationIDs))
	}
}

// F001 Fix: PUT ohne previous_schedule im Body darf das Feld NICHT auf "" zurücksetzen.
// Beweist Read-Modify-Write für PreviousSchedule im UpdateComparePresetHandler.
func TestUpdateComparePreset_PreviousSchedulePreservedWhenBodyOmitsIt(t *testing.T) {
	s := newTestStore(t)

	// Preset anlegen mit PreviousSchedule="weekly".
	weekday := 4
	original := model.ComparePreset{
		ID:               "cp-rwm-1",
		Name:             "Rhythmus-Test",
		UserID:           "user1",
		LocationIDs:      []string{"loc-a"},
		Schedule:         "manual",
		PreviousSchedule: "weekly",
		Profil:           "SUMMER_TREKKING",
		HourFrom:         8,
		HourTo:           17,
		Weekday:          &weekday,
		Empfaenger:       []string{"a@example.com"},
		CreatedAt:        time.Now().UTC(),
	}
	if err := s.WithUser("user1").SaveComparePresets([]model.ComparePreset{original}); err != nil {
		t.Fatalf("SaveComparePresets: %v", err)
	}

	// PUT-Body OHNE previous_schedule (wie ein Client der das Feld nicht kennt).
	body := map[string]interface{}{
		"name":         "Rhythmus-Test",
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
	req := httptest.NewRequest(http.MethodPut, "/api/compare/presets/cp-rwm-1", bytes.NewReader(buf))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "user1")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	// PreviousSchedule muss erhalten bleiben.
	loaded, err := s.WithUser("user1").LoadComparePresets()
	if err != nil {
		t.Fatalf("LoadComparePresets: %v", err)
	}
	if len(loaded) != 1 {
		t.Fatalf("expected 1 preset, got %d", len(loaded))
	}
	if loaded[0].PreviousSchedule != "weekly" {
		t.Errorf("PreviousSchedule erased by PUT without field: expected 'weekly', got %q", loaded[0].PreviousSchedule)
	}
}

// F001 Fix: PUT MIT previous_schedule="daily" setzt den Wert (Client-Wert gewinnt wenn gesetzt).
func TestUpdateComparePreset_PreviousScheduleUpdatedWhenBodySetsIt(t *testing.T) {
	s := newTestStore(t)

	weekday := 4
	original := model.ComparePreset{
		ID:               "cp-rwm-2",
		Name:             "Rhythmus-Update",
		UserID:           "user1",
		LocationIDs:      []string{"loc-b"},
		Schedule:         "manual",
		PreviousSchedule: "weekly",
		Profil:           "SUMMER_TREKKING",
		HourFrom:         9,
		HourTo:           16,
		Weekday:          &weekday,
		Empfaenger:       []string{"b@example.com"},
		CreatedAt:        time.Now().UTC(),
	}
	if err := s.WithUser("user1").SaveComparePresets([]model.ComparePreset{original}); err != nil {
		t.Fatalf("SaveComparePresets: %v", err)
	}

	// PUT-Body MIT previous_schedule="daily".
	body := map[string]interface{}{
		"name":              "Rhythmus-Update",
		"schedule":          "manual",
		"previous_schedule": "daily",
		"profil":            "SUMMER_TREKKING",
		"hour_from":         9,
		"hour_to":           16,
		"location_ids":      []string{"loc-b"},
		"empfaenger":        []string{"b@example.com"},
	}
	buf, _ := json.Marshal(body)

	r := chi.NewRouter()
	r.Put("/api/compare/presets/{id}", UpdateComparePresetHandler(s))
	req := httptest.NewRequest(http.MethodPut, "/api/compare/presets/cp-rwm-2", bytes.NewReader(buf))
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
	if loaded[0].PreviousSchedule != "daily" {
		t.Errorf("expected PreviousSchedule='daily' from PUT body, got %q", loaded[0].PreviousSchedule)
	}
}
