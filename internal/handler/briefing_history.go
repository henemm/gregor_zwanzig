package handler

import (
	"encoding/json"
	"net/http"

	"github.com/go-chi/chi/v5"
	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/store"
)

// BriefingHistoryHandler returns the briefing-log entries for a specific trip,
// filtered by trip ID. Issue #559 AC-1, AC-4, AC-5.
// Fail-soft: missing log file yields empty array, never 500.
func BriefingHistoryHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		userID := middleware.UserIDFromContext(r.Context())
		if userID == "" {
			http.Error(w, "unauthorized", http.StatusUnauthorized)
			return
		}

		tripID := chi.URLParam(r, "id")

		entries, err := s.WithUser(userID).LoadBriefingLog()
		if err != nil {
			http.Error(w, "internal error", http.StatusInternalServerError)
			return
		}

		type responseEntry struct {
			SentAt   string   `json:"sent_at"`
			Kind     string   `json:"kind"`
			Channels []string `json:"channels"`
		}

		result := []responseEntry{}
		for _, e := range entries {
			if e.TripID == tripID {
				result = append(result, responseEntry{
					SentAt:   e.SentAt,
					Kind:     e.Kind,
					Channels: e.Channels,
				})
			}
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(result)
	}
}
