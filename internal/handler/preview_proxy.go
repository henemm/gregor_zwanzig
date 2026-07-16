package handler

import (
	"io"
	"net/http"
	"time"

	"github.com/go-chi/chi/v5"

	"github.com/henemm/gregor-api/internal/middleware"
)

// PreviewProxyHandler proxies GET /api/preview/{trip_id}/{channel} to the
// Python core (channel ∈ {"email", "sms", "signal", "telegram"}). Trip ID via chi.URLParam,
// user_id from auth context appended to query. Original query params
// (type, date) are forwarded verbatim. Timeout 30s wegen Wetter-Fetch.
//
// Spec: docs/specs/modules/epic_140_output_vorschau.md (Master),
//
//	docs/specs/modules/issue_189_preview_tab_integration.md (Frontend).
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
// Spec: docs/specs/modules/compare_channel_preview_dispatch.md (Issue #1270).
func ComparePreviewProxyHandler(pythonURL string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		presetID := chi.URLParam(r, "preset_id")
		query := appendUserID(r.URL.RawQuery, middleware.UserIDFromContext(r.Context()))
		url := pythonURL + "/api/preview/compare/" + presetID
		if query != "" {
			url += "?" + query
		}

		req, err := http.NewRequestWithContext(r.Context(), http.MethodPost, url, r.Body)
		if err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusInternalServerError)
			w.Write([]byte(`{"error":"proxy_error"}`))
			return
		}
		req.Header.Set("Content-Type", r.Header.Get("Content-Type"))

		client := &http.Client{Timeout: 60 * time.Second}
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
}

func PreviewProxyHandler(pythonURL, channel string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		tripID := chi.URLParam(r, "trip_id")
		query := appendUserID(r.URL.RawQuery, middleware.UserIDFromContext(r.Context()))
		url := pythonURL + "/api/preview/" + tripID + "/" + channel
		if query != "" {
			url += "?" + query
		}

		client := &http.Client{Timeout: 30 * time.Second}
		resp, err := client.Get(url)
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
}
