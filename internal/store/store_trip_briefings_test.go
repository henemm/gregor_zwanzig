package store

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	"github.com/henemm/gregor-api/internal/model"
)

// TDD RED — Issue #1250 Scheibe 7a (feat-1250-s7-cutover): Go-Seite des
// Touren-Cutovers route -> briefings/<id>.json.
//
// Spec: docs/specs/modules/issue_1250_briefing_subscription.md, AC-25/26/29.
// KL-7: der Cutover laedt briefings/<id>.json weiterhin in model.Trip (KEIN
// Union-Modell) -- LoadBriefing/SaveBriefing/model.BriefingSubscription
// (briefing_subscription.go) bleiben ungenutzt/tot.
//
// RED heute: LoadTrip/LoadTrips/SaveTrip/DeleteTrip (internal/store/trip.go)
// lesen/schreiben weiterhin TripsDir() -- alle Tests hier schlagen fehl, bis
// diese Methoden auf briefingsDir() umgestellt sind.

// AC-25: LoadTrip muss briefings/<id>.json lesen, nicht trips/<id>.json.
func TestLoadTrip_ReadsBriefingsDir_NotTripsDir(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "cutover-a")

	briefingsDir := filepath.Join(tmpDir, "users", "cutover-a", "briefings")
	tripsDir := filepath.Join(tmpDir, "users", "cutover-a", "trips")
	if err := os.MkdirAll(briefingsDir, 0755); err != nil {
		t.Fatalf("mkdir briefings: %v", err)
	}
	if err := os.MkdirAll(tripsDir, 0755); err != nil {
		t.Fatalf("mkdir trips: %v", err)
	}

	briefingsJSON := `{"id":"gr20-2026","name":"Briefings-Version","kind":"route","stages":[]}`
	tripsJSON := `{"id":"gr20-2026","name":"Alt-Trips-Version","stages":[]}`
	if err := os.WriteFile(filepath.Join(briefingsDir, "gr20-2026.json"), []byte(briefingsJSON), 0644); err != nil {
		t.Fatalf("write briefings fixture: %v", err)
	}
	if err := os.WriteFile(filepath.Join(tripsDir, "gr20-2026.json"), []byte(tripsJSON), 0644); err != nil {
		t.Fatalf("write trips fixture: %v", err)
	}

	trip, err := s.LoadTrip("gr20-2026")
	if err != nil {
		t.Fatalf("LoadTrip: %v", err)
	}
	if trip == nil {
		t.Fatal("expected trip, got nil")
	}
	if trip.Name != "Briefings-Version" {
		t.Fatalf("LoadTrip muss briefings/<id>.json lesen (AC-25), nicht trips/*.json — got name=%q", trip.Name)
	}
}

// AC-25 (Liste): LoadTrips muss briefings/ lesen und dabei kind="vergleich"
// (S5 legte Trips UND Presets nach briefings/) ausfiltern -- nur route-
// Eintraege sind Trips (AC-30: gemischte Liste konsistent per kind).
func TestLoadTrips_ReadsBriefingsDir_NotTripsDir(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "cutover-b")

	briefingsDir := filepath.Join(tmpDir, "users", "cutover-b", "briefings")
	if err := os.MkdirAll(briefingsDir, 0755); err != nil {
		t.Fatalf("mkdir briefings: %v", err)
	}

	routeJSON := `{"id":"route-1","name":"Route Eins","kind":"route","stages":[]}`
	vergleichJSON := `{"id":"vergleich-1","name":"Vergleich Eins","kind":"vergleich"}`
	if err := os.WriteFile(filepath.Join(briefingsDir, "route-1.json"), []byte(routeJSON), 0644); err != nil {
		t.Fatalf("write route fixture: %v", err)
	}
	if err := os.WriteFile(filepath.Join(briefingsDir, "vergleich-1.json"), []byte(vergleichJSON), 0644); err != nil {
		t.Fatalf("write vergleich fixture: %v", err)
	}

	trips, err := s.LoadTrips()
	if err != nil {
		t.Fatalf("LoadTrips: %v", err)
	}
	if len(trips) != 1 {
		t.Fatalf("LoadTrips muss briefings/ lesen und NUR kind=\"route\" liefern (AC-25/AC-30), got %d: %+v", len(trips), trips)
	}
	if trips[0].ID != "route-1" {
		t.Fatalf("expected route-1, got %q", trips[0].ID)
	}
}

// AC-26: SaveTrip schreibt briefings/<id>.json, trips/<id>.json bleibt
// byte-unveraendert liegen (Rollback-Faehigkeit, kein Loeschen im Cutover).
func TestSaveTrip_WritesBriefingsDir_LeavesTripsFileUntouched(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "cutover-c")

	tripsDir := filepath.Join(tmpDir, "users", "cutover-c", "trips")
	if err := os.MkdirAll(tripsDir, 0755); err != nil {
		t.Fatalf("mkdir trips: %v", err)
	}
	tripsPath := filepath.Join(tripsDir, "vanoise-2026.json")
	if err := os.WriteFile(tripsPath, []byte(`{"id":"vanoise-2026","name":"Alt-Version","stages":[]}`), 0644); err != nil {
		t.Fatalf("write trips fixture: %v", err)
	}
	originalBytes, err := os.ReadFile(tripsPath)
	if err != nil {
		t.Fatalf("read original: %v", err)
	}

	trip := model.Trip{ID: "vanoise-2026", Name: "Neu-Gespeichert", Stages: []model.Stage{}, Kind: "route"}
	if err := s.SaveTrip(&trip); err != nil {
		t.Fatalf("SaveTrip: %v", err)
	}

	briefingsPath := filepath.Join(tmpDir, "users", "cutover-c", "briefings", "vanoise-2026.json")
	data, err := os.ReadFile(briefingsPath)
	if err != nil {
		t.Fatalf("SaveTrip muss briefings/<id>.json schreiben (AC-26), aber Datei fehlt: %v", err)
	}
	var saved map[string]interface{}
	if err := json.Unmarshal(data, &saved); err != nil {
		t.Fatalf("unmarshal briefings file: %v", err)
	}
	if saved["name"] != "Neu-Gespeichert" {
		t.Fatalf("briefings-Datei traegt falschen Namen: %v", saved["name"])
	}
	if saved["kind"] != "route" {
		t.Fatalf("briefings-Datei muss kind=\"route\" tragen, got %v", saved["kind"])
	}

	afterBytes, err := os.ReadFile(tripsPath)
	if err != nil {
		t.Fatalf("read trips after save: %v", err)
	}
	if string(afterBytes) != string(originalBytes) {
		t.Fatalf("trips/<id>.json muss beim Cutover-Save byte-unveraendert bleiben (Rollback, AC-26)\nbefore: %s\nafter:  %s", originalBytes, afterBytes)
	}
}

// AC-26-Nachbar: DeleteTrip muss konsistent mit dem neuen Schreibpfad die
// briefings/<id>.json entfernen (Datei-Remove, analog bisher gegen TripsDir()).
func TestDeleteTrip_RemovesBriefingsFile(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "cutover-d")

	briefingsDir := filepath.Join(tmpDir, "users", "cutover-d", "briefings")
	if err := os.MkdirAll(briefingsDir, 0755); err != nil {
		t.Fatalf("mkdir briefings: %v", err)
	}
	briefingsPath := filepath.Join(briefingsDir, "to-delete.json")
	if err := os.WriteFile(briefingsPath, []byte(`{"id":"to-delete","name":"Wird geloescht","kind":"route","stages":[]}`), 0644); err != nil {
		t.Fatalf("write fixture: %v", err)
	}

	if err := s.DeleteTrip("to-delete"); err != nil {
		t.Fatalf("DeleteTrip: %v", err)
	}

	if _, err := os.Stat(briefingsPath); !os.IsNotExist(err) {
		t.Fatalf("DeleteTrip muss briefings/<id>.json entfernen (AC-26-Nachbar), Datei existiert noch (stat err=%v)", err)
	}
}

// Adversary F006 (bleibender Regressionstest): briefingsDir() traegt seit
// der S5-Migration auch ComparePresets (kind="vergleich"). DeleteTrip fuer
// eine ID, die zufaellig mit einem Preset kollidiert, darf dessen Datei NIE
// entfernen (analog LoadTrip's kind-Guard, AC-30).
func TestDeleteTrip_DoesNotRemoveVergleichKindFile(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "cutover-f")

	briefingsDir := filepath.Join(tmpDir, "users", "cutover-f", "briefings")
	if err := os.MkdirAll(briefingsDir, 0755); err != nil {
		t.Fatalf("mkdir briefings: %v", err)
	}
	presetPath := filepath.Join(briefingsDir, "shared-id.json")
	presetJSON := []byte(`{"id":"shared-id","name":"Vergleich Preset","kind":"vergleich"}`)
	if err := os.WriteFile(presetPath, presetJSON, 0644); err != nil {
		t.Fatalf("write fixture: %v", err)
	}

	if err := s.DeleteTrip("shared-id"); err != nil {
		t.Fatalf("DeleteTrip: %v", err)
	}

	after, err := os.ReadFile(presetPath)
	if err != nil {
		t.Fatalf("F006: kind=\"vergleich\"-Datei wurde entfernt (darf nicht): %v", err)
	}
	if string(after) != string(presetJSON) {
		t.Fatalf("F006: kind=\"vergleich\"-Datei wurde veraendert:\nbefore: %s\nafter:  %s", presetJSON, after)
	}
}

// AC-29: Roundtrip ueber briefings/ (Load->Save) verliert kein genestetes
// Feld (report_config/display_config-Maps) -- Fidelity identisch zum
// bisherigen LoadTrip/SaveTrip (AC-29-Wortlaut: "Fidelity identisch zum
// bisherigen Verhalten"). Anders als Python (app.trip.Trip.extra, Issue
// #991) hat model.Trip KEINEN Top-Level-Catch-all fuer unbekannte Felder --
// das war schon VOR dem Cutover so (reines encoding/json-Unmarshal in einen
// typisierten Struct) und ist daher kein Parity-Bruch dieser Scheibe; ein
// "some_unknown_field"-Top-Level-Assert waere hier keine Cutover-Regression,
// sondern eine neue, ausserhalb des S7a-Scopes liegende Modell-Erweiterung.
func TestSaveTrip_RoundtripPreservesNestedMaps(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "cutover-e")

	briefingsDir := filepath.Join(tmpDir, "users", "cutover-e", "briefings")
	if err := os.MkdirAll(briefingsDir, 0755); err != nil {
		t.Fatalf("mkdir briefings: %v", err)
	}
	fixture := `{
		"id": "nested-fields-trip",
		"name": "Nested-Fields",
		"kind": "route",
		"stages": [],
		"report_config": {"trip_id": "nested-fields-trip", "enabled": true, "send_sms": true, "send_telegram": false},
		"display_config": {"metric_alert_levels": {"wind_gust": 60, "temperature_min": -5}},
		"corridors": [{"metric": "wind_gust", "range": [10, 60], "notify": true, "mark": true}],
		"alert_rules": [{"id":"rule-1","kind":"delta","metric":"wind_gust","threshold":5,"unit":"km/h","severity":"warning","enabled":true,"channels":["email"]}]
	}`
	path := filepath.Join(briefingsDir, "nested-fields-trip.json")
	if err := os.WriteFile(path, []byte(fixture), 0644); err != nil {
		t.Fatalf("write fixture: %v", err)
	}

	loaded, err := s.LoadTrip("nested-fields-trip")
	if err != nil {
		t.Fatalf("LoadTrip: %v", err)
	}
	if loaded == nil {
		t.Fatal("LoadTrip muss den Trip aus briefings/ laden koennen (Voraussetzung fuer AC-29)")
	}

	if err := s.SaveTrip(loaded); err != nil {
		t.Fatalf("SaveTrip: %v", err)
	}

	rewritten, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read back briefings file: %v", err)
	}
	var saved map[string]interface{}
	if err := json.Unmarshal(rewritten, &saved); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}

	rc, ok := saved["report_config"].(map[string]interface{})
	if !ok {
		t.Fatalf("report_config verloren beim Roundtrip: %v", saved["report_config"])
	}
	if rc["send_sms"] != true {
		t.Fatalf("report_config.send_sms verloren beim Roundtrip: %v", rc["send_sms"])
	}

	dc, ok := saved["display_config"].(map[string]interface{})
	if !ok {
		t.Fatalf("display_config verloren beim Roundtrip: %v", saved["display_config"])
	}
	if _, ok := dc["metric_alert_levels"]; !ok {
		t.Fatal("display_config.metric_alert_levels verloren beim Roundtrip")
	}
}
