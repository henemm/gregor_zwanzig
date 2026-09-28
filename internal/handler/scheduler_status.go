package handler

import (
	"encoding/json"
	"net/http"

	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/scheduler"
)

// SchedulerStatusHandler returns the full scheduler status. Seit Issue #2155
// S2 nur hinter RequireStatusToken (Maschinen-Token) erreichbar.
func SchedulerStatusHandler(sched *scheduler.Scheduler) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(sched.Status())
	}
}

// SchedulerStatusMeHandler liefert die Nutzer-Sicht des Scheduler-Status
// (Issue #2155 S2): nur trip_reports_hourly mit dem eigenen Laufzustand des
// angemeldeten Nutzers. Die Anmeldepflicht setzt die AuthMiddleware durch.
func SchedulerStatusMeHandler(sched *scheduler.Scheduler) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		userID := middleware.UserIDFromContext(r.Context())
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(sched.StatusForUser(userID))
	}
}

// Issue #1250 Scheibe 0: SchedulerSubscriptionsStatusHandler entfernt —
// Legacy-Drittstack CompareSubscription stillgelegt (#1131), zugehoerige
// Route /api/scheduler/subscriptions-status existiert nicht mehr.
