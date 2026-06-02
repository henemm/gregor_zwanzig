package handler

// TDD RED: Epic #138 Phase 2 — User-Preset-Endpoints (Issue #177, §7)
//
// Spec: docs/specs/modules/epic_138_174_178_metriken_ui.md §7
//
// Tests scheitern absichtlich (RED):
//   - internal/handler/metric_preset.go existiert noch nicht
//   - internal/model/metric_preset.go existiert noch nicht
//   - Store-Methoden LoadMetricPresets/SaveMetricPresets existieren noch nicht

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"reflect"
	"testing"

	"github.com/go-chi/chi/v5"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

// =============================================================================
// AC-6: GET /api/metric-presets — leere Liste
// =============================================================================

func TestListMetricPresets_Empty(t *testing.T) {
	s := newTestStore(t)

	r := chi.NewRouter()
	r.Get("/api/metric-presets", ListMetricPresetsHandler(s))

	req := httptest.NewRequest("GET", "/api/metric-presets", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	var presets []model.MetricPreset
	if err := json.Unmarshal(w.Body.Bytes(), &presets); err != nil {
		t.Fatalf("failed to parse response: %v", err)
	}
	if len(presets) != 0 {
		t.Fatalf("expected empty list, got %d presets", len(presets))
	}
}

// =============================================================================
// AC-6: POST /api/metric-presets — Preset erstellen
// =============================================================================

func TestCreateMetricPreset_Success(t *testing.T) {
	s := newTestStore(t)

	r := chi.NewRouter()
	r.Post("/api/metric-presets", CreateMetricPresetHandler(s))

	body := map[string]interface{}{
		"name":         "Mein Wandern-Preset",
		"description":  "Optimiert für Tagestouren",
		"is_default":   false,
		"metrics":      []string{"temperature", "wind", "precipitation"},
		"friendly_ids": []string{"wind_direction"},
	}
	bodyBytes, _ := json.Marshal(body)

	req := httptest.NewRequest("POST", "/api/metric-presets", bytes.NewReader(bodyBytes))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusCreated {
		t.Fatalf("expected 201 Created, got %d: %s", w.Code, w.Body.String())
	}

	var created model.MetricPreset
	if err := json.Unmarshal(w.Body.Bytes(), &created); err != nil {
		t.Fatalf("failed to parse response: %v", err)
	}
	if created.ID == "" {
		t.Error("created preset must have a non-empty ID")
	}
	if created.Name != "Mein Wandern-Preset" {
		t.Errorf("name mismatch: got %q", created.Name)
	}
	if created.CreatedAt.IsZero() {
		t.Error("created_at must be set")
	}
}

// =============================================================================
// AC-6: POST → GET zeigt gespeichertes Preset in der Liste
// =============================================================================

func TestCreateMetricPreset_AppearsInList(t *testing.T) {
	s := newTestStore(t)

	r := chi.NewRouter()
	r.Get("/api/metric-presets", ListMetricPresetsHandler(s))
	r.Post("/api/metric-presets", CreateMetricPresetHandler(s))

	// Preset erstellen
	body := map[string]interface{}{
		"name":         "Hochtouren",
		"metrics":      []string{"temperature", "wind", "freezing_level"},
		"friendly_ids": []string{},
		"is_default":   false,
	}
	bodyBytes, _ := json.Marshal(body)
	postReq := httptest.NewRequest("POST", "/api/metric-presets", bytes.NewReader(bodyBytes))
	postReq.Header.Set("Content-Type", "application/json")
	postW := httptest.NewRecorder()
	r.ServeHTTP(postW, postReq)

	if postW.Code != http.StatusCreated {
		t.Fatalf("POST failed: %d %s", postW.Code, postW.Body.String())
	}

	// Liste abrufen
	getReq := httptest.NewRequest("GET", "/api/metric-presets", nil)
	getW := httptest.NewRecorder()
	r.ServeHTTP(getW, getReq)

	var presets []model.MetricPreset
	json.Unmarshal(getW.Body.Bytes(), &presets)

	if len(presets) != 1 {
		t.Fatalf("expected 1 preset, got %d", len(presets))
	}
	if presets[0].Name != "Hochtouren" {
		t.Errorf("expected 'Hochtouren', got %q", presets[0].Name)
	}
}

// =============================================================================
// AC-7: is_default=true → nur ein Preset hat is_default=true
// =============================================================================

func TestCreateMetricPreset_IsDefault_OnlyOne(t *testing.T) {
	s := newTestStore(t)

	r := chi.NewRouter()
	r.Get("/api/metric-presets", ListMetricPresetsHandler(s))
	r.Post("/api/metric-presets", CreateMetricPresetHandler(s))

	// Erstes Preset mit is_default=true
	body1 := map[string]interface{}{
		"name":         "Preset A",
		"metrics":      []string{"temperature"},
		"friendly_ids": []string{},
		"is_default":   true,
	}
	b1, _ := json.Marshal(body1)
	r.ServeHTTP(httptest.NewRecorder(),
		withBody(t, "POST", "/api/metric-presets", b1))

	// Zweites Preset mit is_default=true
	body2 := map[string]interface{}{
		"name":         "Preset B",
		"metrics":      []string{"wind"},
		"friendly_ids": []string{},
		"is_default":   true,
	}
	b2, _ := json.Marshal(body2)
	postW2 := httptest.NewRecorder()
	r.ServeHTTP(postW2, withBody(t, "POST", "/api/metric-presets", b2))

	// Liste: genau 1 Preset darf is_default=true haben
	getW := httptest.NewRecorder()
	r.ServeHTTP(getW, httptest.NewRequest("GET", "/api/metric-presets", nil))

	var presets []model.MetricPreset
	json.Unmarshal(getW.Body.Bytes(), &presets)

	defaultCount := 0
	for _, p := range presets {
		if p.IsDefault {
			defaultCount++
		}
	}
	if defaultCount != 1 {
		t.Errorf("expected exactly 1 default preset, got %d", defaultCount)
	}
	// Das zuletzt gespeicherte (Preset B) soll der Default sein
	for _, p := range presets {
		if p.Name == "Preset B" && !p.IsDefault {
			t.Error("Preset B sollte is_default=true haben")
		}
		if p.Name == "Preset A" && p.IsDefault {
			t.Error("Preset A sollte is_default=false haben nach Preset-B-Speicherung")
		}
	}
}

// =============================================================================
// DELETE /api/metric-presets/{id} — Preset loeschen
// =============================================================================

func TestDeleteMetricPreset_Success(t *testing.T) {
	s := newTestStore(t)

	r := chi.NewRouter()
	r.Get("/api/metric-presets", ListMetricPresetsHandler(s))
	r.Post("/api/metric-presets", CreateMetricPresetHandler(s))
	r.Delete("/api/metric-presets/{id}", DeleteMetricPresetHandler(s))

	// Erst erstellen
	body := map[string]interface{}{
		"name":         "Zu loeschendes Preset",
		"metrics":      []string{"temperature"},
		"friendly_ids": []string{},
		"is_default":   false,
	}
	bodyBytes, _ := json.Marshal(body)
	postW := httptest.NewRecorder()
	r.ServeHTTP(postW, withBody(t, "POST", "/api/metric-presets", bodyBytes))

	var created model.MetricPreset
	json.Unmarshal(postW.Body.Bytes(), &created)

	// Dann loeschen
	delW := httptest.NewRecorder()
	r.ServeHTTP(delW, httptest.NewRequest("DELETE", "/api/metric-presets/"+created.ID, nil))

	if delW.Code != http.StatusNoContent {
		t.Fatalf("expected 204, got %d: %s", delW.Code, delW.Body.String())
	}

	// Liste pruefen: leer
	getW := httptest.NewRecorder()
	r.ServeHTTP(getW, httptest.NewRequest("GET", "/api/metric-presets", nil))
	var presets []model.MetricPreset
	json.Unmarshal(getW.Body.Bytes(), &presets)
	if len(presets) != 0 {
		t.Fatalf("expected empty list after delete, got %d", len(presets))
	}
}

func TestDeleteMetricPreset_NotFound(t *testing.T) {
	s := newTestStore(t)

	r := chi.NewRouter()
	r.Delete("/api/metric-presets/{id}", DeleteMetricPresetHandler(s))

	w := httptest.NewRecorder()
	r.ServeHTTP(w, httptest.NewRequest("DELETE", "/api/metric-presets/nonexistent-id", nil))

	if w.Code != http.StatusNotFound {
		t.Fatalf("expected 404, got %d", w.Code)
	}
}

// =============================================================================
// Store: LoadMetricPresets gibt leeren Slice zurueck wenn Datei nicht existiert
// =============================================================================

func TestStore_LoadMetricPresets_EmptyWhenNoFile(t *testing.T) {
	s := newTestStore(t)

	presets, err := s.LoadMetricPresets()
	if err != nil {
		t.Fatalf("LoadMetricPresets should not error when file missing: %v", err)
	}
	if presets == nil {
		t.Fatal("LoadMetricPresets must return non-nil slice (empty, not nil)")
	}
	if len(presets) != 0 {
		t.Fatalf("expected empty slice, got %d entries", len(presets))
	}
}

// =============================================================================
// Issue #342 — PATCH /api/metric-presets/{id}: Read-Modify-Write
// Spec: docs/specs/modules/issue_342_pro_metrik_horizon_backend.md §4, AC-5
//
// Tests scheitern absichtlich (RED): PatchMetricPresetHandler existiert noch
// nicht. Bei `go test` → undefined: handler.PatchMetricPresetHandler.
// =============================================================================

// TestPatchMetricPreset_NameOnly (AC-5)
//
// Given: bestehendes Preset {Name: "Original", Metrics: [wind enabled],
//        IsDefault: false}.
// When:  PATCH /api/metric-presets/{id} mit Body {"name": "Umbenannt"}.
// Then:  HTTP 200, Response hat Name="Umbenannt", Metrics & IsDefault
//        & CreatedAt unverändert. GET zeigt persistierten Zustand.
func TestPatchMetricPreset_NameOnly(t *testing.T) {
	s := newTestStore(t)

	r := chi.NewRouter()
	r.Get("/api/metric-presets", ListMetricPresetsHandler(s))
	r.Post("/api/metric-presets", CreateMetricPresetHandler(s))
	r.Patch("/api/metric-presets/{id}", PatchMetricPresetHandler(s))

	// 1. Preset via POST anlegen.
	createBody := map[string]interface{}{
		"name":       "Original",
		"metrics":    []map[string]interface{}{{"metric_id": "wind", "enabled": true}},
		"is_default": false,
	}
	createBytes, _ := json.Marshal(createBody)
	postW := httptest.NewRecorder()
	r.ServeHTTP(postW, withBody(t, "POST", "/api/metric-presets", createBytes))
	if postW.Code != http.StatusCreated {
		t.Fatalf("POST failed: %d %s", postW.Code, postW.Body.String())
	}
	var created model.MetricPreset
	if err := json.Unmarshal(postW.Body.Bytes(), &created); err != nil {
		t.Fatalf("failed to parse POST response: %v", err)
	}
	originalMetrics := created.Metrics
	originalCreatedAt := created.CreatedAt

	// 2. PATCH nur den Name.
	patchBody := map[string]interface{}{"name": "Umbenannt"}
	patchBytes, _ := json.Marshal(patchBody)
	patchW := httptest.NewRecorder()
	r.ServeHTTP(patchW, withBody(t, "PATCH", "/api/metric-presets/"+created.ID, patchBytes))

	if patchW.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", patchW.Code, patchW.Body.String())
	}

	var patched model.MetricPreset
	if err := json.Unmarshal(patchW.Body.Bytes(), &patched); err != nil {
		t.Fatalf("failed to parse PATCH response: %v", err)
	}

	if patched.Name != "Umbenannt" {
		t.Errorf("expected Name=Umbenannt, got %q", patched.Name)
	}
	if patched.IsDefault != false {
		t.Errorf("IsDefault changed unexpectedly: got %v", patched.IsDefault)
	}
	if !patched.CreatedAt.Equal(originalCreatedAt) {
		t.Errorf("CreatedAt changed: got %v want %v", patched.CreatedAt, originalCreatedAt)
	}
	if !reflect.DeepEqual(patched.Metrics, originalMetrics) {
		t.Errorf("Metrics changed unexpectedly:\ngot:  %#v\nwant: %#v",
			patched.Metrics, originalMetrics)
	}

	// 3. GET zeigt persistierten Zustand.
	getW := httptest.NewRecorder()
	r.ServeHTTP(getW, httptest.NewRequest("GET", "/api/metric-presets", nil))
	var list []model.MetricPreset
	json.Unmarshal(getW.Body.Bytes(), &list)
	if len(list) != 1 {
		t.Fatalf("expected 1 preset after PATCH, got %d", len(list))
	}
	if list[0].Name != "Umbenannt" {
		t.Errorf("persisted Name=%q, expected Umbenannt", list[0].Name)
	}
	if !reflect.DeepEqual(list[0].Metrics, originalMetrics) {
		t.Errorf("persisted Metrics changed:\ngot:  %#v\nwant: %#v",
			list[0].Metrics, originalMetrics)
	}
}

// TestPatchMetricPreset_NotFound
//
// PATCH auf nicht-existierende ID → HTTP 404.
func TestPatchMetricPreset_NotFound(t *testing.T) {
	s := newTestStore(t)

	r := chi.NewRouter()
	r.Patch("/api/metric-presets/{id}", PatchMetricPresetHandler(s))

	patchBytes, _ := json.Marshal(map[string]interface{}{"name": "X"})
	w := httptest.NewRecorder()
	r.ServeHTTP(w, withBody(t, "PATCH", "/api/metric-presets/nonexistent-id", patchBytes))

	if w.Code != http.StatusNotFound {
		t.Fatalf("expected 404, got %d: %s", w.Code, w.Body.String())
	}
}

// TestPatchMetricPreset_IsDefaultExclusive
//
// Zwei Presets A und B (beide is_default=false).
// 1. PATCH B mit {is_default: true} → B=true, A=false.
// 2. PATCH A mit {is_default: true} → A=true, B=false (exklusiver Default).
func TestPatchMetricPreset_IsDefaultExclusive(t *testing.T) {
	s := newTestStore(t)

	r := chi.NewRouter()
	r.Get("/api/metric-presets", ListMetricPresetsHandler(s))
	r.Post("/api/metric-presets", CreateMetricPresetHandler(s))
	r.Patch("/api/metric-presets/{id}", PatchMetricPresetHandler(s))

	createPreset := func(name string) model.MetricPreset {
		body := map[string]interface{}{
			"name":       name,
			"metrics":    []map[string]interface{}{{"metric_id": "wind", "enabled": true}},
			"is_default": false,
		}
		b, _ := json.Marshal(body)
		w := httptest.NewRecorder()
		r.ServeHTTP(w, withBody(t, "POST", "/api/metric-presets", b))
		if w.Code != http.StatusCreated {
			t.Fatalf("create %s failed: %d %s", name, w.Code, w.Body.String())
		}
		var p model.MetricPreset
		json.Unmarshal(w.Body.Bytes(), &p)
		return p
	}

	a := createPreset("Preset A")
	b := createPreset("Preset B")

	loadList := func() []model.MetricPreset {
		w := httptest.NewRecorder()
		r.ServeHTTP(w, httptest.NewRequest("GET", "/api/metric-presets", nil))
		var list []model.MetricPreset
		json.Unmarshal(w.Body.Bytes(), &list)
		return list
	}

	patchDefault := func(id string) {
		body, _ := json.Marshal(map[string]interface{}{"is_default": true})
		w := httptest.NewRecorder()
		r.ServeHTTP(w, withBody(t, "PATCH", "/api/metric-presets/"+id, body))
		if w.Code != http.StatusOK {
			t.Fatalf("PATCH %s failed: %d %s", id, w.Code, w.Body.String())
		}
	}

	defaultByID := func(list []model.MetricPreset) map[string]bool {
		out := map[string]bool{}
		for _, p := range list {
			out[p.ID] = p.IsDefault
		}
		return out
	}

	// 1. B auf default setzen.
	patchDefault(b.ID)
	got := defaultByID(loadList())
	if !got[b.ID] {
		t.Errorf("after PATCH B: B.IsDefault should be true, got false")
	}
	if got[a.ID] {
		t.Errorf("after PATCH B: A.IsDefault should be false, got true")
	}

	// 2. A auf default setzen → B muss zurück auf false.
	patchDefault(a.ID)
	got = defaultByID(loadList())
	if !got[a.ID] {
		t.Errorf("after PATCH A: A.IsDefault should be true, got false")
	}
	if got[b.ID] {
		t.Errorf("after PATCH A: B.IsDefault should be false, got true")
	}
}

// =============================================================================
// Bug #350 (AC-3) — korrupte Preset-Datei darf bei POST nicht überschrieben werden.
// RED: aktuell schluckt LoadMetricPresets den JSON-Fehler (store.go:349) und gibt
// ([], nil) zurück → der Handler läuft durch, SaveMetricPresets überschreibt die
// korrupte Datei mit nur dem neuen Preset → Datenverlust.
// =============================================================================

// TestCreateMetricPreset_CorruptFileNotOverwritten (AC-3)
//
// Given: eine korrupte metric_presets.json (ungültiges JSON) auf der Platte.
// When:  POST /api/metric-presets ein neues Preset anlegen will.
// Then:  Der Handler antwortet 500 store_error UND die Datei auf der Platte
//        bleibt byte-gleich (wird nicht mit der leeren Liste überschrieben).
func TestCreateMetricPreset_CorruptFileNotOverwritten(t *testing.T) {
	tmpDir := t.TempDir()
	s := store.New(tmpDir, "test")

	presetsPath := filepath.Join(tmpDir, "users", "test", "metric_presets.json")
	if err := os.MkdirAll(filepath.Dir(presetsPath), 0755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	corrupt := []byte(`{kaputt — nicht-valides json`)
	if err := os.WriteFile(presetsPath, corrupt, 0644); err != nil {
		t.Fatalf("write corrupt: %v", err)
	}

	r := chi.NewRouter()
	r.Post("/api/metric-presets", CreateMetricPresetHandler(s))

	body, _ := json.Marshal(map[string]interface{}{
		"name":    "Neu",
		"metrics": []string{"wind"},
	})
	req := httptest.NewRequest("POST", "/api/metric-presets", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusInternalServerError {
		t.Errorf("expected 500 on corrupt presets file, got %d: %s", w.Code, w.Body.String())
	}

	after, err := os.ReadFile(presetsPath)
	if err != nil {
		t.Fatalf("read after: %v", err)
	}
	if !bytes.Equal(after, corrupt) {
		t.Errorf("corrupt presets file was overwritten — Datenverlust!\nvorher: %s\nnachher: %s", corrupt, after)
	}
}

// =============================================================================
// Bug #349 — normalizeMetricsPayload Horizons-Zero-Value-Unterscheidung.
// Spec: docs/specs/modules/bug_349_horizons_zero_value.md
//
// AC-1 (RED): Ein explizit gesendetes horizons={false,false,false} darf NICHT
// von der Default-Heuristik mit {true,true,true} ueberschrieben werden.
// AC-2: Fehlt horizons im JSON, gilt der Default {true,true,true}.
// AC-3: Teilweise gesetzte horizons werden exakt uebernommen.
// =============================================================================

func TestNormalizeMetricsPayload_ExplicitAllFalse_Preserved(t *testing.T) {
	raw := json.RawMessage(`[{"metric_id":"wind","enabled":true,"horizons":{"today":false,"tomorrow":false,"day_after":false}}]`)
	got := normalizeMetricsPayload(raw, nil)
	if len(got) != 1 {
		t.Fatalf("expected 1 entry, got %d", len(got))
	}
	h := got[0].Horizons
	if h.Today || h.Tomorrow || h.DayAfter {
		t.Errorf("AC-1 FAIL: explizit alle-false horizons wurden mit alle-true ueberschrieben: got Today=%v Tomorrow=%v DayAfter=%v",
			h.Today, h.Tomorrow, h.DayAfter)
	}
}

func TestNormalizeMetricsPayload_MissingHorizons_DefaultsAllTrue(t *testing.T) {
	raw := json.RawMessage(`[{"metric_id":"wind","enabled":true}]`)
	got := normalizeMetricsPayload(raw, nil)
	if len(got) != 1 {
		t.Fatalf("expected 1 entry, got %d", len(got))
	}
	h := got[0].Horizons
	if !h.Today || !h.Tomorrow || !h.DayAfter {
		t.Errorf("AC-2 FAIL: fehlende horizons sollten Default {true,true,true} liefern, got Today=%v Tomorrow=%v DayAfter=%v",
			h.Today, h.Tomorrow, h.DayAfter)
	}
}

func TestNormalizeMetricsPayload_PartialHorizons_ExactValuePreserved(t *testing.T) {
	raw := json.RawMessage(`[{"metric_id":"wind","enabled":true,"horizons":{"today":true,"tomorrow":false,"day_after":false}}]`)
	got := normalizeMetricsPayload(raw, nil)
	if len(got) != 1 {
		t.Fatalf("expected 1 entry, got %d", len(got))
	}
	h := got[0].Horizons
	if !h.Today || h.Tomorrow || h.DayAfter {
		t.Errorf("AC-3 FAIL: teilweise gesetzte horizons wurden modifiziert: got Today=%v Tomorrow=%v DayAfter=%v want Today=true Tomorrow=false DayAfter=false",
			h.Today, h.Tomorrow, h.DayAfter)
	}
}

// =============================================================================
// Bug #350 (AC-1) — LoadMetricPresets gibt Fehler bei korruptem JSON zurück.
// Issue #540: Fehlender direkter Test für AC-1.
// =============================================================================

// TestStore_LoadMetricPresets_CorruptJSON (AC-1)
//
// Given: eine korrupte metric_presets.json (ungültiges JSON) auf der Platte.
// When:  s.LoadMetricPresets() aufgerufen wird.
// Then:  Rückgabe ist (nil, error) — kein stilles Schlucken des Fehlers.
func TestStore_LoadMetricPresets_CorruptJSON(t *testing.T) {
	tmpDir := t.TempDir()
	s := store.New(tmpDir, "test")

	presetsPath := filepath.Join(tmpDir, "users", "test", "metric_presets.json")
	if err := os.MkdirAll(filepath.Dir(presetsPath), 0755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	if err := os.WriteFile(presetsPath, []byte(`{kaputt — nicht-valides json`), 0644); err != nil {
		t.Fatalf("write corrupt file: %v", err)
	}

	presets, err := s.LoadMetricPresets()
	if err == nil {
		t.Fatal("LoadMetricPresets sollte bei korruptem JSON einen Fehler liefern, hat aber nil")
	}
	if presets != nil {
		t.Errorf("LoadMetricPresets sollte bei Fehler nil zurückgeben, hat aber %v", presets)
	}
}

// =============================================================================
// Helpers
// =============================================================================

func withBody(t *testing.T, method, path string, body []byte) *http.Request {
	t.Helper()
	req := httptest.NewRequest(method, path, bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	return req
}
