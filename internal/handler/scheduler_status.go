package handler

import (
	"encoding/json"
	"net/http"

	authmw "github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/scheduler"
)

// SchedulerStatusHandler returns the public scheduler status.
func SchedulerStatusHandler(sched *scheduler.Scheduler) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(sched.Status())
	}
}

// SchedulerSubscriptionsStatusHandler returns subscription status scoped to the
// authenticated user. Issue #252: subscription names must not leak via the
// public /api/scheduler/status endpoint.
func SchedulerSubscriptionsStatusHandler(sched *scheduler.Scheduler) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		userID := authmw.UserIDFromContext(r.Context())
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]any{
			"compare_subscriptions": sched.BuildCompareSubscriptionsStatus(userID),
		})
	}
}
