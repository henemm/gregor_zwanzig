package store

// Verhaltenstests für Issue #809 — Alerts-Tab Self-Heal.
// Keine Mocks: echter t.TempDir()-Store, echte Trip-JSONs auf Platte.
//
// AC-1: LoadTrip liefert synchronisierte alert_rules wenn display_config.metrics
//       aktive alert-fähige Metriken enthält (kein Write-Back).
// AC-2: Bestehender angepasster Schwellwert wird durch SyncAlertRules nicht
//       überschrieben (Merge-Semantik bleibt erhalten).
// AC-3: SaveTrip synchronisiert alert_rules zentral ohne separaten Handler-Aufruf.
// AC-4: Zwei Nutzer sind strikt isoliert — keine Cross-User-Datenvermischung.
// AC-6: Self-Heal in LoadTrip verändert keine anderen Trip-Felder (Datenerhalt).

import (
	"encoding/json"
	"os"
	"path/filepath"
	"reflect"
	"testing"

	"github.com/henemm/gregor-api/internal/model"
)

// writeTripJSON schreibt ein Trip-Objekt als JSON in das user-scoped trips-Verzeichnis.
func writeTripJSON(t *testing.T, dataDir, userID string, trip model.Trip) {
	t.Helper()
	dir := filepath.Join(dataDir, "users", userID, "trips")
	if err := os.MkdirAll(dir, 0o755); err != nil {
		t.Fatal(err)
	}
	b, err := json.MarshalIndent(trip, "", "  ")
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, trip.ID+".json"), b, 0o644); err != nil {
		t.Fatal(err)
	}
}

// displayConfigWithMetrics baut ein display_config-Map mit den angegebenen Metriken.
// active=true → enabled=true.
func displayConfigWithMetrics(metricIDs []string, enabled bool) map[string]interface{} {
	metrics := make([]interface{}, 0, len(metricIDs))
	for _, id := range metricIDs {
		metrics = append(metrics, map[string]interface{}{
			"metric_id": id,
			"enabled":   enabled,
		})
	}
	return map[string]interface{}{
		"metrics": metrics,
	}
}

// --- AC-1: Self-Heal beim Laden ---

// TestLoadTrip_SelfHeal_CreatesAlertRulesFromMetrics prüft: Ein Bestandstrip mit
// aktiver alert-fähiger Metrik (wind_gust) und leeren alert_rules bekommt nach
// LoadTrip automatisch eine Regel für wind_gust — kein Write-Back auf Platte.
func TestLoadTrip_SelfHeal_CreatesAlertRulesFromMetrics(t *testing.T) {
	dataDir := t.TempDir()
	trip := model.Trip{
		ID:            "trip-legacy",
		Name:          "Legacy Trip",
		AlertRules:    []model.AlertRule{}, // leer — simuliert Bestandstrip vor #701
		DisplayConfig: displayConfigWithMetrics([]string{"wind_gust"}, true),
	}
	writeTripJSON(t, dataDir, "user1", trip)

	s := New(dataDir, "user1")
	loaded, err := s.LoadTrip("trip-legacy")
	if err != nil {
		t.Fatalf("LoadTrip error: %v", err)
	}
	if loaded == nil {
		t.Fatal("LoadTrip returned nil")
	}

	// Nach Self-Heal muss genau eine Regel für wind_gust existieren.
	if len(loaded.AlertRules) != 1 {
		t.Fatalf("expected 1 alert rule after self-heal, got %d: %+v", len(loaded.AlertRules), loaded.AlertRules)
	}
	if loaded.AlertRules[0].Metric != model.AlertMetricWindGust {
		t.Errorf("expected metric wind_gust, got %s", loaded.AlertRules[0].Metric)
	}

	// Kein Write-Back: die JSON-Datei auf Platte darf noch leer sein.
	raw, err := os.ReadFile(filepath.Join(dataDir, "users", "user1", "trips", "trip-legacy.json"))
	if err != nil {
		t.Fatal(err)
	}
	var onDisk model.Trip
	if err := json.Unmarshal(raw, &onDisk); err != nil {
		t.Fatal(err)
	}
	if len(onDisk.AlertRules) != 0 {
		t.Errorf("Self-Heal darf keinen Write-Back ausführen; auf Platte: %+v", onDisk.AlertRules)
	}
}

// --- AC-2: Bestehender Schwellwert (SUPERSEDED #817): absolute Regel → Delta-Migration ---

// TestSyncAlertRules_PreservesCustomThreshold (SUPERSEDED #817):
// Issue #817: Absolute Regeln werden auf Delta-Default migriert.
// Der absolute Threshold (80) war nie alert-wirksam → kein funktionaler Verlust.
// Delta-Threshold für wind_gust ist DefaultDeltaThreshold[AlertMetricWindGust].Threshold = 20.
func TestSyncAlertRules_PreservesCustomThreshold(t *testing.T) {
	dataDir := t.TempDir()
	trip := model.Trip{
		ID:   "trip-custom",
		Name: "Custom Threshold Trip",
		AlertRules: []model.AlertRule{
			{
				ID:        "rule-1",
				Kind:      model.AlertRuleKindAbsolute,
				Metric:    model.AlertMetricWindGust,
				Threshold: 80.0, // absoluter Threshold — war nie alert-wirksam
				Unit:      "km/h",
				Severity:  model.AlertSeverityWarning,
				Enabled:   true,
			},
		},
		DisplayConfig: displayConfigWithMetrics([]string{"wind_gust"}, true),
	}
	writeTripJSON(t, dataDir, "user1", trip)

	s := New(dataDir, "user1")
	loaded, err := s.LoadTrip("trip-custom")
	if err != nil {
		t.Fatalf("LoadTrip error: %v", err)
	}

	if len(loaded.AlertRules) == 0 {
		t.Fatal("expected at least one alert rule")
	}
	// SUPERSEDED #817: absoluter Threshold 80 wird NICHT mehr erhalten.
	// SyncAlertRules migriert auf kind=delta + DefaultDeltaThreshold = 20.
	// Nutzer-ID und Enabled bleiben erhalten (read-modify-write).
	deltaDefault := model.DefaultDeltaThreshold[model.AlertMetricWindGust].Threshold
	found := false
	for _, r := range loaded.AlertRules {
		if r.Metric == model.AlertMetricWindGust {
			found = true
			if r.Kind != model.AlertRuleKindDelta {
				t.Errorf("SUPERSEDED #817: want kind=delta after migration, got %s", r.Kind)
			}
			if r.Threshold != deltaDefault {
				t.Errorf("SUPERSEDED #817: want Delta-Default %.1f (was absolute 80, not alert-wirksam), got %.1f",
					deltaDefault, r.Threshold)
			}
			if r.ID != "rule-1" {
				t.Errorf("ID must be preserved: want rule-1, got %s", r.ID)
			}
		}
	}
	if !found {
		t.Error("wind_gust rule not found after self-heal")
	}
}

// --- AC-3: SaveTrip synchronisiert alert_rules zentral ---

// TestSaveTrip_SyncsAlertRules prüft: SaveTrip synchronisiert alert_rules
// ohne dass der Aufrufer SyncAlertRules explizit aufruft.
// Das rohe JSON auf der Platte muss danach alert_rules für wind_gust enthalten.
func TestSaveTrip_SyncsAlertRules(t *testing.T) {
	dataDir := t.TempDir()
	trip := model.Trip{
		ID:            "trip-save",
		Name:          "Save Sync Trip",
		AlertRules:    []model.AlertRule{}, // leer beim Speichern
		DisplayConfig: displayConfigWithMetrics([]string{"wind_gust"}, true),
	}

	s := New(dataDir, "user1")
	if err := s.SaveTrip(trip); err != nil {
		t.Fatalf("SaveTrip error: %v", err)
	}

	// Rohes JSON lesen und prüfen dass alert_rules befüllt wurde.
	raw, err := os.ReadFile(filepath.Join(dataDir, "users", "user1", "trips", "trip-save.json"))
	if err != nil {
		t.Fatal(err)
	}
	var onDisk model.Trip
	if err := json.Unmarshal(raw, &onDisk); err != nil {
		t.Fatal(err)
	}

	if len(onDisk.AlertRules) == 0 {
		t.Fatal("SaveTrip should have written synchronized alert_rules to disk")
	}
	found := false
	for _, r := range onDisk.AlertRules {
		if r.Metric == model.AlertMetricWindGust {
			found = true
		}
	}
	if !found {
		t.Errorf("expected wind_gust rule in persisted JSON, got: %+v", onDisk.AlertRules)
	}
}

// --- AC-4: Mandantentrennung — zwei Nutzer isoliert ---

// TestLoadTrip_SelfHeal_TwoUsersIsolated prüft: User A mit wind_gust bekommt
// nur eine wind_gust-Regel; User B mit temperature_max bekommt nur eine
// temperature_max-Regel. Keine Cross-User-Vermischung.
func TestLoadTrip_SelfHeal_TwoUsersIsolated(t *testing.T) {
	dataDir := t.TempDir()

	tripA := model.Trip{
		ID:            "trip-A",
		Name:          "User A Trip",
		AlertRules:    []model.AlertRule{},
		DisplayConfig: displayConfigWithMetrics([]string{"wind_gust"}, true),
	}
	tripB := model.Trip{
		ID:            "trip-B",
		Name:          "User B Trip",
		AlertRules:    []model.AlertRule{},
		DisplayConfig: displayConfigWithMetrics([]string{"temperature_max"}, true),
	}
	writeTripJSON(t, dataDir, "user_a", tripA)
	writeTripJSON(t, dataDir, "user_b", tripB)

	base := New(dataDir, "default")

	loadedA, err := base.WithUser("user_a").LoadTrip("trip-A")
	if err != nil || loadedA == nil {
		t.Fatalf("LoadTrip(user_a) failed: %v", err)
	}
	loadedB, err := base.WithUser("user_b").LoadTrip("trip-B")
	if err != nil || loadedB == nil {
		t.Fatalf("LoadTrip(user_b) failed: %v", err)
	}

	// User A: darf nur wind_gust haben, kein temperature_max.
	for _, r := range loadedA.AlertRules {
		if r.Metric == model.AlertMetricTemperatureMax {
			t.Errorf("cross-user leak: user_a hat temperature_max Regel von user_b: %+v", r)
		}
	}
	foundWindGust := false
	for _, r := range loadedA.AlertRules {
		if r.Metric == model.AlertMetricWindGust {
			foundWindGust = true
		}
	}
	if !foundWindGust {
		t.Errorf("user_a: expected wind_gust rule, got: %+v", loadedA.AlertRules)
	}

	// User B: darf nur temperature_max haben, kein wind_gust.
	for _, r := range loadedB.AlertRules {
		if r.Metric == model.AlertMetricWindGust {
			t.Errorf("cross-user leak: user_b hat wind_gust Regel von user_a: %+v", r)
		}
	}
	foundTempMax := false
	for _, r := range loadedB.AlertRules {
		if r.Metric == model.AlertMetricTemperatureMax {
			foundTempMax = true
		}
	}
	if !foundTempMax {
		t.Errorf("user_b: expected temperature_max rule, got: %+v", loadedB.AlertRules)
	}
}

// --- AC-6: Datenerhalt — andere Felder werden nicht verändert ---

// TestLoadTrip_SelfHeal_PreservesOtherFields prüft: Der Self-Heal in LoadTrip
// verändert keine anderen Trip-Felder. Nur alert_rules darf sich ändern.
func TestLoadTrip_SelfHeal_PreservesOtherFields(t *testing.T) {
	dataDir := t.TempDir()
	cooldown := 30
	quietFrom := "22:00"
	quietTo := "06:00"

	trip := model.Trip{
		ID:   "trip-fulldata",
		Name: "Full Data Trip",
		Stages: []model.Stage{
			{ID: "s1", Name: "Etappe 1", Date: "2026-07-01"},
		},
		AlertRules:           []model.AlertRule{}, // leer — wird durch Self-Heal befüllt
		AlertCooldownMinutes: &cooldown,
		AlertQuietFrom:       &quietFrom,
		AlertQuietTo:         &quietTo,
		DisplayConfig:        displayConfigWithMetrics([]string{"wind_gust"}, true),
		ReportConfig: map[string]interface{}{
			"send_email": true,
		},
		Activity: "hiking",
		Region:   "alps",
	}
	writeTripJSON(t, dataDir, "user1", trip)

	s := New(dataDir, "user1")
	loaded, err := s.LoadTrip("trip-fulldata")
	if err != nil || loaded == nil {
		t.Fatalf("LoadTrip error: %v", err)
	}

	// Alle Felder außer alert_rules müssen byte-identisch sein.
	if loaded.Name != trip.Name {
		t.Errorf("Name changed: expected %q, got %q", trip.Name, loaded.Name)
	}
	if loaded.Activity != trip.Activity {
		t.Errorf("Activity changed: expected %q, got %q", trip.Activity, loaded.Activity)
	}
	if loaded.Region != trip.Region {
		t.Errorf("Region changed: expected %q, got %q", trip.Region, loaded.Region)
	}
	if loaded.AlertCooldownMinutes == nil || *loaded.AlertCooldownMinutes != cooldown {
		t.Errorf("AlertCooldownMinutes changed: expected %d", cooldown)
	}
	if loaded.AlertQuietFrom == nil || *loaded.AlertQuietFrom != quietFrom {
		t.Errorf("AlertQuietFrom changed: expected %q", quietFrom)
	}
	if loaded.AlertQuietTo == nil || *loaded.AlertQuietTo != quietTo {
		t.Errorf("AlertQuietTo changed: expected %q", quietTo)
	}
	if !reflect.DeepEqual(loaded.ReportConfig, trip.ReportConfig) {
		t.Errorf("ReportConfig changed: expected %v, got %v", trip.ReportConfig, loaded.ReportConfig)
	}
	if len(loaded.Stages) != 1 || loaded.Stages[0].ID != "s1" {
		t.Errorf("Stages changed: expected 1 stage s1, got %+v", loaded.Stages)
	}

	// alert_rules sollte sich geändert haben (von leer auf 1 Regel).
	if len(loaded.AlertRules) == 0 {
		t.Error("expected alert_rules to be populated by self-heal")
	}
}

// --- model.ActiveAlertableMetricIDs Tests ---

// TestActiveAlertableMetricIDs_FiltersNonAlertable (SUPERSEDED #817):
// Issue #817: thunder_level ist jetzt alertable (delta-Schwelle sinnvoll).
// Nur *_change-Metriken bleiben nicht-alertable.
func TestActiveAlertableMetricIDs_FiltersNonAlertable(t *testing.T) {
	cfg := displayConfigWithMetrics([]string{
		"wind_gust",       // alertable (delta)
		"temperature_max", // alertable (delta)
		"thunder_level",   // SUPERSEDED #817: jetzt alertable (delta-Schwelle 1 Level)
		"wind_change",     // NICHT alertable (*_change konzeptionell redundant, Folge-Issue)
	}, true)

	ids := model.ActiveAlertableMetricIDs(cfg)

	// SUPERSEDED #817: thunder_level ist jetzt alertable → 3 IDs statt 2
	want := map[string]bool{"wind_gust": true, "temperature_max": true, "thunder_level": true}
	for _, id := range ids {
		if !want[id] {
			t.Errorf("unexpected non-alertable metric in result: %s", id)
		}
	}
	if len(ids) != 3 {
		t.Errorf("SUPERSEDED #817: expected 3 alertable IDs (incl. thunder_level), got %d: %v", len(ids), ids)
	}
}

// TestActiveAlertableMetricIDs_IgnoresDisabled prüft: Deaktivierte Metriken werden
// nicht in die ID-Liste aufgenommen.
func TestActiveAlertableMetricIDs_IgnoresDisabled(t *testing.T) {
	cfg := map[string]interface{}{
		"metrics": []interface{}{
			map[string]interface{}{"metric_id": "wind_gust", "enabled": false},
			map[string]interface{}{"metric_id": "temperature_max", "enabled": true},
		},
	}

	ids := model.ActiveAlertableMetricIDs(cfg)

	if len(ids) != 1 || ids[0] != "temperature_max" {
		t.Errorf("expected only temperature_max (enabled), got: %v", ids)
	}
}

// TestActiveAlertableMetricIDs_EmptyConfig prüft: Leere / fehlende display_config
// gibt nil zurück ohne Panic.
func TestActiveAlertableMetricIDs_EmptyConfig(t *testing.T) {
	ids := model.ActiveAlertableMetricIDs(nil)
	if ids != nil {
		t.Errorf("expected nil for nil config, got: %v", ids)
	}
	ids = model.ActiveAlertableMetricIDs(map[string]interface{}{})
	if ids != nil {
		t.Errorf("expected nil for empty config, got: %v", ids)
	}
}
