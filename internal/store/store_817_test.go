package store

// TDD RED — Issue #817: Alerts-Tab Δ-Schwellen — Store-Layer-Tests.
//
// Diese Tests prüfen den Store-Layer (SaveTrip, LoadTrip) für die Migration
// von kind="absolute" auf kind="delta" in alert_rules.
//
// RED-Treiber:
//   - AC-8: LoadTrip gibt heute kind="absolute" zurück (SyncAlertRules erzeugt absolute).
//
// Regression-Guard (heute GRÜN):
//   - AC-7: Mandantentrennung — SaveTrip user_a verändert user_b-alert_rules nicht.
//
// Keine Mocks: echter t.TempDir()-Store, echte Trip-JSONs auf Platte.

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	"github.com/henemm/gregor-api/internal/model"
)

// --- AC-8: Datenerhalt-Roundtrip — absolute alert_rules werden migriert,
//           alle anderen Felder bleiben unverändert ---
//
// RED-Treiber: Nach LoadTrip haben die Regeln heute kind="absolute" (nicht "delta").
// GRÜN nach Implementierung: SyncAlertRules migriert auf "delta".
func TestLoadTrip_817_MigratesAbsoluteRulesToDelta(t *testing.T) {
	dataDir := t.TempDir()

	// Bestands-Trip mit absoluten alert_rules + befüllten anderen Feldern.
	trip := model.Trip{
		ID:   "trip-817-roundtrip",
		Name: "Roundtrip Test Trip",
		Stages: []model.Stage{
			{ID: "stage-1", Name: "Tag 1", Date: "2026-07-01"},
			{ID: "stage-2", Name: "Tag 2", Date: "2026-07-02"},
		},
		AlertRules: []model.AlertRule{
			{
				ID:        "rule-absolute-gust",
				Kind:      model.AlertRuleKindAbsolute,
				Metric:    model.AlertMetricWindGust,
				Threshold: 50,
				Unit:      "km/h",
				Enabled:   true,
				Severity:  model.AlertSeverityWarning,
			},
			{
				ID:        "rule-absolute-precip",
				Kind:      model.AlertRuleKindAbsolute,
				Metric:    model.AlertMetricPrecipitationSum,
				Threshold: 20,
				Unit:      "mm",
				Enabled:   false, // disabled
				Severity:  model.AlertSeverityWarning,
			},
		},
		DisplayConfig: displayConfigWithMetrics([]string{"wind_gust", "precipitation_sum"}, true),
		ReportConfig: map[string]interface{}{
			"send_email": true,
			"channels":   []interface{}{"email"},
		},
		Activity: "hiking",
		Region:   "corsica",
	}

	writeTripJSON(t, dataDir, "user-817", trip)

	s := New(dataDir, "user-817")
	loaded, err := s.LoadTrip("trip-817-roundtrip")
	if err != nil {
		t.Fatalf("AC-8: LoadTrip error: %v", err)
	}
	if loaded == nil {
		t.Fatal("AC-8: LoadTrip returned nil")
	}

	// AC-8: alert_rules müssen migriert sein — kind="delta" für alle Regeln.
	if len(loaded.AlertRules) == 0 {
		t.Fatal("AC-8: want non-empty alert_rules after self-heal")
	}
	for _, r := range loaded.AlertRules {
		if r.Kind != model.AlertRuleKindDelta {
			t.Errorf("AC-8: rule %s (metric=%s): want kind=%q, got %q",
				r.ID, r.Metric, model.AlertRuleKindDelta, r.Kind)
		}
	}

	// AC-8: Alle anderen Trip-Felder müssen unverändert sein (Datenerhalt).
	if loaded.Name != trip.Name {
		t.Errorf("AC-8: Name changed: want %q, got %q", trip.Name, loaded.Name)
	}
	if loaded.Activity != trip.Activity {
		t.Errorf("AC-8: Activity changed: want %q, got %q", trip.Activity, loaded.Activity)
	}
	if loaded.Region != trip.Region {
		t.Errorf("AC-8: Region changed: want %q, got %q", trip.Region, loaded.Region)
	}
	if len(loaded.Stages) != 2 {
		t.Errorf("AC-8: Stages count changed: want 2, got %d", len(loaded.Stages))
	}
	if loaded.Stages[0].ID != "stage-1" {
		t.Errorf("AC-8: Stages[0].ID changed: want %q, got %q", "stage-1", loaded.Stages[0].ID)
	}
	if loaded.Stages[1].ID != "stage-2" {
		t.Errorf("AC-8: Stages[1].ID changed: want %q, got %q", "stage-2", loaded.Stages[1].ID)
	}
}

// --- AC-8b: SaveTrip schreibt delta-Regeln auf Platte ---
//
// RED-Treiber: SaveTrip schreibt heute kind="absolute" auf Platte.
// GRÜN nach Implementierung: Roh-JSON enthält kind="delta".
func TestSaveTrip_817_WritesDeltaRulesToDisk(t *testing.T) {
	dataDir := t.TempDir()

	trip := model.Trip{
		ID:   "trip-817-save",
		Name: "Save Delta Test",
		AlertRules: []model.AlertRule{
			{
				ID:        "rule-legacy",
				Kind:      model.AlertRuleKindAbsolute,
				Metric:    model.AlertMetricWindGust,
				Threshold: 50,
				Unit:      "km/h",
				Enabled:   true,
				Severity:  model.AlertSeverityWarning,
			},
		},
		DisplayConfig: displayConfigWithMetrics([]string{"wind_gust"}, true),
	}

	s := New(dataDir, "user-817-save")
	if err := s.SaveTrip(trip); err != nil {
		t.Fatalf("AC-8b: SaveTrip error: %v", err)
	}

	raw, err := os.ReadFile(filepath.Join(dataDir, "users", "user-817-save", "trips", "trip-817-save.json"))
	if err != nil {
		t.Fatalf("AC-8b: cannot read trip JSON: %v", err)
	}
	var onDisk model.Trip
	if err := json.Unmarshal(raw, &onDisk); err != nil {
		t.Fatalf("AC-8b: cannot unmarshal trip JSON: %v", err)
	}

	if len(onDisk.AlertRules) == 0 {
		t.Fatal("AC-8b: expected alert_rules in persisted JSON")
	}
	for _, r := range onDisk.AlertRules {
		if r.Kind != model.AlertRuleKindDelta {
			t.Errorf("AC-8b: on-disk rule %s: want kind=%q, got %q",
				r.Metric, model.AlertRuleKindDelta, r.Kind)
		}
	}
}

// --- AC-7: Mandantentrennung (Regression-Guard, heute GRÜN) ---
//
// Dieser Test ist ein REGRESSION-GUARD. Er schlägt heute NICHT fehl —
// die Store-Isolation existiert bereits seit #809. Er verhindert Regression
// durch zukünftige Änderungen.
//
// Beweis: Zwei Nutzer mit je eigenem Trip; SaveTrip(user_a) verändert
// user_b-alert_rules nicht.
func TestLoadTrip_817_MandantentrennungRegression(t *testing.T) {
	// REGRESSION-GUARD: AC-7 — Mandantentrennung bleibt nach #817 erhalten.
	// Dieser Test ist bereits GRÜN (Store-Isolation aus #809).
	dataDir := t.TempDir()

	tripA := model.Trip{
		ID:   "trip-a",
		Name: "User A Trip",
		AlertRules: []model.AlertRule{
			{ID: "rule-a", Kind: model.AlertRuleKindAbsolute, Metric: model.AlertMetricWindGust,
				Threshold: 50, Unit: "km/h", Enabled: true, Severity: model.AlertSeverityWarning},
		},
		DisplayConfig: displayConfigWithMetrics([]string{"wind_gust"}, true),
	}
	tripB := model.Trip{
		ID:   "trip-b",
		Name: "User B Trip",
		AlertRules: []model.AlertRule{
			{ID: "rule-b", Kind: model.AlertRuleKindAbsolute, Metric: model.AlertMetricTemperatureMin,
				Threshold: -5, Unit: "°C", Enabled: true, Severity: model.AlertSeverityWarning},
		},
		DisplayConfig: displayConfigWithMetrics([]string{"temperature_min"}, true),
	}

	writeTripJSON(t, dataDir, "user-a-817", tripA)
	writeTripJSON(t, dataDir, "user-b-817", tripB)

	base := New(dataDir, "default")

	if err := base.WithUser("user-a-817").SaveTrip(tripA); err != nil {
		t.Fatalf("AC-7/guard: SaveTrip(user_a) failed: %v", err)
	}

	loadedB, err := base.WithUser("user-b-817").LoadTrip("trip-b")
	if err != nil || loadedB == nil {
		t.Fatalf("AC-7/guard: LoadTrip(user_b) failed: %v", err)
	}

	// user_b's Regeln dürfen NUR temperature_min enthalten.
	for _, r := range loadedB.AlertRules {
		if r.Metric == model.AlertMetricWindGust {
			t.Errorf("AC-7/guard: cross-user leak: user_b hat wind_gust-Regel von user_a: %+v", r)
		}
	}
	foundTempMin := false
	for _, r := range loadedB.AlertRules {
		if r.Metric == model.AlertMetricTemperatureMin {
			foundTempMin = true
		}
	}
	if !foundTempMin {
		t.Errorf("AC-7/guard: user_b: expected temperature_min rule, got: %+v", loadedB.AlertRules)
	}
}
