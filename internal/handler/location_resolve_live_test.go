//go:build integration

// Live-Variante (Issue #3115): prueft den echten Komoot-Vertrag ueber den
// HTTP-Endpunkt. Laeuft nur mit `go test -tags integration`, nie im
// Kern-Lauf (ADR-0094). Offline deckt den Komoot-Erfolgspfad
// internal/resolver/resolver_test.go::TestResolveKomootHighlight ab.
package handler

import (
	"encoding/json"
	"net/http/httptest"
	"strings"
	"testing"
)

// AC-1: Komoot Highlight über HTTP-Endpoint (echter API-Call)
func TestResolveHandlerKomootHighlightLive(t *testing.T) {
	// Highlight 126361 = Gavia Pass (verifiziert erreichbar)
	body := `{"input": "https://www.komoot.com/de-de/highlight/126361"}`

	h := ResolveLocationHandler()
	req := httptest.NewRequest("POST", "/api/locations/resolve", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	var resp map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &resp)
	if resp["lat"] == nil {
		t.Error("expected lat in response")
	}
	if resp["source_type"] != "komoot" {
		t.Errorf("expected source_type 'komoot', got %v", resp["source_type"])
	}
	if resp["timezone"] == nil || resp["timezone"] == "" {
		t.Error("expected timezone in response")
	}
}
