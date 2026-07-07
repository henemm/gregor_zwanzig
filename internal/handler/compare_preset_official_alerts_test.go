package handler

// Issue #1040: Amtliche Alerts Slice 5 — Konfiguration pro Orts-Vergleich.
//
// Spec: docs/specs/modules/issue_1040_alerts_toggle.md (AC-3, Go-Teil)
//
// model.ComparePreset bekommt ein additives Pointer-Feld OfficialAlertsEnabled
// (`json:"official_alerts_enabled,omitempty"`), analog zu Weekday *int: fehlt
// das Feld im JSON (Altdaten), decodiert Go zu nil statt zum Zero-Value false.
// Ein plain bool würde Bestandspresets beim nächsten Speichern durch einen
// Client, der das Feld nicht kennt, unbemerkt auf "aus" umstellen.

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/go-chi/chi/v5"

	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

// OfficialAlertsEnabled überlebt einen Store-Roundtrip (save → load).
func TestComparePreset_OfficialAlertsEnabledRoundtrip(t *testing.T) {
	tmpDir := t.TempDir()
	s := store.New(tmpDir, "user1")

	falseVal := false
	original := model.ComparePreset{
		ID:                    "cp-alerts-toggle-1",
		Name:                  "Vergleich ohne amtliche Warnungen",
		UserID:                "user1",
		LocationIDs:           []string{"loc-a", "loc-b"},
		Schedule:              "manual",
		OfficialAlertsEnabled: &falseVal,
		Profil:                "SUMMER_TREKKING",
		HourFrom:              9,
		HourTo:                16,
		Empfaenger:            []string{"a@example.com"},
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
	if loaded[0].OfficialAlertsEnabled == nil || *loaded[0].OfficialAlertsEnabled != false {
		t.Errorf("expected OfficialAlertsEnabled=false to survive roundtrip, got %v", loaded[0].OfficialAlertsEnabled)
	}
	if loaded[0].Schedule != "manual" {
		t.Errorf("expected Schedule='manual' preserved, got %q", loaded[0].Schedule)
	}
}

// Altdaten-JSON OHNE official_alerts_enabled-Feld laden fehlerfrei; alle
// anderen Felder bleiben intakt (additives Feld → nil Default, kein Datenverlust).
func TestComparePreset_LegacyWithoutOfficialAlertsEnabledLoads(t *testing.T) {
	tmpDir := t.TempDir()
	s := store.New(tmpDir, "user1")

	rawJSON := `[{
		"id": "cp-legacy-alerts",
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

	userDir := filepath.Join(tmpDir, "users", "user1")
	if err := os.MkdirAll(userDir, 0755); err != nil {
		t.Fatalf("MkdirAll: %v", err)
	}
	if err := os.WriteFile(filepath.Join(userDir, "compare_presets.json"), []byte(rawJSON), 0644); err != nil {
		t.Fatalf("WriteFile: %v", err)
	}

	loaded, err := s.LoadComparePresets()
	if err != nil {
		t.Fatalf("LoadComparePresets on legacy data: %v", err)
	}
	if len(loaded) != 1 {
		t.Fatalf("expected 1 preset, got %d", len(loaded))
	}
	p := loaded[0]
	if p.OfficialAlertsEnabled != nil {
		t.Errorf("expected nil OfficialAlertsEnabled for legacy data, got %v", *p.OfficialAlertsEnabled)
	}
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

// PUT ohne official_alerts_enabled im Body darf das Feld NICHT auf nil/true
// zurücksetzen. Beweist Read-Modify-Write für OfficialAlertsEnabled im
// UpdateComparePresetHandler.
func TestUpdateComparePreset_OfficialAlertsEnabledPreservedWhenBodyOmitsIt(t *testing.T) {
	s := newTestStore(t)

	falseVal := false
	original := model.ComparePreset{
		ID:                    "cp-alerts-rwm-1",
		Name:                  "Alerts-Toggle-Test",
		UserID:                "user1",
		LocationIDs:           []string{"loc-a"},
		Schedule:              "manual",
		OfficialAlertsEnabled: &falseVal,
		Profil:                "SUMMER_TREKKING",
		HourFrom:              8,
		HourTo:                17,
		Empfaenger:            []string{"a@example.com"},
		CreatedAt:             time.Now().UTC(),
	}
	if err := s.WithUser("user1").SaveComparePresets([]model.ComparePreset{original}); err != nil {
		t.Fatalf("SaveComparePresets: %v", err)
	}

	// PUT-Body OHNE official_alerts_enabled (wie ein Client der das Feld nicht kennt).
	// Nur "name" wird geändert.
	body := map[string]interface{}{
		"name":         "Alerts-Toggle-Test (umbenannt)",
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
	req := httptest.NewRequest(http.MethodPut, "/api/compare/presets/cp-alerts-rwm-1", bytes.NewReader(buf))
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
	if loaded[0].OfficialAlertsEnabled == nil || *loaded[0].OfficialAlertsEnabled != false {
		t.Errorf("OfficialAlertsEnabled erased by PUT without field: expected false, got %v", loaded[0].OfficialAlertsEnabled)
	}
	if len(loaded[0].LocationIDs) != 1 || loaded[0].LocationIDs[0] != "loc-a" {
		t.Errorf("expected location_ids=[loc-a] preserved, got %v", loaded[0].LocationIDs)
	}
	if len(loaded[0].Empfaenger) != 1 || loaded[0].Empfaenger[0] != "a@example.com" {
		t.Errorf("expected empfaenger preserved, got %v", loaded[0].Empfaenger)
	}
	if loaded[0].Name != "Alerts-Toggle-Test (umbenannt)" {
		t.Errorf("expected name to be updated to the new value, got %q", loaded[0].Name)
	}
}

// Mandanten-Pflicht (CLAUDE.md): Das Update von Nutzer A's Preset darf Nutzer
// B's unabhängiges Preset (eigener official_alerts_enabled-Wert) nicht
// berühren — Cross-User-Isolation im UpdateComparePresetHandler.
func TestUpdateComparePreset_OfficialAlertsEnabledCrossUserIsolation(t *testing.T) {
	s := newTestStore(t)

	falseVal := false
	trueVal := true

	presetA := model.ComparePreset{
		ID:                    "cp-alerts-usera",
		Name:                  "Nutzer A Preset",
		UserID:                "usera",
		LocationIDs:           []string{"loc-a"},
		Schedule:              "manual",
		OfficialAlertsEnabled: &falseVal,
		Profil:                "SUMMER_TREKKING",
		HourFrom:              8,
		HourTo:                17,
		Empfaenger:            []string{"a@example.com"},
		CreatedAt:             time.Now().UTC(),
	}
	presetB := model.ComparePreset{
		ID:                    "cp-alerts-userb",
		Name:                  "Nutzer B Preset",
		UserID:                "userb",
		LocationIDs:           []string{"loc-b"},
		Schedule:              "manual",
		OfficialAlertsEnabled: &trueVal,
		Profil:                "SUMMER_TREKKING",
		HourFrom:              9,
		HourTo:                16,
		Empfaenger:            []string{"b@example.com"},
		CreatedAt:             time.Now().UTC(),
	}
	if err := s.WithUser("usera").SaveComparePresets([]model.ComparePreset{presetA}); err != nil {
		t.Fatalf("SaveComparePresets usera: %v", err)
	}
	if err := s.WithUser("userb").SaveComparePresets([]model.ComparePreset{presetB}); err != nil {
		t.Fatalf("SaveComparePresets userb: %v", err)
	}

	// Nutzer A ändert seinen eigenen Namen, sendet official_alerts_enabled=true.
	body := map[string]interface{}{
		"name":                    "Nutzer A Preset (geändert)",
		"schedule":                "manual",
		"profil":                  "SUMMER_TREKKING",
		"hour_from":               8,
		"hour_to":                 17,
		"location_ids":            []string{"loc-a"},
		"empfaenger":              []string{"a@example.com"},
		"official_alerts_enabled": true,
	}
	buf, _ := json.Marshal(body)

	r := chi.NewRouter()
	r.Put("/api/compare/presets/{id}", UpdateComparePresetHandler(s))
	req := httptest.NewRequest(http.MethodPut, "/api/compare/presets/cp-alerts-usera", bytes.NewReader(buf))
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
	if len(loadedA) != 1 {
		t.Fatalf("expected 1 preset for usera, got %d", len(loadedA))
	}
	if loadedA[0].OfficialAlertsEnabled == nil || *loadedA[0].OfficialAlertsEnabled != true {
		t.Errorf("expected usera OfficialAlertsEnabled=true after explicit PUT, got %v", loadedA[0].OfficialAlertsEnabled)
	}

	// Nutzer B's Preset muss vollkommen unberührt bleiben (eigener Store-Bereich).
	loadedB, err := s.WithUser("userb").LoadComparePresets()
	if err != nil {
		t.Fatalf("LoadComparePresets userb: %v", err)
	}
	if len(loadedB) != 1 {
		t.Fatalf("expected 1 preset for userb, got %d", len(loadedB))
	}
	if loadedB[0].Name != "Nutzer B Preset" {
		t.Errorf("cross-user leak: userb's preset name changed to %q", loadedB[0].Name)
	}
	if loadedB[0].OfficialAlertsEnabled == nil || *loadedB[0].OfficialAlertsEnabled != true {
		t.Errorf("cross-user leak: userb's OfficialAlertsEnabled changed, expected true, got %v", loadedB[0].OfficialAlertsEnabled)
	}
}
