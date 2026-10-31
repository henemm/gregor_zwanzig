package handler

// Issue #2646 (i18n S1) — Sprachwahl bei der Registrierung.
// Spec: docs/specs/modules/i18n_s1_sprachfeld_nutzer_2646.md — AC-4, AC-5.
//
// Echte RegisterHandlerWithInvites-Aufrufe gegen einen Temp-Store und einen
// echten InviteStore; gemessen wird roh auf der Platte.

import (
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/store"
)

func langRegister(t *testing.T, s *store.Store, cfg config.Config, inv *store.InviteStore, body string) *httptest.ResponseRecorder {
	t.Helper()
	w := httptest.NewRecorder()
	RegisterHandlerWithInvites(s, 4, cfg, inv).ServeHTTP(w,
		httptest.NewRequest(http.MethodPost, "/api/auth/register", strings.NewReader(body)))
	return w
}

func langRegBody(id, extra string) string {
	return `{"username":"` + id + `","password":"geheim-pw-123","email":"` + id + `@beispiel.de"` + extra + `}`
}

// AC-4 + AC-5: mit "en" -> Feld gespeichert, Cookie en (Secure bei https).
func TestRegisterMitSpracheEnSpeichertUndSetztCookie(t *testing.T) {
	s := newTestStore(t)
	calls := onbStubVerificationMail(t)
	w := langRegister(t, s, testRegisterCfg(), store.NewInviteStore(t.TempDir()), langRegBody("lang-reg-en", `,"language":"en"`))
	if w.Code != http.StatusCreated {
		t.Fatalf("AC-4: Status %d: %s", w.Code, w.Body.String())
	}
	onbWaitDispatch(t, calls)
	if got := string(onbReadRawUser(t, s, "lang-reg-en")["language"]); got != `"en"` {
		t.Errorf("AC-4: user.json language=%s, erwartet \"en\"", got)
	}
	langPruefeCookie(t, "AC-5 (Registrierung, https)", w, "en", true)
}

// AC-4 + AC-5: ohne language -> Feld fehlt, Cookie de (kein Secure bei http).
func TestRegisterOhneSpracheLaesstFeldWeg(t *testing.T) {
	s := newTestStore(t)
	calls := onbStubVerificationMail(t)
	cfg := testRegisterCfg()
	cfg.PublicHost = "http://localhost:4173"
	w := langRegister(t, s, cfg, store.NewInviteStore(t.TempDir()), langRegBody("lang-reg-leer", ""))
	if w.Code != http.StatusCreated {
		t.Fatalf("AC-4: Status %d: %s", w.Code, w.Body.String())
	}
	onbWaitDispatch(t, calls)
	if v, ok := onbReadRawUser(t, s, "lang-reg-leer")["language"]; ok {
		t.Errorf("AC-4: ohne Sprachwahl steht language=%s in user.json, erwartet: Feld fehlt", v)
	}
	langPruefeCookie(t, "AC-5 (Registrierung ohne Sprache, http)", w, "de", false)
}

// AC-4: "fr" -> 400 invalid_language, kein Konto, Einladung unverbraucht.
func TestRegisterMitUngueltigerSpracheLegtNichtsAn(t *testing.T) {
	s := newTestStore(t)
	inv := store.NewInviteStore(t.TempDir())
	_, token, err := inv.Create("premium", "", "admin")
	if err != nil {
		t.Fatal(err)
	}
	w := langRegister(t, s, testRegisterCfg(), inv, langRegBody("lang-reg-fr", `,"language":"fr","invite":"`+token+`"`))
	if w.Code != http.StatusBadRequest || !strings.Contains(w.Body.String(), `"invalid_language"`) {
		t.Errorf("AC-4: Status %d Body %s, erwartet 400 {\"error\":\"invalid_language\"}", w.Code, w.Body.String())
	}
	if _, err := os.Stat(filepath.Join(s.UserDir("lang-reg-fr"), "user.json")); err == nil {
		t.Errorf("AC-4: trotz ungueltiger Sprache wurde ein Konto angelegt")
	}
	if s.UserExists("lang-reg-fr") {
		t.Errorf("AC-4: UserExists meldet das abgewiesene Konto")
	}
	if _, offen := inv.Peek(token); !offen {
		t.Errorf("AC-4: Einladung wurde trotz Ablehnung verbraucht")
	}
	if c := langCookie(w); c != nil {
		t.Errorf("AC-4: abgewiesene Registrierung setzt gz_lang=%q", c.Value)
	}
}
