package handler

import (
	"encoding/json"
	"net/http"

	"github.com/henemm/gregor-api/internal/scheduler"
)

// SchedulerStatusHandler returns the public scheduler status.
func SchedulerStatusHandler(sched *scheduler.Scheduler) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(sched.Status())
	}
}

// Issue #1250 Scheibe 0: SchedulerSubscriptionsStatusHandler entfernt —
// Legacy-Drittstack CompareSubscription stillgelegt (#1131), zugehoerige
// Route /api/scheduler/subscriptions-status existiert nicht mehr.
