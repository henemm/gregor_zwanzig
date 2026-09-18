package handler

// Issue #458 — Compare-Preset Backend: 5 CRUD-Handler für ComparePresets.
// Spec: docs/specs/modules/issue_458_compare_preset_backend.md
//
// Persistenz seit Issue #1250 Scheibe 7b: per-Datei
// data/users/{userId}/briefings/<id>.json (kind="vergleich"), nicht mehr das
// Array compare_presets.json. DELETE ist echtes os.Remove (F-A).
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

// Issue #1396 S1: ":=" statt "=" beim WithUser-Aufruf — Begruendung
// ausfuehrlich in trip.go:10-28 (Kommentar ueber TripsHandler).

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
	// Issue #1280: Write-Normalisierung — Minuten/Sekunden auf :00 kappen
	// (Truncate, nicht Runden). Der Scheduler nimmt ohnehin nur .hour.
	*value = store.TruncateTimeStringToHour(t.Format("15:04:05"))
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

// Issue #1395 S6 — WARUM ":=" und nicht "=" beim WithUser-Aufruf in jedem
// Handler dieser Datei: "s = s.WithUser(...)" schreibt in die von der Closure
// GETEILTE Variable; zwei gleichzeitige Anfragen ueberschreiben sich damit den
// Store, im schlimmsten Fall ueber Nutzergrenzen hinweg. Hier ist das direkt
// sicherheitsrelevant, weil der Sperrschluessel (LockBriefing: UserID + ID)
// von s.UserID abhaengt — gesperrt wuerde sonst unter der falschen Kennung.
// Gleiche Korrektur wie S2 in trip.go (Issue #1396).
//
// GET /api/compare/presets — die Liste traegt bewusst KEINEN ETag: sie hat
// keinen einzelnen Fingerabdruck, auf den sich ein If-Match beziehen koennte
// (identisch zu TripsHandler seit S2).
func ListComparePresetsHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		s := s.WithUser(middleware.UserIDFromContext(r.Context()))
		presets, err := s.LoadComparePresets()
		if err != nil {
			writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "store_error"})
			return
		}
		// Issue #1280: Read-Heilung laeuft seit dem Adversary-Nachtrag zentral
		// in s.LoadComparePresets() (internal/store/compare_preset.go) — presets
		// kommen hier bereits geheilt an. Beruehrt NIE letzter_versand (#1268).
		writeJSON(w, http.StatusOK, presets)
	}
}

// POST /api/compare/presets
func CreateComparePresetHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		userID := middleware.UserIDFromContext(r.Context())
		s := s.WithUser(userID)

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
		// Issue #1250 Scheibe 2 (Adversary-Fund F002 MEDIUM): paused_at ist
		// server-verwaltet — ein Client koennte sonst mit schedule="manual"
		// einen gefaelschten Zeitstempel unterschieben. Immer aus schedule
		// ableiten, nie vom Client uebernehmen.
		preset.PausedAt = nil
		store.MaterializePausedAt(&preset, time.Now().UTC())

		// Issue #1244 F001: einzige Normalisierungsquelle (Corridors/
		// LocationIDs/Empfaenger) — writeJSON unten schreibt diese lokale
		// `preset`-Kopie, nicht die von SaveComparePresets normalisierte
		// Slice-Kopie, daher muss `preset` selbst normalisiert sein.
		store.NormalizeComparePreset(&preset)
		// Issue #1361/#1372 S1b: ein ungueltiges Tagesfenster-Paar wird am
		// Schreib-Seam geklemmt (analog ClampReportConfigDayWindow beim Trip).
		store.ClampComparePresetDayWindow(&preset)
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

		// Issue #1258 AC-4: Neuanlage ohne mitgeschicktes official_warnings
		// erhaelt bewusst enabled=false (Verhaltenswechsel NUR fuer Neuanlagen,
		// PO-Entscheidung F1) -- anders als ein migriertes Bestands-Preset.
		if preset.OfficialWarnings == nil {
			preset.OfficialWarnings = &model.OfficialWarningsConfig{Enabled: false}
		}

		if err := validateComparePreset(preset); err != nil {
			writeJSON(w, http.StatusBadRequest, map[string]string{"error": "validation_error", "detail": err.Error()})
			return
		}

		// Issue #1395 S6: Sperre um den Schreibvorgang — erst hier moeglich, die
		// ID entsteht oben im Handler (analog CreateTripHandler). Kein If-Match
		// und kein ETag in der Antwort: der Client holt nach dem Anlegen frisch.
		defer s.LockBriefing(preset.ID)()

		// Issue #1250 Scheibe 7b: per-Datei-Save — nur die eigene Datei
		// briefings/<id>.json schreiben (SaveComparePreset setzt kind=vergleich),
		// kein Laden+Zurueckschreiben des ganzen Arrays mehr.
		if err := s.SaveComparePreset(preset); err != nil {
			writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "store_error"})
			return
		}
		writeJSON(w, http.StatusCreated, preset)
	}
}

// applyComparePresetPatch ist der EINE Merge-Kernel fuer beide Compare-PUT-
// Wege (UpdateComparePresetHandler unten und der vergleich-Zweig von
// UpdateBriefingHandler, briefing_subscription.go) -- Issue #2285. Der
// generische JSON-Overlay-Merge (mergeBriefingPatch, briefing_subscription.go)
// ist strukturell preserve-by-default: ein Feld, das der Patch nicht traegt,
// bleibt unveraendert, ohne dass jedes Struct-Feld einzeln als Rettungszeile
// ausgeschrieben werden muss. Nested JSON-Objekte (display_config,
// official_warnings, alert_channel_thresholds) werden dabei automatisch eine
// Ebene tief feldweise gemergt (mergeConfigMap), das deckt den Vier-Kanal-
// Schwellen-Merge und den OfficialWarnings.Sources-Fall generisch ab.
//
// Validierung (validateComparePreset) bleibt bewusst AUSSERHALB des Kernels
// -- die Fehlerantwort ist Handler-Zustaendigkeit, nicht Merge-Zustaendigkeit.
func applyComparePresetPatch(original model.ComparePreset, id string, patch []byte, now time.Time) (model.ComparePreset, error) {
	merged, err := mergeBriefingPatch(original, patch)
	if err != nil {
		return model.ComparePreset{}, err
	}
	var p model.ComparePreset
	if err := json.Unmarshal(merged, &p); err != nil {
		return model.ComparePreset{}, err
	}

	// Server-verwaltete Felder: nie vom Client ueberschreibbar, UNBEDINGT aus
	// original restauriert (Faelschungsschutz, Issue #2285 AC-3). Kind wird
	// hier explizit restauriert -- der Store-seitige Zwang auf "vergleich"
	// (SaveComparePreset) wirkt erst NACH der Response-Serialisierung und
	// schuetzt den ausgelieferten Response-Body nicht.
	p.ID = id
	p.UserID = original.UserID
	p.CreatedAt = original.CreatedAt
	p.LetzterVersand = original.LetzterVersand
	p.TopOrtLetzterVersand = original.TopOrtLetzterVersand
	p.PausedAt = original.PausedAt
	p.ArchivedAt = original.ArchivedAt
	p.Kind = original.Kind

	// Legacy-Sentinels (unveraendert zur bisherigen Compare-PUT-Semantik).
	// #631: previous_schedule erhalten, wenn der Body es nicht traegt.
	if p.PreviousSchedule == "" {
		p.PreviousSchedule = original.PreviousSchedule
	}
	// Issue #764/#781: gueltigen Horizont sicherstellen, auch wenn das
	// Original (Legacy-Daten) noch keinen hatte.
	if p.ForecastHours == 0 {
		p.ForecastHours = original.ForecastHours
	}
	if p.ForecastHours == 0 {
		p.ForecastHours = 48
	}
	// Issue #511 F001: Default weekday=4 (Freitag) fuer weekly-Presets ohne
	// explizit gesetztes weekday-Feld.
	if p.Schedule == "weekly" && p.Weekday == nil {
		four := 4
		p.Weekday = &four
	}
	// Issue #1232 Scheibe 2b: End-Datum-Loesch-Sentinel -- MUSS NACH der
	// Server-Feld-Restauration stehen, sonst wuerde ein bewusst gesendeter
	// Leerstring faelschlich als "Feld fehlte" behandelt.
	if p.EndDate != nil && *p.EndDate == "" {
		p.EndDate = nil
	}

	// Issue #1250 Scheibe 2: materialisiert paused_at bei erstmaligem
	// Pausieren (schedule=="manual").
	store.MaterializePausedAt(&p, now)
	// Issue #1244 F001: einzige Normalisierungsquelle (Corridors/
	// LocationIDs/Empfaenger).
	store.NormalizeComparePreset(&p)
	// Issue #1361/#1372 S1b: ein ungueltiges Tagesfenster-Paar wird am
	// Schreib-Seam geklemmt -- NACH dem Merge, damit ein bewusst gesendetes
	// ungueltiges Paar wirklich geprueft wird, nicht der erhaltene Alt-Wert.
	store.ClampComparePresetDayWindow(&p)

	return p, nil
}

// PUT /api/compare/presets/{id}
func UpdateComparePresetHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		s := s.WithUser(middleware.UserIDFromContext(r.Context()))
		id := chi.URLParam(r, "id")
		// Issue #2140 Scheibe 2: Segment-Pruefung vor dem ersten Store-Aufruf.
		if bailIf(w, !store.ValidEntityID(id), http.StatusBadRequest, "validation_error") {
			return
		}

		// Issue #1395 S6: Sperre ueber den GANZEN Lesen-Pruefen-Schreiben-Zyklus.
		// Dieselbe Sperre nimmt der zweite Schreibweg
		// (PUT /api/briefings/{id}?kind=vergleich) auf dieselbe Datei.
		defer s.LockBriefing(id)()

		// Fingerabdruck des Standes VOR dem Schreiben — Bezugspunkt der
		// If-Match-Pruefung. Ein echter Lesefehler ist ein Store-Fehler; eine
		// fehlende Datei liefert "" ohne Fehler und faellt unten in den 404.
		oldFp, fpErr := s.BriefingFingerprint(id)
		if fpErr != nil {
			writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "store_error"})
			return
		}

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

		// Vorbedingung VOR dem Dekodieren des Rumpfes: stimmt sie nicht, ist der
		// Rumpf irrelevant und es wird nichts geschrieben (AC-5).
		if !ifMatchAllows(r.Header.Get("If-Match"), oldFp) {
			writePreconditionFailed(w, preconditionFailedDetail)
			return
		}

		bodyBytes, err := io.ReadAll(r.Body)
		if err != nil {
			writeJSON(w, http.StatusBadRequest, map[string]string{"error": "bad_request"})
			return
		}
		updated, err := applyComparePresetPatch(original, id, bodyBytes, time.Now().UTC())
		if err != nil {
			writeJSON(w, http.StatusBadRequest, map[string]string{"error": "bad_request"})
			return
		}

		if err := validateComparePreset(updated); err != nil {
			writeJSON(w, http.StatusBadRequest, map[string]string{"error": "validation_error", "detail": err.Error()})
			return
		}

		// Issue #1250 Scheibe 7b: nur die eigene Datei zurueckschreiben
		// (per-Datei-Save), nicht das ganze Array.
		if err := s.SaveComparePreset(updated); err != nil {
			writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "store_error"})
			return
		}
		// Issue #1395 S6: Stempel des soeben geschriebenen Standes — ohne ihn
		// liefe der Client mit dem naechsten Schreibvorgang ins 412, obwohl
		// niemand sonst etwas geaendert hat.
		newFp, newFpErr := s.BriefingFingerprint(id)
		setETagHeader(w, newFp, newFpErr)
		writeJSON(w, http.StatusOK, updated)
	}
}

// DELETE /api/compare/presets/{id}
func DeleteComparePresetHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		s := s.WithUser(middleware.UserIDFromContext(r.Context()))
		id := chi.URLParam(r, "id")
		// Issue #2140 Scheibe 2: Segment-Pruefung vor dem ersten Store-Aufruf.
		if bailIf(w, !store.ValidEntityID(id), http.StatusBadRequest, "validation_error") {
			return
		}

		// Issue #1395 S6: dieselbe Sperre wie die Schreibpfade — ein DELETE, das
		// mitten in einen laufenden PUT faellt, wuerde sonst die Datei entfernen
		// und der PUT sie danach wieder hinschreiben (Wiederauferstehen).
		// KEIN If-Match: der Loeschpfad prueft keine Vorbedingung (analog Trip).
		defer s.LockBriefing(id)()

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
		// Issue #1250 Scheibe 7b (F-A): echtes Datei-Remove statt Array-Filtern.
		// Nur so ist das Preset nach dem Cutover wirklich weg — ein gefiltertes
		// Array-Zurueckschreiben liesse briefings/<id>.json auf der Platte liegen
		// (Wiederauferstehen beim naechsten Load).
		if err := s.DeleteComparePreset(id); err != nil {
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
		s := s.WithUser(middleware.UserIDFromContext(r.Context()))
		id := chi.URLParam(r, "id")
		// Issue #2140 Scheibe 2: Segment-Pruefung vor dem ersten Store-Aufruf.
		if bailIf(w, !store.ValidEntityID(id), http.StatusBadRequest, "validation_error") {
			return
		}

		// Issue #1395 S6: Sperre wie bei den Schreibpfaden, aber KEIN If-Match
		// (analog UpdateTripStateHandler, AC-15) — der Zustandswechsel ist kein
		// inhaltliches Bearbeiten und darf nicht an einem Stempel scheitern.
		defer s.LockBriefing(id)()

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

		// Issue #1250 Scheibe 7b: nur die geaenderte Datei zurueckschreiben.
		if err := s.SaveComparePreset(presets[idx]); err != nil {
			writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "store_error"})
			return
		}
		writeJSON(w, http.StatusOK, presets[idx])
	}
}

// GET /api/compare/presets/{id}
func GetComparePresetHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		s := s.WithUser(middleware.UserIDFromContext(r.Context()))
		id := chi.URLParam(r, "id")
		// Issue #2140 Scheibe 2: Segment-Pruefung vor dem ersten Store-Aufruf.
		if bailIf(w, !store.ValidEntityID(id), http.StatusBadRequest, "validation_error") {
			return
		}

		// Issue #1395 S6: Sperre auch beim Lesen — sonst koennte ein
		// gleichzeitiger PUT zwischen Fingerabdruck und Serialisierung
		// dazwischenfunken, und der Client haelt einen Stempel, der nicht zum
		// ausgelieferten Rumpf gehoert (analog TripHandler).
		defer s.LockBriefing(id)()

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
		// Issue #1280: Read-Heilung (siehe ListComparePresetsHandler oben).
		//
		// Issue #1395 S6: Stempel des ausgelieferten Standes. Der Fingerabdruck
		// kommt aus den Bytes AUF PLATTE, nicht aus dem geheilten Objekt — er
		// muss zu dem passen, was ein PUT spaeter als Vorbedingung prueft.
		fp, fpErr := s.BriefingFingerprint(id)
		setETagHeader(w, fp, fpErr)
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
