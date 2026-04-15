package handler

import (
	"encoding/json"
	"fmt"
	"net/http"

	"github.com/go-chi/chi/v5"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

func SubscriptionsHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
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
		valid := map[string]bool{"wintersport": true, "wandern": true, "allgemein": true}
		if !valid[*sub.ActivityProfile] {
			return fmt.Errorf("activity_profile must be wintersport, wandern, or allgemein")
		}
	}
	return nil
}

func CreateSubscriptionHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
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

func DeleteSubscriptionHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
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
