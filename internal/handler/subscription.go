package handler

import (
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

func SubscriptionsHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		s = s.WithUser(middleware.UserIDFromContext(r.Context()))
		subs, err := s.LoadSubscriptions()
		if err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"store_error"}`))
			return
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(subs)
	}
}

func SubscriptionHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		s = s.WithUser(middleware.UserIDFromContext(r.Context()))
		id := chi.URLParam(r, "id")

		sub, err := s.LoadSubscription(id)
		if err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"store_error"}`))
			return
		}
		if sub == nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(404)
			w.Write([]byte(`{"error":"not_found"}`))
			return
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(sub)
	}
}

func validateSubscription(sub model.CompareSubscription) error {
	if sub.ID == "" {
		return fmt.Errorf("id required")
	}
	if sub.Name == "" {
		return fmt.Errorf("name required")
	}
	if sub.ForecastHours != 24 && sub.ForecastHours != 48 && sub.ForecastHours != 72 {
		return fmt.Errorf("forecast_hours must be 24, 48, or 72")
	}
	if sub.Schedule != "daily_morning" && sub.Schedule != "daily_evening" && sub.Schedule != "weekly" {
		return fmt.Errorf("schedule must be daily_morning, daily_evening, or weekly")
	}
	if sub.TimeWindowStart < 0 || sub.TimeWindowStart > 23 {
		return fmt.Errorf("time_window_start must be 0-23")
	}
	if sub.TimeWindowEnd < 0 || sub.TimeWindowEnd > 23 {
		return fmt.Errorf("time_window_end must be 0-23")
	}
	if sub.TimeWindowStart >= sub.TimeWindowEnd {
		return fmt.Errorf("time_window_start must be < time_window_end")
	}
	if sub.TopN < 1 || sub.TopN > 10 {
		return fmt.Errorf("top_n must be 1-10")
	}
	if sub.Weekday < 0 || sub.Weekday > 6 {
		return fmt.Errorf("weekday must be 0-6")
	}
	if sub.ActivityProfile != nil {
		valid := map[string]bool{"wintersport": true, "wandern": true, "allgemein": true, "summer_trekking": true}
		if !valid[*sub.ActivityProfile] {
			return fmt.Errorf("activity_profile must be wintersport, wandern, allgemein, or summer_trekking")
		}
	}
	if sub.SendEmail && len(sub.Recipients) > 0 {
		for _, addr := range sub.Recipients {
			if !strings.Contains(addr, "@") {
				return fmt.Errorf("recipients: ungültige E-Mail-Adresse: %s", addr)
			}
		}
	}
	return nil
}

func CreateSubscriptionHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		s = s.WithUser(middleware.UserIDFromContext(r.Context()))
		var sub model.CompareSubscription
		if err := json.NewDecoder(r.Body).Decode(&sub); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"bad_request"}`))
			return
		}

		if err := validateSubscription(sub); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(400)
			json.NewEncoder(w).Encode(map[string]string{
				"error":  "validation_error",
				"detail": err.Error(),
			})
			return
		}

		existing, err := s.LoadSubscription(sub.ID)
		if err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"store_error"}`))
			return
		}
		if existing != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(409)
			json.NewEncoder(w).Encode(map[string]string{
				"error":  "already_exists",
				"detail": "subscription with this id already exists",
			})
			return
		}

		if sub.Locations == nil {
			sub.Locations = []string{}
		}

		if err := s.SaveSubscription(sub); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"store_error"}`))
			return
		}

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(201)
		json.NewEncoder(w).Encode(sub)
	}
}

func UpdateSubscriptionHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		s = s.WithUser(middleware.UserIDFromContext(r.Context()))
		id := chi.URLParam(r, "id")

		existing, err := s.LoadSubscription(id)
		if err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"store_error"}`))
			return
		}
		if existing == nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(404)
			w.Write([]byte(`{"error":"not_found"}`))
			return
		}

		var sub model.CompareSubscription
		if err := json.NewDecoder(r.Body).Decode(&sub); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"bad_request"}`))
			return
		}

		sub.ID = id

		// Read-Modify-Write: Scheduler-managed fields aus existing übernehmen
		sub.LastRun = existing.LastRun
		sub.LastStatus = existing.LastStatus
		sub.TopOrtLetzterVersand = existing.TopOrtLetzterVersand

		if err := validateSubscription(sub); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(400)
			json.NewEncoder(w).Encode(map[string]string{
				"error":  "validation_error",
				"detail": err.Error(),
			})
			return
		}

		if sub.Locations == nil {
			sub.Locations = []string{}
		}

		if err := s.SaveSubscription(sub); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"store_error"}`))
			return
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(sub)
	}
}

// PatchSubscriptionRunStatusHandler updates only last_run + last_status on an
// existing subscription. Read-Modify-Write — all other fields preserved.
// Issue #252 §2. Route: PATCH /api/subscriptions/{id}/run-status.
func PatchSubscriptionRunStatusHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		s = s.WithUser(middleware.UserIDFromContext(r.Context()))
		id := chi.URLParam(r, "id")

		existing, err := s.LoadSubscription(id)
		if err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusInternalServerError)
			w.Write([]byte(`{"error":"store_error"}`))
			return
		}
		if existing == nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusNotFound)
			w.Write([]byte(`{"error":"not_found"}`))
			return
		}

		var patch struct {
			LastRun    string `json:"last_run"`
			LastStatus string `json:"last_status"`
		}
		if err := json.NewDecoder(r.Body).Decode(&patch); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusBadRequest)
			w.Write([]byte(`{"error":"bad_request"}`))
			return
		}

		if patch.LastRun != "" {
			t, perr := time.Parse(time.RFC3339, patch.LastRun)
			if perr != nil {
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusBadRequest)
				json.NewEncoder(w).Encode(map[string]string{
					"error":  "bad_request",
					"detail": "last_run must be RFC3339",
				})
				return
			}
			existing.LastRun = &t
		}
		if patch.LastStatus != "" {
			existing.LastStatus = patch.LastStatus
		}

		if err := s.SaveSubscription(*existing); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusInternalServerError)
			w.Write([]byte(`{"error":"store_error"}`))
			return
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(existing)
	}
}

func DeleteSubscriptionHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		s = s.WithUser(middleware.UserIDFromContext(r.Context()))
		id := chi.URLParam(r, "id")

		existing, err := s.LoadSubscription(id)
		if err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"store_error"}`))
			return
		}
		if existing == nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(404)
			w.Write([]byte(`{"error":"not_found"}`))
			return
		}

		if err := s.DeleteSubscription(id); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"store_error"}`))
			return
		}

		w.WriteHeader(204)
	}
}
