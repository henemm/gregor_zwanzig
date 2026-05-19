package handler

import (
	"encoding/json"
	"net/http"

	"github.com/henemm/gregor-api/internal/compare"
	"github.com/henemm/gregor-api/internal/middleware"
)

// CompareRunHandler is the POST /api/compare/run endpoint. It validates the
// request body, delegates the orchestration to the compare.Engine, and
// returns a JSON-encoded CompareResult.
//
// Validation:
//   - location_ids must contain at least two entries (otherwise 400).
//   - profile must be a known ActivityProfile (otherwise 400).
//
// Non-existent locations are dropped silently inside the engine, yielding a
// partial result with HTTP 200 — see Issue #250 AC-4.
func CompareRunHandler(engine *compare.Engine) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")

		var req compare.CompareRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			w.WriteHeader(http.StatusBadRequest)
			w.Write([]byte(`{"error":"invalid_json"}`))
			return
		}

		if len(req.LocationIDs) < 2 {
			w.WriteHeader(http.StatusBadRequest)
			w.Write([]byte(`{"error":"need_at_least_two_locations"}`))
			return
		}
		if !compare.IsValidProfile(req.Profile) {
			w.WriteHeader(http.StatusBadRequest)
			w.Write([]byte(`{"error":"invalid_profile"}`))
			return
		}

		userID := middleware.UserIDFromContext(r.Context())
		result, err := engine.Run(r.Context(), userID, req)
		if err != nil {
			w.WriteHeader(http.StatusInternalServerError)
			w.Write([]byte(`{"error":"compare_run_failed"}`))
			return
		}

		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(result)
	}
}
