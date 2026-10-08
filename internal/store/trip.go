package store

import (
	"encoding/json"
	"log"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"github.com/henemm/gregor-api/internal/model"
)

// normalizeTrip coerces nil slice fields (Corridors, Stages, per-stage
// Waypoints, AlertRules) to empty slices in place. Single source of truth
// for both the read path (LoadTrip/LoadTrips) and the write path (SaveTrip).
//
// Issue #1244 Fix-Loop F001/F002: SaveTrip used to take a value receiver, so
// its nil-coercion only mutated the local copy — the HTTP response still
// carried "corridors":null/"stages":null even though the file on disk was
// already fixed. And the read path only healed AlertRules (Issue #205
// Follow-Up), so GET on a not-yet-migrated legacy file still returned
// "stages":null, crashing the frontend (alertPreviewHelpers.ts
// stages[0]?.id). normalizeTrip closes both gaps from one place.
func normalizeTrip(trip *model.Trip) {
	if trip.Corridors == nil {
		trip.Corridors = []model.Corridor{}
	}
	if trip.Stages == nil {
		trip.Stages = []model.Stage{}
	}
	for i := range trip.Stages {
		if trip.Stages[i].Waypoints == nil {
			trip.Stages[i].Waypoints = []model.Waypoint{}
		}
	}
	if trip.AlertRules == nil {
		trip.AlertRules = []model.AlertRule{}
	}

	// Issue #1250 Scheibe 4: additive flache Slot-/Kanal-Felder + EndDate,
	// bei JEDEM normalizeTrip-Lauf (Load UND Save) frisch aus ReportConfig/
	// Stages ABGELEITET — nie stale. ReportConfig bleibt die einzige Wahrheit
	// fuer den Versand, s. docs/context/feat-1250-s4-trip-konvergenz.md.
	deriveFlatFields(trip)

	// Issue #1981: Alt-Vokabular in metric_alert_levels auch beim Laden
	// uebersetzen (Save-Pfad ruft es zusaetzlich, idempotent).
	migrateMetricAlertLevels(trip.DisplayConfig)
}

// deriveFlatFields leitet additive, nicht-autoritative flache Slot-/Kanal-
// Felder aus trip.ReportConfig sowie EndDate aus max(stage.date) ab
// (Dual-Read, Issue #1250 Scheibe 4). MorningEnabled/EveningEnabled folgen
// slotAktiv (Issue #2422 S3).
func deriveFlatFields(trip *model.Trip) {
	// Fix-Loop F001 (Adversary BROKEN): erst ALLE abgeleiteten Pointer-Felder
	// unbedingt zuruecksetzen, DANN neu ableiten (nur wenn Quelle vorhanden).
	// Sonst bleibt ein zuvor persistierter Wert stehen, wenn die Quelle
	// verschwindet (z.B. Stages werden auf [] geleert, ReportConfig entfaellt)
	// -- Struct-Felder werden sonst nur GESETZT, nie GELOESCHT -> stale.
	trip.MorningTime = nil
	trip.EveningTime = nil
	trip.MorningEnabled = nil
	trip.EveningEnabled = nil
	trip.SendEmail = nil
	trip.SendSms = nil
	trip.SendTelegram = nil
	trip.SendPremiumSms = nil
	trip.EndDate = nil

	if rc := trip.ReportConfig; rc != nil {
		if v, ok := rc["morning_time"].(string); ok {
			trip.MorningTime = &v
		}
		if v, ok := rc["evening_time"].(string); ok {
			trip.EveningTime = &v
		}
		if v, ok := rc["send_email"].(bool); ok {
			trip.SendEmail = &v
		}
		if v, ok := rc["send_sms"].(bool); ok {
			trip.SendSms = &v
		}
		if v, ok := rc["send_telegram"].(bool); ok {
			trip.SendTelegram = &v
		}
		// Issue #1717 S3: viertes Kanal-Feld (Premium-SMS). Kein neuer
		// Schreibpfad — der Client schickt weiterhin
		// report_config.send_premium_sms, mergeConfigMap transportiert es
		// generisch.
		if v, ok := rc["send_premium_sms"].(bool); ok {
			trip.SendPremiumSms = &v
		}
		// Issue #2422 S3 (AC-20): EINE Regel, gleich wie Python slot_aktiv
		// (Tabelle tests/fixtures/report_config_slot_faelle.json).
		morning := slotAktiv(rc, "morning_enabled")
		evening := slotAktiv(rc, "evening_enabled")
		trip.MorningEnabled = &morning
		trip.EveningEnabled = &evening
	}

	if len(trip.Stages) == 0 {
		return
	}
	var maxDate string
	for _, s := range trip.Stages {
		d := strings.Split(s.Date, "T")[0]
		if d > maxDate {
			maxDate = d
		}
	}
	if maxDate != "" {
		trip.EndDate = &maxDate
	}
}

// slotAktiv: Gesamtschalter report_config.enabled (fehlend => an) ist Master —
// explizit false schaltet beide Slots ab. Sonst entscheidet der Per-Slot-bool
// (key), fehlend oder kein bool => Rueckfall an.
func slotAktiv(rc map[string]interface{}, key string) bool {
	if enabled, ok := rc["enabled"].(bool); ok && !enabled {
		return false
	}
	if v, ok := rc[key].(bool); ok {
		return v
	}
	return true
}

func (s *Store) LoadTrips() ([]model.Trip, error) {
	if err := s.requireUser(); err != nil {
		return nil, err
	}
	// Issue #1250 Scheibe 7a: Cutover route -> briefings/ (ADR-0023, KL-7).
	// briefingsDir() traegt sowohl route- als auch vergleich-Eintraege (S5-
	// Migration) -- nur kind=="route" (bzw. leer bei unmigriertem Altbestand)
	// sind Trips, kind=="vergleich" wird uebersprungen (AC-25/AC-30).
	dir := s.briefingsDir()

	entries, err := os.ReadDir(dir)
	if err != nil {
		return []model.Trip{}, nil
	}

	var trips []model.Trip
	for _, entry := range entries {
		if entry.IsDir() || !strings.HasSuffix(entry.Name(), ".json") {
			continue
		}

		data, err := os.ReadFile(filepath.Join(dir, entry.Name()))
		if err != nil {
			log.Printf("skip %s: read error: %v", entry.Name(), err)
			continue
		}

		var trip model.Trip
		if err := json.Unmarshal(data, &trip); err != nil {
			log.Printf("skip %s: json error: %v", entry.Name(), err)
			continue
		}
		if trip.Kind == "vergleich" {
			continue
		}

		// Issue #1244 F002: Read-Path-Coercion symmetrisch zu SaveTrip, für
		// ALLE Slice-Felder (nicht nur AlertRules wie zuvor, Issue #205
		// Follow-Up) — sonst liefert GET/LoadTrips auf eine unmigrierte
		// Legacy-Datei weiterhin "stages":null/"corridors":null.
		normalizeTrip(&trip)
		// Issue #1280 (Tech-Lead-Entscheidung, Adversary-Nachtrag): Read-Heilung
		// zentralisiert HIER im Load-Pfad, NACH deriveFlatFields (innerhalb
		// normalizeTrip) — jeder Aufrufer, der einen ueber LoadTrips geladenen
		// Trip encodiert (Handler, briefing_subscription.go, ...), bekommt
		// automatisch geheilte Zeiten. NUR morning_time/evening_time
		// (verschachtelt + Flach-Feld), NIEMALS andere Zeitstempel. Read-only:
		// kein Write-Back auf die Platte (SaveTrip normalisiert NICHT hier).
		healTripSlotTimes(&trip)

		trips = append(trips, trip)
	}

	sort.Slice(trips, func(i, j int) bool {
		return trips[i].Name < trips[j].Name
	})

	if trips == nil {
		trips = []model.Trip{}
	}

	return trips, nil
}

func (s *Store) LoadTrip(id string) (*model.Trip, error) {
	if err := s.requireUser(); err != nil {
		return nil, err
	}
	// Issue #2140 Scheibe 2: Segment-Pruefung VOR jedem Join.
	if !ValidEntityID(id) {
		return nil, ErrInvalidEntityID
	}
	// Issue #1250 Scheibe 7a: Cutover route -> briefings/ (ADR-0023, KL-7).
	path := filepath.Join(s.briefingsDir(), id+".json")

	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, err
	}

	var trip model.Trip
	if err := json.Unmarshal(data, &trip); err != nil {
		return nil, err
	}
	if trip.Kind == "vergleich" {
		// briefingsDir() traegt auch ComparePresets (S5-Migration) -- kein Trip.
		return nil, nil
	}

	// Issue #1244 F002: Read-Path-Coercion symmetrisch zu SaveTrip, für ALLE
	// Slice-Felder (nicht nur AlertRules wie zuvor, Issue #205 Follow-Up).
	normalizeTrip(&trip)

	// Issue #809: Self-Heal — alert_rules mit aktiven Metriken synchronisieren.
	// In-Memory only, kein Write-Back (analog nil-Coercion Issue #205).
	activeIDs := model.ActiveAlertableMetricIDs(trip.DisplayConfig)
	trip.AlertRules = model.SyncAlertRules(trip.AlertRules, activeIDs)

	// Issue #1280 (Tech-Lead-Entscheidung, Adversary-Nachtrag): Read-Heilung
	// zentralisiert HIER im Load-Pfad (siehe LoadTrips fuer Rationale).
	healTripSlotTimes(&trip)

	return &trip, nil
}

// SaveTrip persists trip to disk. It takes a pointer (Issue #1244 F001):
// a previous value-receiver signature meant the nil-coercion below only
// mutated SaveTrip's local copy — callers that encoded their own variable
// into the HTTP response (e.g. CreateTripHandler) kept seeing
// "corridors":null even though the file on disk was already fixed. A
// pointer parameter makes the normalization visible to every caller that
// holds the same trip afterwards.
func (s *Store) SaveTrip(trip *model.Trip) error {
	if err := s.requireUser(); err != nil {
		return err
	}
	// Issue #2140 Scheibe 2: Segment-Pruefung VOR jedem Join. Ohne sie
	// ueberschreibt eine Kennung wie "../../bob/user" die user.json eines
	// fremden Kontos (briefingsDir liegt zwei Ebenen unter data/users/).
	if !ValidEntityID(trip.ID) {
		return ErrInvalidEntityID
	}
	// Issue #1250 Scheibe 7a: Cutover route -> briefings/ (ADR-0023, KL-7).
	// trips/<id>.json wird NICHT mehr angefasst (Rollback-Faehigkeit, AC-26).
	dir := s.briefingsDir()
	if err := os.MkdirAll(dir, 0755); err != nil {
		return err
	}

	// Issue #1244 F001: einzige Normalisierungsquelle für Corridors/Stages/
	// Waypoints/AlertRules — zieht die vormals separate AlertRules-Coercion
	// (Issue #205 F002) mit ein, statt sie zu duplizieren.
	normalizeTrip(trip)

	// Issue #809: Compute-on-Save — alert_rules zentral synchronisieren,
	// analog zu ComputeStageArrivals (Issue #802).
	activeIDs := model.ActiveAlertableMetricIDs(trip.DisplayConfig)
	trip.AlertRules = model.SyncAlertRules(trip.AlertRules, activeIDs)

	// Issue #1000: snow_line -> freezing_level im Go-Schreibpfad migrieren,
	// symmetrisch zu AC-3 #959 im Python-Loader (kein Werte-Verlust bei
	// Bestands-Clients, die den Legacy-Key schreiben).
	migrateMetricAlertLevels(trip.DisplayConfig)

	// Issue #802: Compute-on-Save — arrival_calculated für alle Stages setzen,
	// zentral an einer Stelle (alle Go-Schreiber rufen SaveTrip).
	speeds := model.ActivitySpeed(trip.Activity)
	for i := range trip.Stages {
		model.ComputeStageArrivals(&trip.Stages[i], speeds)
	}

	// Issue #1250 Scheibe 7a (AC-26): jede Go-SaveTrip-Schreiboperation ist
	// per Definition eine route-Entitaet (Go-Store kennt keine Presets) --
	// kind wird unbedingt gesetzt, unabhaengig vom Vorzustand des Aufrufers.
	trip.Kind = "route"

	data, err := json.MarshalIndent(trip, "", "  ")
	if err != nil {
		return err
	}

	return writeFileLogged(filepath.Join(dir, trip.ID+".json"), data)
}

func (s *Store) DeleteTrip(id string) error {
	if err := s.requireUser(); err != nil {
		return err
	}
	// Issue #2140 Scheibe 2: Segment-Pruefung VOR jedem Join.
	if !ValidEntityID(id) {
		return ErrInvalidEntityID
	}
	// Issue #1250 Scheibe 7a: Cutover route -> briefings/ (ADR-0023, KL-7).
	path := filepath.Join(s.briefingsDir(), id+".json")

	// Adversary F006: briefingsDir() also holds ComparePresets (kind=
	// "vergleich", Scheibe 5 migration) -- a Trip-delete must never remove
	// one, even if a Preset happens to share the same id as the requested
	// Trip (analog LoadTrip's kind guard). A corrupt/unreadable-as-JSON file
	// cannot be confirmed as a Preset either, so it falls through to delete
	// (matches the pre-Cutover fail-open behavior for garbage files).
	if data, rerr := os.ReadFile(path); rerr == nil {
		var probe struct {
			Kind string `json:"kind"`
		}
		if json.Unmarshal(data, &probe) == nil && probe.Kind == "vergleich" {
			return nil
		}
	}

	err := os.Remove(path)
	if os.IsNotExist(err) {
		return nil
	}
	return err
}

// legacyAlertLevelKeys: Alt-Schluessel (Summary-Vokabular) -> Alarm-Name,
// "" = verwerfen. Deckungsgleich mit Python `_ALT_ALERT_LEVEL_KEYS` (Issue #1981).
var legacyAlertLevelKeys = map[string]string{
	"temp_max_c":        "temperature_max",
	"temp_min_c":        "temperature_min",
	"gust_max_kmh":      "wind_gust",
	"precip_sum_mm":     "precipitation_sum",
	"visibility_min_m":  "visibility",
	"cape_max_jkg":      "cape",
	"thunder_level_max": "thunder_level",
	"wind_max_kmh":      "wind_change",
	"snow_line":         "freezing_level", // Issue #959/#1000
	"wind_chill_min_c":  "",
}

// normalizeMetricAlertLevels uebersetzt Alt-Schluessel in-place; ein vorhandener
// Neu-Schluessel gewinnt, andere Schluessel bleiben unveraendert (idempotent).
func normalizeMetricAlertLevels(levels map[string]interface{}) {
	for alt, neu := range legacyAlertLevelKeys {
		v, ok := levels[alt]
		if !ok {
			continue
		}
		if neu != "" {
			if _, exists := levels[neu]; !exists {
				levels[neu] = v
			}
		}
		delete(levels, alt)
	}
}

// migrateMetricAlertLevels wendet die Alt-Vokabular-Uebersetzung auf
// display_config.metric_alert_levels an. Siehe Python-_migrate_metric_alert_levels
// (Issues #959/#1981) und Go-Pendant Issue #1000.
func migrateMetricAlertLevels(displayConfig map[string]interface{}) {
	if displayConfig == nil {
		return
	}
	if levels, ok := displayConfig["metric_alert_levels"].(map[string]interface{}); ok {
		normalizeMetricAlertLevels(levels)
	}
}
