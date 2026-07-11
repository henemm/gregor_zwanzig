package handler

import (
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/go-chi/chi/v5"

	"github.com/henemm/gregor-api/internal/middleware"
)

// startFakeStagesWeatherPython simulates the Python core for
// GET /api/_internal/trips/{id}/stages-weather. It records the last
// request path+query so tests can assert on URL construction (anti-spoofing).
func startFakeStagesWeatherPython(t *testing.T, status int, body string) (*httptest.Server, *string) {
	t.Helper()
	var lastURL string
	mux := http.NewServeMux()
	mux.HandleFunc("/api/_internal/trips/", func(w http.ResponseWriter, r *http.Request) {
		lastURL = r.URL.RequestURI()
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(status)
		_, _ = io.WriteString(w, body)
	})
	srv := httptest.NewServer(mux)
	t.Cleanup(srv.Close)
	return srv, &lastURL
}

// dispatchStagesWeatherWithChi invokes the handler through a chi router so
// chi.URLParam works, optionally injecting an auth-context user_id and a
// client-supplied query string.
func dispatchStagesWeatherWithChi(h http.HandlerFunc, path string, userID string) *httptest.ResponseRecorder {
	r := chi.NewRouter()
	r.Get("/api/trips/{id}/stages/weather", h)
	req := httptest.NewRequest("GET", path, nil)
	if userID != "" {
		req = req.WithContext(middleware.ContextWithUserID(req.Context(), userID))
	}
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	return w
}

// AC-2: authenticated user A must win over a client-supplied user_id=B —
// the proxied URL must carry user_id=A, never B.
func TestStagesWeatherProxyHandlerInjectsAuthenticatedUserID(t *testing.T) {
	py, lastURL := startFakeStagesWeatherPython(t, 200, `{"results":{}}`)

	h := StagesWeatherProxyHandler(py.URL)
	w := dispatchStagesWeatherWithChi(h, "/api/trips/gr20-corsica/stages/weather?user_id=B", "A")

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d (body=%q)", w.Code, w.Body.String())
	}
	if !strings.Contains(*lastURL, "/api/_internal/trips/gr20-corsica/stages-weather") {
		t.Errorf("expected proxied URL to include trip path, got %q", *lastURL)
	}
	if !strings.Contains(*lastURL, "user_id=A") {
		t.Errorf("expected proxied URL to carry authenticated user_id=A, got %q", *lastURL)
	}
	if strings.Contains(*lastURL, "user_id=B") {
		t.Errorf("client-supplied user_id=B must be discarded (anti-spoofing), got %q", *lastURL)
	}
}

// AC-3: unreachable Python core must yield 502 with the exact error body.
func TestStagesWeatherProxyHandlerReturns502OnUpstreamUnreachable(t *testing.T) {
	// A closed server: connecting to it fails immediately.
	srv := httptest.NewServer(http.NewServeMux())
	unreachableURL := srv.URL
	srv.Close()

	h := StagesWeatherProxyHandler(unreachableURL)
	w := dispatchStagesWeatherWithChi(h, "/api/trips/gr20-corsica/stages/weather", "A")

	if w.Code != http.StatusBadGateway {
		t.Fatalf("expected 502, got %d (body=%q)", w.Code, w.Body.String())
	}
	if got := w.Body.String(); got != `{"error":"upstream unreachable"}` {
		t.Errorf("expected exact error body, got %q", got)
	}
	if ct := w.Header().Get("Content-Type"); ct != "application/json" {
		t.Errorf("expected Content-Type application/json, got %q", ct)
	}
}

// AC-4: 404 from Python must propagate unchanged.
func TestStagesWeatherProxyHandlerPropagates404(t *testing.T) {
	py, _ := startFakeStagesWeatherPython(t, 404, `{"detail":"Trip nicht gefunden"}`)

	h := StagesWeatherProxyHandler(py.URL)
	w := dispatchStagesWeatherWithChi(h, "/api/trips/missing-trip/stages/weather", "A")

	if w.Code != 404 {
		t.Errorf("expected 404 to propagate from Python, got %d", w.Code)
	}
	if w.Body.String() != `{"detail":"Trip nicht gefunden"}` {
		t.Errorf("expected body to propagate unchanged, got %q", w.Body.String())
	}
}

// AC-4: 200 body from Python must propagate unchanged (transparent pass-through).
func TestStagesWeatherProxyHandlerPropagates200Body(t *testing.T) {
	body := `{"results":{"stage-1":{"weather_summary":{"temp_min_c":5.0},"risk":"yellow"}}}`
	py, _ := startFakeStagesWeatherPython(t, 200, body)

	h := StagesWeatherProxyHandler(py.URL)
	w := dispatchStagesWeatherWithChi(h, "/api/trips/gr20-corsica/stages/weather", "A")

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d", w.Code)
	}
	if w.Body.String() != body {
		t.Errorf("expected body passed through unchanged, got %q", w.Body.String())
	}
}
