package router

// Issue #2159 AC-9 — Verdrahtung: der Router reicht Config.PublicHost an die
// Ausstellungswege durch. Gemessen am ECHTEN Router, ohne TLS und ohne
// X-Forwarded-Proto: ein erfolgreicher Login bzw. Passwortwechsel muss ein
// Secure-Cookie setzen, wenn PublicHost mit https:// beginnt.
// (Passkey-Wege: Handler-Ebene in internal/handler/session_issuance_test.go.)

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/go-webauthn/webauthn/webauthn"
	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/handler"
	"github.com/henemm/gregor-api/internal/handler/passkeytest"
	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/scheduler"
	"github.com/henemm/gregor-api/internal/store"
)

type secureFixture struct {
	r  http.Handler
	s  *store.Store
	wa *webauthn.WebAuthn
	cs *handler.ChallengeStore
}

func secureRouterWithUser(t *testing.T, publicHost string) secureFixture {
	t.Helper()
	cfg, err := config.Load()
	if err != nil {
		t.Fatalf("config.Load: %v", err)
	}
	cfg.DataDir = t.TempDir()
	cfg.PublicHost = publicHost
	cfg.SMTPHost, cfg.GoogleSMTPHost, cfg.FallbackSMTPHost = "", "", ""
	s := store.New(cfg.DataDir, cfg.UserID)
	hash, _ := bcrypt.GenerateFromPassword([]byte("geheim123"), bcrypt.MinCost)
	verified := time.Now().UTC()
	if err := s.SaveUser(model.User{ID: "alice", PasswordHash: string(hash), EmailVerifiedAt: &verified, CreatedAt: time.Now()}); err != nil {
		t.Fatalf("SaveUser: %v", err)
	}
	wa, err := webauthn.New(&webauthn.Config{RPID: "localhost", RPDisplayName: "Gregor Test", RPOrigins: []string{"http://localhost"}})
	if err != nil {
		t.Fatalf("webauthn.New: %v", err)
	}
	sched, err := scheduler.New(cfg, s)
	if err != nil {
		t.Fatalf("scheduler.New: %v", err)
	}
	t.Cleanup(sched.Stop)
	cs := handler.NewChallengeStore()
	r := New(Deps{
		Config: cfg, Store: s, WebAuthn: wa, ChallengeStore: cs,
		Scheduler: sched, TelegramTokenStore: handler.NewTelegramTokenStore(cfg.DataDir), GitCommit: "test",
	})
	return secureFixture{r: r, s: s, wa: wa, cs: cs}
}

func gzSession(t *testing.T, w *httptest.ResponseRecorder, what string) *http.Cookie {
	t.Helper()
	for _, c := range w.Result().Cookies() {
		if c.Name == "gz_session" {
			return c
		}
	}
	t.Fatalf("%s: kein gz_session-Cookie (Status %d): %s", what, w.Code, w.Body.String())
	return nil
}

func TestRouter_LoginUndPasswortwechsel_CookieSecureAusPublicHost(t *testing.T) {
	for _, tc := range []struct {
		host   string
		secure bool
	}{{"https://gregor.example.invalid", true}, {"http://localhost:4173", false}} {
		r := secureRouterWithUser(t, tc.host).r

		req := httptest.NewRequest(http.MethodPost, "/api/auth/login",
			strings.NewReader(`{"username":"alice","password":"geheim123"}`))
		w := httptest.NewRecorder()
		r.ServeHTTP(w, req)
		if w.Code != 200 {
			t.Fatalf("%s Login: erwartet 200, bekam %d: %s", tc.host, w.Code, w.Body.String())
		}
		login := gzSession(t, w, "Login")
		if login.Secure != tc.secure {
			t.Errorf("%s Login: Secure=%v, erwartet %v", tc.host, login.Secure, tc.secure)
		}

		req = httptest.NewRequest(http.MethodPut, "/api/auth/password",
			strings.NewReader(`{"old_password":"geheim123","new_password":"neuespw456"}`))
		req.AddCookie(&http.Cookie{Name: "gz_session", Value: login.Value})
		w = httptest.NewRecorder()
		r.ServeHTTP(w, req)
		if w.Code != 200 {
			t.Fatalf("%s Passwortwechsel: erwartet 200, bekam %d: %s", tc.host, w.Code, w.Body.String())
		}
		if c := gzSession(t, w, "Passwortwechsel"); c.Secure != tc.secure {
			t.Errorf("%s Passwortwechsel: Secure=%v, erwartet %v", tc.host, c.Secure, tc.secure)
		}
	}
}

// registerPasskey legt ueber die echten Registrier-Handler einen Passkey fuer
// "alice" an (gleicher Store / WebAuthn / ChallengeStore wie der Router).
func registerPasskey(t *testing.T, f secureFixture) *passkeytest.Authenticator {
	t.Helper()
	ctx := func(req *http.Request) *http.Request {
		return req.WithContext(middleware.ContextWithUserID(req.Context(), "alice"))
	}
	bw := httptest.NewRecorder()
	handler.PasskeyRegisterBeginHandler(f.s, f.wa, f.cs).ServeHTTP(bw,
		ctx(httptest.NewRequest("POST", "/api/auth/passkey/register/begin", nil)))
	if bw.Code != 200 {
		t.Fatalf("register begin: %d: %s", bw.Code, bw.Body.String())
	}
	var br struct {
		PublicKey struct {
			Challenge string `json:"challenge"`
		} `json:"publicKey"`
	}
	if err := json.Unmarshal(bw.Body.Bytes(), &br); err != nil {
		t.Fatalf("register begin decode: %v", err)
	}
	auth := passkeytest.NewAuthenticator(t, "localhost", "http://localhost")
	fw := httptest.NewRecorder()
	handler.PasskeyRegisterFinishHandler(f.s, f.wa, f.cs).ServeHTTP(fw,
		ctx(httptest.NewRequest("POST", "/api/auth/passkey/register/finish",
			bytes.NewReader(auth.MakeAttestationResponse(t, br.PublicKey.Challenge)))))
	if fw.Code != 201 {
		t.Fatalf("register finish: %d: %s", fw.Code, fw.Body.String())
	}
	return auth
}

func challengeFrom(t *testing.T, w *httptest.ResponseRecorder) string {
	t.Helper()
	if w.Code != 200 {
		t.Fatalf("begin: %d: %s", w.Code, w.Body.String())
	}
	var br struct {
		PublicKey struct {
			Challenge string `json:"challenge"`
		} `json:"publicKey"`
	}
	if err := json.Unmarshal(w.Body.Bytes(), &br); err != nil {
		t.Fatalf("begin decode: %v", err)
	}
	return br.PublicKey.Challenge
}

// #2159 AC-9: die zwei Passkey-Abschluss-Routen reichen den PublicHost durch.
func TestRouter_PasskeyAbschluss_CookieSecureAusPublicHost(t *testing.T) {
	f := secureRouterWithUser(t, "https://gregor.example.invalid")
	auth := registerPasskey(t, f)

	// login/finish (mit Kennungseingabe)
	bw := httptest.NewRecorder()
	f.r.ServeHTTP(bw, httptest.NewRequest("POST", "/api/auth/passkey/login/begin",
		bytes.NewReader([]byte(`{"username":"alice"}`))))
	fw := httptest.NewRecorder()
	f.r.ServeHTTP(fw, httptest.NewRequest("POST", "/api/auth/passkey/login/finish",
		bytes.NewReader(auth.MakeAssertionResponse(t, challengeFrom(t, bw), 1))))
	if fw.Code != 200 {
		t.Fatalf("login/finish: %d: %s", fw.Code, fw.Body.String())
	}
	if c := gzSession(t, fw, "login/finish"); !c.Secure {
		t.Error("login/finish: Cookie muss aus dem https-PublicHost Secure sein")
	}

	// discoverable/finish (ohne Kennungseingabe)
	bw = httptest.NewRecorder()
	f.r.ServeHTTP(bw, httptest.NewRequest("POST", "/api/auth/passkey/discoverable/begin", nil))
	dreq := httptest.NewRequest("POST", "/api/auth/passkey/discoverable/finish",
		bytes.NewReader(auth.MakeAssertionResponseDiscoverable(t, challengeFrom(t, bw), 2, "alice")))
	dreq.Header.Set("Content-Type", "application/json")
	dw := httptest.NewRecorder()
	f.r.ServeHTTP(dw, dreq)
	if dw.Code != 200 {
		t.Fatalf("discoverable/finish: %d: %s", dw.Code, dw.Body.String())
	}
	if c := gzSession(t, dw, "discoverable/finish"); !c.Secure {
		t.Error("discoverable/finish: Cookie muss aus dem https-PublicHost Secure sein")
	}
}
