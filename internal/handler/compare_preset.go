package handler

// Issue #458 — Compare-Preset Backend: 5 CRUD-Handler für ComparePresets.
// Spec: docs/specs/modules/issue_458_compare_preset_backend.md
//
// Persistenz: data/users/{userId}/compare_presets.json (JSON-Array).
// User-Isolation: UserID stammt ausschließlich aus dem Auth-Kontext, nie aus
// dem Request-Body. Profil-Validierung via model.IsValidProfile().
//
// /send ist ein Stub (Issue #461 implementiert die echte Versandlogik).

import (
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"regexp"
	"strings"
	"time"

	"github.com/go-chi/chi/v5"

	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

// Issue #1232 Scheibe 2a: Validierungs-Pattern fuer die Slot-Zeitfelder.
// timePattern erlaubt sowohl "HH:MM" als auch "HH:MM:SS" (Spec: intern wird
// bei fehlenden Sekunden ":00" ergaenzt); datePattern verlangt ISO-Datum.
var (
	comparePresetTimePattern = regexp.MustCompile(`^\d{2}:\d{2}(:\d{2})?$`)
	comparePresetDatePattern = regexp.MustCompile(`^\d{4}-\d{2}-\d{2}$`)
)

// validateComparePresetSlotTime prueft Format UND Wertebereich (Stunde 0..23,
// Minute 0..59) einer Slot-Uhrzeit; ergaenzt fehlende Sekunden zu ":00".
func validateComparePresetSlotTime(fieldName string, value *string) error {
	if value == nil {
		return nil
	}
	if !comparePresetTimePattern.MatchString(*value) {
		return fmt.Errorf("%s must match HH:MM or HH:MM:SS", fieldName)
	}
	t, err := time.Parse("15:04:05", normalizeComparePresetTime(*value))
	if err != nil {
		return fmt.Errorf("%s is not a valid time: %v", fieldName, err)
	}
	*value = t.Format("15:04:05")
	return nil
}

// normalizeComparePresetTime ergaenzt fehlende Sekunden (":00") an "HH:MM".
func normalizeComparePresetTime(value string) string {
	if len(value) == 5 {
		return value + ":00"
	}
	return value
}

func validateComparePresetEndDate(value *string) error {
	if value == nil {
		return nil
	}
	if !comparePresetDatePattern.MatchString(*value) {
		return fmt.Errorf("end_date must match YYYY-MM-DD")
	}
	if _, err := time.Parse("2006-01-02", *value); err != nil {
		return fmt.Errorf("end_date is not a valid date: %v", err)
	}
	return nil
}

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
	if !model.IsValidProfile(model.ActivityProfile(normalizeProfile(p.Profil))) {
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
	// Issue #1232 Scheibe 2a: Slot-Zeitfelder + Laufzeit-Ende validieren.
	if err := validateComparePresetSlotTime("morning_time", p.MorningTime); err != nil {
		return err
	}
	if err := validateComparePresetSlotTime("evening_time", p.EveningTime); err != nil {
		return err
	}
	if err := validateComparePresetEndDate(p.EndDate); err != nil {
		return err
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

		// Issue #1244 F001: einzige Normalisierungsquelle (Corridors/
		// LocationIDs/Empfaenger) — writeJSON unten schreibt diese lokale
		// `preset`-Kopie, nicht die von SaveComparePresets normalisierte
		// Slice-Kopie, daher muss `preset` selbst normalisiert sein.
		store.NormalizeComparePreset(&preset)
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

		// Issue #1232 Scheibe 2a: Neu-Preset-Defaults fuer die 5 Slot-Felder,
		// wenn der Client sie nicht mitschickt (Marker: MorningTime==nil).
		// Andere Defaults als die Load-Migration (07:00 statt 06:00) — ein
		// frisch angelegtes Preset ist keine Altdaten-Migration.
		if preset.MorningTime == nil {
			trueVal, falseVal := true, false
			morningTime, eveningTime := "07:00:00", "18:00:00"
			preset.MorningEnabled = &trueVal
			preset.MorningTime = &morningTime
			preset.EveningEnabled = &falseVal
			preset.EveningTime = &eveningTime
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
		// Issue #1041 Slice 1b: radar_alert_enabled erhalten wenn Body es nicht
		// trägt (nil nach Decode = Feld fehlte im Request), analog
		// official_alerts_enabled — Datenverlust-Schutz (CLAUDE.md).
		if updated.RadarAlertEnabled == nil {
			updated.RadarAlertEnabled = original.RadarAlertEnabled
		}
		// Issue #1107: hourly_enabled erhalten wenn Body es nicht trägt.
		if updated.HourlyEnabled == nil {
			updated.HourlyEnabled = original.HourlyEnabled
		}
		// Issue #1170: Alarm-Konfiguration erhalten wenn Body sie nicht trägt
		// (nil nach Decode = Feld fehlte im Request), analog official_alerts_enabled.
		if updated.AlertCooldownMinutes == nil {
			updated.AlertCooldownMinutes = original.AlertCooldownMinutes
		}
		if updated.AlertQuietFrom == nil {
			updated.AlertQuietFrom = original.AlertQuietFrom
		}
		if updated.AlertQuietTo == nil {
			updated.AlertQuietTo = original.AlertQuietTo
		}
		// Issue #1216 Slice 2b: Alarm-Trigger + Kanal-Felder erhalten wenn Body sie
		// nicht traegt (nil nach Decode = Feld fehlte im Request), analog
		// official_alerts_enabled — Datenverlust-Schutz (CLAUDE.md).
		if updated.OfficialAlertTriggersEnabled == nil {
			updated.OfficialAlertTriggersEnabled = original.OfficialAlertTriggersEnabled
		}
		if updated.SendTelegram == nil {
			updated.SendTelegram = original.SendTelegram
		}
		if updated.SendSms == nil {
			updated.SendSms = original.SendSms
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

		// Issue #511 F001: Default weekday=4 (Freitag) für weekly-Presets ohne
		// explizit gesetztes weekday-Feld (analog Create).
		if updated.Schedule == "weekly" && updated.Weekday == nil {
			four := 4
			updated.Weekday = &four
		}

		// Issue #1232 Scheibe 2a: nil-Preserve fuer die 5 Slot-Felder — fehlt
		// ein Feld im Request-Body (nil nach Decode), wird der Original-Wert
		// uebernommen. Ein explizit gesendetes false/"" ist ein gueltiger,
		// bewusst gesetzter Wert (analog official_alerts_enabled).
		if updated.MorningEnabled == nil {
			updated.MorningEnabled = original.MorningEnabled
		}
		if updated.MorningTime == nil {
			updated.MorningTime = original.MorningTime
		}
		if updated.EveningEnabled == nil {
			updated.EveningEnabled = original.EveningEnabled
		}
		if updated.EveningTime == nil {
			updated.EveningTime = original.EveningTime
		}
		if updated.EndDate == nil {
			updated.EndDate = original.EndDate
		}
		// Issue #1231 Slice 4: corridors erhalten wenn Body sie nicht traegt (nil
		// nach Decode = Feld fehlte im Request), analog display_config oben —
		// Datenverlust-Schutz (CLAUDE.md). Ein explizit gesendetes leeres []
		// ist eine bewusste Nutzer-Aenderung (alle Korridore entfernt) und bleibt
		// als solches erhalten (nur echtes nil wird ersetzt).
		if updated.Corridors == nil {
			updated.Corridors = original.Corridors
		}
		// Issue #1232 Scheibe 2b: End-Datum-Loesch-Sentinel — ein explizit
		// gesendeter Leerstring end_date:"" loescht ein gesetztes EndDate
		// (statt es wie oben zu erhalten). Muss NACH dem Nil-Preserve-Block
		// stehen, damit ein fehlendes Feld (nil) weiterhin den Original-Wert
		// uebernimmt, waehrend ein bewusst gesendeter Leerstring loescht.
		if updated.EndDate != nil && *updated.EndDate == "" {
			updated.EndDate = nil
		}

		// Issue #1244 F001: einzige Normalisierungsquelle (Corridors/
		// LocationIDs/Empfaenger) — muss NACH dem Corridors-Preserve-Block
		// oben laufen, sonst bleibt "corridors":null in der Response, wenn
		// bereits das Original (Legacy-Datei) null hatte.
		store.NormalizeComparePreset(&updated)

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
