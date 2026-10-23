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

// startFakePreviewPython simulates the Python FastAPI backend for
// GET /api/preview/{trip_id}/{channel}. The optional contentType parameter
// allows overriding the default JSON response.
func startFakePreviewPython(t *testing.T, status int, body, contentType string) (*httptest.Server, *string) {
	t.Helper()
	var lastURL string
	mux := http.NewServeMux()
	mux.HandleFunc("/api/preview/", func(w http.ResponseWriter, r *http.Request) {
		lastURL = r.URL.RequestURI()
		ct := contentType
		if ct == "" {
			ct = "application/json"
		}
		w.Header().Set("Content-Type", ct)
		w.WriteHeader(status)
		_, _ = io.WriteString(w, body)
	})
	srv := httptest.NewServer(mux)
	t.Cleanup(srv.Close)
	return srv, &lastURL
}

// dispatchPreviewWithChi invokes the handler through a chi router so chi.URLParam works.
func dispatchPreviewWithChi(h http.HandlerFunc, channel, path, userID string) *httptest.ResponseRecorder {
	r := chi.NewRouter()
	r.Method("GET", "/api/preview/{trip_id}/"+channel, h)
	req := httptest.NewRequest("GET", path, nil)
	if userID != "" {
		req = req.WithContext(middleware.ContextWithUserID(req.Context(), userID))
	}
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	return w
}

// Issue #1743: im Router ist nur noch der Kanal "sms" registriert
// (email/telegram/compare entfallen, Nachweis in
// internal/router/briefing_vorschau_route_entfernt_test.go). Die Tests hier
// pruefen den generischen Proxy deshalb ueber den sms-Kanal.

func TestPreviewProxyHandlerForwardsTripIDAndChannel(t *testing.T) {
	py, lastURL := startFakePreviewPython(t, 200, `{"subject":"x","token_line":"y","char_count":1}`, "")

	h := PreviewProxyHandler(py.URL, "sms")
	w := dispatchPreviewWithChi(h, "sms", "/api/preview/gr20/sms", "default")

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d (body=%q)", w.Code, w.Body.String())
	}
	if !strings.Contains(*lastURL, "/api/preview/gr20/sms") {
		t.Errorf("expected proxied URL to include trip_id and channel, got %q", *lastURL)
	}
}

func TestPreviewProxyHandlerForwardsTypeQueryParam(t *testing.T) {
	py, lastURL := startFakePreviewPython(t, 200, `{"token_line":"y"}`, "")

	h := PreviewProxyHandler(py.URL, "sms")
	w := dispatchPreviewWithChi(h, "sms", "/api/preview/gr20/sms?type=evening", "default")

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d", w.Code)
	}
	if !strings.Contains(*lastURL, "type=evening") {
		t.Errorf("expected ?type=evening to be forwarded, got %q", *lastURL)
	}
}

func TestPreviewProxyHandlerInjectsUserIDFromAuthContext(t *testing.T) {
	py, lastURL := startFakePreviewPython(t, 200, `{"token_line":"y"}`, "")

	h := PreviewProxyHandler(py.URL, "sms")
	dispatchPreviewWithChi(h, "sms", "/api/preview/gr20/sms?type=morning&user_id=mallory", "alice")

	if !strings.Contains(*lastURL, "user_id=alice") {
		t.Errorf("expected user_id=alice from auth context in upstream URL, got %q", *lastURL)
	}
	if strings.Contains(*lastURL, "mallory") {
		t.Errorf("client-supplied user_id must be discarded, got %q", *lastURL)
	}
	if !strings.Contains(*lastURL, "type=morning") {
		t.Errorf("expected original type=morning to remain alongside user_id, got %q", *lastURL)
	}
}

func TestPreviewProxyHandlerForwardsUpstreamContentType(t *testing.T) {
	py, _ := startFakePreviewPython(t, 200, `{"token_line":"preview"}`, "application/json; charset=utf-8")

	h := PreviewProxyHandler(py.URL, "sms")
	w := dispatchPreviewWithChi(h, "sms", "/api/preview/gr20/sms", "default")

	if got := w.Header().Get("Content-Type"); got != "application/json; charset=utf-8" {
		t.Errorf("expected upstream Content-Type to pass through, got %q", got)
	}
	if !strings.Contains(w.Body.String(), "preview") {
		t.Errorf("expected body to pass through, got %q", w.Body.String())
	}
}

func TestPreviewProxyHandlerPropagates404(t *testing.T) {
	py, _ := startFakePreviewPython(t, 404, `{"detail":"trip not found"}`, "")

	h := PreviewProxyHandler(py.URL, "sms")
	w := dispatchPreviewWithChi(h, "sms", "/api/preview/missing-trip/sms", "default")

	if w.Code != 404 {
		t.Errorf("expected 404 to propagate from Python, got %d", w.Code)
	}
}

func TestPreviewProxyHandlerHandlesUpstreamError(t *testing.T) {
	// Closed server simulates connection-refused.
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {}))
	srv.Close()

	h := PreviewProxyHandler(srv.URL, "sms")
	w := dispatchPreviewWithChi(h, "sms", "/api/preview/gr20/sms?type=morning", "default")

	if w.Code != http.StatusBadGateway {
		t.Errorf("expected 502 on upstream connection error, got %d", w.Code)
	}
	if !strings.Contains(w.Body.String(), "upstream unreachable") {
		t.Errorf("expected upstream-unreachable error body, got %q", w.Body.String())
	}
}
