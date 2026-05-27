package handler

import (
	"encoding/json"
	"net/http"
	"strings"
	"time"

	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/store"
)

// CockpitStatusHandler returns today's briefing sends and last-24h alert fires
// for the authenticated user. Fail-soft: missing log files yield empty arrays.
// Issue #393.
func CockpitStatusHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		userID := middleware.UserIDFromContext(r.Context())
		us := s.WithUser(userID)

		briefingEntries, _ := us.LoadBriefingLog()
		alertEntries, _ := us.LoadAlertLog()

		todayPrefix := time.Now().UTC().Format("2006-01-02")
		cutoff24h := time.Now().UTC().Add(-24 * time.Hour)

		// Briefings: only today's entries (sent_at begins with today's date).
		briefings := make([]store.BriefingLogEntry, 0)
		for _, e := range briefingEntries {
			if strings.HasPrefix(e.SentAt, todayPrefix) {
				briefings = append(briefings, e)
			}
		}

		// Alerts: only entries from the last 24h.
		alerts := make([]store.AlertLogEntry, 0)
		for _, e := range alertEntries {
			t, err := time.Parse(time.RFC3339, e.SentAt)
			if err == nil && t.After(cutoff24h) {
				alerts = append(alerts, e)
			}
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]any{
			"briefings": briefings,
			"alerts":    alerts,
		})
	}
}
