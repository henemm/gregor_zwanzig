package middleware

// MCP-Konnektor „Gregor Wetter“ (Issue #3281, Scheibe 2): gezielte Ausnahmen
// der Schutzschichten. Nur /token, /register und /api/mcp (Bearer-Token statt
// Cookie, kein CSRF) sind Maschinenpfade; die
// Zustimmung (POST /authorize) bleibt unter der Herkunftspruefung, darf aber
// ein Formular sein. Die Anmeldepruefung laesst OAuth-, Metadaten- und
// MCP-Pfade durch (der MCP-Pfad prueft das Bearer-Token selbst), sonst nichts.

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestIsMachinePath_TokenRegisterUndMCP(t *testing.T) {
	for _, p := range []string{"/api/mcp/oauth/token", "/api/mcp/oauth/register", "/api/mcp"} {
		if !IsMachinePath(p) {
			t.Errorf("%s muss Maschinenpfad sein", p)
		}
	}
	for _, p := range []string{"/api/mcp/oauth/authorize", "/api/mcpx", "/api/mcp/", "/api/mcp/oauth/tokenx", "/api/mcp/oauth/"} {
		if IsMachinePath(p) {
			t.Errorf("%s darf kein Maschinenpfad sein", p)
		}
	}
}

func TestRequireJSONBody_ZustimmungAlsFormular(t *testing.T) {
	h := RequireJSONBody()(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(http.StatusOK) }))
	anfrage := func(pfad, typ string) int {
		req := httptest.NewRequest(http.MethodPost, pfad, strings.NewReader("aktion=erlauben"))
		req.Header.Set("Content-Type", typ)
		rec := httptest.NewRecorder()
		h.ServeHTTP(rec, req)
		return rec.Code
	}
	if c := anfrage("/api/mcp/oauth/authorize", "application/x-www-form-urlencoded"); c != http.StatusOK {
		t.Errorf("Zustimmungsformular: %d", c)
	}
	if c := anfrage("/api/mcp/oauth/authorize", "text/plain"); c != http.StatusUnsupportedMediaType {
		t.Errorf("Zustimmung als text/plain: %d", c)
	}
	if c := anfrage("/api/trips", "application/x-www-form-urlencoded"); c != http.StatusUnsupportedMediaType {
		t.Errorf("Formular ausserhalb der Zustimmung: %d", c)
	}
}

func TestOriginGuard_ZustimmungBleibtGeschuetzt(t *testing.T) {
	h := OriginGuard(OriginPolicy{origins: map[string]struct{}{"https://gregor.test": {}}})(
		http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(http.StatusOK) }))
	for pfad, want := range map[string]int{
		"/api/mcp/oauth/authorize": http.StatusForbidden,
		"/api/mcp":                 http.StatusOK,
		"/api/mcp/oauth/token":     http.StatusOK,
		"/api/mcp/oauth/register":  http.StatusOK,
	} {
		req := httptest.NewRequest(http.MethodPost, pfad, nil)
		req.Header.Set("Origin", "https://evil.example")
		rec := httptest.NewRecorder()
		h.ServeHTTP(rec, req)
		if rec.Code != want {
			t.Errorf("%s mit fremder Herkunft: %d, erwartet %d", pfad, rec.Code, want)
		}
	}
}

type keineSitzungen struct{}

func (keineSitzungen) HasSession(string, string) (bool, error) { return false, nil }

func TestAuthMiddleware_MCPPfadeOeffentlich(t *testing.T) {
	h := AuthMiddleware("geheim", keineSitzungen{})(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusTeapot)
	}))
	for _, p := range []string{"/api/mcp", "/api/mcp/oauth/authorize", "/api/mcp/oauth/token", "/api/mcp/oauth/register",
		"/.well-known/oauth-protected-resource", "/.well-known/oauth-protected-resource/api/mcp",
		"/.well-known/oauth-authorization-server"} {
		rec := httptest.NewRecorder()
		h.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, p, nil))
		if rec.Code != http.StatusTeapot {
			t.Errorf("%s: %d (muss ohne Sitzung durch)", p, rec.Code)
		}
	}
	for _, p := range []string{"/api/mcpx", "/api/mcp/andere", "/api/mcp/oauth/geheim", "/.well-known/andere", "/api/trips"} {
		rec := httptest.NewRecorder()
		h.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, p, nil))
		if rec.Code != http.StatusUnauthorized {
			t.Errorf("%s: %d (muss anmeldepflichtig bleiben)", p, rec.Code)
		}
	}
}
