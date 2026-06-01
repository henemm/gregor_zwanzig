package handler

import (
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net/http"
	"time"

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
	// Stages-leer ist zulaessig: Trip-Detail-Overview muss einen leeren Empty-State
	// rendern koennen (Epic #135 Step 4, AC-15). Wizard-Drafts und frisch
	// erstellte Trips landen ohne Stages im Store, bevor der User Etappen plant.
	// Der Backend-Validator beschraenkt sich auf die echten Korrektheitskriterien.
	for _, s := range t.Stages {
		for _, wp := range s.Waypoints {
			if wp.Lat == 0 && wp.Lon == 0 {
				return fmt.Errorf("waypoint %s: coordinates required", wp.ID)
			}
		}
	}
	return nil
}

// randomShortID liefert 8 zufaellige Hex-Zeichen (4 Bytes).
func randomShortID() string {
	b := make([]byte, 4)
	if _, err := rand.Read(b); err != nil {
		panic("crypto/rand unavailable: " + err.Error())
	}
	return hex.EncodeToString(b)
}

// ensureStageIDs belegt leere Stage.ID-Felder mit einer generierten ID.
// Issue #243: Verhindert dass leere Stage-IDs ins Backend gelangen und
// Svelte each_key_duplicate-Fehler im Frontend ausloesen.
func ensureStageIDs(stages []model.Stage) []model.Stage {
	for i := range stages {
		if stages[i].ID == "" {
			stages[i].ID = randomShortID()
		}
	}
	return stages
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

		trip.Stages = ensureStageIDs(trip.Stages)

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
	AlertRules              *[]model.AlertRule      `json:"alert_rules,omitempty"`
	AlertCooldownMinutes    *int                    `json:"alert_cooldown_minutes,omitempty"`
	AlertQuietFrom          *string                 `json:"alert_quiet_from,omitempty"`
	AlertQuietTo            *string                 `json:"alert_quiet_to,omitempty"`
	Region                  *string                 `json:"region,omitempty"`
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
		existing.Stages = ensureStageIDs(existing.Stages)
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
		if req.AlertRules != nil {
			existing.AlertRules = *req.AlertRules
		}
		if req.AlertCooldownMinutes != nil {
			existing.AlertCooldownMinutes = req.AlertCooldownMinutes
		}
		if req.AlertQuietFrom != nil {
			existing.AlertQuietFrom = req.AlertQuietFrom
		}
		if req.AlertQuietTo != nil {
			existing.AlertQuietTo = req.AlertQuietTo
		}
		if req.Region != nil {
			existing.Region = *req.Region
		}
		existing.ID = id

		// Issue #296-BE — Naismith-Ankunftszeiten frisch aus den (ggf. neuen)
		// Wegpunkten berechnen, nach dem Stage-Merge, vor SaveTrip.
		// arrival_calculated ist abgeleitet, nicht user-geliefert.
		for i := range existing.Stages {
			model.ComputeStageArrivals(&existing.Stages[i])
		}

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

// tripStateRequest is the PATCH /api/trips/{id}/state input DTO.
// Pointer fields distinguish "absent in body" (nil) from "explicitly sent" (non-nil),
// so a caller can toggle paused or archived independently without touching the other.
// See docs/specs/modules/epic_135_step2_trip_detail_actions.md §2 (Issue #153).
type tripStateRequest struct {
	Paused   *bool `json:"paused"`
	Archived *bool `json:"archived"`
}

// UpdateTripStateHandler handles PATCH /api/trips/{id}/state for the
// trip-detail pause/archive actions. Only paused_at and archived_at are
// mutated; all other trip fields stay untouched (read-modify-write).
func UpdateTripStateHandler(s *store.Store) http.HandlerFunc {
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

		var req tripStateRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"bad_request"}`))
			return
		}

		now := time.Now().UTC()
		if req.Paused != nil {
			if *req.Paused {
				t := now
				existing.PausedAt = &t
			} else {
				existing.PausedAt = nil
			}
		}
		if req.Archived != nil {
			if *req.Archived {
				t := now
				existing.ArchivedAt = &t
			} else {
				existing.ArchivedAt = nil
			}
		}
		existing.ID = id

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

// confirmWaypointRequest is the PATCH /api/trips/{id}/waypoints/{waypointId}/confirm
// input DTO (Issue #303). arrival_override is optional and only honored when
// confirmed is true.
type confirmWaypointRequest struct {
	Confirmed       bool    `json:"confirmed"`
	ArrivalOverride *string `json:"arrival_override,omitempty"`
}

// ConfirmWaypointHandler confirms (or unconfirms) a waypoint suggestion and
// optionally stores a manual arrival_override. Issue #303 §5.
//
// arrival_calculated is recomputed via ComputeStageArrivals so the persisted
// Naismith value stays current alongside the user override.
func ConfirmWaypointHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		s = s.WithUser(middleware.UserIDFromContext(r.Context()))
		tripID := chi.URLParam(r, "id")
		waypointID := chi.URLParam(r, "waypointId")

		trip, err := s.LoadTrip(tripID)
		if err != nil || trip == nil {
			http.NotFound(w, r)
			return
		}

		var req confirmWaypointRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			http.Error(w, "bad request", http.StatusBadRequest)
			return
		}

		found := false
		for si := range trip.Stages {
			for wi := range trip.Stages[si].Waypoints {
				wp := &trip.Stages[si].Waypoints[wi]
				if wp.ID != waypointID {
					continue
				}
				found = true
				confirmed := req.Confirmed
				wp.Confirmed = &confirmed
				if req.Confirmed {
					wp.ArrivalOverride = req.ArrivalOverride
				} else {
					wp.ArrivalOverride = nil
				}
			}
		}
		if !found {
			http.NotFound(w, r)
			return
		}

		// Naismith-Ankunftszeiten nach der Änderung aktuell halten.
		for si := range trip.Stages {
			model.ComputeStageArrivals(&trip.Stages[si])
		}

		if err := s.SaveTrip(*trip); err != nil {
			http.Error(w, "internal error", http.StatusInternalServerError)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(trip)
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
