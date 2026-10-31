package handler

// NotifyTestHandler — Issue #2521 S2. Ersetzt den reinen Proxy fuer
// POST /api/notify/test: leitet unveraendert an den Python-Core weiter und
// vermerkt test_mail_sent_at im Profil des AUFRUFERS, aber nur bei Kanal
// "email" UND Antwort status=="ok". Der Core meldet Fehler als HTTP 200 mit
// {"error": ...} (Muster sms_daily_usage.go) — HTTP 200 allein genuegt nie.

import (
	"bytes"
	"encoding/json"
	"io"
	"log"
	"net/http"
	"time"

	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/store"
)

func NotifyTestHandler(s *store.Store, pythonURL string) http.HandlerFunc {
	client := &http.Client{Timeout: 120 * time.Second}
	return func(w http.ResponseWriter, r *http.Request) {
		userID := middleware.UserIDFromContext(r.Context())
		if userID == "" {
			WriteError(w, r, http.StatusUnauthorized, "unauthorized", nil)
			return
		}
		reqBody, err := io.ReadAll(r.Body)
		if err != nil {
			WriteError(w, r, http.StatusBadRequest, "invalid_request", nil)
			return
		}
		var in struct {
			Channel string `json:"channel"`
		}
		_ = json.Unmarshal(reqBody, &in)

		target := pythonURL + "/api/notify/test"
		if q := appendUserID(r.URL.RawQuery, userID); q != "" {
			target += "?" + q
		}
		req, err := http.NewRequestWithContext(r.Context(), http.MethodPost, target, bytes.NewReader(reqBody))
		if err != nil {
			WriteError(w, r, http.StatusInternalServerError, "proxy_error", nil)
			return
		}
		req.Header.Set("Content-Type", r.Header.Get("Content-Type"))
		resp, err := client.Do(req)
		if err != nil {
			WriteError(w, r, http.StatusServiceUnavailable, "core_unavailable", nil)
			return
		}
		defer resp.Body.Close()
		body, _ := io.ReadAll(resp.Body)

		if in.Channel == "email" && resp.StatusCode == http.StatusOK {
			var out struct {
				Status string `json:"status"`
			}
			if json.Unmarshal(body, &out) == nil && out.Status == "ok" {
				if err := s.SetUserTestMailSentAt(userID, time.Now()); err != nil {
					log.Printf("notify test: test_mail_sent_at fuer %s nicht gesetzt: %v", userID, err)
				}
			}
		}

		w.Header().Set("Content-Type", resp.Header.Get("Content-Type"))
		w.WriteHeader(resp.StatusCode)
		w.Write(body)
	}
}
