package handler

import (
	"encoding/json"
	"fmt"
	"net/http"
	"time"

	"github.com/henemm/gregor-api/internal/compare"
	"github.com/henemm/gregor-api/internal/middleware"
)

// maxDateRangeDays caps date_to at today+N to match the OpenMeteo 240h limit.
const maxDateRangeDays = 9

// CompareRunHandler is the POST /api/compare/run endpoint. It validates the
// request body, delegates the orchestration to the compare.Engine, and
// returns a JSON-encoded CompareResult.
//
// Validation (Issue #454, Spec §5):
//   - location_ids must contain at least two entries → 400 too_few_locations
//   - date_from / date_to must be YYYY-MM-DD                  → 400 invalid_date_from / invalid_date_to
//   - date_from must be <= date_to                            → 400 invalid_date_range
//   - date_to must not exceed today+9                         → 400 date_range_too_large
//   - hour_from / hour_to must be in [0..23]                  → 400 invalid_hour_from / invalid_hour_to
//   - hour_from must be <= hour_to                            → 400 invalid_hour_range
//   - profile must be a known ActivityProfile                 → 400 invalid_profile
//
// Non-existent locations are dropped silently inside the engine, yielding a
// partial result with HTTP 200.
func CompareRunHandler(engine *compare.Engine) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")

		var req compare.CompareRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			writeCompareError(w, "invalid_json", "Request body is not valid JSON")
			return
		}

		if code, msg, ok := validateCompareRequest(req); !ok {
			writeCompareError(w, code, msg)
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

// validateCompareRequest enforces the Issue #454 validation rules. On a
// violation it returns (errorCode, message, false). On success: ("", "", true).
func validateCompareRequest(req compare.CompareRequest) (string, string, bool) {
	if len(req.LocationIDs) < 2 {
		return "too_few_locations", "location_ids must contain at least 2 entries", false
	}
	dateFrom, err := time.Parse("2006-01-02", req.DateFrom)
	if err != nil {
		return "invalid_date_from", "date_from must be YYYY-MM-DD", false
	}
	dateTo, err := time.Parse("2006-01-02", req.DateTo)
	if err != nil {
		return "invalid_date_to", "date_to must be YYYY-MM-DD", false
	}
	if dateFrom.After(dateTo) {
		return "invalid_date_range", "date_from must be <= date_to", false
	}
	maxDate := time.Now().UTC().Truncate(24 * time.Hour).AddDate(0, 0, maxDateRangeDays)
	if dateTo.After(maxDate) {
		return "date_range_too_large", fmt.Sprintf("date_to must not exceed today+%d", maxDateRangeDays), false
	}
	if req.HourFrom < 0 || req.HourFrom > 23 {
		return "invalid_hour_from", "hour_from must be in [0..23]", false
	}
	if req.HourTo < 0 || req.HourTo > 23 {
		return "invalid_hour_to", "hour_to must be in [0..23]", false
	}
	if req.HourFrom > req.HourTo {
		return "invalid_hour_range", "hour_from must be <= hour_to", false
	}
	if !compare.IsValidProfile(req.Profile) {
		return "invalid_profile", "profile must be a known ActivityProfile", false
	}
	return "", "", true
}

// writeCompareError serialises an error response in the Issue #454 shape:
// {"error":"<code>","message":"<text>"}.
func writeCompareError(w http.ResponseWriter, code, message string) {
	w.WriteHeader(http.StatusBadRequest)
	body, _ := json.Marshal(map[string]string{"error": code, "message": message})
	w.Write(body)
}
