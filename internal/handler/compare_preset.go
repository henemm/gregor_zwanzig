package handler

// Issue #458 — Compare-Preset Backend: 5 CRUD-Handler für ComparePresets.
// Spec: docs/specs/modules/issue_458_compare_preset_backend.md
//
// Persistenz: data/users/{userId}/compare_presets.json (JSON-Array).
// User-Isolation: UserID stammt ausschließlich aus dem Auth-Kontext, nie aus
// dem Request-Body. Profil-Validierung via compare.IsValidProfile().
//
// /send ist ein Stub (Issue #461 implementiert die echte Versandlogik).

import (
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"time"

	"github.com/go-chi/chi/v5"

	"github.com/henemm/gregor-api/internal/compare"
	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

func newComparePresetID() string {
	b := make([]byte, 8)
	if _, err := rand.Read(b); err != nil {
		return "cp-" + time.Now().UTC().Format("20060102150405.000000000")
	}
	return "cp-" + hex.EncodeToString(b)
}

func validateComparePreset(p model.ComparePreset) error {
	if strings.TrimSpace(p.Name) == "" {
		return fmt.Errorf("name is required")
	}
	if p.Schedule != "daily" && p.Schedule != "weekly" && p.Schedule != "manual" {
		return fmt.Errorf("schedule must be daily, weekly, or manual")
	}
	if !compare.IsValidProfile(compare.ActivityProfile(p.Profil)) {
		return fmt.Errorf("profil is not a valid activity profile")
	}
	if p.HourFrom < 0 || p.HourFrom > 23 {
		return fmt.Errorf("hour_from must be 0..23")
	}
	if p.HourTo < 0 || p.HourTo > 23 {
		return fmt.Errorf("hour_to must be 0..23")
	}
	if p.HourTo < p.HourFrom {
		return fmt.Errorf("hour_to must be >= hour_from")
	}
	for _, e := range p.Empfaenger {
		if !strings.Contains(e, "@") {
			return fmt.Errorf("empfaenger entry %q is not a valid email address", e)
		}
	}
	return nil
}

// findComparePresetIdx returns the slice index of the preset with the given id,
// or -1 if not found.
func findComparePresetIdx(presets []model.ComparePreset, id string) int {
	for i, p := range presets {
		if p.ID == id {
			return i
		}
	}
	return -1
}

// GET /api/compare/presets
func ListComparePresetsHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		s = s.WithUser(middleware.UserIDFromContext(r.Context()))
		presets, err := s.LoadComparePresets()
		if err != nil {
			writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "store_error"})
			return
		}
		writeJSON(w, http.StatusOK, presets)
	}
}

// POST /api/compare/presets
func CreateComparePresetHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		userID := middleware.UserIDFromContext(r.Context())
		s = s.WithUser(userID)

		var preset model.ComparePreset
		if err := json.NewDecoder(r.Body).Decode(&preset); err != nil {
			writeJSON(w, http.StatusBadRequest, map[string]string{"error": "bad_request"})
			return
		}
		preset.ID = newComparePresetID()
		preset.UserID = userID
		preset.CreatedAt = time.Now().UTC()
		// LetzterVersand + TopOrtLetzterVersand bleiben nil (server-managed).
		preset.LetzterVersand = nil
		preset.TopOrtLetzterVersand = nil

		if preset.LocationIDs == nil {
			preset.LocationIDs = []string{}
		}
		if preset.Empfaenger == nil {
			preset.Empfaenger = []string{}
		}

		if err := validateComparePreset(preset); err != nil {
			writeJSON(w, http.StatusBadRequest, map[string]string{"error": "validation_error", "detail": err.Error()})
			return
		}

		presets, err := s.LoadComparePresets()
		if err != nil {
			writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "store_error"})
			return
		}
		presets = append(presets, preset)
		if err := s.SaveComparePresets(presets); err != nil {
			writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "store_error"})
			return
		}
		writeJSON(w, http.StatusCreated, preset)
	}
}

// PUT /api/compare/presets/{id}
func UpdateComparePresetHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		s = s.WithUser(middleware.UserIDFromContext(r.Context()))
		id := chi.URLParam(r, "id")

		presets, err := s.LoadComparePresets()
		if err != nil {
			writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "store_error"})
			return
		}

		idx := findComparePresetIdx(presets, id)
		if idx < 0 {
			writeJSON(w, http.StatusNotFound, map[string]string{"error": "not_found"})
			return
		}

		original := presets[idx]
		var updated model.ComparePreset
		if err := json.NewDecoder(r.Body).Decode(&updated); err != nil {
			writeJSON(w, http.StatusBadRequest, map[string]string{"error": "bad_request"})
			return
		}
		// Preserve server-managed fields.
		updated.ID = id
		updated.UserID = original.UserID
		updated.CreatedAt = original.CreatedAt
		updated.LetzterVersand = original.LetzterVersand
		updated.TopOrtLetzterVersand = original.TopOrtLetzterVersand

		if updated.LocationIDs == nil {
			updated.LocationIDs = []string{}
		}
		if updated.Empfaenger == nil {
			updated.Empfaenger = []string{}
		}

		if err := validateComparePreset(updated); err != nil {
			writeJSON(w, http.StatusBadRequest, map[string]string{"error": "validation_error", "detail": err.Error()})
			return
		}

		presets[idx] = updated
		if err := s.SaveComparePresets(presets); err != nil {
			writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "store_error"})
			return
		}
		writeJSON(w, http.StatusOK, updated)
	}
}

// DELETE /api/compare/presets/{id}
func DeleteComparePresetHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		s = s.WithUser(middleware.UserIDFromContext(r.Context()))
		id := chi.URLParam(r, "id")

		presets, err := s.LoadComparePresets()
		if err != nil {
			writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "store_error"})
			return
		}

		idx := findComparePresetIdx(presets, id)
		if idx < 0 {
			writeJSON(w, http.StatusNotFound, map[string]string{"error": "not_found"})
			return
		}
		filtered := append(presets[:idx:idx], presets[idx+1:]...)
		if err := s.SaveComparePresets(filtered); err != nil {
			writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "store_error"})
			return
		}
		w.WriteHeader(http.StatusNoContent)
	}
}

// POST /api/compare/presets/{id}/send — Stub (echte Logik folgt in #461).
func SendComparePresetHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		s = s.WithUser(middleware.UserIDFromContext(r.Context()))
		id := chi.URLParam(r, "id")

		presets, err := s.LoadComparePresets()
		if err != nil {
			writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "store_error"})
			return
		}
		if findComparePresetIdx(presets, id) < 0 {
			writeJSON(w, http.StatusNotFound, map[string]string{"error": "not_found"})
			return
		}
		writeJSON(w, http.StatusOK, map[string]string{"status": "queued"})
	}
}
