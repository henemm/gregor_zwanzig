package resolver_test

// Client-ID-Metadaten-Dokument (CIMD) fuer den MCP-Konnektor (Issue #3281,
// Scheibe 2): Abruf nur ueber den abgeschotteten Client (ADR-0114), nur von
// claude.ai, ohne Weiterleitungen, hoechstens 64 KB.

import (
	"context"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/henemm/gregor-api/internal/resolver"
)

func TestClientDokumentHolen_NurClaudeAI(t *testing.T) {
	for _, adresse := range []string{
		"https://evil.example/meta", "http://claude.ai/meta", "https://claude.ai:8443/meta",
		"https://user@claude.ai/meta", "https://claude.ai.evil.example/meta", "kein url",
	} {
		if _, err := resolver.ClientDokumentHolen(context.Background(), adresse); err == nil {
			t.Errorf("%s: Abruf haette abgelehnt werden muessen", adresse)
		}
	}
}

func TestClientDokumentHolen_AbrufOhneWeiterleitung(t *testing.T) {
	var agenten []string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		agenten = append(agenten, r.Header.Get("User-Agent"))
		switch r.URL.Path {
		case "/meta":
			w.Write([]byte(`{"client_id":"x","redirect_uris":["https://claude.ai/api/mcp/auth_callback"]}`))
		case "/weiter":
			http.Redirect(w, r, "/meta", http.StatusFound)
		case "/gross":
			w.Write([]byte(strings.Repeat("a", 70000)))
		default:
			w.WriteHeader(http.StatusNotFound)
		}
	}))
	defer srv.Close()
	resolver.ErlaubeLoopbackVerbindung(t)
	resolver.ErlaubeHTTPSchema(t)
	resolver.ErlaubeClientDokumentHost(t, "127.0.0.1")

	roh, err := resolver.ClientDokumentHolen(context.Background(), srv.URL+"/meta")
	if err != nil || !strings.Contains(string(roh), "redirect_uris") {
		t.Fatalf("Abruf: %v %s", err, roh)
	}
	if len(agenten) != 1 || !strings.HasPrefix(agenten[0], "gregor-zwanzig/") {
		t.Errorf("eigene Kennung erwartet (claude.ai weist Standardkennungen ab): %v", agenten)
	}
	if _, err := resolver.ClientDokumentHolen(context.Background(), srv.URL+"/weiter"); err == nil {
		t.Errorf("Weiterleitung darf nicht gefolgt werden")
	}
	if len(agenten) != 2 {
		t.Errorf("Weiterleitungsziel wurde abgerufen: %v", agenten)
	}
	if _, err := resolver.ClientDokumentHolen(context.Background(), srv.URL+"/fehlt"); err == nil {
		t.Errorf("404 ist kein Dokument")
	}
	if _, err := resolver.ClientDokumentHolen(context.Background(), srv.URL+"/gross"); err == nil {
		t.Errorf("Dokument ueber 64 KB muss abgelehnt werden")
	}
}
