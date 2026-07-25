package handler

// Issue #1361/#1372 S1b — gemeinsames Tagesfenster fuer Trip und Ortsvergleich.
//
// Spec: docs/specs/modules/compare_shared_day_window.md (AC-1, AC-2, AC-8)
//
// model.ComparePreset bekommt additive Pointer-Felder DayWindowStartHour/
// DayWindowEndHour (analog HourlyEnabled *bool): fehlen sie im JSON (Altdaten),
// decodiert Go zu nil -> Python-Default 4/19 beim naechsten Lesen. Ein
// ungueltiges Paar (ausserhalb 0-23, start>=end) wird am Schreib-Seam UND beim
// Laden geklemmt (ClampComparePresetDayWindow, analog ClampReportConfigDayWindow
// beim Trip).

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

// Ein gueltiges Tagesfenster ueberlebt einen Store-Roundtrip (save → load).
func TestComparePreset_DayWindowRoundtrip(t *testing.T) {
	tmpDir := t.TempDir()
	s := store.New(tmpDir, "user1")

	start, end := 6, 20
	original := model.ComparePreset{
		ID:                 "cp-daywindow-1",
		Name:               "Vergleich mit Tagesfenster",
		UserID:             "user1",
		LocationIDs:        []string{"loc-a", "loc-b"},
		Schedule:           "manual",
		DayWindowStartHour: &start,
		DayWindowEndHour:   &end,
		Profil:             "SUMMER_TREKKING",
		Empfaenger:         []string{"a@example.com"},
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
	if loaded[0].DayWindowStartHour == nil || *loaded[0].DayWindowStartHour != 6 {
		t.Errorf("expected DayWindowStartHour=6 to survive roundtrip, got %v", loaded[0].DayWindowStartHour)
	}
	if loaded[0].DayWindowEndHour == nil || *loaded[0].DayWindowEndHour != 20 {
		t.Errorf("expected DayWindowEndHour=20 to survive roundtrip, got %v", loaded[0].DayWindowEndHour)
	}
}

// Altdaten-JSON OHNE day_window_*-Felder laden fehlerfrei zu nil (kein
// Absturz, kein Zero-Value 0).
func TestComparePreset_LegacyWithoutDayWindowLoads(t *testing.T) {
	tmpDir := t.TempDir()
	s := store.New(tmpDir, "user1")

	rawJSON := `[{
		"id": "cp-legacy-daywindow",
		"name": "Legacy Preset",
		"user_id": "user1",
		"location_ids": ["loc-a"],
		"schedule": "weekly",
		"weekday": 2,
		"profil": "SUMMER_TREKKING",
		"hour_from": 8,
		"hour_to": 17,
		"empfaenger": ["x@example.com"],
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
	if p.DayWindowStartHour != nil || p.DayWindowEndHour != nil {
		t.Errorf("expected nil DayWindow*Hour for legacy data, got start=%v end=%v", p.DayWindowStartHour, p.DayWindowEndHour)
	}
	// hour_from/hour_to bleiben unangetastete Persistenz (Bestandswahrung).
	if p.HourFrom != 8 || p.HourTo != 17 {
		t.Errorf("expected hour_from/hour_to preserved as legacy data, got %d/%d", p.HourFrom, p.HourTo)
	}
}

// Ein ungueltiges Paar (start >= end) wird beim Create auf nil geklemmt statt
// gespeichert -- Defense-in-Depth, analog ClampReportConfigDayWindow.
func TestCreateComparePreset_ClampsInvalidDayWindowPair(t *testing.T) {
	s := newTestStore(t)

	body := map[string]interface{}{
		"name":                  "Ungueltiges Fenster",
		"schedule":              "manual",
		"profil":                "SUMMER_TREKKING",
		"location_ids":          []string{"loc-a"},
		"empfaenger":            []string{"a@example.com"},
		"day_window_start_hour": 19,
		"day_window_end_hour":   19,
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

	var resp model.ComparePreset
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if resp.DayWindowStartHour != nil || resp.DayWindowEndHour != nil {
		t.Errorf("expected invalid pair (19,19) clamped to nil in response, got start=%v end=%v", resp.DayWindowStartHour, resp.DayWindowEndHour)
	}

	loaded, err := s.WithUser("user1").LoadComparePresets()
	if err != nil {
		t.Fatalf("LoadComparePresets: %v", err)
	}
	if len(loaded) != 1 {
		t.Fatalf("expected 1 preset, got %d", len(loaded))
	}
	if loaded[0].DayWindowStartHour != nil || loaded[0].DayWindowEndHour != nil {
		t.Errorf("expected invalid pair clamped to nil on disk, got start=%v end=%v", loaded[0].DayWindowStartHour, loaded[0].DayWindowEndHour)
	}
}

// PUT ohne day_window_* im Body darf ein zuvor gesetztes Fenster NICHT
// loeschen (Read-Modify-Write, Datenerhalt CLAUDE.md).
func TestUpdateComparePreset_DayWindowPreservedWhenBodyOmitsIt(t *testing.T) {
	s := newTestStore(t)

	start, end := 6, 20
	original := model.ComparePreset{
		ID:                 "cp-daywindow-rmw-1",
		Name:               "Tagesfenster-Test",
		UserID:             "user1",
		LocationIDs:        []string{"loc-a"},
		Schedule:           "manual",
		DayWindowStartHour: &start,
		DayWindowEndHour:   &end,
		Profil:             "SUMMER_TREKKING",
		Empfaenger:         []string{"a@example.com"},
		CreatedAt:          time.Now().UTC(),
	}
	if err := s.WithUser("user1").SaveComparePresets([]model.ComparePreset{original}); err != nil {
		t.Fatalf("SaveComparePresets: %v", err)
	}

	// PUT-Body OHNE day_window_start_hour/_end_hour (wie ein Client der die
	// Felder nicht kennt). Nur "name" wird geaendert.
	body := map[string]interface{}{
		"name":         "Tagesfenster-Test (umbenannt)",
		"schedule":     "manual",
		"profil":       "SUMMER_TREKKING",
		"location_ids": []string{"loc-a"},
		"empfaenger":   []string{"a@example.com"},
	}
	buf, _ := json.Marshal(body)

	r := chi.NewRouter()
	r.Put("/api/compare/presets/{id}", UpdateComparePresetHandler(s))
	req := httptest.NewRequest(http.MethodPut, "/api/compare/presets/cp-daywindow-rmw-1", bytes.NewReader(buf))
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
	if loaded[0].DayWindowStartHour == nil || *loaded[0].DayWindowStartHour != 6 {
		t.Errorf("DayWindowStartHour erased by PUT without field: expected 6, got %v", loaded[0].DayWindowStartHour)
	}
	if loaded[0].DayWindowEndHour == nil || *loaded[0].DayWindowEndHour != 20 {
		t.Errorf("DayWindowEndHour erased by PUT without field: expected 20, got %v", loaded[0].DayWindowEndHour)
	}
	if loaded[0].Name != "Tagesfenster-Test (umbenannt)" {
		t.Errorf("expected name to be updated to the new value, got %q", loaded[0].Name)
	}
}

// Ein explizit gesendetes ungueltiges Paar (start == end) wird beim Update
// geklemmt (nicht der erhaltene Alt-Wert der RMW-Preserve-Logik).
//
// Issue #1361/#1372 S1b (PO-Entscheidung 2026-07-25): der bisherige
// Repro-Fall (22,3) ist seit dieser Scheibe ein GUELTIGES Mitternachts-
// Fenster -- wandert daher zu start==end. Der Mitternachts-Fall wird in
// TestUpdateComparePreset_KeepsExplicitValidWrapDayWindowPair separat bewiesen.
func TestUpdateComparePreset_ClampsExplicitInvalidDayWindowPair(t *testing.T) {
	s := newTestStore(t)

	start, end := 6, 20
	original := model.ComparePreset{
		ID:                 "cp-daywindow-invalid-1",
		Name:               "Tagesfenster-Invalid-Test",
		UserID:             "user1",
		LocationIDs:        []string{"loc-a"},
		Schedule:           "manual",
		DayWindowStartHour: &start,
		DayWindowEndHour:   &end,
		Profil:             "SUMMER_TREKKING",
		Empfaenger:         []string{"a@example.com"},
		CreatedAt:          time.Now().UTC(),
	}
	if err := s.WithUser("user1").SaveComparePresets([]model.ComparePreset{original}); err != nil {
		t.Fatalf("SaveComparePresets: %v", err)
	}

	body := map[string]interface{}{
		"name":                  "Tagesfenster-Invalid-Test",
		"schedule":              "manual",
		"profil":                "SUMMER_TREKKING",
		"location_ids":          []string{"loc-a"},
		"empfaenger":            []string{"a@example.com"},
		"day_window_start_hour": 22,
		"day_window_end_hour":   22,
	}
	buf, _ := json.Marshal(body)

	r := chi.NewRouter()
	r.Put("/api/compare/presets/{id}", UpdateComparePresetHandler(s))
	req := httptest.NewRequest(http.MethodPut, "/api/compare/presets/cp-daywindow-invalid-1", bytes.NewReader(buf))
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
	if loaded[0].DayWindowStartHour != nil || loaded[0].DayWindowEndHour != nil {
		t.Errorf("expected invalid pair (22,22) clamped to nil, got start=%v end=%v", loaded[0].DayWindowStartHour, loaded[0].DayWindowEndHour)
	}
}

// Issue #1361/#1372 S1b (AC-3, PO-Entscheidung 2026-07-25): ein explizit
// gesendetes Mitternachts-Fenster (22,3) ist GUELTIG und darf beim Update
// nicht geklemmt werden.
func TestUpdateComparePreset_KeepsExplicitValidWrapDayWindowPair(t *testing.T) {
	s := newTestStore(t)

	start, end := 6, 20
	original := model.ComparePreset{
		ID:                 "cp-daywindow-wrap-1",
		Name:               "Tagesfenster-Wrap-Test",
		UserID:             "user1",
		LocationIDs:        []string{"loc-a"},
		Schedule:           "manual",
		DayWindowStartHour: &start,
		DayWindowEndHour:   &end,
		Profil:             "SUMMER_TREKKING",
		Empfaenger:         []string{"a@example.com"},
		CreatedAt:          time.Now().UTC(),
	}
	if err := s.WithUser("user1").SaveComparePresets([]model.ComparePreset{original}); err != nil {
		t.Fatalf("SaveComparePresets: %v", err)
	}

	body := map[string]interface{}{
		"name":                  "Tagesfenster-Wrap-Test",
		"schedule":              "manual",
		"profil":                "SUMMER_TREKKING",
		"location_ids":          []string{"loc-a"},
		"empfaenger":            []string{"a@example.com"},
		"day_window_start_hour": 22,
		"day_window_end_hour":   3,
	}
	buf, _ := json.Marshal(body)

	r := chi.NewRouter()
	r.Put("/api/compare/presets/{id}", UpdateComparePresetHandler(s))
	req := httptest.NewRequest(http.MethodPut, "/api/compare/presets/cp-daywindow-wrap-1", bytes.NewReader(buf))
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
	if loaded[0].DayWindowStartHour == nil || *loaded[0].DayWindowStartHour != 22 {
		t.Errorf("Mitternachts-Fenster darf nicht geklemmt werden, expected start=22, got %v", loaded[0].DayWindowStartHour)
	}
	if loaded[0].DayWindowEndHour == nil || *loaded[0].DayWindowEndHour != 3 {
		t.Errorf("Mitternachts-Fenster darf nicht geklemmt werden, expected end=3, got %v", loaded[0].DayWindowEndHour)
	}
}
