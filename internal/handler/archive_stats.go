package handler

import (
	"encoding/json"
	"net/http"

	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/store"
)

// ArchiveStatsHandler returns the total number of briefings sent and alerts
// fired per trip for the authenticated user (Issue #396). Unlike the cockpit
// endpoint these counts are NOT time-filtered — the archive view shows the
// full history. Fail-soft: missing log files yield empty maps, never a 500.
func ArchiveStatsHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		userID := middleware.UserIDFromContext(r.Context())
		us := s.WithUser(userID)

		briefings, _ := us.BriefingCountByTrip()
		alerts, _ := us.AlertCountByTrip()

		if briefings == nil {
			briefings = make(map[string]int)
		}
		if alerts == nil {
			alerts = make(map[string]int)
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]any{
			"briefings": briefings,
			"alerts":    alerts,
		})
	}
}
