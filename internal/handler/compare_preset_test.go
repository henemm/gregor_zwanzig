package handler

// TDD RED: Issue #458 — Compare-Preset Backend (CRUD-Endpoints + DB-Modell)
//
// Spec: docs/specs/modules/issue_458_compare_preset_backend.md
//
// Tests scheitern absichtlich (RED):
//   - internal/handler/compare_preset.go existiert noch nicht
//   - internal/model/compare_preset.go existiert noch nicht
//   - Store-Methoden LoadComparePresets/SaveComparePresets existieren noch nicht

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

// =============================================================================
// Helpers
// =============================================================================

func validPresetBody() map[string]interface{} {
	return map[string]interface{}{
		"name":         "Zillertal vs. Stubai",
		"location_ids": []string{"loc-1", "loc-2"},
		"schedule":     "daily",
		"profil":       "SUMMER_TREKKING",
		"hour_from":    6,
		"hour_to":      18,
		"empfaenger":   []string{"test@example.com"},
	}
}

func jsonBody(t *testing.T, v interface{}) *bytes.Reader {
	t.Helper()
	b, err := json.Marshal(v)
	if err != nil {
		t.Fatalf("json.Marshal: %v", err)
	}
	return bytes.NewReader(b)
}

// =============================================================================
// AC-1: GET /api/compare/presets — leere Liste
// =============================================================================

func TestListComparePresets_Empty(t *testing.T) {
	s := newTestStore(t)
	r := chi.NewRouter()
	r.Get("/api/compare/presets", ListComparePresetsHandler(s))

	req := httptest.NewRequest("GET", "/api/compare/presets", nil)
	req = addUserToContext(req, "user1")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
	var presets []model.ComparePreset
	if err := json.Unmarshal(w.Body.Bytes(), &presets); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if len(presets) != 0 {
		t.Fatalf("expected empty list, got %d presets", len(presets))
	}
}

// =============================================================================
// AC-2: POST /api/compare/presets — erfolgreiches Anlegen
// =============================================================================

func TestCreateComparePreset_Success(t *testing.T) {
	s := newTestStore(t)
	r := chi.NewRouter()
	r.Post("/api/compare/presets", CreateComparePresetHandler(s))

	req := httptest.NewRequest("POST", "/api/compare/presets", jsonBody(t, validPresetBody()))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "user1")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusCreated {
		t.Fatalf("expected 201, got %d: %s", w.Code, w.Body.String())
	}
	var preset model.ComparePreset
	if err := json.Unmarshal(w.Body.Bytes(), &preset); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if len(preset.ID) < 3 || preset.ID[:3] != "cp-" {
		t.Errorf("expected ID with 'cp-' prefix, got %q", preset.ID)
	}
	if preset.UserID != "user1" {
		t.Errorf("expected user_id='user1' from context, got %q", preset.UserID)
	}
	if preset.Name != "Zillertal vs. Stubai" {
		t.Errorf("expected name preserved, got %q", preset.Name)
	}
	if preset.CreatedAt.IsZero() {
		t.Error("expected created_at to be set")
	}
}

// =============================================================================
// AC-3: POST — name fehlt → 400
// =============================================================================

func TestCreateComparePreset_NameRequired(t *testing.T) {
	s := newTestStore(t)
	r := chi.NewRouter()
	r.Post("/api/compare/presets", CreateComparePresetHandler(s))

	body := validPresetBody()
	delete(body, "name")

	req := httptest.NewRequest("POST", "/api/compare/presets", jsonBody(t, body))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "user1")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Fatalf("expected 400, got %d: %s", w.Code, w.Body.String())
	}
}

// =============================================================================
// AC-4: POST — ungültiger schedule → 400
// =============================================================================

func TestCreateComparePreset_InvalidSchedule(t *testing.T) {
	s := newTestStore(t)
	r := chi.NewRouter()
	r.Post("/api/compare/presets", CreateComparePresetHandler(s))

	body := validPresetBody()
	body["schedule"] = "monatlich"

	req := httptest.NewRequest("POST", "/api/compare/presets", jsonBody(t, body))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "user1")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Fatalf("expected 400, got %d: %s", w.Code, w.Body.String())
	}
}

// =============================================================================
// AC-5: POST — ungültiges profil → 400
// =============================================================================

func TestCreateComparePreset_InvalidProfil(t *testing.T) {
	s := newTestStore(t)
	r := chi.NewRouter()
	r.Post("/api/compare/presets", CreateComparePresetHandler(s))

	body := validPresetBody()
	body["profil"] = "UNBEKANNT"

	req := httptest.NewRequest("POST", "/api/compare/presets", jsonBody(t, body))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "user1")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Fatalf("expected 400, got %d: %s", w.Code, w.Body.String())
	}
}

// =============================================================================
// AC-6: POST — hour_from > hour_to → 400
// =============================================================================

func TestCreateComparePreset_InvalidHourRange(t *testing.T) {
	s := newTestStore(t)
	r := chi.NewRouter()
	r.Post("/api/compare/presets", CreateComparePresetHandler(s))

	body := validPresetBody()
	body["hour_from"] = 14
	body["hour_to"] = 10

	req := httptest.NewRequest("POST", "/api/compare/presets", jsonBody(t, body))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "user1")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Fatalf("expected 400, got %d: %s", w.Code, w.Body.String())
	}
}

// =============================================================================
// AC-7: POST — empfaenger ohne @ → 400
// =============================================================================

func TestCreateComparePreset_InvalidEmpfaenger(t *testing.T) {
	s := newTestStore(t)
	r := chi.NewRouter()
	r.Post("/api/compare/presets", CreateComparePresetHandler(s))

	body := validPresetBody()
	body["empfaenger"] = []string{"keine-email-adresse"}

	req := httptest.NewRequest("POST", "/api/compare/presets", jsonBody(t, body))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "user1")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Fatalf("expected 400, got %d: %s", w.Code, w.Body.String())
	}
}

// =============================================================================
// AC-8: PUT — erfolgreiches Ersetzen, CreatedAt + UserID bleiben erhalten
// =============================================================================

func TestUpdateComparePreset_Success(t *testing.T) {
	s := newTestStore(t)

	// Erst anlegen
	createRouter := chi.NewRouter()
	createRouter.Post("/api/compare/presets", CreateComparePresetHandler(s))
	createReq := httptest.NewRequest("POST", "/api/compare/presets", jsonBody(t, validPresetBody()))
	createReq.Header.Set("Content-Type", "application/json")
	createReq = addUserToContext(createReq, "user1")
	createW := httptest.NewRecorder()
	createRouter.ServeHTTP(createW, createReq)
	if createW.Code != http.StatusCreated {
		t.Fatalf("setup: create failed with %d: %s", createW.Code, createW.Body.String())
	}
	var original model.ComparePreset
	json.Unmarshal(createW.Body.Bytes(), &original)

	// Dann aktualisieren
	updateBody := validPresetBody()
	updateBody["name"] = "Geänderter Name"
	updateBody["schedule"] = "weekly"

	r := chi.NewRouter()
	r.Put("/api/compare/presets/{id}", UpdateComparePresetHandler(s))
	req := httptest.NewRequest("PUT", "/api/compare/presets/"+original.ID, jsonBody(t, updateBody))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "user1")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
	var updated model.ComparePreset
	json.Unmarshal(w.Body.Bytes(), &updated)

	if updated.Name != "Geänderter Name" {
		t.Errorf("expected updated name, got %q", updated.Name)
	}
	if updated.Schedule != "weekly" {
		t.Errorf("expected updated schedule, got %q", updated.Schedule)
	}
	if updated.UserID != original.UserID {
		t.Errorf("user_id must be preserved: want %q got %q", original.UserID, updated.UserID)
	}
	if !updated.CreatedAt.Equal(original.CreatedAt) {
		t.Errorf("created_at must be preserved: want %v got %v", original.CreatedAt, updated.CreatedAt)
	}
}

// =============================================================================
// AC-9: PUT — unbekannte ID → 404
// =============================================================================

func TestUpdateComparePreset_NotFound(t *testing.T) {
	s := newTestStore(t)
	r := chi.NewRouter()
	r.Put("/api/compare/presets/{id}", UpdateComparePresetHandler(s))

	req := httptest.NewRequest("PUT", "/api/compare/presets/cp-doesnotexist", jsonBody(t, validPresetBody()))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "user1")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusNotFound {
		t.Fatalf("expected 404, got %d: %s", w.Code, w.Body.String())
	}
}

// =============================================================================
// AC-10: DELETE — erfolgreiches Löschen → 204
// =============================================================================

func TestDeleteComparePreset_Success(t *testing.T) {
	s := newTestStore(t)

	// Erst anlegen
	createRouter := chi.NewRouter()
	createRouter.Post("/api/compare/presets", CreateComparePresetHandler(s))
	createReq := httptest.NewRequest("POST", "/api/compare/presets", jsonBody(t, validPresetBody()))
	createReq.Header.Set("Content-Type", "application/json")
	createReq = addUserToContext(createReq, "user1")
	createW := httptest.NewRecorder()
	createRouter.ServeHTTP(createW, createReq)
	if createW.Code != http.StatusCreated {
		t.Fatalf("setup: create failed with %d", createW.Code)
	}
	var preset model.ComparePreset
	json.Unmarshal(createW.Body.Bytes(), &preset)

	// Dann löschen
	r := chi.NewRouter()
	r.Delete("/api/compare/presets/{id}", DeleteComparePresetHandler(s))
	req := httptest.NewRequest("DELETE", "/api/compare/presets/"+preset.ID, nil)
	req = addUserToContext(req, "user1")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusNoContent {
		t.Fatalf("expected 204, got %d: %s", w.Code, w.Body.String())
	}

	// Liste muss leer sein
	listRouter := chi.NewRouter()
	listRouter.Get("/api/compare/presets", ListComparePresetsHandler(s))
	listReq := httptest.NewRequest("GET", "/api/compare/presets", nil)
	listReq = addUserToContext(listReq, "user1")
	listW := httptest.NewRecorder()
	listRouter.ServeHTTP(listW, listReq)
	var presets []model.ComparePreset
	json.Unmarshal(listW.Body.Bytes(), &presets)
	if len(presets) != 0 {
		t.Errorf("expected empty list after delete, got %d presets", len(presets))
	}
}

// =============================================================================
// AC-11: DELETE — unbekannte ID → 404
// =============================================================================

func TestDeleteComparePreset_NotFound(t *testing.T) {
	s := newTestStore(t)
	r := chi.NewRouter()
	r.Delete("/api/compare/presets/{id}", DeleteComparePresetHandler(s))

	req := httptest.NewRequest("DELETE", "/api/compare/presets/cp-doesnotexist", nil)
	req = addUserToContext(req, "user1")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusNotFound {
		t.Fatalf("expected 404, got %d: %s", w.Code, w.Body.String())
	}
}

// =============================================================================
// AC-12: POST /{id}/send — Proxy → leitet an Python weiter, gibt Body durch
// (Issue #627: SendComparePresetHandler ist jetzt ein Proxy, kein Stub mehr)
// =============================================================================

func TestSendComparePreset_Success(t *testing.T) {
	// Fake Python upstream, der 200 {"status":"ok"} zurückgibt.
	fakePython := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"status":"ok","winner":"Zermatt"}`))
	}))
	defer fakePython.Close()

	r := chi.NewRouter()
	r.Post("/api/compare/presets/{id}/send", SendComparePresetHandler(fakePython.URL))
	req := httptest.NewRequest("POST", "/api/compare/presets/cp-test/send", nil)
	req = addUserToContext(req, "user1")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
	var resp map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("unmarshal response: %v", err)
	}
	if resp["status"] != "ok" {
		t.Errorf("expected status='ok' from proxy, got %q", resp["status"])
	}
}

// =============================================================================
// AC-13: POST /{id}/send — Proxy leitet 404 vom Upstream durch
// (Issue #627: Lookup passiert jetzt in Python, nicht im Go-Handler)
// =============================================================================

func TestSendComparePreset_NotFound(t *testing.T) {
	// Fake Python upstream, der 404 zurückgibt (unbekannte Preset-ID).
	fakePython := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusNotFound)
		w.Write([]byte(`{"detail":"Compare-Preset cp-doesnotexist nicht gefunden"}`))
	}))
	defer fakePython.Close()

	r := chi.NewRouter()
	r.Post("/api/compare/presets/{id}/send", SendComparePresetHandler(fakePython.URL))
	req := httptest.NewRequest("POST", "/api/compare/presets/cp-doesnotexist/send", nil)
	req = addUserToContext(req, "user1")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusNotFound {
		t.Fatalf("expected 404, got %d: %s", w.Code, w.Body.String())
	}
}

// =============================================================================
// AC-14: User-Isolation — User B sieht Presets von User A nicht
// =============================================================================

func TestComparePreset_UserIsolation(t *testing.T) {
	s := newTestStore(t)

	// User A legt Preset an
	createRouter := chi.NewRouter()
	createRouter.Post("/api/compare/presets", CreateComparePresetHandler(s))
	createReq := httptest.NewRequest("POST", "/api/compare/presets", jsonBody(t, validPresetBody()))
	createReq.Header.Set("Content-Type", "application/json")
	createReq = addUserToContext(createReq, "userA")
	createW := httptest.NewRecorder()
	createRouter.ServeHTTP(createW, createReq)
	if createW.Code != http.StatusCreated {
		t.Fatalf("setup: userA create failed with %d", createW.Code)
	}

	// User B fragt Liste ab
	listRouter := chi.NewRouter()
	listRouter.Get("/api/compare/presets", ListComparePresetsHandler(s))
	listReq := httptest.NewRequest("GET", "/api/compare/presets", nil)
	listReq = addUserToContext(listReq, "userB")
	listW := httptest.NewRecorder()
	listRouter.ServeHTTP(listW, listReq)

	if listW.Code != http.StatusOK {
		t.Fatalf("expected 200 for userB, got %d", listW.Code)
	}
	var presets []model.ComparePreset
	json.Unmarshal(listW.Body.Bytes(), &presets)
	if len(presets) != 0 {
		t.Errorf("userB should see 0 presets, got %d (user isolation broken)", len(presets))
	}
}

// =============================================================================
// Zusatz: POST erscheint anschließend in GET-Liste
// =============================================================================

func TestCreateComparePreset_AppearsInList(t *testing.T) {
	s := newTestStore(t)

	createRouter := chi.NewRouter()
	createRouter.Post("/api/compare/presets", CreateComparePresetHandler(s))
	req := httptest.NewRequest("POST", "/api/compare/presets", jsonBody(t, validPresetBody()))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "user1")
	w := httptest.NewRecorder()
	createRouter.ServeHTTP(w, req)
	if w.Code != http.StatusCreated {
		t.Fatalf("create failed: %d %s", w.Code, w.Body.String())
	}

	listRouter := chi.NewRouter()
	listRouter.Get("/api/compare/presets", ListComparePresetsHandler(s))
	listReq := httptest.NewRequest("GET", "/api/compare/presets", nil)
	listReq = addUserToContext(listReq, "user1")
	listW := httptest.NewRecorder()
	listRouter.ServeHTTP(listW, listReq)

	var presets []model.ComparePreset
	json.Unmarshal(listW.Body.Bytes(), &presets)
	if len(presets) != 1 {
		t.Errorf("expected 1 preset in list, got %d", len(presets))
	}
}

// Compile-time import guard — ensures time package is used
var _ = time.Now

// =============================================================================
// Bug #591 — Round-Trip: Lowercase profil muss PUT akzeptieren (AC-1)
// =============================================================================

// TestUpdateComparePreset_LowercaseProfil_RoundTrip prüft dass ein per Store
// direkt angelegtes Preset mit lowercase profil ("allgemein") per PUT
// aktualisiert werden kann — HTTP 200, kein 400 validation_error.
// Simuliert bestehende Daten die vor Einführung der API-Validation angelegt wurden.
func TestUpdateComparePreset_LowercaseProfil_RoundTrip(t *testing.T) {
	s := newTestStore(t).WithUser("user1")

	// Direkt in den Store schreiben (simuliert migrierte/geseedete Daten mit lowercase profil)
	seeded := model.ComparePreset{
		ID:          "cp-seed-allgemein",
		UserID:      "user1",
		Name:        "Mallorca Test",
		LocationIDs: []string{"loc-a", "loc-b"},
		Schedule:    "daily",
		Profil:      "allgemein", // Lowercase — wie in bestehenden Daten
		HourFrom:    9,
		HourTo:      16,
		Empfaenger:  []string{"test@example.com"},
		CreatedAt:   time.Now().UTC(),
	}
	if err := s.SaveComparePresets([]model.ComparePreset{seeded}); err != nil {
		t.Fatalf("setup: SaveComparePresets: %v", err)
	}

	// PUT mit demselben lowercase profil + schedule auf "manual"
	updateBody := map[string]interface{}{
		"name":         seeded.Name,
		"location_ids": seeded.LocationIDs,
		"schedule":     "manual",
		"profil":       "allgemein", // Lowercase wie im Preset gespeichert
		"hour_from":    seeded.HourFrom,
		"hour_to":      seeded.HourTo,
		"empfaenger":   seeded.Empfaenger,
	}

	r := chi.NewRouter()
	r.Put("/api/compare/presets/{id}", UpdateComparePresetHandler(s))
	req := httptest.NewRequest("PUT", "/api/compare/presets/"+seeded.ID, jsonBody(t, updateBody))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "user1")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("AC-1 FAIL: expected 200 for lowercase profil, got %d: %s", w.Code, w.Body.String())
	}
	var updated model.ComparePreset
	if err := json.Unmarshal(w.Body.Bytes(), &updated); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if updated.Schedule != "manual" {
		t.Errorf("AC-2 FAIL: expected schedule=manual, got %q", updated.Schedule)
	}
}

// TestUpdateComparePreset_LowercaseWintersport_RoundTrip prüft "wintersport" (lowercase).
func TestUpdateComparePreset_LowercaseWintersport_RoundTrip(t *testing.T) {
	s := newTestStore(t).WithUser("user1")

	seeded := model.ComparePreset{
		ID:          "cp-seed-wintersport",
		UserID:      "user1",
		Name:        "Zillertal",
		LocationIDs: []string{"loc-z"},
		Schedule:    "daily",
		Profil:      "wintersport", // Lowercase
		HourFrom:    8,
		HourTo:      14,
		Empfaenger:  []string{},
		CreatedAt:   time.Now().UTC(),
	}
	if err := s.SaveComparePresets([]model.ComparePreset{seeded}); err != nil {
		t.Fatalf("setup: SaveComparePresets: %v", err)
	}

	updateBody := map[string]interface{}{
		"name":         seeded.Name,
		"location_ids": seeded.LocationIDs,
		"schedule":     "manual",
		"profil":       "wintersport",
		"hour_from":    seeded.HourFrom,
		"hour_to":      seeded.HourTo,
		"empfaenger":   seeded.Empfaenger,
	}

	r := chi.NewRouter()
	r.Put("/api/compare/presets/{id}", UpdateComparePresetHandler(s))
	req := httptest.NewRequest("PUT", "/api/compare/presets/"+seeded.ID, jsonBody(t, updateBody))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "user1")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("AC-1 FAIL: expected 200 for lowercase wintersport, got %d: %s", w.Code, w.Body.String())
	}
}

// TestUpdateComparePreset_LowercaseWandern_RoundTrip prüft "wandern" → ALPINE_TOURING mapping.
func TestUpdateComparePreset_LowercaseWandern_RoundTrip(t *testing.T) {
	s := newTestStore(t).WithUser("user1")

	seeded := model.ComparePreset{
		ID:          "cp-seed-wandern",
		UserID:      "user1",
		Name:        "Alpen",
		LocationIDs: []string{"loc-a"},
		Schedule:    "daily",
		Profil:      "wandern",
		HourFrom:    7,
		HourTo:      17,
		Empfaenger:  []string{},
		CreatedAt:   time.Now().UTC(),
	}
	if err := s.SaveComparePresets([]model.ComparePreset{seeded}); err != nil {
		t.Fatalf("setup: SaveComparePresets: %v", err)
	}

	updateBody := map[string]interface{}{
		"name":         seeded.Name,
		"location_ids": seeded.LocationIDs,
		"schedule":     "manual",
		"profil":       "wandern",
		"hour_from":    seeded.HourFrom,
		"hour_to":      seeded.HourTo,
		"empfaenger":   seeded.Empfaenger,
	}

	r := chi.NewRouter()
	r.Put("/api/compare/presets/{id}", UpdateComparePresetHandler(s))
	req := httptest.NewRequest("PUT", "/api/compare/presets/"+seeded.ID, jsonBody(t, updateBody))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "user1")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("AC-1 FAIL: expected 200 for lowercase wandern, got %d: %s", w.Code, w.Body.String())
	}
}

// ============================================================================
// Issue #781 — ComparePreset-Handler validiert forecast_hours (24/48/72).
// ============================================================================

func TestCreateComparePreset_ValidForecastHours_Accepted(t *testing.T) {
	s := newTestStore(t)
	r := chi.NewRouter()
	r.Post("/api/compare/presets", CreateComparePresetHandler(s))

	for _, hours := range []int{24, 48, 72} {
		body := validPresetBody()
		body["forecast_hours"] = hours

		req := httptest.NewRequest("POST", "/api/compare/presets", jsonBody(t, body))
		req.Header.Set("Content-Type", "application/json")
		req = addUserToContext(req, "user1")
		w := httptest.NewRecorder()
		r.ServeHTTP(w, req)

		if w.Code != http.StatusCreated {
			t.Fatalf("forecast_hours=%d: expected 201, got %d: %s", hours, w.Code, w.Body.String())
		}
	}
}

func TestCreateComparePreset_InvalidForecastHours_Rejected(t *testing.T) {
	s := newTestStore(t)
	r := chi.NewRouter()
	r.Post("/api/compare/presets", CreateComparePresetHandler(s))

	for _, hours := range []int{-1, 99, 1, 23, 25, 71, 73} {
		body := validPresetBody()
		body["forecast_hours"] = hours

		req := httptest.NewRequest("POST", "/api/compare/presets", jsonBody(t, body))
		req.Header.Set("Content-Type", "application/json")
		req = addUserToContext(req, "user1")
		w := httptest.NewRecorder()
		r.ServeHTTP(w, req)

		if w.Code != http.StatusBadRequest {
			t.Fatalf("forecast_hours=%d: expected 400, got %d: %s", hours, w.Code, w.Body.String())
		}
	}
}

func TestCreateComparePreset_MissingForecastHours_DefaultsTo48(t *testing.T) {
	s := newTestStore(t)
	r := chi.NewRouter()
	r.Post("/api/compare/presets", CreateComparePresetHandler(s))

	body := validPresetBody()
	// forecast_hours bewusst nicht gesetzt

	req := httptest.NewRequest("POST", "/api/compare/presets", jsonBody(t, body))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "user1")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusCreated {
		t.Fatalf("expected 201, got %d: %s", w.Code, w.Body.String())
	}
	var preset model.ComparePreset
	if err := json.Unmarshal(w.Body.Bytes(), &preset); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if preset.ForecastHours != 48 {
		t.Errorf("missing forecast_hours must default to 48, got %d", preset.ForecastHours)
	}
}

func TestUpdateComparePreset_InvalidForecastHours_Rejected(t *testing.T) {
	s := newTestStore(t).WithUser("user1")
	seeded := model.ComparePreset{
		ID:            "cp-seed-781",
		UserID:        "user1",
		Name:          "Test",
		LocationIDs:   []string{"loc-a"},
		Schedule:      "daily",
		Profil:        "allgemein",
		HourFrom:      9,
		HourTo:        16,
		ForecastHours: 48,
		Empfaenger:    []string{"test@example.com"},
		CreatedAt:     time.Now().UTC(),
	}
	if err := s.SaveComparePresets([]model.ComparePreset{seeded}); err != nil {
		t.Fatalf("setup: SaveComparePresets: %v", err)
	}

	updateBody := validPresetBody()
	updateBody["forecast_hours"] = 99

	r := chi.NewRouter()
	r.Put("/api/compare/presets/{id}", UpdateComparePresetHandler(s))
	req := httptest.NewRequest("PUT", "/api/compare/presets/"+seeded.ID, jsonBody(t, updateBody))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "user1")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Fatalf("expected 400 for forecast_hours=99, got %d: %s", w.Code, w.Body.String())
	}
}

// ============================================================================
// Issue #1170 — Alarm-Konfiguration: Round-Trip + RMW-nil-Merge (Adversary F004).
// ============================================================================

// TestUpdateComparePreset_AlertFields_RoundtripAndRMW deckt zwei Verhaltensweisen ab:
//  1. Ein PUT, das alle Alarm-Felder setzt (alert_cooldown_minutes, alert_quiet_from,
//     alert_quiet_to, display_config.metric_alert_levels), liefert diese Werte
//     unverändert in der Response zurück (Round-Trip).
//  2. Ein FOLGE-PUT, das NUR ein anderes Feld ändert (name) und die Alarm-Felder
//     im Body NICHT mitschickt, darf die zuvor gesetzten Alarm-Felder nicht
//     verlieren (Read-Modify-Write-nil-Merge, analog official_alerts_enabled).
func TestUpdateComparePreset_AlertFields_RoundtripAndRMW(t *testing.T) {
	s := newTestStore(t)

	// Preset anlegen (noch ohne Alarm-Felder).
	createRouter := chi.NewRouter()
	createRouter.Post("/api/compare/presets", CreateComparePresetHandler(s))
	createReq := httptest.NewRequest("POST", "/api/compare/presets", jsonBody(t, validPresetBody()))
	createReq.Header.Set("Content-Type", "application/json")
	createReq = addUserToContext(createReq, "user1")
	createW := httptest.NewRecorder()
	createRouter.ServeHTTP(createW, createReq)
	if createW.Code != http.StatusCreated {
		t.Fatalf("setup: create failed with %d: %s", createW.Code, createW.Body.String())
	}
	var original model.ComparePreset
	json.Unmarshal(createW.Body.Bytes(), &original)

	// Schritt 1: PUT setzt alle Alarm-Felder.
	firstBody := validPresetBody()
	firstBody["alert_cooldown_minutes"] = 45
	firstBody["alert_quiet_from"] = "22:00"
	firstBody["alert_quiet_to"] = "07:00"
	firstBody["display_config"] = map[string]interface{}{
		"metric_alert_levels": map[string]interface{}{
			"temperature": "sensitive",
			"wind":        "normal",
		},
	}

	r := chi.NewRouter()
	r.Put("/api/compare/presets/{id}", UpdateComparePresetHandler(s))
	req := httptest.NewRequest("PUT", "/api/compare/presets/"+original.ID, jsonBody(t, firstBody))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "user1")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("first PUT: expected 200, got %d: %s", w.Code, w.Body.String())
	}
	var afterFirst model.ComparePreset
	json.Unmarshal(w.Body.Bytes(), &afterFirst)

	if afterFirst.AlertCooldownMinutes == nil || *afterFirst.AlertCooldownMinutes != 45 {
		t.Fatalf("round-trip FAIL: expected alert_cooldown_minutes=45, got %v", afterFirst.AlertCooldownMinutes)
	}
	if afterFirst.AlertQuietFrom == nil || *afterFirst.AlertQuietFrom != "22:00" {
		t.Fatalf("round-trip FAIL: expected alert_quiet_from=22:00, got %v", afterFirst.AlertQuietFrom)
	}
	if afterFirst.AlertQuietTo == nil || *afterFirst.AlertQuietTo != "07:00" {
		t.Fatalf("round-trip FAIL: expected alert_quiet_to=07:00, got %v", afterFirst.AlertQuietTo)
	}
	levels, ok := afterFirst.DisplayConfig["metric_alert_levels"].(map[string]interface{})
	if !ok {
		t.Fatalf("round-trip FAIL: expected display_config.metric_alert_levels to be a map, got %T", afterFirst.DisplayConfig["metric_alert_levels"])
	}
	if levels["temperature"] != "sensitive" || levels["wind"] != "normal" {
		t.Fatalf("round-trip FAIL: metric_alert_levels not preserved, got %v", levels)
	}

	// Schritt 2: Folge-PUT ändert NUR name, Alarm-Felder + display_config fehlen im Body.
	secondBody := validPresetBody()
	secondBody["name"] = "Anderer Name"
	// Bewusst KEINE alert_* / display_config Felder im Body.

	req2 := httptest.NewRequest("PUT", "/api/compare/presets/"+original.ID, jsonBody(t, secondBody))
	req2.Header.Set("Content-Type", "application/json")
	req2 = addUserToContext(req2, "user1")
	w2 := httptest.NewRecorder()
	r.ServeHTTP(w2, req2)

	if w2.Code != http.StatusOK {
		t.Fatalf("second PUT: expected 200, got %d: %s", w2.Code, w2.Body.String())
	}
	var afterSecond model.ComparePreset
	json.Unmarshal(w2.Body.Bytes(), &afterSecond)

	if afterSecond.Name != "Anderer Name" {
		t.Errorf("expected name to be updated, got %q", afterSecond.Name)
	}
	if afterSecond.AlertCooldownMinutes == nil || *afterSecond.AlertCooldownMinutes != 45 {
		t.Errorf("RMW FAIL: alert_cooldown_minutes must survive an unrelated update, got %v", afterSecond.AlertCooldownMinutes)
	}
	if afterSecond.AlertQuietFrom == nil || *afterSecond.AlertQuietFrom != "22:00" {
		t.Errorf("RMW FAIL: alert_quiet_from must survive an unrelated update, got %v", afterSecond.AlertQuietFrom)
	}
	if afterSecond.AlertQuietTo == nil || *afterSecond.AlertQuietTo != "07:00" {
		t.Errorf("RMW FAIL: alert_quiet_to must survive an unrelated update, got %v", afterSecond.AlertQuietTo)
	}
	levels2, ok := afterSecond.DisplayConfig["metric_alert_levels"].(map[string]interface{})
	if !ok {
		t.Fatalf("RMW FAIL: expected display_config.metric_alert_levels to survive, got %T", afterSecond.DisplayConfig["metric_alert_levels"])
	}
	if levels2["temperature"] != "sensitive" || levels2["wind"] != "normal" {
		t.Errorf("RMW FAIL: metric_alert_levels not preserved after unrelated update, got %v", levels2)
	}
}

// TestUpdateComparePreset_AlertFields_UserIsolation prüft, dass ein Update der
// Alarm-Felder durch User A ein gleichnamig-strukturiertes Preset von User B
// nicht berührt (Multi-User-Isolation, analog TestComparePreset_UserIsolation).
func TestUpdateComparePreset_AlertFields_UserIsolation(t *testing.T) {
	s := newTestStore(t)

	// User A legt Preset an.
	createRouterA := chi.NewRouter()
	createRouterA.Post("/api/compare/presets", CreateComparePresetHandler(s))
	createReqA := httptest.NewRequest("POST", "/api/compare/presets", jsonBody(t, validPresetBody()))
	createReqA.Header.Set("Content-Type", "application/json")
	createReqA = addUserToContext(createReqA, "userA")
	createWA := httptest.NewRecorder()
	createRouterA.ServeHTTP(createWA, createReqA)
	if createWA.Code != http.StatusCreated {
		t.Fatalf("setup: userA create failed with %d", createWA.Code)
	}
	var presetA model.ComparePreset
	json.Unmarshal(createWA.Body.Bytes(), &presetA)

	// User B legt eigenes Preset an.
	createReqB := httptest.NewRequest("POST", "/api/compare/presets", jsonBody(t, validPresetBody()))
	createReqB.Header.Set("Content-Type", "application/json")
	createReqB = addUserToContext(createReqB, "userB")
	createWB := httptest.NewRecorder()
	createRouterA.ServeHTTP(createWB, createReqB)
	if createWB.Code != http.StatusCreated {
		t.Fatalf("setup: userB create failed with %d", createWB.Code)
	}
	var presetB model.ComparePreset
	json.Unmarshal(createWB.Body.Bytes(), &presetB)

	// User A setzt Alarm-Felder auf sein eigenes Preset.
	bodyA := validPresetBody()
	bodyA["alert_cooldown_minutes"] = 30

	updateRouter := chi.NewRouter()
	updateRouter.Put("/api/compare/presets/{id}", UpdateComparePresetHandler(s))
	reqA := httptest.NewRequest("PUT", "/api/compare/presets/"+presetA.ID, jsonBody(t, bodyA))
	reqA.Header.Set("Content-Type", "application/json")
	reqA = addUserToContext(reqA, "userA")
	wA := httptest.NewRecorder()
	updateRouter.ServeHTTP(wA, reqA)
	if wA.Code != http.StatusOK {
		t.Fatalf("userA update failed with %d: %s", wA.Code, wA.Body.String())
	}

	// User B ruft SEIN Preset ab — muss unberührt sein (kein alert_cooldown_minutes).
	getRouter := chi.NewRouter()
	getRouter.Get("/api/compare/presets", ListComparePresetsHandler(s))
	getReqB := httptest.NewRequest("GET", "/api/compare/presets", nil)
	getReqB = addUserToContext(getReqB, "userB")
	getWB := httptest.NewRecorder()
	getRouter.ServeHTTP(getWB, getReqB)

	var presetsB []model.ComparePreset
	json.Unmarshal(getWB.Body.Bytes(), &presetsB)
	if len(presetsB) != 1 {
		t.Fatalf("expected userB to see exactly 1 preset, got %d", len(presetsB))
	}
	if presetsB[0].ID != presetB.ID {
		t.Fatalf("user isolation broken: userB sees preset %q, expected own %q", presetsB[0].ID, presetB.ID)
	}
	if presetsB[0].AlertCooldownMinutes != nil {
		t.Errorf("user isolation broken: userB's preset gained alert_cooldown_minutes=%v from userA's update", *presetsB[0].AlertCooldownMinutes)
	}
}
