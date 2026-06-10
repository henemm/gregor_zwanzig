package handler

// Epic #138 Issue #177 — User-MetricPreset-Endpoints.
// Spec: docs/specs/modules/epic_138_174_178_metriken_ui.md §7
//
// Issue #342: Schema-Erweiterung um []DisplayMetric mit horizons + PATCH-Endpoint.
// Spec: docs/specs/modules/issue_342_pro_metrik_horizon_backend.md §4–§5

import (
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"net/http"
	"strings"
	"time"

	"github.com/go-chi/chi/v5"

	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

// createPresetRequest akzeptiert sowohl Legacy- (Metrics []string +
// FriendlyIDs []string) als auch Neu-Schema-Payloads (Metrics []DisplayMetric).
// Beide werden via json.RawMessage entgegengenommen und in
// CreateMetricPresetHandler in die kanonische []DisplayMetric-Form normalisiert.
type createPresetRequest struct {
	Name        string          `json:"name"`
	Description string          `json:"description,omitempty"`
	IsDefault   bool            `json:"is_default"`
	Metrics     json.RawMessage `json:"metrics"`
	FriendlyIDs []string        `json:"friendly_ids"`
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

// normalizeMetricsPayload akzeptiert beide Eingabe-Formen (Legacy []string +
// friendly_ids ODER Neu []DisplayMetric) und liefert die kanonische
// []DisplayMetric-Form. Fehlende horizons-Felder werden auf {true,true,true}
// defaultet (Backward-Compat, Spec §3).
func normalizeMetricsPayload(raw json.RawMessage, friendlyIDs []string) []model.DisplayMetric {
	allTrue := model.Horizons{Today: true, Tomorrow: true, DayAfter: true}
	out := []model.DisplayMetric{}
	if len(raw) == 0 {
		return out
	}

	// Erst []DisplayMetric direkt versuchen (Neu-Schema).
	// Bug #349: Lokaler Decode-Struct mit *Horizons unterscheidet sicher
	// zwischen "Feld fehlt im JSON" (nil) und "explizit {false,false,false}".
	type displayMetricInput struct {
		MetricID          string          `json:"metric_id"`
		Enabled           bool            `json:"enabled"`
		UseFriendlyFormat bool            `json:"use_friendly_format"`
		Horizons          *model.Horizons `json:"horizons"`
	}
	var asInputs []displayMetricInput
	if err := json.Unmarshal(raw, &asInputs); err == nil && len(asInputs) > 0 {
		// Erkennen, ob mindestens ein metric_id gesetzt ist – sonst ist es
		// vermutlich Legacy []string und wir landen unten im Fallback.
		anyID := false
		for _, m := range asInputs {
			if m.MetricID != "" {
				anyID = true
				break
			}
		}
		if anyID {
			asStructs := make([]model.DisplayMetric, len(asInputs))
			for i, in := range asInputs {
				asStructs[i] = model.DisplayMetric{
					MetricID:          in.MetricID,
					Enabled:           in.Enabled,
					UseFriendlyFormat: in.UseFriendlyFormat,
				}
				if in.Horizons == nil {
					asStructs[i].Horizons = allTrue
				} else {
					asStructs[i].Horizons = *in.Horizons
				}
			}
			return asStructs
		}
	}

	// Fallback: Legacy []string + friendly_ids.
	friendly := map[string]bool{}
	for _, fid := range friendlyIDs {
		friendly[fid] = true
	}
	var asStrings []string
	if err := json.Unmarshal(raw, &asStrings); err == nil {
		for _, id := range asStrings {
			out = append(out, model.DisplayMetric{
				MetricID:          id,
				Enabled:           true,
				UseFriendlyFormat: friendly[id],
				Horizons:          allTrue,
			})
		}
	}
	return out
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
		name := strings.TrimSpace(req.Name)
		if name == "" {
			writeJSON(w, http.StatusBadRequest, map[string]string{"error": "name_required"})
			return
		}

		presets, err := s.LoadMetricPresets()
		if err != nil {
			writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "store_error"})
			return
		}

		// Issue #690: Eindeutigkeit pro Nutzer (case-insensitive, getrimmt).
		nameLower := strings.ToLower(name)
		for _, p := range presets {
			if strings.ToLower(strings.TrimSpace(p.Name)) == nameLower {
				writeJSON(w, http.StatusConflict, map[string]string{"error": "name_exists"})
				return
			}
		}

		// Wenn IsDefault=true → alle anderen auf false setzen (genau ein Default).
		if req.IsDefault {
			for i := range presets {
				presets[i].IsDefault = false
			}
		}

		preset := model.MetricPreset{
			ID:          newPresetID(),
			Name:        name,
			Description: req.Description,
			IsDefault:   req.IsDefault,
			Metrics:     normalizeMetricsPayload(req.Metrics, req.FriendlyIDs),
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

// PATCH /api/metric-presets/{id} — Read-Modify-Write (Issue #342 §4).
//
// Alle Felder im Payload sind optional; fehlende Felder bleiben unveraendert.
// Wenn is_default=true gesetzt wird, werden alle anderen Presets exklusiv
// auf is_default=false zurueckgesetzt.
func PatchMetricPresetHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		s = s.WithUser(middleware.UserIDFromContext(r.Context()))
		id := chi.URLParam(r, "id")

		presets, err := s.LoadMetricPresets()
		if err != nil {
			writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "store_error"})
			return
		}

		idx := -1
		for i, p := range presets {
			if p.ID == id {
				idx = i
				break
			}
		}
		if idx < 0 {
			writeJSON(w, http.StatusNotFound, map[string]string{"error": "not_found"})
			return
		}

		var patch struct {
			Name        *string            `json:"name,omitempty"`
			Description *string            `json:"description,omitempty"`
			IsDefault   *bool              `json:"is_default,omitempty"`
			Metrics     *[]model.DisplayMetric `json:"metrics,omitempty"`
		}
		if err := json.NewDecoder(r.Body).Decode(&patch); err != nil {
			writeJSON(w, http.StatusBadRequest, map[string]string{"error": "bad_request"})
			return
		}

		existing := presets[idx]
		if patch.Name != nil {
			existing.Name = *patch.Name
		}
		if patch.Description != nil {
			existing.Description = *patch.Description
		}
		if patch.IsDefault != nil {
			existing.IsDefault = *patch.IsDefault
		}
		if patch.Metrics != nil {
			existing.Metrics = *patch.Metrics
		}

		if patch.IsDefault != nil && *patch.IsDefault {
			for i := range presets {
				if i != idx {
					presets[i].IsDefault = false
				}
			}
		}
		presets[idx] = existing

		if err := s.SaveMetricPresets(presets); err != nil {
			writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "store_error"})
			return
		}
		writeJSON(w, http.StatusOK, existing)
	}
}
