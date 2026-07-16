package handler

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/go-chi/chi/v5"

	"github.com/henemm/gregor-api/internal/middleware"
)

// Issue #1270 — Go-Proxy fuer POST /api/preview/compare/{preset_id}.
// Spec: docs/specs/modules/compare_channel_preview_dispatch.md (AC-6/AC-7).
//
// Echter HTTP-Verkehr gegen einen httptest-Server statt Mock: der Test prueft
// das tatsaechlich abgesetzte Upstream-Request (URL, Query, Body, Status).

// dispatchComparePreview invokes the handler through a chi router so
// chi.URLParam("preset_id") resolves.
func dispatchComparePreview(h http.HandlerFunc, path, userID, body string) *httptest.ResponseRecorder {
	r := chi.NewRouter()
	r.Method("POST", "/api/preview/compare/{preset_id}", h)
	req := httptest.NewRequest("POST", path, strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	if userID != "" {
		req = req.WithContext(middleware.ContextWithUserID(req.Context(), userID))
	}
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	return w
}

func TestComparePreviewProxyForwardsPresetIDAndAllChannels(t *testing.T) {
	py, lastURL := startFakePreviewPython(
		t, 200,
		`{"subject":"Vergleich","email_html":"<p>x</p>","telegram":"ORTS-VERGLEICH","sms":"Vergleich 17.07.","sms_char_count":17}`,
		"",
	)

	h := ComparePreviewProxyHandler(py.URL)
	w := dispatchComparePreview(h, "/api/preview/compare/cmp-1270", "alice", "{}")

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d (body=%q)", w.Code, w.Body.String())
	}
	if !strings.HasPrefix(*lastURL, "/api/preview/compare/cmp-1270") {
		t.Errorf("expected proxied URL to include preset_id, got %q", *lastURL)
	}
	// AC-7: eine Antwort traegt alle Kanaele — kein Nachladen beim Kanalwechsel.
	for _, key := range []string{"email_html", "telegram", "sms", "sms_char_count"} {
		if !strings.Contains(w.Body.String(), key) {
			t.Errorf("expected %q in proxied response body, got %q", key, w.Body.String())
		}
	}
}

// AC-6 / ADR-0003: die user_id kommt aus dem Auth-Kontext, niemals vom Client.
func TestComparePreviewProxyInjectsUserIDFromAuthContext(t *testing.T) {
	py, lastURL := startFakePreviewPython(t, 200, `{}`, "")

	h := ComparePreviewProxyHandler(py.URL)
	dispatchComparePreview(h, "/api/preview/compare/cmp-1270?date=2026-07-17", "alice", "{}")

	if !strings.Contains(*lastURL, "user_id=alice") {
		t.Errorf("expected user_id=alice from auth context, got %q", *lastURL)
	}
	if !strings.Contains(*lastURL, "date=2026-07-17") {
		t.Errorf("expected date query param to be forwarded, got %q", *lastURL)
	}
}

// Anti-Spoofing: eine mitgeschickte fremde user_id wird verworfen, nicht
// ergaenzt — sonst waere die Preset-Isolation (AC-6) umgehbar.
func TestComparePreviewProxyOverridesClientSuppliedUserID(t *testing.T) {
	py, lastURL := startFakePreviewPython(t, 200, `{}`, "")

	h := ComparePreviewProxyHandler(py.URL)
	dispatchComparePreview(h, "/api/preview/compare/cmp-1270?user_id=victim", "attacker", "{}")

	if strings.Contains(*lastURL, "victim") {
		t.Errorf("client-supplied user_id must be discarded, got %q", *lastURL)
	}
	if !strings.Contains(*lastURL, "user_id=attacker") {
		t.Errorf("expected authenticated user_id to be injected, got %q", *lastURL)
	}
}

// Fremdes Preset → Python antwortet 404; der Proxy darf das nicht schoenen.
func TestComparePreviewProxyPropagates404(t *testing.T) {
	py, _ := startFakePreviewPython(t, 404, `{"detail":"preset not found"}`, "")

	h := ComparePreviewProxyHandler(py.URL)
	w := dispatchComparePreview(h, "/api/preview/compare/foreign-preset", "bob", "{}")

	if w.Code != 404 {
		t.Errorf("expected 404 to propagate from Python, got %d", w.Code)
	}
}

func TestComparePreviewProxyHandlesUpstreamError(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {}))
	srv.Close()

	h := ComparePreviewProxyHandler(srv.URL)
	w := dispatchComparePreview(h, "/api/preview/compare/cmp-1270", "alice", "{}")

	if w.Code != http.StatusBadGateway {
		t.Errorf("expected 502 on upstream connection error, got %d", w.Code)
	}
	if !strings.Contains(w.Body.String(), "upstream unreachable") {
		t.Errorf("expected upstream-unreachable error body, got %q", w.Body.String())
	}
}
