package handler

// F003: scheitert SaveUser nach der Reservierung, wird die Einladung
// zurueckgerollt (bleibt offen). Root-sicher: users wird als DATEI
// vorbelegt, so scheitert die Kontoanlage ohne chmod.

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
	// Issue #2961: ein vorhandener Kontoordner (auch eine Datei an seiner
	// Stelle) gilt als belegt (409 vor der Einloesung). Darum steht hier die
	// Datei an der Stelle von users/: die Kennung ist frei, Redeem laeuft, erst
	// die Kontoanlage scheitert — so wird der Rollback-Pfad wirklich betreten.
	if err := os.WriteFile(filepath.Join(dir, "users"), []byte("x"), 0o644); err != nil {
		t.Fatal(err)
	}
	// Issue #2194/#2961: eine vorhersagbare ID gibt es nur fuer Testkonten,
	// und die nur im Staging/Fixture-Modus/als Admin.
	h := RegisterHandlerWithInvites(s, bcrypt.MinCost, config.Config{Env: "staging"}, inv)
	body := `{"username":"blockiert","password":"geheim-pw-123","email":"b@example.org","is_test_user":true,"invite":"` + token + `"}`
	w := httptest.NewRecorder()
	h.ServeHTTP(w, httptest.NewRequest(http.MethodPost, "/api/auth/register", bytes.NewReader([]byte(body))))
	if w.Code < 500 {
		t.Fatalf("Messaufbau: erwartet 5xx durch SaveUser-Fehler, bekommen %d: %s", w.Code, w.Body.String())
	}
	if _, ok := inv.Peek(token); !ok {
		t.Errorf("Einladung nach gescheitertem SaveUser nicht mehr offen (Rollback fehlt)")
	}
}
