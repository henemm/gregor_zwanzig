package handler

// Epic #138 Issue #177 — User-MetricPreset-Endpoints.
// Spec: docs/specs/modules/epic_138_174_178_metriken_ui.md §7

import (
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"net/http"
	"time"

	"github.com/go-chi/chi/v5"

	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

type createPresetRequest struct {
	Name        string   `json:"name"`
	Description string   `json:"description,omitempty"`
	IsDefault   bool     `json:"is_default"`
	Metrics     []string `json:"metrics"`
	FriendlyIDs []string `json:"friendly_ids"`
}

func newPresetID() string {
	b := make([]byte, 8)
	if _, err := rand.Read(b); err != nil {
		// Fallback auf nanosekunden-basierte ID
		return "p-" + time.Now().UTC().Format("20060102150405.000000000")
	}
	return "p-" + hex.EncodeToString(b)
}

func writeJSON(w http.ResponseWriter, status int, v interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

// GET /api/metric-presets
func ListMetricPresetsHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		s = s.WithUser(middleware.UserIDFromContext(r.Context()))
		presets, err := s.LoadMetricPresets()
		if err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusInternalServerError)
			w.Write([]byte(`{"error":"store_error"}`))
			return
		}
		writeJSON(w, http.StatusOK, presets)
	}
}

// POST /api/metric-presets
func CreateMetricPresetHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		s = s.WithUser(middleware.UserIDFromContext(r.Context()))

		var req createPresetRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			writeJSON(w, http.StatusBadRequest, map[string]string{"error": "bad_request"})
			return
		}
		if req.Name == "" {
			writeJSON(w, http.StatusBadRequest, map[string]string{"error": "name_required"})
			return
		}

		presets, err := s.LoadMetricPresets()
		if err != nil {
			writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "store_error"})
			return
		}

		// Wenn IsDefault=true → alle anderen auf false setzen (genau ein Default).
		if req.IsDefault {
			for i := range presets {
				presets[i].IsDefault = false
			}
		}

		if req.Metrics == nil {
			req.Metrics = []string{}
		}
		if req.FriendlyIDs == nil {
			req.FriendlyIDs = []string{}
		}

		preset := model.MetricPreset{
			ID:          newPresetID(),
			Name:        req.Name,
			Description: req.Description,
			IsDefault:   req.IsDefault,
			Metrics:     req.Metrics,
			FriendlyIDs: req.FriendlyIDs,
			CreatedAt:   time.Now().UTC(),
		}
		presets = append(presets, preset)

		if err := s.SaveMetricPresets(presets); err != nil {
			writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "store_error"})
			return
		}
		writeJSON(w, http.StatusCreated, preset)
	}
}

// DELETE /api/metric-presets/{id}
func DeleteMetricPresetHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		s = s.WithUser(middleware.UserIDFromContext(r.Context()))
		id := chi.URLParam(r, "id")

		presets, err := s.LoadMetricPresets()
		if err != nil {
			writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "store_error"})
			return
		}

		filtered := make([]model.MetricPreset, 0, len(presets))
		found := false
		for _, p := range presets {
			if p.ID == id {
				found = true
				continue
			}
			filtered = append(filtered, p)
		}
		if !found {
			writeJSON(w, http.StatusNotFound, map[string]string{"error": "not_found"})
			return
		}

		if err := s.SaveMetricPresets(filtered); err != nil {
			writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "store_error"})
			return
		}
		w.WriteHeader(http.StatusNoContent)
	}
}
