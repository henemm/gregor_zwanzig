package router

// TDD — Issue #1250 Scheibe 0: Legacy-CompareSubscription-Stack stilllegen (#1131).
//
// Spec: docs/specs/modules/issue_1250_briefing_subscription.md § AC-1
//
// AC-1: Die 9 bisherigen /api/subscriptions*-Routen (internal/router/router.go,
// vormals :145-158) existieren nach Scheibe 0 nicht mehr im Router — ein Request
// gegen jede dieser Routen antwortet mit 404 (Route nicht registriert), nicht mit
// 401 (Route existiert, nur Auth fehlt) oder 405 (Route existiert, falsche Methode).
//
// Echter httptest-Request gegen den vollstaendig verdrahteten router.New(...)
// (kein Mock) — mit gueltigem gz_session-Cookie, damit AuthMiddleware den
// Request tatsaechlich bis zur chi-Routen-Aufloesung durchlaesst (sonst wuerde
// jede nicht-exemptierte Route unabhaengig von Registrierung 401 liefern und der
// Test bewiese nichts).

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/go-webauthn/webauthn/webauthn"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/handler"
	authmw "github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/scheduler"
	"github.com/henemm/gregor-api/internal/store"
)

func newTestRouterForLegacySubscriptionCheck(t *testing.T) (http.Handler, string) {
	t.Helper()

	cfg, err := config.Load()
	if err != nil {
		t.Fatalf("config.Load: %v", err)
	}
	cfg.DataDir = t.TempDir()

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

	sessionCookie := authmw.SignSession("legacy-sub-test-user", cfg.SessionSecret)
	return r, sessionCookie
}

// AC-1: alle 9 vormaligen /api/subscriptions*-Routen antworten mit 404.
func TestLegacySubscriptionRoutesReturn404(t *testing.T) {
	r, sessionCookie := newTestRouterForLegacySubscriptionCheck(t)

	cases := []struct {
		method string
		path   string
	}{
		{"GET", "/api/subscriptions"},
		{"GET", "/api/subscriptions/some-id"},
		{"POST", "/api/subscriptions"},
		{"PUT", "/api/subscriptions/some-id"},
		{"PATCH", "/api/subscriptions/some-id/run-status"},
		{"DELETE", "/api/subscriptions/some-id"},
		{"POST", "/api/subscriptions/some-id/send"},
		{"GET", "/api/subscriptions/some-id/weather-config"},
		{"PUT", "/api/subscriptions/some-id/weather-config"},
	}

	for _, c := range cases {
		req := httptest.NewRequest(c.method, c.path, nil)
		req.AddCookie(&http.Cookie{Name: "gz_session", Value: sessionCookie})
		w := httptest.NewRecorder()
		r.ServeHTTP(w, req)

		if w.Code != http.StatusNotFound {
			t.Errorf(
				"%s %s: erwartet 404 (Route entfernt), bekommen %d — Legacy-CompareSubscription-Route ist noch registriert",
				c.method, c.path, w.Code,
			)
		}
	}
}

// AC-1 (Scheduler-Proxy-Anteil): die toten Go-Proxies fuer
// /api/scheduler/morning-subscriptions und /api/scheduler/evening-subscriptions
// (Python-Gegenseite liefert 404 seit #515) sind ebenfalls entfernt.
func TestLegacySchedulerSubscriptionProxiesReturn404(t *testing.T) {
	r, sessionCookie := newTestRouterForLegacySubscriptionCheck(t)

	for _, path := range []string{
		"/api/scheduler/morning-subscriptions",
		"/api/scheduler/evening-subscriptions",
	} {
		req := httptest.NewRequest("POST", path, nil)
		req.AddCookie(&http.Cookie{Name: "gz_session", Value: sessionCookie})
		w := httptest.NewRecorder()
		r.ServeHTTP(w, req)

		if w.Code != http.StatusNotFound {
			t.Errorf(
				"POST %s: erwartet 404 (toter Proxy entfernt), bekommen %d",
				path, w.Code,
			)
		}
	}
}

// AC-1 (Scheduler-Status-Endpoint): der ehemalige
// SchedulerSubscriptionsStatusHandler (GET /api/scheduler/subscriptions-status)
// ist zusammen mit dem Legacy-CompareSubscription-Stack entfernt (Scheibe 0).
func TestLegacySchedulerSubscriptionsStatusEndpointReturns404(t *testing.T) {
	r, sessionCookie := newTestRouterForLegacySubscriptionCheck(t)

	req := httptest.NewRequest("GET", "/api/scheduler/subscriptions-status", nil)
	req.AddCookie(&http.Cookie{Name: "gz_session", Value: sessionCookie})
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusNotFound {
		t.Errorf(
			"GET /api/scheduler/subscriptions-status: erwartet 404 (Route entfernt), bekommen %d",
			w.Code,
		)
	}
}
