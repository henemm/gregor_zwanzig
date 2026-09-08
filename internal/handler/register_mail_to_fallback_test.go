package handler

// TDD RED — Issue #2144: alle vier Registrierungswege müssen `MailTo` mit der
// bei der Registrierung verwendeten E-Mail-Adresse setzen, sonst fällt der
// Python-Kern beim Versand auf den globalen `.env`-Fallback (Betreiber-Adresse)
// zurück (Cross-Tenant-Zustellung).
//
// Spec: docs/specs/bugfix/user_recipient_fallback.md, AC-1.
// Muss FEHLSCHLAGEN bis implementiert: `MailTo` ist aktuell in keinem der vier
// `model.User{...}`-Literale gesetzt.

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/mail"
)

// AC-1 (Passwort-Weg): RegisterHandler setzt MailTo auf die Registrierungs-Mail.
func TestRegisterHandler_SetsMailToOnRegistration_AC1(t *testing.T) {
	s := newTestStore(t)

	calls := make(chan struct{}, 1)
	origSend := sendVerificationMailFn
	sendVerificationMailFn = func(cfg mail.MailConfig, to string, msg mail.Mail) error {
		calls <- struct{}{}
		return nil
	}
	defer func() { sendVerificationMailFn = origSend }()

	h := RegisterHandler(s, 4, testRegisterCfg())

	body := `{"username":"mailto-pw","password":"geheim123","email":"mailto-pw@beispiel.de"}`
	req := httptest.NewRequest("POST", "/api/auth/register", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != http.StatusCreated {
		t.Fatalf("AC-1: expected 201, got %d: %s", w.Code, w.Body.String())
	}

	select {
	case <-calls:
	case <-time.After(2 * time.Second):
		t.Fatal("AC-1: expected dispatch goroutine within 2s")
	}

	user, err := s.LoadUser("mailto-pw")
	if err != nil || user == nil {
		t.Fatalf("AC-1: user not found after registration: %v", err)
	}
	if user.MailTo != "mailto-pw@beispiel.de" {
		t.Errorf("AC-1: expected MailTo 'mailto-pw@beispiel.de', got %q", user.MailTo)
	}
}

// AC-1 (Magic-Link-Weg): MagicLinkRequestHandler setzt MailTo für den neu
// angelegten User auf dieselbe Adresse, mit der er sich angemeldet hat.
func TestMagicLinkRequestHandler_SetsMailToOnRegistration_AC1(t *testing.T) {
	t.Cleanup(ResetOTPStoreForTest)

	s := newTestStore(t)
	cfg := &config.Config{SMTPHost: ""}

	h := MagicLinkRequestHandler(s, cfg)

	body := `{"email":"mailto-magic@beispiel.de"}`
	req := httptest.NewRequest(http.MethodPost, "/api/auth/magic-link", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("AC-1: expected 200, got %d", w.Code)
	}

	ids, err := s.ListUserIDs()
	if err != nil || len(ids) == 0 {
		t.Fatalf("AC-1: expected a new user to be created: %v", err)
	}
	user, err := s.LoadUser(ids[0])
	if err != nil || user == nil {
		t.Fatalf("AC-1: user not found: %v", err)
	}
	if user.MailTo != "mailto-magic@beispiel.de" {
		t.Errorf("AC-1: expected MailTo 'mailto-magic@beispiel.de', got %q", user.MailTo)
	}
}

// AC-1 (OAuth-Weg): GoogleOAuthCallbackHandler setzt MailTo für ein neu
// angelegtes Konto auf die vom Provider gemeldete, verifizierte Adresse.
func TestGoogleOAuthCallback_SetsMailToOnRegistration_AC1(t *testing.T) {
	userinfoURL, tokenURL := oauthFakeServers(t, "sub-mailto-2144", "mailto-oauth@beispiel.de")

	cfg := &config.Config{
		GoogleClientID:     "test-client-id",
		GoogleClientSecret: "test-secret",
		GoogleRedirectURL:  "https://example.com/callback",
		SessionSecret:      "test-session-secret",
		PublicHost:         "https://gregor20.henemm.com",
		SMTPHost:           "smtp.resend.com", SMTPPort: 587, SMTPUser: "resend", SMTPPass: "re_x",
	}
	s := newTestStore(t)

	origSend := sendVerificationMailFn
	sendVerificationMailFn = func(cfg mail.MailConfig, to string, msg mail.Mail) error { return nil }
	defer func() { sendVerificationMailFn = origSend }()

	h := GoogleOAuthCallbackHandlerWithEndpoints(cfg, s, userinfoURL, tokenURL)
	const state = "test-state-value"
	req := httptest.NewRequest(http.MethodGet, "/api/auth/google/callback?code=test-code&state="+state, nil)
	req.AddCookie(&http.Cookie{Name: "gz_oauth_state", Value: state})
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != http.StatusFound {
		t.Fatalf("AC-1: expected 302, got %d: %s", w.Code, w.Body.String())
	}

	newUser, err := s.FindUserByOAuthSub("google", "sub-mailto-2144")
	if err != nil || newUser == nil {
		t.Fatalf("AC-1: new account for unknown sub must exist: %v", err)
	}
	if newUser.MailTo != "mailto-oauth@beispiel.de" {
		t.Errorf("AC-1: expected MailTo 'mailto-oauth@beispiel.de', got %q", newUser.MailTo)
	}
}

// AC-1 (Passkey-Weg): PasskeyRegisterPublicFinishHandler setzt MailTo auf die
// im Begin-Schritt übermittelte Adresse (dieselbe, die bereits user.Email füllt).
func TestPasskeyRegisterPublicFinish_SetsMailToOnRegistration_AC1(t *testing.T) {
	rpID, origin := "localhost", "http://localhost"
	s := newTestStore(t)
	wa := newTestWebAuthn(t, rpID, origin)
	cs := NewChallengeStore()
	secret := "test-secret-32-chars-long-enough"

	beginBody := []byte(`{"username":"mailto-pk","email":"mailto-pk@beispiel.de"}`)
	beginReq := httptest.NewRequest("POST", "/api/auth/passkey/register/public/begin", bytes.NewReader(beginBody))
	beginW := httptest.NewRecorder()
	PasskeyRegisterPublicBeginHandler(s, wa, cs).ServeHTTP(beginW, beginReq)

	if beginW.Code != http.StatusOK {
		t.Fatalf("AC-1 begin: expected 200, got %d: %s", beginW.Code, beginW.Body.String())
	}
	var beginResp struct {
		PublicKey struct {
			Challenge string `json:"challenge"`
		} `json:"publicKey"`
	}
	if err := json.Unmarshal(beginW.Body.Bytes(), &beginResp); err != nil {
		t.Fatalf("AC-1 begin: cannot decode response: %v", err)
	}

	auth := newTestAuthenticator(t, rpID, origin)
	finishBody := auth.makeAttestationResponse(t, beginResp.PublicKey.Challenge)

	finishReq := httptest.NewRequest("POST", "/api/auth/passkey/register/public/finish", bytes.NewReader(finishBody))
	finishW := httptest.NewRecorder()
	PasskeyRegisterPublicFinishHandler(s, wa, cs, secret, config.Config{}).ServeHTTP(finishW, finishReq)

	if finishW.Code != http.StatusCreated {
		t.Fatalf("AC-1 finish: expected 201, got %d: %s", finishW.Code, finishW.Body.String())
	}

	user, err := s.LoadUser("mailto-pk")
	if err != nil || user == nil {
		t.Fatalf("AC-1: user not found after registration: %v", err)
	}
	if user.MailTo != "mailto-pk@beispiel.de" {
		t.Errorf("AC-1: expected MailTo 'mailto-pk@beispiel.de', got %q", user.MailTo)
	}
}
