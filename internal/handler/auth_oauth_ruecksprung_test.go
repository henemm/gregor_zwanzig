package handler

// Issue #3281 (MCP-Konnektor, Nacharbeit): der Google-Login behaelt den
// Ruecksprung der Anmeldeseite (z. B. zur Autorisierung des Konnektors).
// init merkt sich ein zulaessiges `redirect` in einem kurzlebigen Cookie neben
// dem state, der Callback springt nach erfolgreicher Anmeldung dorthin.
// Fremde Ziele (Open Redirect) werden nie gemerkt und nie angesprungen.
// Kein Mock: echte Handler, Google-Endpunkte als httptest-Server.

import (
	"net/http"
	"net/http/httptest"
	"net/url"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/model"
)

const ruecksprungAuthorize = "/api/mcp/oauth/authorize?client_id=c_x&code_challenge=abc&state=z"

func googleTestConfig() *config.Config {
	return &config.Config{
		GoogleClientID: "test-client-id", GoogleClientSecret: "test-secret",
		GoogleRedirectURL: "https://example.com/callback", SessionSecret: "test-session-secret",
		PublicHost: "https://gregor20.henemm.com",
	}
}

func cookieAus(w *httptest.ResponseRecorder, name string) *http.Cookie {
	for _, c := range w.Result().Cookies() {
		if c.Name == name {
			return c
		}
	}
	return nil
}

func TestGoogleInit_MerktZulaessigenRuecksprung(t *testing.T) {
	h := GoogleOAuthInitHandler(googleTestConfig())
	req := httptest.NewRequest(http.MethodGet, "/api/auth/google/init?redirect="+url.QueryEscape(ruecksprungAuthorize), nil)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)
	c := cookieAus(w, "gz_oauth_redirect")
	if w.Code != http.StatusFound || c == nil || !c.HttpOnly || c.MaxAge <= 0 {
		t.Fatalf("Ruecksprung-Cookie erwartet: %d %+v", w.Code, c)
	}
	if v, _ := url.QueryUnescape(c.Value); v != ruecksprungAuthorize {
		t.Errorf("gemerkter Ruecksprung %q", c.Value)
	}
	for _, fremd := range []string{"https://evil.example/x", "//evil.example", "/\\evil.example", ""} {
		req := httptest.NewRequest(http.MethodGet, "/api/auth/google/init?redirect="+url.QueryEscape(fremd), nil)
		w := httptest.NewRecorder()
		h.ServeHTTP(w, req)
		if c := cookieAus(w, "gz_oauth_redirect"); c != nil && c.MaxAge > 0 {
			t.Errorf("fremdes Ziel %q gemerkt: %+v", fremd, c)
		}
	}
}

func googleCallback(t *testing.T, ruecksprung string) *httptest.ResponseRecorder {
	t.Helper()
	userinfoURL, tokenURL := oauthFakeServers(t, "sub-ruecksprung", "rueck@beispiel.de")
	s := newTestStore(t)
	jetzt := time.Now()
	if err := s.SaveUser(model.User{ID: "g-rueck", OAuthProvider: "google", OAuthSub: "sub-ruecksprung",
		Email: "rueck@beispiel.de", EmailVerifiedAt: &jetzt, CreatedAt: jetzt}); err != nil {
		t.Fatal(err)
	}
	_ = s.ProvisionUserDirs("g-rueck")
	h := GoogleOAuthCallbackHandlerWithEndpoints(googleTestConfig(), s, userinfoURL, tokenURL)
	req := httptest.NewRequest(http.MethodGet, "/api/auth/google/callback?code=c&state=st", nil)
	req.AddCookie(&http.Cookie{Name: "gz_oauth_state", Value: "st"})
	if ruecksprung != "" {
		req.AddCookie(&http.Cookie{Name: "gz_oauth_redirect", Value: url.QueryEscape(ruecksprung)})
	}
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)
	if cookieAus(w, "gz_session") == nil {
		t.Fatalf("Anmeldung gescheitert: %d %q", w.Code, w.Header().Get("Location"))
	}
	return w
}

func TestGoogleCallback_SpringtZumGemerktenRuecksprung(t *testing.T) {
	w := googleCallback(t, ruecksprungAuthorize)
	if w.Code != http.StatusFound || w.Header().Get("Location") != ruecksprungAuthorize {
		t.Fatalf("Ruecksprung erwartet: %d %q", w.Code, w.Header().Get("Location"))
	}
	if c := cookieAus(w, "gz_oauth_redirect"); c == nil || c.MaxAge >= 0 {
		t.Errorf("Ruecksprung-Cookie muss geloescht werden: %+v", c)
	}
}

func TestGoogleCallback_OhneOderMitFremdemRuecksprungAufStartseite(t *testing.T) {
	for _, r := range []string{"", "https://evil.example/x", "//evil.example"} {
		if w := googleCallback(t, r); w.Header().Get("Location") != "/" {
			t.Errorf("Ruecksprung %q: Location %q, erwartet /", r, w.Header().Get("Location"))
		}
	}
}

func TestSichererRuecksprung(t *testing.T) {
	for roh, want := range map[string]string{
		"/trips/abc?tab=x": "/trips/abc?tab=x", ruecksprungAuthorize: ruecksprungAuthorize,
		"": "", "//evil": "", "/\\evil": "", "https://evil": "", "evil": "", "/a\nb": "", "/a\\b": "",
	} {
		if got := sichererRuecksprung(roh); got != want {
			t.Errorf("sichererRuecksprung(%q) = %q, erwartet %q", roh, got, want)
		}
	}
}
