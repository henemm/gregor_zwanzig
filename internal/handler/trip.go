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

		// Issue #1258 AC-4: Neuanlage ohne mitgeschicktes official_warnings
		// erhaelt bewusst enabled=false (Verhaltenswechsel NUR fuer Neuanlagen,
		// PO-Entscheidung F1) -- anders als ein migrierter Bestandstrip.
		if trip.OfficialWarnings == nil {
			trip.OfficialWarnings = &model.OfficialWarningsConfig{Enabled: false}
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

		if err := s.SaveTrip(&trip); err != nil {
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
	AlertRules       *[]model.AlertRule      `json:"alert_rules,omitempty"`
	// Corridors — Issue #1231, Slice 3: additiv neben AlertRules, RMW-Kontrakt
	// analog AlertRules (nil = im Body nicht gesendet -> bestehende Corridors
	// bleiben erhalten, statt geloescht zu werden).
	Corridors                    *[]model.Corridor `json:"corridors,omitempty"`
	AlertCooldownMinutes         *int              `json:"alert_cooldown_minutes,omitempty"`
	AlertQuietFrom               *string           `json:"alert_quiet_from,omitempty"`
	AlertQuietTo                 *string           `json:"alert_quiet_to,omitempty"`
	Region                       *string           `json:"region,omitempty"`
	Activity                     *string           `json:"activity,omitempty"`
	OfficialAlertsEnabled        *bool             `json:"official_alerts_enabled,omitempty"`
	OfficialAlertTriggersEnabled *bool             `json:"official_alert_triggers_enabled,omitempty"`
	// OfficialWarnings — Issue #1258, RMW-Kontrakt analog OfficialAlertTriggersEnabled
	// (nil = im Body nicht gesendet -> bestehender Wert bleibt erhalten).
	OfficialWarnings *model.OfficialWarningsConfig `json:"official_warnings,omitempty"`
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
			// Issue #1129: Feld-Level-Merge statt Blind-Replace, analog #1103.
			if existing.Aggregation == nil {
				existing.Aggregation = map[string]interface{}{}
			}
			for k, v := range *req.Aggregation {
				existing.Aggregation[k] = v
			}
		}
		if req.WeatherConfig != nil {
			if existing.WeatherConfig == nil {
				existing.WeatherConfig = map[string]interface{}{}
			}
			for k, v := range *req.WeatherConfig {
				existing.WeatherConfig[k] = v
			}
		}
		if req.DisplayConfig != nil {
			if existing.DisplayConfig == nil {
				existing.DisplayConfig = map[string]interface{}{}
			}
			for k, v := range *req.DisplayConfig {
				existing.DisplayConfig[k] = v
			}
		}
		if req.ReportConfig != nil {
			// Issue #1103: Feld-Level-Merge statt Blind-Replace — Teil-Updates
			// duerfen bestehende report_config-Keys nicht loeschen.
			if existing.ReportConfig == nil {
				existing.ReportConfig = map[string]interface{}{}
			}
			for k, v := range *req.ReportConfig {
				existing.ReportConfig[k] = v
			}
		}
		if req.AlertRules != nil {
			existing.AlertRules = *req.AlertRules
		}
		if req.Corridors != nil {
			existing.Corridors = *req.Corridors
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
		// Issue #674 — Activity-Feld aus PUT-Body übernehmen (F001-Fix).
		if req.Activity != nil {
			existing.Activity = *req.Activity
		}
		// Issue #1087 — Read-Modify-Write-Merge: nil = Feld fehlte im Body,
		// bestehender Wert (auch explizit false) bleibt erhalten.
		if req.OfficialAlertsEnabled != nil {
			existing.OfficialAlertsEnabled = req.OfficialAlertsEnabled
		}
		// Issue #1088 — gleiches RMW-Merge-Muster wie OfficialAlertsEnabled.
		if req.OfficialAlertTriggersEnabled != nil {
			existing.OfficialAlertTriggersEnabled = req.OfficialAlertTriggersEnabled
		}
		// Issue #1258 — gleiches RMW-Merge-Muster wie OfficialAlertTriggersEnabled.
		if req.OfficialWarnings != nil {
			// Fix-Loop F002: RMW griff bisher nur auf Objekt-Ebene — ein PUT mit
			// z.B. nur {"enabled":false} (sources im Body fehlt -> nil nach
			// Decode) hat bestehende Sources geloescht, weil der ganze Pointer
			// ersetzt wurde. Sources nur uebernehmen, wenn der Body sie
			// mitschickt (explizites "sources":[] bleibt non-nil und wird
			// respektiert — nur das Fehlen des Keys bedeutet "unveraendert").
			if req.OfficialWarnings.Sources == nil && existing.OfficialWarnings != nil {
				req.OfficialWarnings.Sources = existing.OfficialWarnings.Sources
			}
			existing.OfficialWarnings = req.OfficialWarnings
		}
		existing.ID = id

		// Issue #802: ComputeStageArrivals wird jetzt zentral in store.SaveTrip
		// gerufen — hier nicht mehr nötig (Doppelberechnung vermeiden).

		if err := validateTrip(*existing); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(400)
			json.NewEncoder(w).Encode(map[string]string{
				"error":  "validation_error",
				"detail": err.Error(),
			})
			return
		}

		if err := s.SaveTrip(existing); err != nil {
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

		if err := s.SaveTrip(existing); err != nil {
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

		// Issue #802: ComputeStageArrivals wird jetzt zentral in store.SaveTrip
		// gerufen — hier nicht mehr nötig (Doppelberechnung vermeiden).

		if err := s.SaveTrip(trip); err != nil {
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
