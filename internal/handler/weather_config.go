package handler

import (
	"encoding/json"
	"net/http"

	"github.com/go-chi/chi/v5"
	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

// --- Trip Weather Config ---

func GetTripWeatherConfigHandler(s *store.Store) http.HandlerFunc {
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
		json.NewEncoder(w).Encode(trip.DisplayConfig)
	}
}

func PutTripWeatherConfigHandler(s *store.Store) http.HandlerFunc {
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
		var cfg map[string]interface{}
		if err := json.NewDecoder(r.Body).Decode(&cfg); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"bad_request"}`))
			return
		}
		// Issue #1151: Feld-Level-Merge statt Blind-Replace, analog #1129/#1103.
		// Teil-Updates (nur `metrics` gesendet) duerfen andere zuvor gespeicherte
		// display_config-Keys (z.B. `theme`) nicht loeschen.
		if trip.DisplayConfig == nil {
			trip.DisplayConfig = map[string]interface{}{}
		}
		for k, v := range cfg {
			trip.DisplayConfig[k] = v
		}
		// Sync alert_rules with active weather metrics (Issue #701)
		activeIDs := model.ActiveAlertableMetricIDs(trip.DisplayConfig)
		trip.AlertRules = model.SyncAlertRules(trip.AlertRules, activeIDs)
		if err := s.SaveTrip(trip); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"store_error"}`))
			return
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(trip.DisplayConfig)
	}
}

// --- Location Weather Config ---

func GetLocationWeatherConfigHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		s = s.WithUser(middleware.UserIDFromContext(r.Context()))
		id := chi.URLParam(r, "id")
		loc, err := s.LoadLocation(id)
		if err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"store_error"}`))
			return
		}
		if loc == nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(404)
			w.Write([]byte(`{"error":"not_found"}`))
			return
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(loc.DisplayConfig)
	}
}

func PutLocationWeatherConfigHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		s = s.WithUser(middleware.UserIDFromContext(r.Context()))
		id := chi.URLParam(r, "id")
		loc, err := s.LoadLocation(id)
		if err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"store_error"}`))
			return
		}
		if loc == nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(404)
			w.Write([]byte(`{"error":"not_found"}`))
			return
		}
		var cfg map[string]interface{}
		if err := json.NewDecoder(r.Body).Decode(&cfg); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"bad_request"}`))
			return
		}
		loc.DisplayConfig = cfg
		if err := s.SaveLocation(*loc); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"store_error"}`))
			return
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(loc.DisplayConfig)
	}
}

// Issue #1257: extractActiveMetricIDs entfernt — dupliziertes, kaputtes
// zweites Mapping (roher Katalog-ID-Vergleich gegen AlertMetric-Vokabular,
// matchte nie). PutTripWeatherConfigHandler nutzt jetzt zentral
// model.ActiveAlertableMetricIDs (dieselbe Stelle wie store.SaveTrip/LoadTrip).

// Issue #1250 Scheibe 0: Subscription Weather Config (GetSubscriptionWeatherConfigHandler,
// PutSubscriptionWeatherConfigHandler) entfernt — Legacy-Drittstack CompareSubscription
// stillgelegt (#1131), store.LoadSubscription/SaveSubscription existieren nicht mehr.
