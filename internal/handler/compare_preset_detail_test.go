package handler

// TDD RED: Issue #491 — Orts-Vergleich Detail-Seite
//
// Spec: docs/specs/modules/issue_491_compare_detail.md
//
// Tests schlagen fehl weil GetComparePresetHandler in compare_preset.go
// noch nicht existiert — der Code kompiliert nicht.
//
// Ausführung:
//   go test ./internal/handler/... -run "TestGetComparePreset" -v

import (
	"encoding/json"
	"net/http/httptest"
	"testing"

	"github.com/go-chi/chi/v5"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

// seedComparePreset speichert ein Preset im Store für den Test-User "test".
func seedComparePreset(t *testing.T, s *store.Store, id, name string, locIDs []string) {
	t.Helper()
	existing, err := s.LoadComparePresets()
	if err != nil {
		t.Fatalf("seedComparePreset: LoadComparePresets: %v", err)
	}
	preset := model.ComparePreset{
		ID:          id,
		Name:        name,
		UserID:      "test",
		LocationIDs: locIDs,
		Schedule:    "daily",
		Profil:      "ALLGEMEIN",
		HourFrom:    6,
		HourTo:      18,
		Empfaenger:  []string{"test@example.com"},
	}
	existing = append(existing, preset)
	if err := s.SaveComparePresets(existing); err != nil {
		t.Fatalf("seedComparePreset: SaveComparePresets: %v", err)
	}
}

// TestGetComparePreset_ValidID_Returns200 — AC-4 Positivfall:
// Bekannte Preset-ID → 200 + JSON mit id und name.
func TestGetComparePreset_ValidID_Returns200(t *testing.T) {
	s := newTestStore(t)
	seedComparePreset(t, s, "cp-test-123", "Zillertal vs. Stubai", []string{"loc-1", "loc-2"})

	r := chi.NewRouter()
	r.Get("/api/compare/presets/{id}", GetComparePresetHandler(s))

	req := httptest.NewRequest("GET", "/api/compare/presets/cp-test-123", nil)
	req = addUserToContext(req, "test")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	var preset model.ComparePreset
	if err := json.NewDecoder(w.Body).Decode(&preset); err != nil {
		t.Fatalf("JSON-Decode fehlgeschlagen: %v", err)
	}
	if preset.ID != "cp-test-123" {
		t.Errorf("expected id='cp-test-123', got %q", preset.ID)
	}
	if preset.Name != "Zillertal vs. Stubai" {
		t.Errorf("expected name='Zillertal vs. Stubai', got %q", preset.Name)
	}
}

// TestGetComparePreset_UnknownID_Returns404 — AC-4 Negativfall:
// Unbekannte Preset-ID → 404.
func TestGetComparePreset_UnknownID_Returns404(t *testing.T) {
	s := newTestStore(t)
	// Kein Preset seeden — Store ist leer.

	r := chi.NewRouter()
	r.Get("/api/compare/presets/{id}", GetComparePresetHandler(s))

	req := httptest.NewRequest("GET", "/api/compare/presets/unknown-id", nil)
	req = addUserToContext(req, "test")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 404 {
		t.Fatalf("expected 404 for unknown id, got %d: %s", w.Code, w.Body.String())
	}
}
