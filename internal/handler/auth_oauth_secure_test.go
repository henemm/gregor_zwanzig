package handler

// Issue #2159 AC-9 — Secure-Flag des Cookies gz_oauth_state kommt aus dem
// Schema von Config.PublicHost (oder r.TLS), NICHT aus X-Forwarded-Proto.

import (
	"crypto/tls"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/henemm/gregor-api/internal/config"
)

func oauthStateSecure(t *testing.T, publicHost string, forwardedProto string, withTLS bool) bool {
	t.Helper()
	cfg := &config.Config{
		GoogleClientID: "client-id", GoogleClientSecret: "x",
		GoogleRedirectURL: "https://example.invalid/cb", SessionSecret: "test-secret",
		PublicHost: publicHost,
	}
	req := httptest.NewRequest(http.MethodGet, "/api/auth/google/init", nil)
	if forwardedProto != "" {
		req.Header.Set("X-Forwarded-Proto", forwardedProto)
	}
	if withTLS {
		req.TLS = &tls.ConnectionState{}
	}
	rr := httptest.NewRecorder()
	GoogleOAuthInitHandler(cfg).ServeHTTP(rr, req)
	for _, c := range rr.Result().Cookies() {
		if c.Name == "gz_oauth_state" {
			return c.Secure
		}
	}
	t.Fatal("Cookie gz_oauth_state nicht gesetzt")
	return false
}

func TestOAuthStateCookie_SecureAusPublicHost(t *testing.T) {
	if !oauthStateSecure(t, "https://gregor20.henemm.com", "", false) {
		t.Error("https-PublicHost ohne X-Forwarded-Proto: Cookie muss Secure sein")
	}
	if oauthStateSecure(t, "http://localhost:4173", "https", false) {
		t.Error("http-PublicHost: X-Forwarded-Proto darf Secure NICHT erzwingen")
	}
	if oauthStateSecure(t, "http://localhost:4173", "", false) {
		t.Error("http-PublicHost ohne TLS: Cookie darf nicht Secure sein")
	}
	if !oauthStateSecure(t, "http://localhost:4173", "", true) {
		t.Error("echte TLS-Verbindung: Cookie muss immer Secure sein")
	}
}
