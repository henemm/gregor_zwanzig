package handler

// Issue #1280 — Versandzeit-Eingabe auf volle Stunden begrenzen (Compare-Pfad).
// Spec: docs/specs/modules/fix_1280_versandzeit_stunden_raster.md (AC-1, AC-3, AC-4)
//
// Co-located Handler-Tests gegen echten Store (t.TempDir, keine Mocks), Muster
// wie compare_preset_slot_schedule_test.go.

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

// AC-1: PUT eines Compare-Presets mit krummer morning_time (07:30) speichert und
// liefert den Wert auf die volle Stunde gekappt (07:00) — sowohl in der Response
// als auch persistiert auf der Platte.
func TestUpdateComparePreset_MorningTimeTruncatedToFullHourOnWrite(t *testing.T) {
	s := newTestStore(t)

	trueVal := true
	morningTime := "07:00:00"
	original := model.ComparePreset{
		ID:             "cp-1280-write",
		Name:           "Write-Truncate-Test",
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
	}
	if err := s.WithUser("user1").SaveComparePresets([]model.ComparePreset{original}); err != nil {
		t.Fatalf("SaveComparePresets: %v", err)
	}

	body := map[string]interface{}{
		"name":            "Write-Truncate-Test",
		"schedule":        "manual",
		"profil":          "SUMMER_TREKKING",
		"hour_from":       8,
		"hour_to":         17,
		"location_ids":    []string{"loc-a"},
		"empfaenger":      []string{"a@example.com"},
		"morning_time":    "07:30:00",
		"morning_enabled": true,
	}
	buf, _ := json.Marshal(body)

	r := chi.NewRouter()
	r.Put("/api/compare/presets/{id}", UpdateComparePresetHandler(s))
	req := httptest.NewRequest(http.MethodPut, "/api/compare/presets/cp-1280-write", bytes.NewReader(buf))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "user1")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	var resp model.ComparePreset
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("unmarshal response: %v", err)
	}
	if resp.MorningTime == nil || *resp.MorningTime != "07:00:00" {
		t.Errorf("Response morning_time: erwartet 07:00:00 (gekappt), got %v", resp.MorningTime)
	}

	loaded, err := s.WithUser("user1").LoadComparePresets()
	if err != nil {
		t.Fatalf("LoadComparePresets: %v", err)
	}
	if loaded[0].MorningTime == nil || *loaded[0].MorningTime != "07:00:00" {
		t.Errorf("Persistierte morning_time: erwartet 07:00:00 (gekappt), got %v", loaded[0].MorningTime)
	}
}

// AC-3 + AC-4: Ein direkt (unter Umgehung der Handler-Write-Normalisierung) mit
// krummer morning_time (18:45) UND einem realen letzter_versand-Zeitstempel bei
// 06:03 geseedetes Preset wird beim GET so ausgeliefert, dass das Konfig-Feld auf
// die volle Stunde geheilt ist (18:00), der REALE Zeitstempel aber minutengenau
// bleibt (06:03) — kein Rueckfall auf den vor #1268 behobenen Fehler.
func TestGetComparePresetHandler_ReadHealsMorningTime_ButPreservesLetzterVersandMinutes(t *testing.T) {
	s := newTestStore(t)

	trueVal := true
	morningTime := "18:45:00"
	realSend := time.Date(2026, 7, 16, 6, 3, 0, 0, time.UTC)
	seeded := model.ComparePreset{
		ID:             "cp-1280-heal",
		Name:           "Read-Heal-Test",
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
		LetzterVersand: &realSend,
	}
	if err := s.WithUser("user1").SaveComparePresets([]model.ComparePreset{seeded}); err != nil {
		t.Fatalf("SaveComparePresets: %v", err)
	}

	r := chi.NewRouter()
	r.Get("/api/compare/presets/{id}", GetComparePresetHandler(s))
	req := httptest.NewRequest(http.MethodGet, "/api/compare/presets/cp-1280-heal", nil)
	req = addUserToContext(req, "user1")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	var resp model.ComparePreset
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("unmarshal response: %v", err)
	}
	// AC-3: Konfig-Feld auf volle Stunde geheilt.
	if resp.MorningTime == nil || *resp.MorningTime != "18:00:00" {
		t.Errorf("GET morning_time: erwartet 18:00:00 (geheilt), got %v", resp.MorningTime)
	}
	// AC-4: realer Zeitstempel bleibt minutengenau (#1268-Schutz).
	if resp.LetzterVersand == nil {
		t.Fatalf("letzter_versand darf nicht verloren gehen")
	}
	if resp.LetzterVersand.Minute() != 3 {
		t.Errorf("letzter_versand darf NICHT gekappt werden: erwartet Minute 3 (06:03), got %02d:%02d",
			resp.LetzterVersand.Hour(), resp.LetzterVersand.Minute())
	}
}
