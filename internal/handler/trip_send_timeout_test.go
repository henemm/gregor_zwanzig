package handler

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/go-chi/chi/v5"

	"github.com/henemm/gregor-api/internal/middleware"
)

// Issue #1756 — SendTripReportProxyHandler: Timeout-Anhebung 120s -> 300s
// (AC-8) plus 409-Passthrough. Spec: docs/specs/modules/fix_1756_send_idempotenz_lock.md

func dispatchTripSend(h http.HandlerFunc, path, userID string) *httptest.ResponseRecorder {
	r := chi.NewRouter()
	r.Method("POST", "/api/trips/{id}/send", h)
	req := httptest.NewRequest("POST", path, nil)
	if userID != "" {
		req = req.WithContext(middleware.ContextWithUserID(req.Context(), userID))
	}
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	return w
}

// Issue #2124: der fruehere Quelltext-Grep-Test auf das Literal "300 * time.Second"
// (TestSendTripReportProxyHandlerTimeoutIs300Seconds) ist entfallen. Wert UND Wirkort
// des 300-s-Timeouts bewacht jetzt proxy_timeout_chain_test.go verhaltensnah
// (sendProxyTimeout, gemeinsam fuer Trip und Compare).

func startFakeSchedulerPython(t *testing.T, status int, body string) *httptest.Server {
	t.Helper()
	mux := http.NewServeMux()
	mux.HandleFunc("/api/scheduler/", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(status)
		_, _ = w.Write([]byte(body))
	})
	srv := httptest.NewServer(mux)
	t.Cleanup(srv.Close)
	return srv
}

func TestSendTripReportProxyHandlerPropagates409(t *testing.T) {
	py := startFakeSchedulerPython(t, 409, `{"detail":"Versand fuer evening laeuft bereits - bitte warten"}`)

	h := SendTripReportProxyHandler(py.URL)
	w := dispatchTripSend(h, "/api/trips/korsika/send?report_type=evening", "alice")

	if w.Code != http.StatusConflict {
		t.Errorf("expected 409 to propagate from Python, got %d (body=%q)", w.Code, w.Body.String())
	}
	if !strings.Contains(w.Body.String(), "laeuft bereits") {
		t.Errorf("expected upstream detail body to pass through unchanged, got %q", w.Body.String())
	}
}
