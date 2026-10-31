package handler

// Issue #2676 (G2), F004: Ist der Python-Core nicht erreichbar, antwortet der
// Test-Versand mit 503 und dem Code core_unavailable. Kein Mock: ein echter
// HTTP-Server wird gestartet und sofort geschlossen, damit die Verbindung
// tatsaechlich abgelehnt wird.

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/henemm/gregor-api/internal/store"
)

func TestNotifyTestHandler_CoreNichtErreichbar_503CoreUnavailable(t *testing.T) {
	gestoppt := httptest.NewServer(http.NotFoundHandler())
	url := gestoppt.URL
	gestoppt.Close()

	s := store.New(t.TempDir(), "default")
	h := NotifyTestHandler(s, url)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, authedRequest(http.MethodPost, "/api/notify/test", "alice",
		[]byte(`{"channel":"email"}`)))

	if w.Code != http.StatusServiceUnavailable {
		t.Fatalf("F004: erwartet 503, bekommen %d: %s", w.Code, w.Body.String())
	}
	if code := fehlerCodeVon(w); code != "core_unavailable" {
		t.Errorf("F004: erwartet code core_unavailable, bekommen %q: %s", code, w.Body.String())
	}
	if !strings.Contains(w.Body.String(), "core_unavailable") {
		t.Errorf("F004: Body ohne core_unavailable: %s", w.Body.String())
	}
}
