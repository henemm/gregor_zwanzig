package handler

// TDD RED — Issue #2124 AC-1: Upstream-Versand laeuft trotz Client-Abbruch zu Ende.
//
// Spec: docs/specs/modules/fix_2124_versand_nginx_timeout.md (AC-1)
//
// Given der Browser oder nginx bricht die Verbindung ab, waehrend der
// Python-Upstream eines Trip- oder Ortsvergleich-Versands noch laeuft /
// When der Go-Handler den Upstream-Request ausfuehrt / Then wird der
// Upstream-Request nicht abgebrochen und laeuft zu Ende.
//
// Kein Mock: echter httptest-Upstream (simulierter Python-Core), der
// verzoegert antwortet und beobachtet, ob SEIN Request-Context abgebrochen
// wird (Go-HTTP-Server bricht r.Context() ab, sobald der Client — hier der
// Go-Proxy — die Verbindung schliesst). Der Client-Context des Handler-
// Requests wird mitten im Lauf per cancel() abgebrochen (= Browser/nginx
// legt auf).
//
// RED heute: beide Handler bauen den Upstream-Request mit r.Context();
// der Abbruch schlaegt bis zum Upstream durch -> Ergebnis "canceled".
// GREEN nach Fix: context.WithoutCancel(r.Context()) -> "completed".

import (
	"context"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/go-chi/chi/v5"

	"github.com/henemm/gregor-api/internal/middleware"
)

const ctxTestUpstreamDelay = 400 * time.Millisecond

// startCancelObservingUpstream startet einen Fake-Python-Core, der beim
// Betreten `entered` signalisiert und dann entweder nach der Verzoegerung
// regulaer antwortet ("completed") oder vorher den Abbruch seines eigenen
// Request-Contexts beobachtet ("canceled"). Das Ergebnis landet in `result`.
func startCancelObservingUpstream(t *testing.T, pathPrefix string) (*httptest.Server, <-chan struct{}, <-chan string) {
	t.Helper()
	entered := make(chan struct{}, 1)
	result := make(chan string, 1)
	mux := http.NewServeMux()
	mux.HandleFunc(pathPrefix, func(w http.ResponseWriter, r *http.Request) {
		select {
		case entered <- struct{}{}:
		default:
		}
		select {
		case <-time.After(ctxTestUpstreamDelay):
			result <- "completed"
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusOK)
			_, _ = w.Write([]byte(`{"status":"ok"}`))
		case <-r.Context().Done():
			result <- "canceled"
		}
	})
	srv := httptest.NewServer(mux)
	t.Cleanup(srv.Close)
	return srv, entered, result
}

// runWithClientAbort ruft den Handler ueber einen chi-Router mit einem
// abbrechbaren Client-Context auf, bricht diesen ab, sobald der Upstream
// betreten wurde, und liefert das vom Upstream beobachtete Ergebnis.
func runWithClientAbort(t *testing.T, h http.HandlerFunc, routePattern, path string,
	entered <-chan struct{}, result <-chan string) string {
	t.Helper()
	router := chi.NewRouter()
	router.Method(http.MethodPost, routePattern, h)

	ctx, cancel := context.WithCancel(middleware.ContextWithUserID(context.Background(), "alice"))
	defer cancel()
	req := httptest.NewRequest(http.MethodPost, path, nil).WithContext(ctx)
	rec := httptest.NewRecorder()

	done := make(chan struct{})
	go func() {
		defer close(done)
		router.ServeHTTP(rec, req)
	}()

	select {
	case <-entered:
	case <-time.After(3 * time.Second):
		t.Fatal("Upstream wurde nicht betreten — Handler hat nicht weitergeleitet")
	}

	// Browser/nginx legt auf, waehrend der Upstream noch arbeitet.
	cancel()

	var got string
	select {
	case got = <-result:
	case <-time.After(3 * time.Second):
		t.Fatal("Upstream hat weder abgeschlossen noch einen Abbruch beobachtet")
	}

	select {
	case <-done:
	case <-time.After(3 * time.Second):
		t.Fatal("Handler ist nicht zurueckgekehrt")
	}
	return got
}

func TestSendTripReportProxy_ClientAbortDoesNotCancelUpstream(t *testing.T) {
	py, entered, result := startCancelObservingUpstream(t, "/api/scheduler/trips/")
	h := SendTripReportProxyHandler(py.URL)

	got := runWithClientAbort(t, h, "/api/trips/{id}/send",
		"/api/trips/trip-2124/send?report_type=evening", entered, result)

	if got != "completed" {
		t.Errorf("Trip-Versand: Client-Abbruch hat den Upstream-Request abgebrochen "+
			"(Upstream beobachtete %q, erwartet \"completed\") — der Python-Lauf muss "+
			"vom Client-Context entkoppelt sein (context.WithoutCancel).", got)
	}
}

func TestSendComparePresetProxy_ClientAbortDoesNotCancelUpstream(t *testing.T) {
	py, entered, result := startCancelObservingUpstream(t, "/api/scheduler/compare-presets/")
	h := SendComparePresetHandler(py.URL)

	got := runWithClientAbort(t, h, "/api/compare/presets/{id}/send",
		"/api/compare/presets/cp-2124/send", entered, result)

	if got != "completed" {
		t.Errorf("Ortsvergleich-Versand: Client-Abbruch hat den Upstream-Request abgebrochen "+
			"(Upstream beobachtete %q, erwartet \"completed\") — der Python-Lauf muss "+
			"vom Client-Context entkoppelt sein (context.WithoutCancel).", got)
	}
}
