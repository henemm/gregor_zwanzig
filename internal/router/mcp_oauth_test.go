package router

// OAuth 2.1 des MCP-Konnektors „Gregor Wetter“ durch den echten Router
// (Issue #3281, Scheibe 2; AC-3, AC-4, AC-6 bis AC-10).
// SPEC: docs/specs/modules/mcp_wetter_konnektor.md
// Vorbild der Faelle: henemm/frieda-reist engine/tests/test_oauth.py.

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/henemm/gregor-api/internal/model"
)

func TestMCP_Metadaten_OeffentlichUndAufDieBasisBezogen(t *testing.T) {
	w := neueMCPWelt(t)
	for _, pfad := range []string{"/.well-known/oauth-protected-resource", "/.well-known/oauth-protected-resource/api/mcp"} {
		rec := w.anfrage(httptest.NewRequest(http.MethodGet, pfad, nil))
		var m map[string]any
		json.Unmarshal(rec.Body.Bytes(), &m)
		if rec.Code != http.StatusOK || m["resource"] != mcpBasis+"/api/mcp" {
			t.Fatalf("%s: Status %d, %v", pfad, rec.Code, m)
		}
		server, _ := m["authorization_servers"].([]any)
		if len(server) != 1 || server[0] != mcpBasis {
			t.Errorf("%s: authorization_servers %v", pfad, m["authorization_servers"])
		}
	}
	rec := w.anfrage(httptest.NewRequest(http.MethodGet, "/.well-known/oauth-authorization-server", nil))
	var m map[string]any
	json.Unmarshal(rec.Body.Bytes(), &m)
	if rec.Code != http.StatusOK || m["issuer"] != mcpBasis ||
		m["authorization_endpoint"] != mcpBasis+"/api/mcp/oauth/authorize" ||
		m["token_endpoint"] != mcpBasis+"/api/mcp/oauth/token" ||
		m["registration_endpoint"] != mcpBasis+"/api/mcp/oauth/register" ||
		m["client_id_metadata_document_supported"] != true ||
		m["authorization_response_iss_parameter_supported"] != true {
		t.Fatalf("Server-Metadaten falsch: %d %v", rec.Code, m)
	}
	if s, _ := json.Marshal(m["code_challenge_methods_supported"]); string(s) != `["S256"]` {
		t.Errorf("nur S256 erwartet: %s", s)
	}
	if s, _ := json.Marshal(m["token_endpoint_auth_methods_supported"]); string(s) != `["none"]` {
		t.Errorf("nur public clients erwartet: %s", s)
	}
}

// AC-6: ohne/mit ungueltigem Token 401 mit resource_metadata.
func TestMCP_OhneToken_401MitZeigerAufMetadaten(t *testing.T) {
	w := neueMCPWelt(t)
	rec, _ := w.mcp("", "initialize", map[string]any{})
	want := `Bearer resource_metadata="` + mcpBasis + `/.well-known/oauth-protected-resource/api/mcp"`
	if rec.Code != http.StatusUnauthorized || rec.Header().Get("WWW-Authenticate") != want {
		t.Fatalf("ohne Token: %d, WWW-Authenticate %q", rec.Code, rec.Header().Get("WWW-Authenticate"))
	}
	rec, _ = w.mcp(strings.Repeat("x", 43), "initialize", map[string]any{})
	if rec.Code != http.StatusUnauthorized || !strings.Contains(rec.Header().Get("WWW-Authenticate"), `error="invalid_token"`) {
		t.Fatalf("ungueltiges Token: %d, %q", rec.Code, rec.Header().Get("WWW-Authenticate"))
	}
	get := w.anfrage(httptest.NewRequest(http.MethodGet, "/api/mcp", nil))
	if get.Code != http.StatusUnauthorized {
		t.Errorf("GET ohne Token: %d", get.Code)
	}
}

// AC-4 + ganzer Ablauf wie die Claude-App, AC-9 (Rotation, Familie).
func TestMCP_GanzerAblaufWieDieClaudeApp(t *testing.T) {
	w := neueMCPWelt(t, "anna")
	keks := w.konto(model.User{ID: "anna", DisplayName: "Anna", Language: "de"})
	code, c := w.registrieren(mcpCallback)
	if code != http.StatusCreated || c["token_endpoint_auth_method"] != "none" {
		t.Fatalf("Registrierung: %d %v", code, c)
	}
	client := c["client_id"].(string)
	v, ch := pkcePaar()
	q := authorizeWerte(client, ch)

	// AC-4: ohne Sitzung Umleitung auf die Anmeldung mit Ruecksprung.
	rec := w.authorizeGet(q, nil)
	if rec.Code != http.StatusFound {
		t.Fatalf("ohne Sitzung: Status %d (erwartet 302), %s", rec.Code, rec.Body.String())
	}
	loc, _ := url.Parse(rec.Header().Get("Location"))
	if loc.Path != "/login" || !strings.HasPrefix(loc.Query().Get("redirect"), "/api/mcp/oauth/authorize?") {
		t.Fatalf("Umleitung falsch: %q", rec.Header().Get("Location"))
	}
	zurueck, _ := url.Parse(loc.Query().Get("redirect"))
	if zurueck.Query().Get("code_challenge") != ch || zurueck.Query().Get("client_id") != client ||
		zurueck.Query().Get("state") != "zustand-1" {
		t.Fatalf("Ruecksprung verliert Parameter: %q", loc.Query().Get("redirect"))
	}
	// Nach der Anmeldung (Cookie) fuehrt derselbe Ruecksprung zur Zustimmungsseite.
	req := httptest.NewRequest(http.MethodGet, zurueck.String(), nil)
	req.AddCookie(keks)
	rec = w.anfrage(req)
	if rec.Code != http.StatusOK || !strings.Contains(rec.Body.String(), "claude.ai") ||
		!strings.Contains(rec.Body.String(), "Gregor Wetter") {
		t.Fatalf("Zustimmungsseite: %d %s", rec.Code, rec.Body.String())
	}
	csp := rec.Header().Get("Content-Security-Policy")
	if !strings.Contains(csp, "form-action 'self' https://claude.ai") || !strings.Contains(csp, "frame-ancestors 'none'") {
		t.Errorf("CSP der Zustimmungsseite: %q", csp)
	}

	rec = w.authorizePost(q, "erlauben", keks, mcpBasis)
	ziel, _ := url.Parse(rec.Header().Get("Location"))
	if rec.Code != http.StatusSeeOther || !strings.HasPrefix(rec.Header().Get("Location"), mcpCallback+"?") ||
		ziel.Query().Get("state") != "zustand-1" || ziel.Query().Get("iss") != mcpBasis || ziel.Query().Get("code") == "" {
		t.Fatalf("Zustimmung: %d %q", rec.Code, rec.Header().Get("Location"))
	}
	status, tok := w.token(url.Values{"grant_type": {"authorization_code"}, "code": {ziel.Query().Get("code")},
		"redirect_uri": {mcpCallback}, "client_id": {client}, "code_verifier": {v}})
	if status != http.StatusOK || tok["token_type"] != "Bearer" || tok["expires_in"] != float64(3600) || tok["refresh_token"] == "" {
		t.Fatalf("Token: %d %v", status, tok)
	}
	access := tok["access_token"].(string)
	rec, a := w.mcp(access, "initialize", map[string]any{"protocolVersion": "2025-06-18"})
	res, _ := a["result"].(map[string]any)
	if rec.Code != http.StatusOK || res["protocolVersion"] != "2025-06-18" {
		t.Fatalf("initialize: %d %s", rec.Code, rec.Body.String())
	}

	// AC-9: Refresh mit Rotation; der alte Access-Token ist ersetzt.
	status, tok2 := w.token(url.Values{"grant_type": {"refresh_token"}, "refresh_token": {tok["refresh_token"].(string)}, "client_id": {client}})
	if status != http.StatusOK || tok2["refresh_token"] == tok["refresh_token"] {
		t.Fatalf("Refresh: %d %v", status, tok2)
	}
	if rec, _ := w.mcp(access, "ping", nil); rec.Code != http.StatusUnauthorized {
		t.Errorf("alter Access-Token gilt noch: %d", rec.Code)
	}
	access2 := tok2["access_token"].(string)
	if rec, _ := w.mcp(access2, "ping", nil); rec.Code != http.StatusOK {
		t.Fatalf("neuer Access-Token: %d", rec.Code)
	}
	// Wiederverwendung des rotierten Refresh-Tokens entwertet die Familie.
	status, f := w.token(url.Values{"grant_type": {"refresh_token"}, "refresh_token": {tok["refresh_token"].(string)}, "client_id": {client}})
	if status != http.StatusBadRequest || f["error"] != "invalid_grant" {
		t.Fatalf("Wiederverwendung: %d %v", status, f)
	}
	if rec, _ := w.mcp(access2, "ping", nil); rec.Code != http.StatusUnauthorized {
		t.Errorf("AC-9: Familie nicht entwertet, neuer Access-Token gilt noch: %d", rec.Code)
	}
	status, _ = w.token(url.Values{"grant_type": {"refresh_token"}, "refresh_token": {tok2["refresh_token"].(string)}, "client_id": {client}})
	if status != http.StatusBadRequest {
		t.Errorf("AC-9: neuer Refresh-Token der entwerteten Familie gilt noch: %d", status)
	}
}

// AC-8: PKCE; der Code ist nach einem Fehlversuch verbraucht.
func TestMCP_PKCEUndCodeNurEinmal(t *testing.T) {
	w := neueMCPWelt(t, "anna")
	keks := w.konto(model.User{ID: "anna"})
	_, c := w.registrieren(mcpCallback)
	client := c["client_id"].(string)
	v, ch := pkcePaar()
	falsch := strings.Repeat("f4lsch-", 7)

	for name, verifier := range map[string]string{"ohne": "", "falsch": falsch} {
		code := codeAus(w.zustimmen(client, ch, keks))
		felder := url.Values{"grant_type": {"authorization_code"}, "code": {code}, "redirect_uri": {mcpCallback}, "client_id": {client}}
		if verifier != "" {
			felder.Set("code_verifier", verifier)
		}
		status, f := w.token(felder)
		if status != http.StatusBadRequest || f["error"] != "invalid_grant" {
			t.Fatalf("%s Verifier: %d %v", name, status, f)
		}
		felder.Set("code_verifier", v)
		if status, _ := w.token(felder); status != http.StatusBadRequest {
			t.Errorf("AC-8 (%s): Code nach Fehlversuch nicht verbraucht: %d", name, status)
		}
	}
	code := codeAus(w.zustimmen(client, ch, keks))
	felder := url.Values{"grant_type": {"authorization_code"}, "code": {code}, "redirect_uri": {mcpCallback}, "client_id": {client}, "code_verifier": {v}}
	status, tok := w.token(felder)
	if status != http.StatusOK {
		t.Fatalf("richtiger Verifier: %d %v", status, tok)
	}
	// Zweites Einloesen widerruft alles aus diesem Code.
	if status, _ := w.token(felder); status != http.StatusBadRequest {
		t.Errorf("zweites Einloesen: %d", status)
	}
	if rec, _ := w.mcp(tok["access_token"].(string), "ping", nil); rec.Code != http.StatusUnauthorized {
		t.Errorf("zweites Einloesen widerruft nicht: %d", rec.Code)
	}
	if _, f := w.token(url.Values{"grant_type": {"password"}, "client_id": {client}}); f["error"] != "unsupported_grant_type" {
		t.Errorf("fremder grant_type: %v", f)
	}
	if status, _ := w.token(url.Values{"grant_type": {"refresh_token"}, "refresh_token": {"x"}, "client_id": {"unbekannt"}}); status != http.StatusUnauthorized {
		t.Errorf("unbekannter Client: %d", status)
	}
}

// AC-7: nur erlaubte Ruecksprungadressen.
func TestMCP_NurErlaubteRuecksprungadressen(t *testing.T) {
	w := neueMCPWelt(t, "anna")
	for _, falsch := range [][]string{{"https://evil.example/cb"}, {"http://beispiel.invalid/cb"}, {}, {"https://claude.ai/anders"}} {
		status, f := w.registrieren(falsch...)
		if status != http.StatusBadRequest || f["error"] != "invalid_redirect_uri" {
			t.Errorf("Registrierung %v: %d %v", falsch, status, f)
		}
	}
	if eintraege, _ := os.ReadDir(filepath.Join(w.cfg.DataDir, "mcp")); len(eintraege) > 0 {
		if roh, _ := os.ReadFile(filepath.Join(w.cfg.DataDir, "mcp", "clients.json")); strings.Contains(string(roh), "evil.example") {
			t.Errorf("abgelehnter Client wurde gespeichert: %s", roh)
		}
	}
	keks := w.konto(model.User{ID: "anna"})
	status, c := w.registrieren("http://localhost/callback")
	if status != http.StatusCreated {
		t.Fatalf("Loopback-Registrierung: %d %v", status, c)
	}
	_, ch := pkcePaar()
	q := authorizeWerte(c["client_id"].(string), ch)
	q.Set("redirect_uri", "http://localhost:54321/callback")
	rec := w.authorizeGet(q, keks)
	if rec.Code != http.StatusOK || !strings.Contains(rec.Header().Get("Content-Security-Policy"), "http://localhost:*") {
		t.Fatalf("Loopback mit beliebigem Port: %d %q", rec.Code, rec.Header().Get("Content-Security-Policy"))
	}
	for _, anders := range []string{"http://localhost:54321/anders", "https://evil.example/cb", mcpCallback} {
		q2 := url.Values{}
		for k, v := range q {
			q2[k] = v
		}
		q2.Set("redirect_uri", anders)
		rec := w.authorizeGet(q2, keks)
		if rec.Code != http.StatusBadRequest || rec.Header().Get("Location") != "" {
			t.Errorf("redirect_uri %s: %d %q", anders, rec.Code, rec.Header().Get("Location"))
		}
		rec = w.authorizePost(q2, "erlauben", keks, mcpBasis)
		if rec.Code == http.StatusSeeOther || strings.Contains(rec.Header().Get("Location"), "code=") {
			t.Errorf("AC-7: Code an %s: %d %q", anders, rec.Code, rec.Header().Get("Location"))
		}
	}
	for feld, wert := range map[string]string{"code_challenge_method": "plain", "resource": "https://anders.invalid/api/mcp", "response_type": "token"} {
		q2 := url.Values{}
		for k, v := range q {
			q2[k] = v
		}
		q2.Set(feld, wert)
		if rec := w.authorizeGet(q2, keks); rec.Code != http.StatusBadRequest {
			t.Errorf("%s=%s: %d", feld, wert, rec.Code)
		}
	}
	// Zustimmung nur aus Gregors eigener Herkunft.
	if rec := w.authorizePost(q, "erlauben", keks, "https://evil.example"); rec.Code != http.StatusForbidden {
		t.Errorf("fremde Herkunft: %d", rec.Code)
	}
	if rec := w.authorizePost(q, "erlauben", keks, ""); rec.Code != http.StatusForbidden {
		t.Errorf("ohne Origin: %d", rec.Code)
	}
	// Abbrechen: Fehler an den Client, kein Code.
	rec = w.authorizePost(q, "abbrechen", keks, mcpBasis)
	if rec.Code != http.StatusSeeOther || !strings.Contains(rec.Header().Get("Location"), "error=access_denied") ||
		strings.Contains(rec.Header().Get("Location"), "code=") {
		t.Errorf("Abbrechen: %d %q", rec.Code, rec.Header().Get("Location"))
	}
}

// AC-3: ohne Freigabe kein Code und kein Token; leere Liste sperrt alle.
func TestMCP_OhneFreigabeKeinCode(t *testing.T) {
	for name, liste := range map[string][]string{"andere freigegeben": {"anna"}, "leere Liste": nil} {
		t.Run(name, func(t *testing.T) {
			w := neueMCPWelt(t, liste...)
			keks := w.konto(model.User{ID: "bernd", Language: "de"})
			_, c := w.registrieren(mcpCallback)
			_, ch := pkcePaar()
			q := authorizeWerte(c["client_id"].(string), ch)
			rec := w.authorizeGet(q, keks)
			if rec.Code != http.StatusForbidden || !strings.Contains(rec.Body.String(), "nicht freigegeben") {
				t.Fatalf("Fehlerseite erwartet: %d %s", rec.Code, rec.Body.String())
			}
			rec = w.authorizePost(q, "erlauben", keks, mcpBasis)
			if rec.Code == http.StatusSeeOther || strings.Contains(rec.Header().Get("Location"), "code=") {
				t.Fatalf("AC-3: Code ohne Freigabe: %d %q", rec.Code, rec.Header().Get("Location"))
			}
		})
	}
}

// AC-3/AC-10: Freigabe-Entzug und Kontosperre wirken auf vorhandene Tokens.
func TestMCP_SperreUndEntzugBeendenDenZugriff(t *testing.T) {
	w := neueMCPWelt(t, "anna")
	keks := w.konto(model.User{ID: "anna"})
	tok, client := w.verbinden(keks)
	access := tok["access_token"].(string)
	if rec, _ := w.mcp(access, "ping", nil); rec.Code != http.StatusOK {
		t.Fatalf("Token vor der Sperre: %d", rec.Code)
	}
	if _, err := w.s.UpdateUser("anna", func(u *model.User) error { u.Disabled = true; return nil }); err != nil {
		t.Fatalf("Sperren: %v", err)
	}
	if rec, _ := w.mcp(access, "ping", nil); rec.Code != http.StatusUnauthorized {
		t.Errorf("AC-10: gesperrtes Konto, Token gilt noch: %d", rec.Code)
	}
	if status, _ := w.token(url.Values{"grant_type": {"refresh_token"}, "refresh_token": {tok["refresh_token"].(string)}, "client_id": {client}}); status != http.StatusBadRequest {
		t.Errorf("AC-10: Refresh fuer gesperrtes Konto: %d", status)
	}
	_, ch := pkcePaar()
	q := authorizeWerte(client, ch)
	if rec := w.authorizePost(q, "erlauben", keks, mcpBasis); strings.Contains(rec.Header().Get("Location"), "code=") {
		t.Errorf("AC-10: Code fuer gesperrtes Konto: %q", rec.Header().Get("Location"))
	}
}

func TestMCP_EntzugDerFreigabeWirktSofort(t *testing.T) {
	w := neueMCPWelt(t, "anna")
	keks := w.konto(model.User{ID: "anna"})
	tok, _ := w.verbinden(keks)
	// Dieselbe Ablage, neuer Router ohne Freigabe (Env-Aenderung + Neustart).
	w.cfg.MCPUserIDs = ""
	w2 := *w
	w2.r = neuerRouterMitConfig(t, w.cfg, w.s)
	if rec, _ := w2.mcp(tok["access_token"].(string), "ping", nil); rec.Code != http.StatusUnauthorized {
		t.Errorf("AC-3: Token ohne Freigabe gilt noch: %d", rec.Code)
	}
}

// Ablage: nur Hashes, nie Klartext-Tokens auf der Platte.
func TestMCP_TokensNurAlsHashAufDerPlatte(t *testing.T) {
	w := neueMCPWelt(t, "anna")
	keks := w.konto(model.User{ID: "anna"})
	tok, _ := w.verbinden(keks)
	var alles strings.Builder
	filepath.Walk(w.cfg.DataDir, func(p string, info os.FileInfo, err error) error {
		if err == nil && !info.IsDir() {
			roh, _ := os.ReadFile(p)
			alles.Write(roh)
		}
		return nil
	})
	for _, f := range []string{"access_token", "refresh_token"} {
		if strings.Contains(alles.String(), tok[f].(string)) {
			t.Errorf("%s liegt im Klartext unter GZ_DATA_DIR", f)
		}
	}
	if _, err := os.Stat(filepath.Join(w.cfg.DataDir, "mcp", "tokens.json")); err != nil {
		t.Errorf("Token-Ablage fehlt: %v", err)
	}
}

// F007 (Adversary #3282): /register haengt im Router an einer IP-Bremse von
// 20 Registrierungen je Stunde; eine andere Adresse ist davon unberuehrt.
func TestMCP_RegisterIPBremse(t *testing.T) {
	w := neueMCPWelt(t)
	anfrage := func(ip string) int {
		req := httptest.NewRequest(http.MethodPost, "/api/mcp/oauth/register",
			strings.NewReader(`{"client_name":"Claude","redirect_uris":["`+mcpCallback+`"]}`))
		req.Header.Set("Content-Type", "application/json")
		req.RemoteAddr = ip + ":4711"
		return w.anfrage(req).Code
	}
	for i := 0; i < 20; i++ {
		if c := anfrage("192.0.2.10"); c != http.StatusCreated {
			t.Fatalf("Registrierung %d: %d", i+1, c)
		}
	}
	if c := anfrage("192.0.2.10"); c != http.StatusTooManyRequests {
		t.Errorf("21. Registrierung derselben Adresse: %d (erwartet 429)", c)
	}
	if c := anfrage("192.0.2.11"); c != http.StatusCreated {
		t.Errorf("andere Adresse gebremst: %d", c)
	}
}

// Nacharbeit (Tech Lead): /api/mcp ist Maschinenpfad. Die Claude-App darf
// eine Herkunft mitschicken; das Sitzungs-Cookie wirkt dort nie als Anmeldung.
func TestMCP_HerkunftClaudeAIMitTokenUndCookieOhneToken(t *testing.T) {
	w := neueMCPWelt(t, "anna")
	keks := w.konto(model.User{ID: "anna"})
	tok, _ := w.verbinden(keks)
	for _, methode := range []string{http.MethodPost, http.MethodGet, http.MethodDelete} {
		req := httptest.NewRequest(methode, "/api/mcp", strings.NewReader(`{"jsonrpc":"2.0","id":1,"method":"ping"}`))
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("Origin", "https://claude.ai")
		req.Header.Set("Sec-Fetch-Site", "cross-site")
		req.Header.Set("Authorization", "Bearer "+tok["access_token"].(string))
		want := map[string]int{http.MethodPost: http.StatusOK, http.MethodGet: http.StatusMethodNotAllowed, http.MethodDelete: http.StatusMethodNotAllowed}[methode]
		if rec := w.anfrage(req); rec.Code != want {
			t.Errorf("%s mit Origin claude.ai und Token: %d, erwartet %d (%s)", methode, rec.Code, want, rec.Body.String())
		}
		req = httptest.NewRequest(methode, "/api/mcp", strings.NewReader(`{"jsonrpc":"2.0","id":1,"method":"ping"}`))
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("Origin", "https://claude.ai")
		req.AddCookie(keks)
		if rec := w.anfrage(req); rec.Code != http.StatusUnauthorized {
			t.Errorf("%s mit gueltigem Cookie ohne Bearer: %d, erwartet 401", methode, rec.Code)
		}
	}
	// Die Zustimmung bleibt unter der Herkunftspruefung.
	_, ch := pkcePaar()
	_, c := w.registrieren(mcpCallback)
	if rec := w.authorizePost(authorizeWerte(c["client_id"].(string), ch), "erlauben", keks, "https://claude.ai"); rec.Code != http.StatusForbidden {
		t.Errorf("Zustimmung mit fremder Herkunft: %d", rec.Code)
	}
}
