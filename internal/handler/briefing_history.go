package handler

import (
	"encoding/json"
	"net/http"

	"github.com/go-chi/chi/v5"
	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/store"
)

// briefingLogEntityType maps the web briefing kind (route | vergleich) onto
// the log entity type (trip | compare, same vocabulary as the alert log #1467).
func briefingLogEntityType(kind string) string {
	if kind == briefingKindVergleich {
		return "compare"
	}
	return "trip"
}

// BriefingHistoryHandler returns the briefing-log entries of ONE briefing:
// GET /api/briefings/{id}/briefing-history?kind=route|vergleich (Issue #2281,
// formerly trip-only #559). Unknown or foreign IDs yield 200 [] (no existence
// check); a malformed ID or a missing/invalid kind yields 400.
// Fail-soft: missing log file yields empty array, never 500.
func BriefingHistoryHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		briefingHistory(s, w, r, r.URL.Query().Get("kind"))
	}
}

// TripBriefingHistoryHandler is the legacy alias GET /api/trips/{id}/briefing-history
// — the same code path with kind=route (#2281 AC-9).
func TripBriefingHistoryHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		briefingHistory(s, w, r, briefingKindRoute)
	}
}

func briefingHistory(s *store.Store, w http.ResponseWriter, r *http.Request, kind string) {
	userID := middleware.UserIDFromContext(r.Context())
	if userID == "" {
		http.Error(w, "unauthorized", http.StatusUnauthorized)
		return
	}
	if !isValidBriefingKind(kind) {
		writeBriefingKindRequired(w)
		return
	}
	id := chi.URLParam(r, "id")
	if bailIf(w, r, !store.ValidEntityID(id), http.StatusBadRequest, "validation_error") {
		return
	}

	entries, err := s.WithUser(userID).LoadBriefingLog()
	if err != nil {
		http.Error(w, "internal error", http.StatusInternalServerError)
		return
	}

	type responseEntry struct {
		SentAt   string   `json:"sent_at"`
		Kind     string   `json:"kind"`
		Channels []string `json:"channels"`
		OnDemand bool     `json:"on_demand"`
	}

	entityType := briefingLogEntityType(kind)
	result := []responseEntry{}
	for _, e := range entries {
		if e.EntityType == entityType && e.EntityID == id {
			result = append(result, responseEntry{
				SentAt:   e.SentAt,
				Kind:     e.Kind,
				Channels: e.Channels,
				OnDemand: e.OnDemand,
			})
		}
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(result)
}
