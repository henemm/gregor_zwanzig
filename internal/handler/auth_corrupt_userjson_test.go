package handler

import (
	"bytes"
	"log"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// TDD RED (#1596, AC-1 + AC-4-Abgrenzung): eine VORHANDENE, aber kaputte
// user.json muss serverseitig geloggt werden; eine tatsaechlich FEHLENDE
// user.json (legitimer Normalfall) muss weiterhin still bleiben. Die
// Client-Antwort (401 + generischer Body) bleibt in BEIDEN Faellen
// identisch -- kein User-Enumeration-Leak.
func TestLoginHandlerLogsOnlyForCorruptNotMissingUserJSON(t *testing.T) {
	s := newTestStore(t)
	dir := filepath.Join(s.DataDir, "users", "alice")
	os.MkdirAll(dir, 0755)
	os.WriteFile(filepath.Join(dir, "user.json"), []byte(`{not valid json`), 0644)

	h := LoginHandler(s, "secret")

	// Fall 1: kaputte, aber vorhandene user.json ("alice") -> muss geloggt
	// werden (AC-1).
	var logBuf bytes.Buffer
	log.SetOutput(&logBuf)
	defer log.SetOutput(os.Stderr)

	body := `{"username":"alice","password":"geheim123"}`
	req := httptest.NewRequest("POST", "/api/auth/login", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 401 {
		t.Fatalf("expected 401 for corrupt user.json (no enumeration leak), got %d", w.Code)
	}
	if !strings.Contains(w.Body.String(), "invalid credentials") {
		t.Errorf("expected generic 'invalid credentials' body, got %q", w.Body.String())
	}
	if !strings.Contains(logBuf.String(), "alice") {
		t.Errorf("AC-1: Server-Log muss den betroffenen Nutzernamen enthalten (kaputte user.json), bekam: %q", logBuf.String())
	}

	// Fall 2: tatsaechlich FEHLENDE user.json ("nobody") -> darf NICHT
	// geloggt werden (AC-4-Abgrenzung, legitimer Normalfall).
	logBuf.Reset()
	body2 := `{"username":"nobody","password":"geheim123"}`
	req2 := httptest.NewRequest("POST", "/api/auth/login", strings.NewReader(body2))
	w2 := httptest.NewRecorder()
	h.ServeHTTP(w2, req2)

	if w2.Code != 401 {
		t.Fatalf("expected 401 for unknown user, got %d", w2.Code)
	}
	if logBuf.Len() != 0 {
		t.Errorf("AC-4: fehlende user.json ist der Normalfall und darf NICHT geloggt werden, bekam: %q", logBuf.String())
	}
}
