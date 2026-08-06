package router

// Nachtrag Issue #923: die Spec-Annahme "Kein Go-Anteil" war falsch — jeder
// Frontend-Aufruf an /api/_validator/* läuft über die Go-API (Port 8090) als
// Proxy zum Python-Core. Ohne dedizierte Route in router.go wäre der neue
// Endpoint /api/_validator/sms-fidelity-preview im Browser mit 404
// fehlgeschlagen, obwohl alle Python- und Frontend-Tests grün waren (keiner
// davon ist über den echten Go-Proxy-Weg gelaufen).
//
// Dieser Test läuft gegen den ECHTEN Produktions-Router (router.New(...),
// dieselbe Verdrahtung wie cmd/server/main.go) inkl. AuthMiddleware — Muster
// aus briefing_subscription_test.go. Statt eines echten Python-Core-Prozesses
// steht ein httptest.NewServer als Fake-Backend bereit, dessen empfangene
// Request-Daten der Test prüft (Pfad, Methode, Body-Weiterleitung).

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/go-webauthn/webauthn/webauthn"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/handler"
	"github.com/henemm/gregor-api/internal/scheduler"
	"github.com/henemm/gregor-api/internal/store"
)

// newSmsFidelityTestRouter baut den echten Produktions-Router mit einem
// ueberschriebenen PythonCoreURL, der auf ein Fake-Backend zeigt (analog
// newBriefingTestRouter, hier zusaetzlich parametrisierbar).
func newSmsFidelityTestRouter(t *testing.T, pythonURL string) (http.Handler, string) {
	t.Helper()

	cfg, err := config.Load()
	if err != nil {
		t.Fatalf("config.Load: %v", err)
	}
	cfg.DataDir = t.TempDir()
	cfg.PythonCoreURL = pythonURL

	s := store.New(cfg.DataDir, cfg.UserID)

	wa, err := webauthn.New(&webauthn.Config{
		RPID:          cfg.WebAuthnRPID,
		RPDisplayName: cfg.WebAuthnRPDisplayName,
		RPOrigins:     []string{"http://localhost:5173"},
	})
	if err != nil {
		t.Fatalf("webauthn.New: %v", err)
	}

	sched, err := scheduler.New(cfg, s)
	if err != nil {
		t.Fatalf("scheduler.New: %v", err)
	}
	t.Cleanup(sched.Stop)

	r := New(Deps{
		Config:             cfg,
		Store:              s,
		WeatherProvider:    nil,
		WebAuthn:           wa,
		ChallengeStore:     handler.NewChallengeStore(),
		Scheduler:          sched,
		TelegramTokenStore: handler.NewTelegramTokenStore(cfg.DataDir),
		GitCommit:          "test",
	})

	return r, cfg.SessionSecret
}

// TestSmsFidelityPreviewRoute_ProxiesToPythonCore:
// GIVEN ein gueltiges Session-Cookie und einen laufenden (Fake-)Python-Core
// WHEN  POST /api/_validator/sms-fidelity-preview ueber den ECHTEN Router
// THEN  200, der Body wird 1:1 an das Python-Backend weitergereicht und dessen
//       Antwort unveraendert durchgereicht — beweist, dass die Route
//       tatsaechlich registriert ist (vorher: 404, s. Nachtrag oben).
func TestSmsFidelityPreviewRoute_ProxiesToPythonCore(t *testing.T) {
	var receivedPath, receivedMethod, receivedBody string
	py := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		receivedPath = r.URL.Path
		receivedMethod = r.Method
		buf := new(bytes.Buffer)
		buf.ReadFrom(r.Body)
		receivedBody = buf.String()
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"line":"Etappe: D18","char_count":11,"max_length":160,"carried_ids":["temperature"]}`))
	}))
	defer py.Close()

	r, secret := newSmsFidelityTestRouter(t, py.URL)
	cookie := sessionCookieFor("user1", secret)

	body := []byte(`{"metric_ids":["temperature"]}`)
	req := httptest.NewRequest("POST", "/api/_validator/sms-fidelity-preview", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	req.AddCookie(cookie)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
	if receivedMethod != "POST" {
		t.Errorf("expected Python-Core to receive POST, got %q", receivedMethod)
	}
	if receivedPath != "/api/_validator/sms-fidelity-preview" {
		t.Errorf("expected Python-Core path /api/_validator/sms-fidelity-preview, got %q", receivedPath)
	}
	if receivedBody != string(body) {
		t.Errorf("expected body forwarded unchanged, got %q", receivedBody)
	}

	var result map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &result); err != nil {
		t.Fatalf("expected valid JSON response, got error: %v", err)
	}
	if result["line"] != "Etappe: D18" {
		t.Errorf("expected proxied response body, got %v", result)
	}
}

// TestSmsFidelityPreviewRoute_NoLongerFourOhFour:
// Der Kern des Nachtrags: ohne Route-Registrierung antwortet chi mit 404 fuer
// JEDEN Request gegen /api/_validator/sms-fidelity-preview — unabhaengig vom
// Body. Dieser Test macht das Fehlen der Route explizit unmoeglich zu
// uebersehen (Regressions-Guard fuer kuenftige Refactorings von router.go).
func TestSmsFidelityPreviewRoute_NoLongerFourOhFour(t *testing.T) {
	py := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte(`{}`))
	}))
	defer py.Close()

	r, secret := newSmsFidelityTestRouter(t, py.URL)
	cookie := sessionCookieFor("user1", secret)

	req := httptest.NewRequest("POST", "/api/_validator/sms-fidelity-preview", bytes.NewReader([]byte(`{}`)))
	req.Header.Set("Content-Type", "application/json")
	req.AddCookie(cookie)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code == http.StatusNotFound {
		t.Fatalf("REGRESSION: /api/_validator/sms-fidelity-preview is not registered (404) — see router.go")
	}
}

// TestSmsFidelityPreviewRoute_PythonCoreDown:
// GIVEN ein nicht erreichbarer Python-Core
// WHEN  POST ueber den echten Router
// THEN  502 (upstream unreachable), kein 500/Crash — dasselbe Fail-soft-
//       Verhalten wie die uebrigen Proxy-Handler (s. CompareEmailPreviewProxyHandler).
func TestSmsFidelityPreviewRoute_PythonCoreDown(t *testing.T) {
	r, secret := newSmsFidelityTestRouter(t, "http://127.0.0.1:19999")
	cookie := sessionCookieFor("user1", secret)

	req := httptest.NewRequest("POST", "/api/_validator/sms-fidelity-preview", bytes.NewReader([]byte(`{}`)))
	req.Header.Set("Content-Type", "application/json")
	req.AddCookie(cookie)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusBadGateway {
		t.Errorf("expected 502 when Python-Core is unreachable, got %d: %s", w.Code, w.Body.String())
	}
}

// TestSmsFidelityPreviewRoute_RequiresAuth:
// GIVEN kein Session-Cookie
// WHEN  POST /api/_validator/sms-fidelity-preview
// THEN  401 (AuthMiddleware greift global, auch fuer zustandslose Validator-
//       Endpoints — kein Public-Pfad-Ausnahme in middleware/auth.go).
func TestSmsFidelityPreviewRoute_RequiresAuth(t *testing.T) {
	py := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte(`{}`))
	}))
	defer py.Close()

	r, _ := newSmsFidelityTestRouter(t, py.URL)

	req := httptest.NewRequest("POST", "/api/_validator/sms-fidelity-preview", bytes.NewReader([]byte(`{}`)))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusUnauthorized {
		t.Errorf("expected 401 without session cookie, got %d: %s", w.Code, w.Body.String())
	}
}
