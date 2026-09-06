package handler

import (
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"

	"github.com/henemm/gregor-api/internal/middleware"
)

// TDD RED: Tests for account deletion — must FAIL until implemented.

func TestDeleteAccountSuccess(t *testing.T) {
	s := newTestStore(t)

	// Create user with data directories
	dir := filepath.Join(s.DataDir, "users", "alice")
	os.MkdirAll(filepath.Join(dir, "locations"), 0755)
	os.MkdirAll(filepath.Join(dir, "trips"), 0755)
	os.WriteFile(filepath.Join(dir, "user.json"), []byte(`{"id":"alice","password_hash":"x"}`), 0644)
	os.WriteFile(filepath.Join(dir, "locations", "loc1.json"), []byte(`{"id":"loc1"}`), 0644)

	h := DeleteAccountHandler(s)

	req := httptest.NewRequest("DELETE", "/api/auth/account", nil)
	ctx := middleware.ContextWithUserID(req.Context(), "alice")
	req = req.WithContext(ctx)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	// User directory should be completely gone
	if _, err := os.Stat(dir); !os.IsNotExist(err) {
		t.Error("user directory should be deleted")
	}
}

func TestDeleteAccountClearsCookie(t *testing.T) {
	s := newTestStore(t)
	dir := filepath.Join(s.DataDir, "users", "bob")
	os.MkdirAll(dir, 0755)
	os.WriteFile(filepath.Join(dir, "user.json"), []byte(`{"id":"bob","password_hash":"x"}`), 0644)

	h := DeleteAccountHandler(s)

	req := httptest.NewRequest("DELETE", "/api/auth/account", nil)
	req.AddCookie(&http.Cookie{Name: "gz_session", Value: "bob.123.sig"})
	ctx := middleware.ContextWithUserID(req.Context(), "bob")
	req = req.WithContext(ctx)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d", w.Code)
	}

	// Cookie should be cleared
	found := false
	for _, c := range w.Result().Cookies() {
		if c.Name == "gz_session" && c.MaxAge == -1 {
			found = true
		}
	}
	if !found {
		t.Error("gz_session cookie should be cleared")
	}

	// Issue #2129: die Gaesteliste liegt IM Nutzerordner und ist mit dem Konto
	// verschwunden. Das ersetzt die abgeloeste prozesslokale Sperrliste und
	// wirkt anders als diese auch nach einem Dienst-Neustart.
	if sessions, err := s.LoadSessions("bob"); err != nil || len(sessions) != 0 {
		t.Errorf("Gaesteliste muss nach der Kontoloeschung leer sein, sind %d (err=%v)",
			len(sessions), err)
	}
}

func TestDeleteAccountUserNotFound(t *testing.T) {
	s := newTestStore(t)
	h := DeleteAccountHandler(s)

	req := httptest.NewRequest("DELETE", "/api/auth/account", nil)
	ctx := middleware.ContextWithUserID(req.Context(), "nobody")
	req = req.WithContext(ctx)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 404 {
		t.Fatalf("expected 404, got %d", w.Code)
	}
}
