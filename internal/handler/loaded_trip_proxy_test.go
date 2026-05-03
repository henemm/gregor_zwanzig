package handler

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/go-chi/chi/v5"

	"github.com/henemm/gregor-api/internal/middleware"
)

// startFakeLoadedTripPython simulates the Python FastAPI backend for
// GET /api/_internal/trip/{trip_id}/loaded. It records the last request
// path+query so tests can assert on URL construction.
func startFakeLoadedTripPython(t *testing.T, status int, body string) (*httptest.Server, *string) {
	t.Helper()
	var lastURL string
	mux := http.NewServeMux()
	mux.HandleFunc("/api/_internal/trip/", func(w http.ResponseWriter, r *http.Request) {
		lastURL = r.URL.RequestURI()
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(status)
		_, _ = io.WriteString(w, body)
	})
	srv := httptest.NewServer(mux)
	t.Cleanup(srv.Close)
	return srv, &lastURL
}

// dispatchWithChi invokes the handler through a chi router so chi.URLParam works.
func dispatchWithChi(h http.HandlerFunc, method, path string, userID string) *httptest.ResponseRecorder {
	r := chi.NewRouter()
	r.Method(method, "/api/_internal/trip/{id}/loaded", h)
	req := httptest.NewRequest(method, path, nil)
	if userID != "" {
		req = req.WithContext(middleware.ContextWithUserID(req.Context(), userID))
	}
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	return w
}

func TestLoadedTripProxyHandlerForwardsToPython(t *testing.T) {
	body := `{"id":"gr221-mallorca","name":"GR221 Mallorca","display_config":{"metrics":[]}}`
	py, lastURL := startFakeLoadedTripPython(t, 200, body)

	h := LoadedTripProxyHandler(py.URL)
	w := dispatchWithChi(h, "GET", "/api/_internal/trip/gr221-mallorca/loaded", "default")

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d (body=%q)", w.Code, w.Body.String())
	}
	if !strings.Contains(*lastURL, "/api/_internal/trip/gr221-mallorca/loaded") {
		t.Errorf("expected proxied URL to include trip path, got %q", *lastURL)
	}
	if !strings.Contains(*lastURL, "user_id=default") {
		t.Errorf("expected proxied URL to include user_id from auth context, got %q", *lastURL)
	}
}

func TestLoadedTripProxyHandlerPropagatesPythonBody(t *testing.T) {
	body := `{"id":"gr221-mallorca","display_config":{"metrics":[{"metric_id":"fresh_snow","enabled":true}]}}`
	py, _ := startFakeLoadedTripPython(t, 200, body)

	h := LoadedTripProxyHandler(py.URL)
	w := dispatchWithChi(h, "GET", "/api/_internal/trip/gr221-mallorca/loaded", "default")

	var got map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &got); err != nil {
		t.Fatalf("response body not valid JSON: %v (body=%q)", err, w.Body.String())
	}
	if got["id"] != "gr221-mallorca" {
		t.Errorf("expected id passed through, got %v", got["id"])
	}
	if _, ok := got["display_config"]; !ok {
		t.Error("expected display_config to be passed through unchanged")
	}
}

func TestLoadedTripProxyHandlerPropagates404(t *testing.T) {
	py, _ := startFakeLoadedTripPython(t, 404, `{"detail":"Trip nicht gefunden"}`)

	h := LoadedTripProxyHandler(py.URL)
	w := dispatchWithChi(h, "GET", "/api/_internal/trip/missing-trip/loaded", "default")

	if w.Code != 404 {
		t.Errorf("expected 404 to propagate from Python, got %d", w.Code)
	}
}

func TestLoadedTripProxyHandlerExtractsTripIDFromPath(t *testing.T) {
	py, lastURL := startFakeLoadedTripPython(t, 200, `{}`)

	h := LoadedTripProxyHandler(py.URL)
	dispatchWithChi(h, "GET", "/api/_internal/trip/some-other-trip-123/loaded", "default")

	if !strings.Contains(*lastURL, "/api/_internal/trip/some-other-trip-123/loaded") {
		t.Errorf("trip_id from chi.URLParam not forwarded correctly. Got %q", *lastURL)
	}
}
