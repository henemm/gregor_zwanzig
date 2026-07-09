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
	"io"
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

// profileNormMap maps frontend/storage lowercase profile names to engine uppercase constants.
// Accepts both frontend namespace ("allgemein") and engine namespace ("ALLGEMEIN").
var profileNormMap = map[string]string{
	"allgemein":       "ALLGEMEIN",
	"wintersport":     "WINTERSPORT",
	"wandern":         "ALPINE_TOURING",
	"summer_trekking": "SUMMER_TREKKING",
	// engine namespace passthrough
	"ALLGEMEIN":       "ALLGEMEIN",
	"WINTERSPORT":     "WINTERSPORT",
	"ALPINE_TOURING":  "ALPINE_TOURING",
	"SUMMER_TREKKING": "SUMMER_TREKKING",
}

func normalizeProfile(s string) string {
	if norm, ok := profileNormMap[s]; ok {
		return norm
	}
	return s
}

func validateComparePreset(p model.ComparePreset) error {
	if strings.TrimSpace(p.Name) == "" {
		return fmt.Errorf("name is required")
	}
	if p.Schedule != "daily" && p.Schedule != "weekly" && p.Schedule != "manual" {
		return fmt.Errorf("schedule must be daily, weekly, or manual")
	}
	if !compare.IsValidProfile(compare.ActivityProfile(normalizeProfile(p.Profil))) {
		return fmt.Errorf("profil is not a valid activity profile")
	}
	if p.ForecastHours != 24 && p.ForecastHours != 48 && p.ForecastHours != 72 {
		return fmt.Errorf("forecast_hours must be 24, 48, or 72")
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
	if p.Schedule == "weekly" && p.Weekday != nil && (*p.Weekday < 0 || *p.Weekday > 6) {
		return fmt.Errorf("weekday must be between 0 and 6 for weekly presets")
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
		// Issue #781: forecast_hours fehlt oder ist 0 → Default 48 ( konsistent mit
		// LoadComparePresets-Migration und dem Python-Versandpfad).
		if preset.ForecastHours == 0 {
			preset.ForecastHours = 48
		}

		// Issue #511 F001: Default weekday=4 (Freitag) für weekly-Presets ohne
		// explizit gesetztes weekday-Feld. weekday=0 (Montag) bleibt erhalten,
		// weil JSON-Decode in *int nur dann nil liefert, wenn das Feld FEHLT.
		if preset.Schedule == "weekly" && preset.Weekday == nil {
			four := 4
			preset.Weekday = &four
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
		// Issue #582 — Read-Modify-Write: display_config aus Original erhalten wenn
		// der Client es nicht mitsschickt (nil nach Decode = Feld fehlte im Request).
		// Verhindert clobbern von Region/channel_layouts durch Clients die display_config
		// nicht kennen (z.B. Editor-Tabs die nur Scheduler-Felder senden).
		if updated.DisplayConfig == nil {
			updated.DisplayConfig = original.DisplayConfig
		}
		// #631: previous_schedule erhalten wenn Body es nicht trägt (Datenverlust-Schutz).
		if updated.PreviousSchedule == "" {
			updated.PreviousSchedule = original.PreviousSchedule
		}
		// Issue #1040: official_alerts_enabled erhalten wenn Body es nicht trägt
		// (nil nach Decode = Feld fehlte im Request). false ist ein gültiger,
		// bewusst gesetzter Wert und darf nicht mit "Feld fehlte" verwechselt werden.
		if updated.OfficialAlertsEnabled == nil {
			updated.OfficialAlertsEnabled = original.OfficialAlertsEnabled
		}
		// Issue #1107: hourly_enabled erhalten wenn Body es nicht trägt.
		if updated.HourlyEnabled == nil {
			updated.HourlyEnabled = original.HourlyEnabled
		}
		// Issue #764: forecast_hours erhalten wenn Body es nicht trägt (0 = Feld fehlte im Body).
		if updated.ForecastHours == 0 {
			updated.ForecastHours = original.ForecastHours
		}
		// Issue #781: Sicherstellen dass ein gültiger Horizont vorliegt, auch wenn
		// das Original noch keinen hatte (Legacy-Daten, die nie geladen wurden).
		if updated.ForecastHours == 0 {
			updated.ForecastHours = 48
		}

		if updated.LocationIDs == nil {
			updated.LocationIDs = []string{}
		}
		if updated.Empfaenger == nil {
			updated.Empfaenger = []string{}
		}

		// Issue #511 F001: Default weekday=4 (Freitag) für weekly-Presets ohne
		// explizit gesetztes weekday-Feld (analog Create).
		if updated.Schedule == "weekly" && updated.Weekday == nil {
			four := 4
			updated.Weekday = &four
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

// comparePresetStateRequest is the PATCH /api/compare/presets/{id}/state input DTO.
// Pointer field distinguishes "absent in body" (nil) from "explicitly sent",
// analog zu tripStateRequest (Issue #611).
type comparePresetStateRequest struct {
	Archived *bool `json:"archived"`
}

// UpdateComparePresetStateHandler handles PATCH /api/compare/presets/{id}/state.
// Only archived_at is mutated; all other preset fields stay untouched
// (read-modify-write), analog zu UpdateTripStateHandler (Issue #611).
func UpdateComparePresetStateHandler(s *store.Store) http.HandlerFunc {
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

		var req comparePresetStateRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			writeJSON(w, http.StatusBadRequest, map[string]string{"error": "bad_request"})
			return
		}

		if req.Archived != nil {
			if *req.Archived {
				now := time.Now().UTC()
				presets[idx].ArchivedAt = &now
			} else {
				presets[idx].ArchivedAt = nil
			}
		}

		if err := s.SaveComparePresets(presets); err != nil {
			writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "store_error"})
			return
		}
		writeJSON(w, http.StatusOK, presets[idx])
	}
}

// GET /api/compare/presets/{id}
func GetComparePresetHandler(s *store.Store) http.HandlerFunc {
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
		writeJSON(w, http.StatusOK, presets[idx])
	}
}

// POST /api/compare/presets/{id}/send — Proxy to Python Core. Issue #627.
// Vorbild: SendSubscriptionProxyHandler in proxy.go.
func SendComparePresetHandler(pythonURL string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id := chi.URLParam(r, "id")
		query := appendUserID(r.URL.RawQuery, middleware.UserIDFromContext(r.Context()))
		url := pythonURL + "/api/scheduler/compare-presets/" + id + "/send"
		if query != "" {
			url += "?" + query
		}

		req, err := http.NewRequestWithContext(r.Context(), http.MethodPost, url, nil)
		if err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusInternalServerError)
			w.Write([]byte(`{"error":"proxy_error"}`))
			return
		}
		req.Header.Set("Content-Type", "application/json")

		client := &http.Client{Timeout: 120 * time.Second}
		resp, err := client.Do(req)
		if err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusBadGateway)
			w.Write([]byte(`{"error":"upstream unreachable"}`))
			return
		}
		defer resp.Body.Close()

		ct := resp.Header.Get("Content-Type")
		if ct == "" {
			ct = "application/json"
		}
		w.Header().Set("Content-Type", ct)
		w.WriteHeader(resp.StatusCode)
		io.Copy(w, resp.Body)
	}
}
