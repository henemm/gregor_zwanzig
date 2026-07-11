package handler

// TDD RED: Issue #425 — Google OAuth Login
// Spec: docs/specs/modules/google_oauth_login.md
//
// Tests für GoogleOAuthInitHandler und GoogleOAuthCallbackHandler.
// Muss FEHLSCHLAGEN bis implementiert (Compile-Fehler: Funktionen existieren nicht).
// Ausführung: cd <repo> && go test ./internal/handler/... -run TestGoogleOAuth -v

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/mail"
	"github.com/henemm/gregor-api/internal/model"
)

// AC-6: Wenn GZ_GOOGLE_CLIENT_ID leer ist → HTTP 501.
func TestGoogleOAuthInitHandler_Disabled(t *testing.T) {
	// GIVEN: Config ohne Client-ID
	cfg := &config.Config{
		GoogleClientID:     "",
		GoogleClientSecret: "",
		GoogleRedirectURL:  "",
		SessionSecret:      "test-secret",
	}

	h := GoogleOAuthInitHandler(cfg)

	// WHEN: /api/auth/google/init aufrufen
	req := httptest.NewRequest(http.MethodGet, "/api/auth/google/init", nil)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	// THEN: 501 Not Implemented
	if w.Code != http.StatusNotImplemented {
		t.Errorf("expected 501, got %d — GoogleClientID empty should disable the feature", w.Code)
	}
}

// AC-1: Wenn GZ_GOOGLE_CLIENT_ID konfiguriert ist → Redirect zu Google OAuth + State-Cookie.
func TestGoogleOAuthInitHandler_Redirects(t *testing.T) {
	// GIVEN: Config mit gültiger Client-ID
	cfg := &config.Config{
		GoogleClientID:     "fake-client-id.apps.googleusercontent.com",
		GoogleClientSecret: "fake-secret",
		GoogleRedirectURL:  "https://gregor20.henemm.com/api/auth/google/callback",
		SessionSecret:      "test-secret",
	}

	h := GoogleOAuthInitHandler(cfg)

	// WHEN: /api/auth/google/init aufrufen
	req := httptest.NewRequest(http.MethodGet, "/api/auth/google/init", nil)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	// THEN: 302 Redirect zu accounts.google.com
	if w.Code != http.StatusFound {
		t.Errorf("expected 302 redirect, got %d: %s", w.Code, w.Body.String())
	}
	location := w.Header().Get("Location")
	if location == "" {
		t.Error("expected Location header in redirect")
	}
	if len(location) < 30 {
		t.Errorf("Location too short, expected Google OAuth URL, got: %s", location)
	}

	// AND: gz_oauth_state Cookie gesetzt (CSRF-Schutz)
	cookies := w.Result().Cookies()
	var stateCookie *http.Cookie
	for _, c := range cookies {
		if c.Name == "gz_oauth_state" {
			stateCookie = c
			break
		}
	}
	if stateCookie == nil {
		t.Error("expected gz_oauth_state cookie for CSRF protection")
	}
	if stateCookie != nil && stateCookie.HttpOnly == false {
		t.Error("gz_oauth_state cookie must be HttpOnly")
	}
	if stateCookie != nil && stateCookie.MaxAge <= 0 {
		t.Error("gz_oauth_state cookie must have positive MaxAge (short-lived)")
	}
}

// AC-4: State-Mismatch im Callback → Redirect zu /login?error=oauth_failed.
func TestGoogleOAuthCallbackHandler_StateMismatch(t *testing.T) {
	// GIVEN: Config + Store, State im Cookie ≠ State im URL-Parameter
	cfg := &config.Config{
		GoogleClientID:     "fake-client-id.apps.googleusercontent.com",
		GoogleClientSecret: "fake-secret",
		GoogleRedirectURL:  "https://gregor20.henemm.com/api/auth/google/callback",
		SessionSecret:      "test-secret",
	}
	s := newTestStore(t)

	h := GoogleOAuthCallbackHandler(cfg, s)

	// WHEN: Callback mit abweichendem State (CSRF-Angriff)
	req := httptest.NewRequest(http.MethodGet, "/api/auth/google/callback?code=authcode&state=attacker-state", nil)
	req.AddCookie(&http.Cookie{
		Name:  "gz_oauth_state",
		Value: "legit-state-value",
	})
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	// THEN: 302 zu /login?error=oauth_failed (kein Token-Exchange)
	if w.Code != http.StatusFound {
		t.Errorf("expected 302, got %d", w.Code)
	}
	location := w.Header().Get("Location")
	if location != "/login?error=oauth_failed" {
		t.Errorf("expected redirect to /login?error=oauth_failed, got: %s", location)
	}
}

// AC-4: Fehlender State-Cookie im Callback → Redirect zu /login?error=oauth_failed.
func TestGoogleOAuthCallbackHandler_MissingStateCookie(t *testing.T) {
	// GIVEN: Config + Store, kein gz_oauth_state-Cookie
	cfg := &config.Config{
		GoogleClientID:     "fake-client-id.apps.googleusercontent.com",
		GoogleClientSecret: "fake-secret",
		GoogleRedirectURL:  "https://gregor20.henemm.com/api/auth/google/callback",
		SessionSecret:      "test-secret",
	}
	s := newTestStore(t)

	h := GoogleOAuthCallbackHandler(cfg, s)

	// WHEN: Callback ohne State-Cookie
	req := httptest.NewRequest(http.MethodGet, "/api/auth/google/callback?code=authcode&state=some-state", nil)
	// kein Cookie gesetzt
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	// THEN: 302 zu /login?error=oauth_failed
	if w.Code != http.StatusFound {
		t.Errorf("expected 302, got %d", w.Code)
	}
	location := w.Header().Get("Location")
	if location != "/login?error=oauth_failed" {
		t.Errorf("expected /login?error=oauth_failed, got: %s", location)
	}
}

// AC-6: GoogleOAuthCallbackHandler wenn Feature deaktiviert → 501.
func TestGoogleOAuthCallbackHandler_Disabled(t *testing.T) {
	// GIVEN: Config ohne Client-ID
	cfg := &config.Config{
		GoogleClientID: "",
		SessionSecret:  "test-secret",
	}
	s := newTestStore(t)

	h := GoogleOAuthCallbackHandler(cfg, s)

	req := httptest.NewRequest(http.MethodGet, "/api/auth/google/callback?code=x&state=y", nil)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != http.StatusNotImplemented {
		t.Errorf("expected 501 when Google OAuth disabled, got %d", w.Code)
	}
}

// AC-5 (aktualisiert): email_verified=false → Redirect zu /login?error=oauth_failed
// Vollständiger Flow mit Fake-Userinfo- und Fake-Token-Server (kein Mock — echte HTTP-Roundtrips).
func TestGoogleOAuthCallbackHandler_EmailNotVerified(t *testing.T) {
	// GIVEN: Fake Userinfo-Server liefert email_verified: false
	fakeUserinfo := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]interface{}{
			"sub":            "sub-unverified-123",
			"email":          "unverified@example.com",
			"email_verified": false,
		})
	}))
	defer fakeUserinfo.Close()

	// Fake Token-Exchange-Server (gibt Bearer-Token aus)
	fakeTokenServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]interface{}{
			"access_token": "fake-access-token",
			"token_type":   "Bearer",
			"expires_in":   3600,
		})
	}))
	defer fakeTokenServer.Close()

	cfg := &config.Config{
		GoogleClientID:     "test-client-id",
		GoogleClientSecret: "test-secret",
		GoogleRedirectURL:  "https://example.com/callback",
		SessionSecret:      "test-session-secret",
	}
	s := newTestStore(t)

	h := GoogleOAuthCallbackHandlerWithEndpoints(cfg, s, fakeUserinfo.URL, fakeTokenServer.URL)

	const state = "test-state-value"
	req := httptest.NewRequest(http.MethodGet, "/api/auth/google/callback?code=test-code&state="+state, nil)
	req.AddCookie(&http.Cookie{Name: "gz_oauth_state", Value: state})
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	// THEN: Redirect zu /login?error=oauth_failed (email nicht verifiziert)
	if w.Code != http.StatusFound {
		t.Errorf("expected 302, got %d: %s", w.Code, w.Body.String())
	}
	location := w.Header().Get("Location")
	if location != "/login?error=oauth_failed" {
		t.Errorf("expected /login?error=oauth_failed, got: %s", location)
	}

	// Und: Kein User-Eintrag angelegt
	ids, _ := s.ListUserIDs()
	if len(ids) != 0 {
		t.Errorf("expected no users created, got %d", len(ids))
	}
}

// -----------------------------------------------------------------------------
// Issue #1226 — Verifikations-Dispatch bei Google-OAuth-Kontoerstellung
// -----------------------------------------------------------------------------

// oauthFakeServers baut Fake-Userinfo- und Token-Server für einen gegebenen sub
// mit email_verified=true. Kein Mock — echte HTTP-Roundtrips gegen httptest.
func oauthFakeServers(t *testing.T, sub, email string) (userinfoURL, tokenURL string) {
	t.Helper()
	fakeUserinfo := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]interface{}{
			"sub":            sub,
			"email":          email,
			"email_verified": true,
		})
	}))
	t.Cleanup(fakeUserinfo.Close)

	fakeToken := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]interface{}{
			"access_token": "fake-access-token",
			"token_type":   "Bearer",
			"expires_in":   3600,
		})
	}))
	t.Cleanup(fakeToken.Close)

	return fakeUserinfo.URL, fakeToken.URL
}

// AC-4: neuer (unbekannter) sub → neues Konto UND genau ein Verifikations-Dispatch
// mit der Google-Adresse.
func TestGoogleOAuthCallback_NewUserTriggersDispatch_AC4(t *testing.T) {
	userinfoURL, tokenURL := oauthFakeServers(t, "sub-new-1226", "neu-oauth@beispiel.de")

	// SMTPHost gesetzt → der (nicht-Test-User-)Resend-Zweig in
	// dispatchVerificationMail betritt den beobachtbaren sendVerificationMailFn.
	cfg := &config.Config{
		GoogleClientID:     "test-client-id",
		GoogleClientSecret: "test-secret",
		GoogleRedirectURL:  "https://example.com/callback",
		SessionSecret:      "test-session-secret",
		PublicHost:         "https://gregor20.henemm.com",
		SMTPHost:           "smtp.resend.com", SMTPPort: 587, SMTPUser: "resend", SMTPPass: "re_x",
	}
	s := newTestStore(t)

	type observedCall struct{ to string }
	calls := make(chan observedCall, 4)
	origSend := sendVerificationMailFn
	sendVerificationMailFn = func(cfg mail.MailConfig, to string, msg mail.Mail) error {
		calls <- observedCall{to: to}
		return nil
	}
	defer func() { sendVerificationMailFn = origSend }()

	h := GoogleOAuthCallbackHandlerWithEndpoints(cfg, s, userinfoURL, tokenURL)
	const state = "test-state-value"
	req := httptest.NewRequest(http.MethodGet, "/api/auth/google/callback?code=test-code&state="+state, nil)
	req.AddCookie(&http.Cookie{Name: "gz_oauth_state", Value: state})
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != http.StatusFound {
		t.Fatalf("AC-4: expected 302, got %d: %s", w.Code, w.Body.String())
	}
	// Neues Konto wurde via createOAuthUser angelegt.
	newUser, err := s.FindUserByOAuthSub("google", "sub-new-1226")
	if err != nil || newUser == nil {
		t.Fatalf("AC-4: new account for unknown sub must exist: %v", err)
	}

	select {
	case c := <-calls:
		if c.to != "neu-oauth@beispiel.de" {
			t.Errorf("AC-4: expected dispatch to 'neu-oauth@beispiel.de', got %q", c.to)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("AC-4: expected exactly one dispatch call within 2s, none observed")
	}
	select {
	case extra := <-calls:
		t.Errorf("AC-4: expected exactly ONE dispatch call, extra observed: %+v", extra)
	default:
	}
}

// AC-5: bekannter sub (Login, keine Neuanlage) → KEIN Dispatch (Regressionsschutz
// gegen Mail-Spam bei jedem Login), Session-Cookie wird trotzdem gesetzt.
func TestGoogleOAuthCallback_ExistingUserNoDispatch_AC5(t *testing.T) {
	userinfoURL, tokenURL := oauthFakeServers(t, "sub-known-1226", "bekannt-oauth@beispiel.de")

	cfg := &config.Config{
		GoogleClientID:     "test-client-id",
		GoogleClientSecret: "test-secret",
		GoogleRedirectURL:  "https://example.com/callback",
		SessionSecret:      "test-session-secret",
		PublicHost:         "https://gregor20.henemm.com",
		SMTPHost:           "smtp.resend.com", SMTPPort: 587, SMTPUser: "resend", SMTPPass: "re_x",
	}
	s := newTestStore(t)

	// Bestehendes OAuth-Konto für denselben sub vorab anlegen.
	if err := s.SaveUser(model.User{
		ID: "g-existing", OAuthProvider: "google", OAuthSub: "sub-known-1226",
		Email: "bekannt-oauth@beispiel.de", CreatedAt: time.Now(),
	}); err != nil {
		t.Fatalf("AC-5: seed existing oauth user: %v", err)
	}
	_ = s.ProvisionUserDirs("g-existing")

	calls := make(chan struct{}, 4)
	origSend := sendVerificationMailFn
	sendVerificationMailFn = func(cfg mail.MailConfig, to string, msg mail.Mail) error {
		calls <- struct{}{}
		return nil
	}
	defer func() { sendVerificationMailFn = origSend }()

	h := GoogleOAuthCallbackHandlerWithEndpoints(cfg, s, userinfoURL, tokenURL)
	const state = "test-state-value"
	req := httptest.NewRequest(http.MethodGet, "/api/auth/google/callback?code=test-code&state="+state, nil)
	req.AddCookie(&http.Cookie{Name: "gz_oauth_state", Value: state})
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != http.StatusFound {
		t.Fatalf("AC-5: expected 302, got %d: %s", w.Code, w.Body.String())
	}
	// Session-Cookie muss gesetzt sein (Login funktioniert normal).
	var sess *http.Cookie
	for _, c := range w.Result().Cookies() {
		if c.Name == "gz_session" {
			sess = c
			break
		}
	}
	if sess == nil {
		t.Fatalf("AC-5: expected gz_session cookie on login of existing user")
	}
	// Kein neues Konto angelegt (nur der eine geseedete User).
	ids, _ := s.ListUserIDs()
	if len(ids) != 1 {
		t.Errorf("AC-5: expected no new account, got %d users", len(ids))
	}
	// Kein Dispatch — 200ms Fenster reicht, da bei Login gar keine Goroutine startet.
	select {
	case <-calls:
		t.Error("AC-5: no verification dispatch must happen on login of an existing OAuth user")
	case <-time.After(300 * time.Millisecond):
		// erwartetes Verhalten — kein Aufruf
	}
}
