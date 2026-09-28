package handler

// TDD RED — Issue #2155 Scheibe S1 (Admin-Rolle), AC-8 + AC-9.
//
// Spec: docs/specs/modules/admin_rolle_s1.md § "5. Profil-role"
//
// Scheitert heute beim Uebersetzen: GetProfileHandler kennt die Admin-Menge
// noch nicht (Spec: zusaetzlicher Parameter `admins map[string]struct{}`).
//
// HINWEIS FUER /50-implement: die neue Signatur
//   GetProfileHandler(s *store.Store, admins map[string]struct{})
// zwingt dazu, ALLE bestehenden Aufrufe in internal/handler/*_test.go
// (rund 27 Stellen, z. B. auth_tier_change_test.go) mit `nil` als zweitem
// Argument nachzuziehen — das ist mechanisch und gehoert in den Fix-Commit.
//
// Echter Store auf t.TempDir(), echte Handler; die Rolle wird ueber die
// Antwort UND ueber die Bytes der user.json geprueft.

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

func rolleTestStore(t *testing.T) (*store.Store, string) {
	t.Helper()
	dir := t.TempDir()
	s := store.New(dir, "test")
	for _, id := range []string{"alice", "bob"} {
		if err := s.SaveUser(model.User{ID: id, CreatedAt: time.Now()}); err != nil {
			t.Fatalf("SaveUser %s: %v", id, err)
		}
	}
	return s, dir
}

func alsNutzer(req *http.Request, id string) *http.Request {
	return req.WithContext(middleware.ContextWithUserID(req.Context(), id))
}

func profilRolle(t *testing.T, h http.Handler, id string) string {
	t.Helper()
	req := alsNutzer(httptest.NewRequest(http.MethodGet, "/api/auth/profile", nil), id)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("GET profile (%s): erwartet 200, bekommen %d: %s", id, w.Code, w.Body.String())
	}
	var body map[string]any
	if err := json.Unmarshal(w.Body.Bytes(), &body); err != nil {
		t.Fatalf("GET profile (%s): kein JSON: %v", id, err)
	}
	role, ok := body["role"].(string)
	if !ok {
		t.Fatalf("GET profile (%s): Feld role fehlt oder ist kein Text: %v", id, body["role"])
	}
	return role
}

// AC-8: Zwei-Nutzer-Test mit echtem Store.
func TestProfile_Role_AdminAndUser(t *testing.T) {
	s, _ := rolleTestStore(t)
	h := GetProfileHandler(s, config.ParseAdminUserIDs("alice"))

	if got := profilRolle(t, h, "alice"); got != "admin" {
		t.Errorf("alice: erwartet role=admin, bekommen %q", got)
	}
	if got := profilRolle(t, h, "bob"); got != "user" {
		t.Errorf("bob: erwartet role=user, bekommen %q", got)
	}
}

// Fail-closed im Profil: ohne Admin-Menge ist jeder "user".
func TestProfile_Role_NoAdminList_EveryoneIsUser(t *testing.T) {
	s, _ := rolleTestStore(t)
	h := GetProfileHandler(s, config.ParseAdminUserIDs(""))

	for _, id := range []string{"alice", "bob"} {
		if got := profilRolle(t, h, id); got != "user" {
			t.Errorf("%s: erwartet role=user, bekommen %q", id, got)
		}
	}
}

// Die Rolle wird NIE aus der gespeicherten user.json gelesen: selbst ein dort
// eingeschmuggeltes "role":"admin" macht bob nicht zum Admin.
func TestProfile_Role_NeverReadFromStoredUserJSON(t *testing.T) {
	s, dir := rolleTestStore(t)
	pfad := filepath.Join(dir, "users", "bob", "user.json")
	if err := os.WriteFile(pfad, []byte(`{"id":"bob","role":"admin"}`), 0o644); err != nil {
		t.Fatalf("user.json praeparieren: %v", err)
	}
	h := GetProfileHandler(s, config.ParseAdminUserIDs("alice"))

	if got := profilRolle(t, h, "bob"); got != "user" {
		t.Fatalf("bob mit eingeschmuggeltem role in user.json: erwartet role=user, bekommen %q", got)
	}
}

// AC-9: PUT mit role=admin wird ignoriert und nicht gespeichert.
func TestProfile_PutWithRole_IsIgnored_NotStored_TriggerStaysForbidden(t *testing.T) {
	s, dir := rolleTestStore(t)
	admins := config.ParseAdminUserIDs("alice")
	get := GetProfileHandler(s, admins)
	put := UpdateProfileHandler(s, config.Config{}, NewMailFloodLimiter(3, time.Hour), NewMailFloodLimiter(3, time.Hour))

	// Ein echter Schreibvorgang (display_name) plus das eingeschmuggelte Feld.
	body, _ := json.Marshal(map[string]any{"display_name": "Bob", "role": "admin"})
	req := alsNutzer(httptest.NewRequest(http.MethodPut, "/api/auth/profile", bytes.NewReader(body)), "bob")
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	put.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("PUT profile: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}

	// 1) Der Schreibvorgang hat wirklich stattgefunden (sonst beweist der Rest nichts).
	rohe, err := os.ReadFile(filepath.Join(dir, "users", "bob", "user.json"))
	if err != nil {
		t.Fatalf("user.json lesen: %v", err)
	}
	var gespeichert map[string]any
	if err := json.Unmarshal(rohe, &gespeichert); err != nil {
		t.Fatalf("user.json kein JSON: %v", err)
	}
	if gespeichert["display_name"] != "Bob" {
		t.Fatalf("Vorbedingung: display_name muss gespeichert sein, user.json=%s", rohe)
	}

	// 2) Kein role-Schluessel in der gespeicherten user.json.
	if _, hat := gespeichert["role"]; hat {
		t.Errorf("user.json darf kein Feld role enthalten, ist aber: %s", rohe)
	}

	// 3) Profil zeigt weiter "user".
	if got := profilRolle(t, get, "bob"); got != "user" {
		t.Errorf("nach PUT mit role=admin: erwartet role=user, bekommen %q", got)
	}

	// 4) Die Betriebs-Trigger bleiben fuer bob gesperrt (Middleware mit derselben Menge).
	aufrufe := 0
	geschuetzt := middleware.RequireAdmin(admins)(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		aufrufe++
	}))
	treq := alsNutzer(httptest.NewRequest(http.MethodPost, "/api/scheduler/trip-reports", nil), "bob")
	tw := httptest.NewRecorder()
	geschuetzt.ServeHTTP(tw, treq)
	if tw.Code != http.StatusForbidden || aufrufe != 0 {
		t.Errorf("bob nach PUT mit role=admin: Trigger erwartet 403 ohne Handler-Aufruf, bekommen %d / %d Aufrufe", tw.Code, aufrufe)
	}
}
