package handler

// TDD RED — Issue #627: Compare-Preset Einzel-Sofortversand via Go-Proxy.
//
// Spec: docs/specs/modules/issue_627_631_compare_send_rhythm.md (AC-1/AC-2/AC-3)
//
// Vorbild: internal/handler/loaded_trip_proxy_test.go (httptest-Fake-Upstream,
// KEIN Mock — ein echter HTTP-Server).
//
// SOLL-Verhalten nach Fix:
//   - SendComparePresetHandler bekommt eine NEUE Signatur (pythonURL string) und
//     proxyt POST auf /api/scheduler/compare-presets/{id}/send an den Python-Core.
//   - Die an den Upstream weitergereichte URL trägt die ECHTE user_id aus dem
//     Auth-Kontext (NIE "default", NIE ein client-geschmuggeltes user_id).
//   - Status + Body werden 1:1 durchgereicht.
//
// RED-Erwartung (vor Fix): COMPILE-FEHLER, weil die aktuelle Signatur
//   SendComparePresetHandler(s *store.Store) ist und keine pythonURL-Variante
//   existiert. Ein Compile-Fehler zählt als gültiges RED.

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/go-chi/chi/v5"

	"github.com/henemm/gregor-api/internal/middleware"
)

// startFakeComparePresetSendPython simuliert den Python-Core für
// POST /api/scheduler/compare-presets/{id}/send. Es zeichnet die letzte
// angefragte URL (Pfad+Query) auf, damit Tests die URL-Konstruktion prüfen können.
func startFakeComparePresetSendPython(t *testing.T, status int, body string) (*httptest.Server, *string) {
	t.Helper()
	var lastURL string
	mux := http.NewServeMux()
	mux.HandleFunc("/api/scheduler/compare-presets/", func(w http.ResponseWriter, r *http.Request) {
		lastURL = r.URL.RequestURI()
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(status)
		_, _ = w.Write([]byte(body))
	})
	srv := httptest.NewServer(mux)
	t.Cleanup(srv.Close)
	return srv, &lastURL
}

// dispatchComparePresetSend invokes the handler through a chi router so
// chi.URLParam("id") works. The given user_id (if non-empty) is injected via
// the auth context. An optional rawQuery (e.g. a smuggled "user_id=bob") is
// appended to the request path.
func dispatchComparePresetSend(h http.HandlerFunc, presetID, userID, rawQuery string) *httptest.ResponseRecorder {
	r := chi.NewRouter()
	r.Method(http.MethodPost, "/api/compare/presets/{id}/send", h)
	path := "/api/compare/presets/" + presetID + "/send"
	if rawQuery != "" {
		path += "?" + rawQuery
	}
	req := httptest.NewRequest(http.MethodPost, path, nil)
	if userID != "" {
		req = req.WithContext(middleware.ContextWithUserID(req.Context(), userID))
	}
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	return w
}

// AC-2 (HART): Auth-Kontext-User wird als ECHTE user_id durchgereicht.
func TestComparePresetSend_ForwardsRealUserID(t *testing.T) {
	py, lastURL := startFakeComparePresetSendPython(t, 200, `{"status":"ok","winner":"Zermatt"}`)

	h := SendComparePresetHandler(py.URL) // NEUE Signatur (pythonURL string)
	w := dispatchComparePresetSend(h, "cp-abc123", "alice", "")

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d (body=%q)", w.Code, w.Body.String())
	}
	if !strings.Contains(*lastURL, "/api/scheduler/compare-presets/cp-abc123/send") {
		t.Errorf("expected proxied URL to include preset send path, got %q", *lastURL)
	}
	if !strings.Contains(*lastURL, "user_id=alice") {
		t.Errorf("expected proxied URL to carry user_id=alice from auth context, got %q", *lastURL)
	}
	if strings.Contains(*lastURL, "user_id=default") {
		t.Errorf("user_id must NEVER fall back to 'default' in an authenticated path, got %q", *lastURL)
	}
}

// AC-2 (Anti-Spoofing): client-geschmuggeltes ?user_id=bob wird durch den
// authentifizierten User (alice) ersetzt.
func TestComparePresetSend_AntiSpoofing(t *testing.T) {
	py, lastURL := startFakeComparePresetSendPython(t, 200, `{"status":"ok","winner":"Zermatt"}`)

	h := SendComparePresetHandler(py.URL)
	w := dispatchComparePresetSend(h, "cp-abc123", "alice", "user_id=bob")

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d (body=%q)", w.Code, w.Body.String())
	}
	if !strings.Contains(*lastURL, "user_id=alice") {
		t.Errorf("expected smuggled user_id to be replaced by alice, got %q", *lastURL)
	}
	if strings.Contains(*lastURL, "user_id=bob") {
		t.Errorf("client-supplied user_id=bob MUST be stripped (anti-spoofing), got %q", *lastURL)
	}
}

// AC-1/AC-3: Status 200 + Body 1:1 durchgereicht; Pfad enthält die Preset-ID.
func TestComparePresetSend_PropagatesBodyAndStatus(t *testing.T) {
	py, lastURL := startFakeComparePresetSendPython(t, 200, `{"status":"ok","winner":"Zermatt"}`)

	h := SendComparePresetHandler(py.URL)
	w := dispatchComparePresetSend(h, "cp-weekly-1", "alice", "")

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d", w.Code)
	}
	got := w.Body.String()
	if !strings.Contains(got, `"status":"ok"`) || !strings.Contains(got, `"winner":"Zermatt"`) {
		t.Errorf("expected upstream body passed through 1:1, got %q", got)
	}
	if !strings.Contains(*lastURL, "cp-weekly-1") {
		t.Errorf("expected preset id in proxied URL, got %q", *lastURL)
	}
}

// AC-3-Beweis auf Proxy-Ebene: ein 422 (kein Empfänger) vom Upstream wird
// ebenfalls 1:1 durchgereicht — der Handler erfindet kein "ok".
func TestComparePresetSend_PropagatesUpstreamError(t *testing.T) {
	py, _ := startFakeComparePresetSendPython(t, 422, `{"detail":"no recipients"}`)

	h := SendComparePresetHandler(py.URL)
	w := dispatchComparePresetSend(h, "cp-no-recipients", "alice", "")

	if w.Code != 422 {
		t.Errorf("expected upstream 422 to propagate, got %d (body=%q)", w.Code, w.Body.String())
	}
}
