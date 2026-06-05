package handler

// Issue #611 — Compare-Preset Archiv-State (PATCH /api/compare/presets/{id}/state).
//
// Mock-frei: echte Store-Instanz (newTestStore) + httptest. Kein Mock/patch.
//
// AC-6/AC-8: archived=true setzt archived_at (read-modify-write, andere Felder
// unberührt); archived=false setzt es auf null. 404 bei unbekannter ID.

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/go-chi/chi/v5"
	"github.com/henemm/gregor-api/internal/model"
)

// seedPreset legt ein Preset über den echten Create-Handler an und liefert dessen ID.
func seedPreset(t *testing.T, s storeForTest, r *chi.Mux) string {
	t.Helper()
	req := httptest.NewRequest("POST", "/api/compare/presets", jsonBody(t, validPresetBody()))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "user1")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	if w.Code != http.StatusCreated {
		t.Fatalf("seed: expected 201, got %d: %s", w.Code, w.Body.String())
	}
	var created model.ComparePreset
	if err := json.Unmarshal(w.Body.Bytes(), &created); err != nil {
		t.Fatalf("seed unmarshal: %v", err)
	}
	return created.ID
}

func TestUpdateComparePresetState_ArchiveAndReactivate(t *testing.T) {
	s := newTestStore(t)
	r := chi.NewRouter()
	r.Post("/api/compare/presets", CreateComparePresetHandler(s))
	r.Patch("/api/compare/presets/{id}/state", UpdateComparePresetStateHandler(s))
	r.Get("/api/compare/presets/{id}", GetComparePresetHandler(s))

	id := seedPreset(t, nil, r)

	// archived=true → archived_at gesetzt
	patch := func(body string) *httptest.ResponseRecorder {
		req := httptest.NewRequest("PATCH", "/api/compare/presets/"+id+"/state", bytes.NewReader([]byte(body)))
		req.Header.Set("Content-Type", "application/json")
		req = addUserToContext(req, "user1")
		w := httptest.NewRecorder()
		r.ServeHTTP(w, req)
		return w
	}

	w := patch(`{"archived":true}`)
	if w.Code != http.StatusOK {
		t.Fatalf("archive: expected 200, got %d: %s", w.Code, w.Body.String())
	}
	var p model.ComparePreset
	if err := json.Unmarshal(w.Body.Bytes(), &p); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if p.ArchivedAt == nil {
		t.Fatalf("expected archived_at set after archive=true")
	}
	// andere Felder unberührt
	if p.Name != "Zillertal vs. Stubai" || len(p.LocationIDs) != 2 {
		t.Fatalf("read-modify-write broke other fields: %+v", p)
	}

	// archived=false → archived_at == null. Fresh var, weil omitempty das Feld
	// im Response weglässt und json.Unmarshal vorhandene Felder nicht zurücksetzt.
	w = patch(`{"archived":false}`)
	if w.Code != http.StatusOK {
		t.Fatalf("reactivate: expected 200, got %d: %s", w.Code, w.Body.String())
	}
	var p2 model.ComparePreset
	if err := json.Unmarshal(w.Body.Bytes(), &p2); err != nil {
		t.Fatalf("unmarshal2: %v", err)
	}
	if p2.ArchivedAt != nil {
		t.Fatalf("expected archived_at nil after archive=false, got %v", p2.ArchivedAt)
	}
}

func TestUpdateComparePresetState_NotFound(t *testing.T) {
	s := newTestStore(t)
	r := chi.NewRouter()
	r.Patch("/api/compare/presets/{id}/state", UpdateComparePresetStateHandler(s))

	req := httptest.NewRequest("PATCH", "/api/compare/presets/does-not-exist/state",
		bytes.NewReader([]byte(`{"archived":true}`)))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "user1")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusNotFound {
		t.Fatalf("expected 404, got %d: %s", w.Code, w.Body.String())
	}
}

// Schema-Roundtrip: ComparePreset-JSON OHNE archived_at lädt fehlerfrei und
// serialisiert ohne null-Feld (additiv + omitempty).
func TestComparePresetRoundTrip_ArchivedAtOptional(t *testing.T) {
	// ohne archived_at
	legacy := []byte(`{"id":"cp-x","name":"Alt","schedule":"manual","profil":"ALLGEMEIN","hour_from":6,"hour_to":18}`)
	var p model.ComparePreset
	if err := json.Unmarshal(legacy, &p); err != nil {
		t.Fatalf("legacy unmarshal failed: %v", err)
	}
	if p.ArchivedAt != nil {
		t.Fatalf("expected nil archived_at for legacy preset")
	}
	out, err := json.Marshal(p)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	var got map[string]any
	if err := json.Unmarshal(out, &got); err != nil {
		t.Fatalf("re-unmarshal: %v", err)
	}
	if _, exists := got["archived_at"]; exists {
		t.Fatalf("archived_at should be omitted when nil, got %v", got["archived_at"])
	}
}

// storeForTest is unused alias to keep the seedPreset signature explicit; the
// real store comes from the router closure.
type storeForTest = interface{}
