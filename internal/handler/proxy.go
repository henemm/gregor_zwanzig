package handler

import (
	"encoding/json"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"

	"github.com/go-chi/chi/v5"

	"github.com/henemm/gregor-api/internal/middleware"
)

const version = "0.1.0"

// Issue #2124: Zeitgrenzen-Kette Python-Lauf < Go-Client < nginx.
// sendProxyTimeout gilt fuer Trip- UND Compare-Versand. nginxProxyReadTimeout
// spiegelt proxy_read_timeout/proxy_send_timeout in `location /api/` der vhosts
// (henemm-infra/nginx/*.conf). Paket-var, damit Tests den Wirkort pruefen koennen.
var sendProxyTimeout = 300 * time.Second

const nginxProxyReadTimeout = 330 * time.Second

// stagesWeatherProxyTimeout: Wetterabruf (Lesezugriff), Issue #2124 AC-9.
var stagesWeatherProxyTimeout = 120 * time.Second

// HealthHandler liefert den Gesundheitsstatus. rpID ist die effektive
// Passkey-RP-ID der real gebauten WebAuthn-Instanz (Issue #2130) — der
// Post-Deploy-Selbsttest haelt sie gegen den Produktions-Hostnamen.
func HealthHandler(pythonURL string, gitCommit string, rpID string) http.HandlerFunc {
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
			"status":        status,
			"version":       version,
			"python_core":   pythonStatus,
			"commit":        gitCommit,
			"webauthn_rpid": rpID,
		})
	}
}

func ProxyHandler(pythonURL, path string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		client := &http.Client{Timeout: 10 * time.Second}

		url := pythonURL + path
		if q := stripUserIDQuery(r.URL.RawQuery); q != "" {
			url += "?" + q
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

// stripUserIDQuery entfernt aus der Roh-Query alle Segmente, deren Schluessel
// nach URL-Dekodierung exakt "user_id" ist (Issue #2163 Punkt 8: eine von
// aussen gesetzte user_id erreicht den Core nie). Uebrige Segmente behalten
// Reihenfolge und Kodierung; ohne Treffer bleibt die Roh-Query unveraendert.
func stripUserIDQuery(raw string) string {
	if raw == "" {
		return raw
	}
	segs := strings.Split(raw, "&")
	kept := make([]string, 0, len(segs))
	for _, seg := range segs {
		key, _, _ := strings.Cut(seg, "=")
		if k, err := url.QueryUnescape(key); err == nil && k == "user_id" {
			continue
		}
		kept = append(kept, seg)
	}
	if len(kept) == len(segs) {
		return raw
	}
	return strings.Join(kept, "&")
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

// StagesWeatherProxyHandler proxies GET /api/trips/{id}/stages/weather to the
// Python core's /api/_internal/trips/{id}/stages-weather endpoint. The trip
// ID is extracted via chi.URLParam; the client-supplied user_id is discarded
// and the authenticated user_id from the auth context is injected instead
// (anti-spoofing). Timeout stagesWeatherProxyTimeout (120s) — the weather fetch spans multiple stages.
// Spec: docs/specs/modules/stage_weather_go_proxy.md (Issue #1212, Slice R2).
func StagesWeatherProxyHandler(pythonURL string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id := chi.URLParam(r, "id")
		query := appendUserID("", middleware.UserIDFromContext(r.Context()))
		url := pythonURL + "/api/_internal/trips/" + id + "/stages-weather?" + query

		client := &http.Client{Timeout: stagesWeatherProxyTimeout}
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

// NextBriefingsProxyHandler proxies GET /api/next-briefings to the Python core
// (GET /api/_internal/next-briefings). Issue #1969: user_id comes ONLY from the
// auth context (appendUserID overwrites a client-supplied user_id); the
// optional ?trip_id= / ?preset_id= filters pass through. Without auth context
// the request is rejected with 401 BEFORE any upstream call — appendUserID
// would otherwise forward the client query unchanged (never "default").
// Spec: docs/specs/modules/feat_1969_naechstes_briefing.md
func NextBriefingsProxyHandler(pythonURL string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		uid := middleware.UserIDFromContext(r.Context())
		if uid == "" {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusUnauthorized)
			w.Write([]byte(`{"error":"unauthorized"}`))
			return
		}
		url := pythonURL + "/api/_internal/next-briefings?" + appendUserID(r.URL.RawQuery, uid)

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

// ValidatorFormatMetricProxyHandler proxies GET /api/_validator/format-metric.
// Pure-function endpoint — no user_id injection needed, query string is passed
// through verbatim. Cookie-auth via global AuthMiddleware remains required.
// Spec: docs/specs/modules/issue_221_validator_observability_endpoints.md.
func ValidatorFormatMetricProxyHandler(pythonURL string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		client := &http.Client{Timeout: 10 * time.Second}
		url := pythonURL + "/api/_validator/format-metric"
		if r.URL.RawQuery != "" {
			url += "?" + r.URL.RawQuery
		}

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

// SendTripReportProxyHandler proxies POST /api/trips/{id}/send.
// Trip ID via chi.URLParam, user_id from auth context appended to query.
// Spec: docs/specs/modules/issue_695_test_briefing_send.md
// Issue #2280 AC-13: Alt-Route, Delegate auf forwardSend (send_proxy.go);
// ohne ID-Validierung (Bestand), Default report_type=evening setzt Python.
func SendTripReportProxyHandler(pythonURL string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id := chi.URLParam(r, "id")
		forwardSend(w, r, pythonURL+"/api/scheduler/trips/"+id+"/send", r.URL.RawQuery)
	}
}

// AlertPreviewProxyHandler proxies POST /api/trips/{id}/alert-preview.
// Trip ID via chi.URLParam, user_id from auth context appended to query.
// Spec: docs/specs/modules/issue_221_validator_observability_endpoints.md.
// Issue #2283 AC-16: Alt-Route, Delegate auf forwardPreview (preview_proxy.go).
func AlertPreviewProxyHandler(pythonURL string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id := chi.URLParam(r, "id")
		forwardPreview(w, r, http.MethodPost, pythonURL+"/api/trips/"+id+"/alert-preview", previewProxyTimeout)
	}
}

// DetectorThresholdsProxyHandler proxies GET /api/_validator/detector-thresholds.
// Forwards trip query param and injects authenticated user_id.
// Spec: docs/specs/modules/issue_221_validator_observability_endpoints.md.
func DetectorThresholdsProxyHandler(pythonURL string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		query := appendUserID(r.URL.RawQuery, middleware.UserIDFromContext(r.Context()))
		url := pythonURL + "/api/_validator/detector-thresholds"
		if query != "" {
			url += "?" + query
		}

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

// MetricsForChannelProxyHandler proxies GET /api/_validator/metrics-for-channel.
// Forwards trip, channel, report query params and injects authenticated user_id.
// Spec: docs/specs/modules/issue_448_validator_metrics_for_channel.md.
func MetricsForChannelProxyHandler(pythonURL string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		query := appendUserID(r.URL.RawQuery, middleware.UserIDFromContext(r.Context()))
		url := pythonURL + "/api/_validator/metrics-for-channel"
		if query != "" {
			url += "?" + query
		}

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

// CompareEmailPreviewProxyHandler proxies POST /api/_validator/compare-email-preview.
// Pure render endpoint — no user_id injection needed (no trip context).
// Spec: docs/specs/modules/issue_464_compare_email_preview_validator.md.
func CompareEmailPreviewProxyHandler(pythonURL string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		url := pythonURL + "/api/_validator/compare-email-preview"

		req, err := http.NewRequestWithContext(r.Context(), http.MethodPost, url, r.Body)
		if err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusInternalServerError)
			w.Write([]byte(`{"error":"proxy_error"}`))
			return
		}
		req.Header.Set("Content-Type", r.Header.Get("Content-Type"))

		client := &http.Client{Timeout: 10 * time.Second}
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

// SmsFidelityPreviewProxyHandler proxies POST /api/_validator/sms-fidelity-preview.
// Pure render endpoint — no user_id injection needed (no trip context).
// Spec: docs/specs/modules/fix_923_sms_fidelity_backend.md.
func SmsFidelityPreviewProxyHandler(pythonURL string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		url := pythonURL + "/api/_validator/sms-fidelity-preview"

		req, err := http.NewRequestWithContext(r.Context(), http.MethodPost, url, r.Body)
		if err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusInternalServerError)
			w.Write([]byte(`{"error":"proxy_error"}`))
			return
		}
		req.Header.Set("Content-Type", r.Header.Get("Content-Type"))

		client := &http.Client{Timeout: 10 * time.Second}
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
