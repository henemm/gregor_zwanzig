package handler

// Issue #1250 Scheibe 6 (ADR-0023 KL-6): /api/briefings* dispatcht per kind ueber
// die BESTEHENDEN Stores (route->Trip, vergleich->ComparePreset, kein briefings/-Store); kind ist immer explizit, nie per Store-Probing geraten.

import (
	"bytes"
	"encoding/json"
	"io"
	"net/http"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

const (
	briefingKindRoute     = "route"
	briefingKindVergleich = "vergleich"
)

func isValidBriefingKind(kind string) bool {
	return kind == briefingKindRoute || kind == briefingKindVergleich
}

func writeBriefingKindRequired(w http.ResponseWriter) {
	writeJSON(w, http.StatusBadRequest, map[string]string{"error": "kind_required"})
}

// bailIf writes {"error": code} with status and reports true when cond holds
// — collapses the repeated error/not-found guards below into one call.
func bailIf(w http.ResponseWriter, cond bool, status int, code string) bool {
	if !cond {
		return false
	}
	writeJSON(w, status, map[string]string{"error": code})
	return true
}

// GET /api/briefings/{id}?kind=route|vergleich
func GetBriefingHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		kind := r.URL.Query().Get("kind")
		if !isValidBriefingKind(kind) {
			writeBriefingKindRequired(w)
			return
		}
		s = s.WithUser(middleware.UserIDFromContext(r.Context()))
		id := chi.URLParam(r, "id")

		if kind == briefingKindRoute {
			trip, err := s.LoadTrip(id)
			if bailIf(w, err != nil, http.StatusInternalServerError, "store_error") {
				return
			}
			if bailIf(w, trip == nil, http.StatusNotFound, "not_found") {
				return
			}
			trip.Kind = briefingKindRoute
			writeJSON(w, http.StatusOK, trip)
			return
		}

		presets, err := s.LoadComparePresets()
		if bailIf(w, err != nil, http.StatusInternalServerError, "store_error") {
			return
		}
		idx := findComparePresetIdx(presets, id)
		if bailIf(w, idx < 0, http.StatusNotFound, "not_found") {
			return
		}
		presets[idx].Kind = briefingKindVergleich
		writeJSON(w, http.StatusOK, presets[idx])
	}
}

// GET /api/briefings — Aggregat aus beiden Alt-Stores, kind-getaggt.
func ListBriefingsHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		s = s.WithUser(middleware.UserIDFromContext(r.Context()))
		trips, err := s.LoadTrips()
		if bailIf(w, err != nil, http.StatusInternalServerError, "store_error") {
			return
		}
		presets, err := s.LoadComparePresets()
		if bailIf(w, err != nil, http.StatusInternalServerError, "store_error") {
			return
		}
		items := make([]interface{}, 0, len(trips)+len(presets))
		for i := range trips {
			trips[i].Kind = briefingKindRoute
			items = append(items, trips[i])
		}
		for i := range presets {
			presets[i].Kind = briefingKindVergleich
			items = append(items, presets[i])
		}
		writeJSON(w, http.StatusOK, items)
	}
}

// POST /api/briefings — kind aus Body, delegiert an Create*Handler (kein
// duplizierter Validierungs-/Persistenzcode).
func CreateBriefingHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		bodyBytes, err := io.ReadAll(r.Body)
		if bailIf(w, err != nil, http.StatusBadRequest, "bad_request") {
			return
		}
		var probe struct {
			Kind string `json:"kind"`
		}
		if err := json.Unmarshal(bodyBytes, &probe); bailIf(w, err != nil || !isValidBriefingKind(probe.Kind), http.StatusBadRequest, "kind_required") {
			return
		}
		r.Body = io.NopCloser(bytes.NewReader(bodyBytes))
		if probe.Kind == briefingKindRoute {
			CreateTripHandler(s).ServeHTTP(w, r)
			return
		}
		CreateComparePresetHandler(s).ServeHTTP(w, r)
	}
}

// DELETE /api/briefings/{id}?kind=route|vergleich — delegiert an Delete*Handler.
func DeleteBriefingHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		kind := r.URL.Query().Get("kind")
		if !isValidBriefingKind(kind) {
			writeBriefingKindRequired(w)
			return
		}
		if kind == briefingKindRoute {
			DeleteTripHandler(s).ServeHTTP(w, r)
			return
		}
		DeleteComparePresetHandler(s).ServeHTTP(w, r)
	}
}

// mergeBriefingPatch mergt Patch-Felder in existing (AC-22): Top-Level-Felder
// ueberschreiben, fehlende bleiben erhalten. Ist ein Feld auf BEIDEN Seiten
// selbst ein JSON-Objekt (z.B. display_config), wird es zusaetzlich per
// mergeConfigMap (#1159-Kernel, config_merge.go) eine Ebene tiefer gemergt
// statt blind ersetzt — sonst loescht {"display_config":{"A":9}} alle
// anderen display_config-Keys (GR221-Klasse).
func mergeBriefingPatch(existing interface{}, patch []byte) ([]byte, error) {
	existingBytes, err := json.Marshal(existing)
	if err != nil {
		return nil, err
	}
	var base map[string]interface{}
	if err := json.Unmarshal(existingBytes, &base); err != nil {
		return nil, err
	}
	var overlay map[string]interface{}
	if err := json.Unmarshal(patch, &overlay); err != nil {
		return nil, err
	}
	for k, v := range overlay {
		if nestedNew, ok := v.(map[string]interface{}); ok {
			if nestedOld, ok2 := base[k].(map[string]interface{}); ok2 {
				base[k] = mergeConfigMap(nestedOld, nestedNew)
				continue
			}
		}
		base[k] = v
	}
	return json.Marshal(base)
}

// PUT /api/briefings/{id}?kind=route|vergleich. route delegiert an
// UpdateTripHandler (dessen Pointer-DTO ist bereits teil-body-sicher UND
// fälschungssicher — kein paused_at/archived_at im DTO). vergleich behaelt
// den Merge (Alt-Compare-PUT ist fuer Klartext-Felder wie location_ids NICHT
// teil-body-sicher), restauriert danach dieselben server-verwalteten Felder
// wie UpdateComparePresetHandler (compare_preset.go:278-283, :394-402) und
// ehrt den end_date:""-Loesch-Sentinel (compare_preset.go:408).
func UpdateBriefingHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		kind := r.URL.Query().Get("kind")
		if !isValidBriefingKind(kind) {
			writeBriefingKindRequired(w)
			return
		}
		if kind == briefingKindRoute {
			UpdateTripHandler(s).ServeHTTP(w, r)
			return
		}

		s = s.WithUser(middleware.UserIDFromContext(r.Context()))
		id := chi.URLParam(r, "id")
		patch, err := io.ReadAll(r.Body)
		if bailIf(w, err != nil, http.StatusBadRequest, "bad_request") {
			return
		}

		presets, err := s.LoadComparePresets()
		if bailIf(w, err != nil, http.StatusInternalServerError, "store_error") {
			return
		}
		idx := findComparePresetIdx(presets, id)
		if bailIf(w, idx < 0, http.StatusNotFound, "not_found") {
			return
		}
		original := presets[idx]
		merged, err := mergeBriefingPatch(original, patch)
		if bailIf(w, err != nil, http.StatusBadRequest, "bad_request") {
			return
		}
		var preset model.ComparePreset
		if bailIf(w, json.Unmarshal(merged, &preset) != nil, http.StatusBadRequest, "bad_request") {
			return
		}
		// Server-verwaltete Felder: nie vom Patch ueberschreibbar, exakter
		// gleicher Feldsatz wie UpdateComparePresetHandler.
		preset.ID = id
		preset.UserID = original.UserID
		preset.CreatedAt = original.CreatedAt
		preset.LetzterVersand = original.LetzterVersand
		preset.TopOrtLetzterVersand = original.TopOrtLetzterVersand
		preset.PausedAt = original.PausedAt
		preset.ArchivedAt = original.ArchivedAt
		// end_date:"" ist der explizite Loesch-Sentinel (analog compare_preset.go:408).
		if preset.EndDate != nil && *preset.EndDate == "" {
			preset.EndDate = nil
		}
		// F008: paused_at bei erstmaligem Pausieren materialisieren (analog compare_preset.go:402).
		store.MaterializePausedAt(&preset, time.Now().UTC())
		store.NormalizeComparePreset(&preset)
		if err := validateComparePreset(preset); err != nil {
			writeJSON(w, http.StatusBadRequest, map[string]string{"error": "validation_error", "detail": err.Error()})
			return
		}
		presets[idx] = preset
		if bailIf(w, s.SaveComparePresets(presets) != nil, http.StatusInternalServerError, "store_error") {
			return
		}
		writeJSON(w, http.StatusOK, preset)
	}
}
