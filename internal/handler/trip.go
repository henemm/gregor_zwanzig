package handler

import (
	"encoding/json"
	"fmt"
	"net/http"

	"github.com/go-chi/chi/v5"
	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

func TripsHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		s = s.WithUser(middleware.UserIDFromContext(r.Context()))
		trips, err := s.LoadTrips()
		if err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"store_error"}`))
			return
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(trips)
	}
}

func TripHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		s = s.WithUser(middleware.UserIDFromContext(r.Context()))
		id := chi.URLParam(r, "id")

		trip, err := s.LoadTrip(id)
		if err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"store_error"}`))
			return
		}

		if trip == nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(404)
			w.Write([]byte(`{"error":"not_found"}`))
			return
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(trip)
	}
}

func validateTrip(t model.Trip) error {
	if t.ID == "" {
		return fmt.Errorf("id required")
	}
	if t.Name == "" {
		return fmt.Errorf("name required")
	}
	if len(t.Stages) == 0 {
		return fmt.Errorf("at least one stage required")
	}
	for _, s := range t.Stages {
		if len(s.Waypoints) == 0 {
			return fmt.Errorf("stage %s: at least one waypoint required", s.ID)
		}
		for _, wp := range s.Waypoints {
			if wp.Lat == 0 && wp.Lon == 0 {
				return fmt.Errorf("waypoint %s: coordinates required", wp.ID)
			}
		}
	}
	return nil
}

func CreateTripHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		s = s.WithUser(middleware.UserIDFromContext(r.Context()))
		var trip model.Trip
		if err := json.NewDecoder(r.Body).Decode(&trip); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"bad_request"}`))
			return
		}

		if err := validateTrip(trip); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(400)
			json.NewEncoder(w).Encode(map[string]string{
				"error":  "validation_error",
				"detail": err.Error(),
			})
			return
		}

		if err := s.SaveTrip(trip); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"store_error"}`))
			return
		}

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(201)
		json.NewEncoder(w).Encode(trip)
	}
}

// tripUpdateRequest is the PUT /api/trips/{id} input DTO. Pointer fields let the
// JSON decoder distinguish "absent in body" (nil) from "explicitly sent" (non-nil),
// so optional configs are merged into the existing trip instead of being silently
// dropped. See docs/specs/bugfix/update_trip_handler_merge.md (Issue #99).
type tripUpdateRequest struct {
	Name             *string                 `json:"name"`
	Stages           *[]model.Stage          `json:"stages"`
	AvalancheRegions *[]string               `json:"avalanche_regions,omitempty"`
	Aggregation      *map[string]interface{} `json:"aggregation,omitempty"`
	WeatherConfig    *map[string]interface{} `json:"weather_config,omitempty"`
	DisplayConfig    *map[string]interface{} `json:"display_config,omitempty"`
	ReportConfig     *map[string]interface{} `json:"report_config,omitempty"`
}

func UpdateTripHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		s = s.WithUser(middleware.UserIDFromContext(r.Context()))
		id := chi.URLParam(r, "id")

		existing, err := s.LoadTrip(id)
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

		var req tripUpdateRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"bad_request"}`))
			return
		}

		if req.Name != nil {
			existing.Name = *req.Name
		}
		if req.Stages != nil {
			existing.Stages = *req.Stages
		}
		if req.AvalancheRegions != nil {
			existing.AvalancheRegions = *req.AvalancheRegions
		}
		if req.Aggregation != nil {
			existing.Aggregation = *req.Aggregation
		}
		if req.WeatherConfig != nil {
			existing.WeatherConfig = *req.WeatherConfig
		}
		if req.DisplayConfig != nil {
			existing.DisplayConfig = *req.DisplayConfig
		}
		if req.ReportConfig != nil {
			existing.ReportConfig = *req.ReportConfig
		}
		existing.ID = id

		if err := validateTrip(*existing); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(400)
			json.NewEncoder(w).Encode(map[string]string{
				"error":  "validation_error",
				"detail": err.Error(),
			})
			return
		}

		if err := s.SaveTrip(*existing); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"store_error"}`))
			return
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(existing)
	}
}

func DeleteTripHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		s = s.WithUser(middleware.UserIDFromContext(r.Context()))
		id := chi.URLParam(r, "id")

		if err := s.DeleteTrip(id); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"store_error"}`))
			return
		}

		w.WriteHeader(204)
	}
}
