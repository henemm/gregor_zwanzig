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

	"github.com/henemm/gregor-api/internal/config"
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
