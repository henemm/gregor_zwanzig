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

func (s *Store) TripsDir() string {
	return filepath.Join(s.DataDir, "users", s.UserID, "trips")
}

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
}

// deriveFlatFields leitet additive, nicht-autoritative flache Slot-/Kanal-
// Felder aus trip.ReportConfig sowie EndDate aus max(stage.date) ab
// (Dual-Read, Issue #1250 Scheibe 4). trip.ReportConfig.enabled ist der
// EINZIGE Schalter (kein getrenntes morning/evening-Flag) -> steuert beide
// abgeleiteten *Enabled-Felder.
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
		if v, ok := rc["enabled"].(bool); ok {
			trip.MorningEnabled = &v
			trip.EveningEnabled = &v
		}
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

func (s *Store) LoadTrips() ([]model.Trip, error) {
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

// migrateMetricAlertLevels verschiebt einen Legacy-Key
// "display_config.metric_alert_levels.snow_line" nach "freezing_level",
// falls letzterer noch nicht gesetzt ist. Siehe Python-_migrate_metric_alert_levels
// (Issue #959) und Go-Pendant Issue #1000.
func migrateMetricAlertLevels(displayConfig map[string]interface{}) {
	if displayConfig == nil {
		return
	}
	raw, ok := displayConfig["metric_alert_levels"]
	if !ok {
		return
	}
	levels, ok := raw.(map[string]interface{})
	if !ok {
		return
	}
	if v, ok := levels["snow_line"]; ok {
		if _, exists := levels["freezing_level"]; !exists {
			levels["freezing_level"] = v
		}
		delete(levels, "snow_line")
	}
}
