package handler

import (
	"io"
	"net/http"
	"time"

	"github.com/go-chi/chi/v5"

	"github.com/henemm/gregor-api/internal/middleware"
)

// PreviewProxyHandler proxies GET /api/preview/{trip_id}/{channel} to the
// Python core (channel ∈ {"email", "sms"}). Trip ID via chi.URLParam,
// user_id from auth context appended to query. Original query params
// (type, date) are forwarded verbatim. Timeout 30s wegen Wetter-Fetch.
//
// Spec: docs/specs/modules/epic_140_output_vorschau.md (Master),
//
//	docs/specs/modules/issue_189_preview_tab_integration.md (Frontend).
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
