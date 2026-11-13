package handler_test

import (
	"net/http"
	"testing"

	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/model"
)

// nachweis setzt dem Konto ein Passwort und erbringt damit ueber den echten
// Router den frischen Nachweis fuer die Sitzung c (Issue #2961, ADR-0115):
// ohne ihn antwortet ein Adresswechsel mit 403 reauth_required.
func (e *smsUmgebung2406) nachweis(t *testing.T, uid string, c *http.Cookie) {
	t.Helper()
	hash, err := bcrypt.GenerateFromPassword([]byte("nachweis-pw-2961"), bcrypt.MinCost)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := e.store.UpdateUser(uid, func(u *model.User) error { u.PasswordHash = string(hash); return nil }); err != nil {
		t.Fatalf("Passwort setzen: %v", err)
	}
	if w := e.anfrage(t, http.MethodPost, "/api/auth/reauth", `{"password":"nachweis-pw-2961"}`, c); w.Code != http.StatusOK {
		t.Fatalf("Nachweis: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
}
