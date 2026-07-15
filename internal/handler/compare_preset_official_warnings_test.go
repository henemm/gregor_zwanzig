package handler

// Issue #1258 Scheibe S1 (AC-4/AC-5) — official_warnings-Pointer-Feld auf
// ComparePreset: Neuanlage-Default via POST, Read-Modify-Write-Preserve via
// PUT (Datenverlust-Schutz BUG-DATALOSS-GR221), Zwei-Nutzer-Isolation
// (CLAUDE.md Multi-User-Pflicht).
//
// Spec: docs/specs/modules/issue_1258_alarme_tab_official_warnings.md AC-4/AC-5.

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

// AC-4: POST /api/compare/presets ohne official_warnings im Body setzt
// enabled=false (bewusster Verhaltenswechsel NUR fuer Neuanlagen).
func TestCreateComparePresetHandler_OfficialWarningsDefaultsDisabled(t *testing.T) {
	s := newTestStore(t)

	body := map[string]interface{}{
		"name":         "Neuanlage",
		"schedule":     "manual",
		"profil":       "SUMMER_TREKKING",
		"hour_from":    8,
		"hour_to":      17,
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

	var resp model.ComparePreset
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if resp.OfficialWarnings == nil || resp.OfficialWarnings.Enabled != false {
		t.Fatalf("expected official_warnings.enabled=false in response, got %+v", resp.OfficialWarnings)
	}

	loaded, err := s.WithUser("user1").LoadComparePresets()
	if err != nil {
		t.Fatalf("LoadComparePresets: %v", err)
	}
	if len(loaded) != 1 {
		t.Fatalf("expected 1 preset, got %d", len(loaded))
	}
	if loaded[0].OfficialWarnings == nil || loaded[0].OfficialWarnings.Enabled != false {
		t.Fatalf("expected persisted official_warnings.enabled=false, got %+v", loaded[0].OfficialWarnings)
	}
}

// RMW-Preserve: PUT ohne official_warnings im Body darf einen zuvor
// gesetzten Wert nicht auf den Default zuruecksetzen (BUG-DATALOSS-GR221).
func TestUpdateComparePreset_OfficialWarningsPreservedWhenBodyOmitsIt(t *testing.T) {
	s := newTestStore(t)

	original := model.ComparePreset{
		ID:               "cp-1258-rmw",
		Name:             "RMW-Test",
		UserID:           "user1",
		LocationIDs:      []string{"loc-a"},
		Schedule:         "manual",
		Profil:           "SUMMER_TREKKING",
		HourFrom:         8,
		HourTo:           17,
		Empfaenger:       []string{"a@example.com"},
		OfficialWarnings: &model.OfficialWarningsConfig{Enabled: true, Sources: []string{"geosphere_warn"}},
		CreatedAt:        time.Now().UTC(),
	}
	if err := s.WithUser("user1").SaveComparePresets([]model.ComparePreset{original}); err != nil {
		t.Fatalf("SaveComparePresets: %v", err)
	}

	// PUT-Body OHNE official_warnings — nur "name" geaendert.
	body := map[string]interface{}{
		"name":         "RMW-Test (umbenannt)",
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
	req := httptest.NewRequest(http.MethodPut, "/api/compare/presets/cp-1258-rmw", bytes.NewReader(buf))
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
	if p.OfficialWarnings == nil || p.OfficialWarnings.Enabled != true ||
		len(p.OfficialWarnings.Sources) != 1 || p.OfficialWarnings.Sources[0] != "geosphere_warn" {
		t.Errorf("official_warnings erased by PUT without field: expected {enabled:true, sources:[geosphere_warn]}, got %+v", p.OfficialWarnings)
	}
	if p.Name != "RMW-Test (umbenannt)" {
		t.Errorf("expected name updated, got %q", p.Name)
	}
}

// AC-5: Nutzer A aendert official_warnings seines Presets — Nutzer B's
// gleichartiges Preset bleibt unveraendert (Isolation ueber user_id, kein
// Cross-User-Leck, PFLICHT-Test lt. CLAUDE.md).
func TestUpdateComparePreset_OfficialWarningsCrossUserIsolation(t *testing.T) {
	s := newTestStore(t)

	presetA := model.ComparePreset{
		ID:               "cp-1258-usera",
		Name:             "Nutzer A",
		UserID:           "usera",
		LocationIDs:      []string{"loc-a"},
		Schedule:         "manual",
		Profil:           "SUMMER_TREKKING",
		HourFrom:         8,
		HourTo:           17,
		Empfaenger:       []string{"a@example.com"},
		OfficialWarnings: &model.OfficialWarningsConfig{Enabled: true},
		CreatedAt:        time.Now().UTC(),
	}
	presetB := model.ComparePreset{
		ID:               "cp-1258-userb",
		Name:             "Nutzer B",
		UserID:           "userb",
		LocationIDs:      []string{"loc-b"},
		Schedule:         "manual",
		Profil:           "SUMMER_TREKKING",
		HourFrom:         9,
		HourTo:           16,
		Empfaenger:       []string{"b@example.com"},
		OfficialWarnings: &model.OfficialWarningsConfig{Enabled: false},
		CreatedAt:        time.Now().UTC(),
	}
	if err := s.WithUser("usera").SaveComparePresets([]model.ComparePreset{presetA}); err != nil {
		t.Fatalf("SaveComparePresets usera: %v", err)
	}
	if err := s.WithUser("userb").SaveComparePresets([]model.ComparePreset{presetB}); err != nil {
		t.Fatalf("SaveComparePresets userb: %v", err)
	}

	body := map[string]interface{}{
		"name":              "Nutzer A (geaendert)",
		"schedule":          "manual",
		"profil":            "SUMMER_TREKKING",
		"hour_from":         8,
		"hour_to":           17,
		"location_ids":      []string{"loc-a"},
		"empfaenger":        []string{"a@example.com"},
		"official_warnings": map[string]interface{}{"enabled": false},
	}
	buf, _ := json.Marshal(body)

	r := chi.NewRouter()
	r.Put("/api/compare/presets/{id}", UpdateComparePresetHandler(s))
	req := httptest.NewRequest(http.MethodPut, "/api/compare/presets/cp-1258-usera", bytes.NewReader(buf))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "usera")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	loadedA, err := s.WithUser("usera").LoadComparePresets()
	if err != nil {
		t.Fatalf("LoadComparePresets usera: %v", err)
	}
	if loadedA[0].OfficialWarnings == nil || loadedA[0].OfficialWarnings.Enabled != false {
		t.Errorf("expected usera official_warnings.enabled=false after PUT, got %+v", loadedA[0].OfficialWarnings)
	}

	loadedB, err := s.WithUser("userb").LoadComparePresets()
	if err != nil {
		t.Fatalf("LoadComparePresets userb: %v", err)
	}
	if loadedB[0].Name != "Nutzer B" {
		t.Errorf("cross-user leak: userb's preset name changed to %q", loadedB[0].Name)
	}
	if loadedB[0].OfficialWarnings == nil || loadedB[0].OfficialWarnings.Enabled != false {
		t.Errorf("userb's official_warnings unexpectedly changed, expected enabled=false (unveraendert seit Anlage), got %+v", loadedB[0].OfficialWarnings)
	}
}

// Fix-Loop F002: PUT mit official_warnings={"enabled":false} OHNE "sources"
// darf zuvor gesetzte Sources nicht loeschen — RMW griff bisher nur auf
// Objekt-Ebene, nicht auf Feld-Ebene innerhalb official_warnings.
func TestUpdateComparePreset_OfficialWarningsEnabledOnlyPreservesSources(t *testing.T) {
	s := newTestStore(t)

	original := model.ComparePreset{
		ID:               "cp-1258-f002-preserve",
		Name:             "F002-Preserve-Test",
		UserID:           "user1",
		LocationIDs:      []string{"loc-a"},
		Schedule:         "manual",
		Profil:           "SUMMER_TREKKING",
		HourFrom:         8,
		HourTo:           17,
		Empfaenger:       []string{"a@example.com"},
		OfficialWarnings: &model.OfficialWarningsConfig{Enabled: true, Sources: []string{"geosphere_warn"}},
		CreatedAt:        time.Now().UTC(),
	}
	if err := s.WithUser("user1").SaveComparePresets([]model.ComparePreset{original}); err != nil {
		t.Fatalf("SaveComparePresets: %v", err)
	}

	// PUT setzt nur enabled:false, "sources" fehlt im Body komplett.
	body := map[string]interface{}{
		"name":              "F002-Preserve-Test",
		"schedule":          "manual",
		"profil":            "SUMMER_TREKKING",
		"hour_from":         8,
		"hour_to":           17,
		"location_ids":      []string{"loc-a"},
		"empfaenger":        []string{"a@example.com"},
		"official_warnings": map[string]interface{}{"enabled": false},
	}
	buf, _ := json.Marshal(body)

	r := chi.NewRouter()
	r.Put("/api/compare/presets/{id}", UpdateComparePresetHandler(s))
	req := httptest.NewRequest(http.MethodPut, "/api/compare/presets/cp-1258-f002-preserve", bytes.NewReader(buf))
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
	if p.OfficialWarnings == nil || p.OfficialWarnings.Enabled != false {
		t.Fatalf("expected enabled=false applied, got %+v", p.OfficialWarnings)
	}
	if len(p.OfficialWarnings.Sources) != 1 || p.OfficialWarnings.Sources[0] != "geosphere_warn" {
		t.Errorf("F002: sources erased by enabled-only PUT, expected [geosphere_warn], got %+v", p.OfficialWarnings.Sources)
	}
}

// Gegenprobe zu F002: ein PUT mit explizit leerem "sources":[] MUSS weiterhin
// leeren — nur das komplette Fehlen des Keys bedeutet "unveraendert".
func TestUpdateComparePreset_OfficialWarningsExplicitEmptySourcesClears(t *testing.T) {
	s := newTestStore(t)

	original := model.ComparePreset{
		ID:               "cp-1258-f002-clear",
		Name:             "F002-Clear-Test",
		UserID:           "user1",
		LocationIDs:      []string{"loc-a"},
		Schedule:         "manual",
		Profil:           "SUMMER_TREKKING",
		HourFrom:         8,
		HourTo:           17,
		Empfaenger:       []string{"a@example.com"},
		OfficialWarnings: &model.OfficialWarningsConfig{Enabled: true, Sources: []string{"geosphere_warn"}},
		CreatedAt:        time.Now().UTC(),
	}
	if err := s.WithUser("user1").SaveComparePresets([]model.ComparePreset{original}); err != nil {
		t.Fatalf("SaveComparePresets: %v", err)
	}

	body := map[string]interface{}{
		"name":              "F002-Clear-Test",
		"schedule":          "manual",
		"profil":            "SUMMER_TREKKING",
		"hour_from":         8,
		"hour_to":           17,
		"location_ids":      []string{"loc-a"},
		"empfaenger":        []string{"a@example.com"},
		"official_warnings": map[string]interface{}{"enabled": true, "sources": []string{}},
	}
	buf, _ := json.Marshal(body)

	r := chi.NewRouter()
	r.Put("/api/compare/presets/{id}", UpdateComparePresetHandler(s))
	req := httptest.NewRequest(http.MethodPut, "/api/compare/presets/cp-1258-f002-clear", bytes.NewReader(buf))
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
	if len(loaded[0].OfficialWarnings.Sources) != 0 {
		t.Errorf("explicit empty sources must clear, got %+v", loaded[0].OfficialWarnings.Sources)
	}
}
