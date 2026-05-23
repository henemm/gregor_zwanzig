package handler

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/go-chi/chi/v5"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

// TDD RED: Issue #341 — Group-CRUD-Handler + PatchLocationHandler.
// Spec: docs/specs/modules/issue_341_group_backend.md §5/§6
//
// Referenziert handler.GroupsHandler/CreateGroupHandler/UpdateGroupHandler/
// DeleteGroupHandler/PatchLocationHandler sowie model.Group und
// model.Location.GroupID — in RED existiert nichts davon → Paket kompiliert
// nicht → alle Tests rot.

func sptr(s string) *string { return &s }

// AC-1: GET /api/groups liefert nach Order sortiert.
func TestGroupsHandler_ReturnsSortedByOrder(t *testing.T) {
	s := store.New(t.TempDir(), "default")
	s.ProvisionUserDirs("default")
	s.SaveGroup(model.Group{ID: "b", Name: "B", Order: 2})
	s.SaveGroup(model.Group{ID: "a", Name: "A", Order: 1})

	r := chi.NewRouter()
	r.Get("/api/groups", GroupsHandler(s))

	req := httptest.NewRequest(http.MethodGet, "/api/groups", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
	var groups []model.Group
	if err := json.Unmarshal(w.Body.Bytes(), &groups); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if len(groups) != 2 {
		t.Fatalf("expected 2 groups, got %d", len(groups))
	}
	if groups[0].Order > groups[1].Order {
		t.Errorf("not sorted by order: %+v", groups)
	}
}

// AC-2: POST /api/groups ohne id → id aus Name (kebab), order automatisch, 201.
func TestCreateGroupHandler_AutoIDAndOrder(t *testing.T) {
	s := store.New(t.TempDir(), "default")
	s.ProvisionUserDirs("default")

	r := chi.NewRouter()
	r.Post("/api/groups", CreateGroupHandler(s))

	body, _ := json.Marshal(map[string]string{"name": "Skigebiete Tirol"})
	req := httptest.NewRequest(http.MethodPost, "/api/groups", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusCreated {
		t.Fatalf("expected 201, got %d: %s", w.Code, w.Body.String())
	}
	var g model.Group
	json.Unmarshal(w.Body.Bytes(), &g)
	if g.ID == "" {
		t.Error("expected auto-generated id")
	}
	if g.Name != "Skigebiete Tirol" {
		t.Errorf("name: %q", g.Name)
	}
}

// AC-2 negativ: fehlender Name → 400.
func TestCreateGroupHandler_MissingNameIsBadRequest(t *testing.T) {
	s := store.New(t.TempDir(), "default")
	s.ProvisionUserDirs("default")

	r := chi.NewRouter()
	r.Post("/api/groups", CreateGroupHandler(s))

	body, _ := json.Marshal(map[string]string{})
	req := httptest.NewRequest(http.MethodPost, "/api/groups", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d", w.Code)
	}
}

// AC-3: PATCH /api/groups/{id} ändert nur gesendete Felder, Rest bleibt erhalten.
func TestUpdateGroupHandler_MergesOnlyProvidedFields(t *testing.T) {
	s := store.New(t.TempDir(), "default")
	s.ProvisionUserDirs("default")
	s.SaveGroup(model.Group{ID: "ski", Name: "Ski", DefaultProfile: sptr("wintersport"), Order: 3})

	r := chi.NewRouter()
	r.Patch("/api/groups/{id}", UpdateGroupHandler(s))

	body, _ := json.Marshal(map[string]string{"name": "Ski Tirol"})
	req := httptest.NewRequest(http.MethodPatch, "/api/groups/ski", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
	var g model.Group
	json.Unmarshal(w.Body.Bytes(), &g)
	if g.Name != "Ski Tirol" {
		t.Errorf("name not updated: %q", g.Name)
	}
	if g.DefaultProfile == nil || *g.DefaultProfile != "wintersport" {
		t.Errorf("default_profile not preserved: %v", g.DefaultProfile)
	}
	if g.Order != 3 {
		t.Errorf("order not preserved: %d", g.Order)
	}
}

// AC-3 not found.
func TestUpdateGroupHandler_NotFound(t *testing.T) {
	s := store.New(t.TempDir(), "default")
	s.ProvisionUserDirs("default")

	r := chi.NewRouter()
	r.Patch("/api/groups/{id}", UpdateGroupHandler(s))

	body, _ := json.Marshal(map[string]string{"name": "X"})
	req := httptest.NewRequest(http.MethodPatch, "/api/groups/ghost", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusNotFound {
		t.Errorf("expected 404, got %d", w.Code)
	}
}

// AC-4: DELETE /api/groups/{id} setzt group_id der Mitglieder auf null, ohne andere Felder zu verlieren.
func TestDeleteGroupHandler_NullsMemberLocationGroupID(t *testing.T) {
	s := store.New(t.TempDir(), "default")
	s.ProvisionUserDirs("default")
	gid := "ski"
	s.SaveGroup(model.Group{ID: gid, Name: "Ski", Order: 0})
	s.SaveLocation(model.Location{ID: "stubai", Name: "Stubai", Lat: 47, Lon: 11, GroupID: &gid})
	s.SaveLocation(model.Location{ID: "tux", Name: "Tux", Lat: 47, Lon: 11, GroupID: &gid})

	r := chi.NewRouter()
	r.Delete("/api/groups/{id}", DeleteGroupHandler(s))

	req := httptest.NewRequest(http.MethodDelete, "/api/groups/ski", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusNoContent {
		t.Fatalf("expected 204, got %d", w.Code)
	}
	for _, id := range []string{"stubai", "tux"} {
		loc, _ := s.LoadLocation(id)
		if loc == nil {
			t.Fatalf("location %s vanished", id)
		}
		if loc.GroupID != nil {
			t.Errorf("location %s still has group_id %v", id, *loc.GroupID)
		}
		if loc.Name == "" {
			t.Errorf("location %s lost name", id)
		}
	}
}

// AC-5: PATCH /api/locations/{id} setzt/nullt group_id ohne andere Felder zu verlieren.
func TestPatchLocationHandler_SetAndNullGroupID(t *testing.T) {
	s := store.New(t.TempDir(), "default")
	s.ProvisionUserDirs("default")
	s.SaveLocation(model.Location{ID: "loc1", Name: "Loc One", Lat: 47.5, Lon: 11.5, ActivityProfile: sptr("wandern")})

	r := chi.NewRouter()
	r.Patch("/api/locations/{id}", PatchLocationHandler(s))

	// group_id setzen
	body, _ := json.Marshal(map[string]string{"group_id": "ski-tirol"})
	req := httptest.NewRequest(http.MethodPatch, "/api/locations/loc1", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("set: expected 200, got %d: %s", w.Code, w.Body.String())
	}
	loc, _ := s.LoadLocation("loc1")
	if loc.GroupID == nil || *loc.GroupID != "ski-tirol" {
		t.Fatalf("group_id not set: %v", loc.GroupID)
	}
	if loc.Name != "Loc One" || loc.Lat != 47.5 {
		t.Errorf("other fields changed: %+v", loc)
	}
	if loc.ActivityProfile == nil || *loc.ActivityProfile != "wandern" {
		t.Errorf("activity_profile lost: %v", loc.ActivityProfile)
	}

	// group_id nullen (ent-gruppieren)
	req2 := httptest.NewRequest(http.MethodPatch, "/api/locations/loc1", bytes.NewReader([]byte(`{"group_id":null}`)))
	req2.Header.Set("Content-Type", "application/json")
	w2 := httptest.NewRecorder()
	r.ServeHTTP(w2, req2)
	if w2.Code != http.StatusOK {
		t.Fatalf("null: expected 200, got %d", w2.Code)
	}
	loc2, _ := s.LoadLocation("loc1")
	if loc2.GroupID != nil {
		t.Errorf("group_id not nulled: %v", *loc2.GroupID)
	}
	if loc2.Name != "Loc One" {
		t.Errorf("name lost after null patch: %q", loc2.Name)
	}
}

// AC-5 not found.
func TestPatchLocationHandler_NotFound(t *testing.T) {
	s := store.New(t.TempDir(), "default")
	s.ProvisionUserDirs("default")

	r := chi.NewRouter()
	r.Patch("/api/locations/{id}", PatchLocationHandler(s))

	req := httptest.NewRequest(http.MethodPatch, "/api/locations/ghost", bytes.NewReader([]byte(`{"group_id":"x"}`)))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusNotFound {
		t.Errorf("expected 404, got %d", w.Code)
	}
}

// Compile-time: model.Group hat id, name, default_profile, order.
func TestGroupModelHasFields(t *testing.T) {
	g := model.Group{ID: "x", Name: "X", DefaultProfile: sptr("wintersport"), Order: 5}
	if g.ID != "x" || g.Name != "X" || g.Order != 5 || *g.DefaultProfile != "wintersport" {
		t.Errorf("unexpected group: %+v", g)
	}
}
