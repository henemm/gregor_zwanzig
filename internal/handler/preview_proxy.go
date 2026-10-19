package handler

import (
	"io"
	"net/http"
	"time"

	"github.com/go-chi/chi/v5"

	"github.com/henemm/gregor-api/internal/middleware"
)

// Issue #2283 S1 (AC-5): Zeitgrenzen der Vorschau-Proxys. Trip-Vorschau und
// Alarm-Vorschau 30 s (Wetter-Fetch), Orts-Vergleich 60 s (Wetter fuer jeden
// Ort des Presets, gleiches Budget wie CompareProxyHandler).
const (
	previewProxyTimeout        = 30 * time.Second
	comparePreviewProxyTimeout = 60 * time.Second
)

// forwardPreview ist die EINE Proxy-Behandlung aller Vorschau-Routen (Issue
// #2283 AC-5): Alt-Routen und kind-neutrale Briefing-Routen laufen beide hier
// durch. Client-user_id wird verworfen und die Kennung aus dem Auth-Kontext
// injiziert (ADR-0003, nie "default"); uebrige Query-Parameter gehen verbatim
// durch. Bei POST wird der Request-Body samt Content-Type weitergereicht.
// Status, Content-Type und Body der Python-Antwort kommen unveraendert zurueck.
func forwardPreview(w http.ResponseWriter, r *http.Request, method, path string, timeout time.Duration) {
	query := appendUserID(r.URL.RawQuery, middleware.UserIDFromContext(r.Context()))
	target := path
	if query != "" {
		target += "?" + query
	}

	var body io.Reader
	if method == http.MethodPost {
		body = r.Body
	}
	req, err := http.NewRequestWithContext(r.Context(), method, target, body)
	if err != nil {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusInternalServerError)
		w.Write([]byte(`{"error":"proxy_error"}`))
		return
	}
	if ct := r.Header.Get("Content-Type"); method == http.MethodPost && ct != "" {
		req.Header.Set("Content-Type", ct)
	}

	client := &http.Client{Timeout: timeout}
	resp, err := client.Do(req)
	if err != nil {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusBadGateway)
		w.Write([]byte(`{"error":"upstream unreachable"}`))
		return
	}
	defer resp.Body.Close()

	ct := resp.Header.Get("Content-Type")
	if ct == "" {
		ct = "application/json"
	}
	w.Header().Set("Content-Type", ct)
	w.WriteHeader(resp.StatusCode)
	io.Copy(w, resp.Body)
}

// ComparePreviewProxyHandler proxies POST /api/preview/compare/{preset_id} to
// the Python core. Preset ID via chi.URLParam; the client-supplied user_id is
// discarded and the authenticated user_id from the auth context is injected
// instead (anti-spoofing, ADR-0003 — never "default"). The Python route is
// user-scoped, a foreign preset is therefore not resolvable (404, AC-6).
//
// One call returns ALL channels ({subject, email_html, telegram, sms,
// sms_char_count}) from a single ComparisonEngine run (ADR-0011) — the channel
// switch in the preview tab needs no further request (AC-7).
// Timeout 60s: the comparison fetches weather for every location of the preset
// (same budget as CompareProxyHandler).
//
// Issue #2283 AC-5: Alt-Route, Delegate auf forwardPreview.
//
// Spec: docs/specs/modules/compare_channel_preview_dispatch.md (Issue #1270).
func ComparePreviewProxyHandler(pythonURL string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		presetID := chi.URLParam(r, "preset_id")
		forwardPreview(w, r, http.MethodPost, pythonURL+"/api/preview/compare/"+presetID, comparePreviewProxyTimeout)
	}
}

// PreviewProxyHandler proxies GET /api/preview/{trip_id}/{channel} to the
// Python core (channel ∈ {"email", "sms", "telegram"}). Trip ID via chi.URLParam,
// user_id from auth context appended to query. Original query params
// (type, date) are forwarded verbatim. Timeout 30s wegen Wetter-Fetch.
//
// Issue #2283 AC-5: Alt-Route, Delegate auf forwardPreview.
//
// Spec: docs/specs/modules/epic_140_output_vorschau.md (Master),
//
//	docs/specs/modules/issue_189_preview_tab_integration.md (Frontend).
func PreviewProxyHandler(pythonURL, channel string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		tripID := chi.URLParam(r, "trip_id")
		forwardPreview(w, r, http.MethodGet, pythonURL+"/api/preview/"+tripID+"/"+channel, previewProxyTimeout)
	}
}
