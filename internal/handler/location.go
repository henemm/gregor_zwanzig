package handler

import (
	"encoding/json"
	"fmt"
	"net/http"
	"regexp"
	"strings"

	"github.com/go-chi/chi/v5"
	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

var nonAlphaNum = regexp.MustCompile(`[^a-z0-9]+`)

func toKebab(s string) string {
	s = strings.TrimSpace(strings.ToLower(s))
	s = nonAlphaNum.ReplaceAllString(s, "-")
	s = strings.Trim(s, "-")
	return s
}

func LocationsHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		s = s.WithUser(middleware.UserIDFromContext(r.Context()))
		locations, err := s.LoadLocations()
		if err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"store_error"}`))
			return
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(locations)
	}
}

func validateLocation(loc model.Location) error {
	if loc.ID == "" {
		return fmt.Errorf("id required")
	}
	if loc.Name == "" {
		return fmt.Errorf("name required")
	}
	if loc.Lat == 0 && loc.Lon == 0 {
		return fmt.Errorf("coordinates required")
	}
	return nil
}

func CreateLocationHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		s = s.WithUser(middleware.UserIDFromContext(r.Context()))
		var loc model.Location
		if err := json.NewDecoder(r.Body).Decode(&loc); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"bad_request"}`))
			return
		}

		// Auto-generate ID from name if not provided
		if loc.ID == "" && loc.Name != "" {
			loc.ID = toKebab(loc.Name)
		}

		if err := validateLocation(loc); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(400)
			json.NewEncoder(w).Encode(map[string]string{
				"error":  "validation_error",
				"detail": err.Error(),
			})
			return
		}

		if err := s.SaveLocation(loc); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"store_error"}`))
			return
		}

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(201)
		json.NewEncoder(w).Encode(loc)
	}
}

func UpdateLocationHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		s = s.WithUser(middleware.UserIDFromContext(r.Context()))
		id := chi.URLParam(r, "id")

		existing, err := s.LoadLocation(id)
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

		var loc model.Location
		if err := json.NewDecoder(r.Body).Decode(&loc); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"bad_request"}`))
			return
		}

		loc.ID = id

		if err := validateLocation(loc); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(400)
			json.NewEncoder(w).Encode(map[string]string{
				"error":  "validation_error",
				"detail": err.Error(),
			})
			return
		}

		if err := s.SaveLocation(loc); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"store_error"}`))
			return
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(loc)
	}
}

func DeleteLocationHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		s = s.WithUser(middleware.UserIDFromContext(r.Context()))
		id := chi.URLParam(r, "id")

		if err := s.DeleteLocation(id); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"store_error"}`))
			return
		}

		w.WriteHeader(204)
	}
}
