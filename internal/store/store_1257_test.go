package store

import (
	"encoding/json"
	"os"
	"path/filepath"
	"reflect"
	"testing"

	"github.com/henemm/gregor-api/internal/model"
)

// AC-1: Trip mit "gust" aktiv + manuell angelegter Regel überlebt Save+Load
// (vor #1257 verschwand die Regel).
func TestSaveLoad_1257_GustRuleSurvivesRoundTrip(t *testing.T) {
	dataDir := t.TempDir()
	trip := model.Trip{
		ID: "trip-1257-roundtrip", Name: "Roundtrip Gust Trip",
		AlertRules: []model.AlertRule{{ID: "manual-gust-rule", Kind: model.AlertRuleKindDelta,
			Metric: model.AlertMetricWindGust, Threshold: 25, Unit: "km/h", Enabled: true, Severity: model.AlertSeverityWarning}},
		DisplayConfig: displayConfigWithMetrics([]string{"gust"}, true),
	}
	s := New(dataDir, "user-1257")
	if err := s.SaveTrip(&trip); err != nil {
		t.Fatalf("AC-1: SaveTrip error: %v", err)
	}
	loaded, err := s.LoadTrip("trip-1257-roundtrip")
	if err != nil || loaded == nil || len(loaded.AlertRules) == 0 {
		t.Fatalf("AC-1: alert_rules lost after round trip: err=%v loaded=%+v", err, loaded)
	}
	found := false
	for _, r := range loaded.AlertRules {
		found = found || r.Metric == model.AlertMetricWindGust
	}
	if !found {
		t.Errorf("AC-1: want wind_gust rule to survive, got: %+v", loaded.AlertRules)
	}
}

// AC-6: MigrateAllTripsAlertRules ist idempotent — zwei Läufe liefern
// identische alert_rules on-disk.
func TestMigrateAllTripsAlertRules_Idempotent(t *testing.T) {
	dataDir := t.TempDir()
	writeTripJSON(t, dataDir, "user-migrate", model.Trip{
		ID: "trip-migrate", Name: "Migrate Test Trip", AlertRules: []model.AlertRule{},
		DisplayConfig: displayConfigWithMetrics([]string{"gust", "snowfall_limit"}, true),
	})
	tripPath := filepath.Join(dataDir, "users", "user-migrate", "trips", "trip-migrate.json")

	n1, err := MigrateAllTripsAlertRules(dataDir)
	if err != nil || n1 != 1 {
		t.Fatalf("AC-6: run 1: n=%d err=%v", n1, err)
	}
	raw1, _ := os.ReadFile(tripPath)
	var state1 model.Trip
	json.Unmarshal(raw1, &state1)
	if len(state1.AlertRules) == 0 {
		t.Fatal("AC-6: expected materialized alert_rules after run 1")
	}

	n2, err := MigrateAllTripsAlertRules(dataDir)
	if err != nil || n2 != 1 {
		t.Fatalf("AC-6: run 2: n=%d err=%v", n2, err)
	}
	raw2, _ := os.ReadFile(tripPath)
	var state2 model.Trip
	json.Unmarshal(raw2, &state2)
	if !reflect.DeepEqual(state1.AlertRules, state2.AlertRules) {
		t.Errorf("AC-6: not idempotent:\nrun1: %+v\nrun2: %+v", state1.AlertRules, state2.AlertRules)
	}
}
