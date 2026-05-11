package handler

import (
	"encoding/json"
	"io"
	"net/http"
	"net/url"
	"time"

	"github.com/go-chi/chi/v5"

	"github.com/henemm/gregor-api/internal/middleware"
)

const version = "0.1.0"

func HealthHandler(pythonURL string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		client := &http.Client{Timeout: 2 * time.Second}
		pythonStatus := "ok"

		resp, err := client.Get(pythonURL + "/health")
		if err != nil || resp.StatusCode != 200 {
			pythonStatus = "unavailable"
		}
		if resp != nil {
			resp.Body.Close()
		}

		status := "ok"
		if pythonStatus == "unavailable" {
			status = "degraded"
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{
			"status":      status,
			"version":     version,
			"python_core": pythonStatus,
		})
	}
}

func ProxyHandler(pythonURL, path string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		client := &http.Client{Timeout: 10 * time.Second}

		url := pythonURL + path
		if r.URL.RawQuery != "" {
			url += "?" + r.URL.RawQuery
		}

		resp, err := client.Get(url)
		if err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(503)
			w.Write([]byte(`{"error":"core_unavailable"}`))
			return
		}
		defer resp.Body.Close()

		for k, vals := range resp.Header {
			for _, v := range vals {
				w.Header().Set(k, v)
			}
		}
		w.WriteHeader(resp.StatusCode)
		io.Copy(w, resp.Body)
	}
}

// CompareProxyHandler proxies /api/compare to Python with a long timeout (60s)
// because the comparison fetches weather data for multiple locations.
func CompareProxyHandler(pythonURL string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		client := &http.Client{Timeout: 60 * time.Second}

		url := pythonURL + "/api/compare"
		query := appendUserID(r.URL.RawQuery, middleware.UserIDFromContext(r.Context()))
		if query != "" {
			url += "?" + query
		}

		resp, err := client.Get(url)
		if err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(503)
			w.Write([]byte(`{"error":"core_unavailable"}`))
			return
		}
		defer resp.Body.Close()

		for k, vals := range resp.Header {
			for _, v := range vals {
				w.Header().Set(k, v)
			}
		}
		w.WriteHeader(resp.StatusCode)
		io.Copy(w, resp.Body)
	}
}

// ProxyPostHandler proxies POST requests to Python with query string forwarding.
// Forwards the original request body and Content-Type header.
func ProxyPostHandler(pythonURL, path string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		client := &http.Client{Timeout: 120 * time.Second}

		url := pythonURL + path
		query := appendUserID(r.URL.RawQuery, middleware.UserIDFromContext(r.Context()))
		if query != "" {
			url += "?" + query
		}

		req, err := http.NewRequestWithContext(r.Context(), http.MethodPost, url, r.Body)
		if err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"proxy_error"}`))
			return
		}
		req.Header.Set("Content-Type", r.Header.Get("Content-Type"))

		resp, err := client.Do(req)
		if err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(503)
			w.Write([]byte(`{"error":"core_unavailable"}`))
			return
		}
		defer resp.Body.Close()

		w.Header().Set("Content-Type", resp.Header.Get("Content-Type"))
		w.WriteHeader(resp.StatusCode)
		io.Copy(w, resp.Body)
	}
}

// appendUserID adds the authenticated user_id to a query string, replacing any
// client-supplied user_id values (anti-spoofing — Bug #200 / Issue #199).
//
// Behaviour:
//   - userID == "" (no auth context): rawQuery is returned unchanged
//   - rawQuery contains user_id=X: X is removed, authenticated user_id is set
//   - malformed rawQuery: dropped, only authenticated user_id remains
func appendUserID(rawQuery, userID string) string {
	if userID == "" {
		return rawQuery
	}
	values, err := url.ParseQuery(rawQuery)
	if err != nil {
		// Malformed query — defense-in-depth: drop everything, keep only auth.
		return "user_id=" + userID
	}
	values.Del("user_id")
	values.Set("user_id", userID)
	return values.Encode()
}

// LoadedTripProxyHandler proxies GET /api/_internal/trip/{id}/loaded to the
// Python core. The trip ID is extracted via chi.URLParam, and the user ID
// from the auth context is appended as ?user_id=... query param.
// Spec: docs/specs/modules/validator_internal_loaded_endpoint.md (Issue #115).
func LoadedTripProxyHandler(pythonURL string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id := chi.URLParam(r, "id")
		query := appendUserID("", middleware.UserIDFromContext(r.Context()))
		url := pythonURL + "/api/_internal/trip/" + id + "/loaded?" + query

		client := &http.Client{Timeout: 10 * time.Second}
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

func GpxProxyHandler(pythonURL string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		client := &http.Client{Timeout: 30 * time.Second}

		url := pythonURL + "/api/gpx/parse"
		query := appendUserID(r.URL.RawQuery, middleware.UserIDFromContext(r.Context()))
		if query != "" {
			url += "?" + query
		}

		req, err := http.NewRequestWithContext(r.Context(), http.MethodPost, url, r.Body)
		if err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"proxy_error"}`))
			return
		}
		req.Header.Set("Content-Type", r.Header.Get("Content-Type"))

		resp, err := client.Do(req)
		if err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(503)
			w.Write([]byte(`{"error":"core_unavailable"}`))
			return
		}
		defer resp.Body.Close()

		w.Header().Set("Content-Type", resp.Header.Get("Content-Type"))
		w.WriteHeader(resp.StatusCode)
		io.Copy(w, resp.Body)
	}
}
