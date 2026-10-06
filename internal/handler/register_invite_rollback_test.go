package handler

// F003: scheitert SaveUser nach der Reservierung, wird die Einladung
// zurueckgerollt (bleibt offen). Root-sicher: users/<id> wird als DATEI
// vorbelegt, so scheitert MkdirAll in SaveUser ohne chmod.

import (
	"bytes"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"

	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/store"
)

func TestRegisterMitEinladung_SaveUserScheitert_EinladungBleibtOffen(t *testing.T) {
	dir := t.TempDir()
	s := store.New(dir, "test")
	inv := store.NewInviteStore(t.TempDir())
	_, token, _ := inv.Create("premium", "", "admin")
	if err := os.MkdirAll(filepath.Join(dir, "users"), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(s.UserDir("blockiert"), []byte("x"), 0o644); err != nil {
		t.Fatal(err)
	}
	h := RegisterHandlerWithInvites(s, bcrypt.MinCost, config.Config{}, inv)
	body := `{"username":"blockiert","password":"geheim-pw-123","email":"b@example.org","invite":"` + token + `"}`
	w := httptest.NewRecorder()
	h.ServeHTTP(w, httptest.NewRequest(http.MethodPost, "/api/auth/register", bytes.NewReader([]byte(body))))
	if w.Code < 500 {
		t.Fatalf("Messaufbau: erwartet 5xx durch SaveUser-Fehler, bekommen %d: %s", w.Code, w.Body.String())
	}
	if _, ok := inv.Peek(token); !ok {
		t.Errorf("Einladung nach gescheitertem SaveUser nicht mehr offen (Rollback fehlt)")
	}
}
