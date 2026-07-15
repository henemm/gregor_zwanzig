package handler

import (
	"encoding/json"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/go-chi/chi/v5"
	"github.com/henemm/gregor-api/internal/model"
)

// Issue #701: PutTripWeatherConfigHandler synchronisiert alert_rules nach dem Speichern.
// Issue #817: alert_rules sind jetzt kind="delta" (statt "absolute").

// AC-1 + AC-3 (SUPERSEDED #817): Speichern einer WeatherConfig mit aktiven Metriken
// → alert_rules automatisch als Delta-Regeln befüllt.
func TestPutTripWeatherConfig_SyncsAlertRules(t *testing.T) {
	s := newTestStore(t)
	// Trip ohne alert_rules anlegen
	trip := model.Trip{
		ID:   "trip-sync-test",
		Name: "Sync Test Trip",
		Stages: []model.Stage{{
			ID: "S1", Name: "D1", Date: "2026-06-15",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}},
		}},
	}
	s.SaveTrip(&trip)

	r := chi.NewRouter()
	r.Put("/api/trips/{id}/weather-config", PutTripWeatherConfigHandler(s))

	// WeatherConfig mit gust + precipitation aktiv senden (Issue #1257: echte Katalog-IDs)
	body := `{"metrics":[{"metric_id":"gust","enabled":true,"use_friendly_format":true,"horizons":{"today":true,"tomorrow":true,"day_after":true}},{"metric_id":"precipitation","enabled":true,"use_friendly_format":true,"horizons":{"today":true,"tomorrow":true,"day_after":true}},{"metric_id":"temperature_change","enabled":true,"use_friendly_format":false,"horizons":{"today":true,"tomorrow":true,"day_after":true}}]}`
	req := httptest.NewRequest("PUT", "/api/trips/trip-sync-test/weather-config", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("want 200, got %d: %s", w.Code, w.Body.String())
	}

	// Trip nachladen und alert_rules prüfen
	saved, err := s.LoadTrip("trip-sync-test")
	if err != nil || saved == nil {
		t.Fatalf("failed to load saved trip: %v", err)
	}

	// Erwartet: 2 Regeln (wind_gust + precipitation_sum), NICHT temperature_change (delta-only)
	if len(saved.AlertRules) != 2 {
		t.Fatalf("want 2 alert_rules (wind_gust+precipitation_sum), got %d: %+v", len(saved.AlertRules), saved.AlertRules)
	}
	metrics := map[model.AlertMetric]bool{}
	for _, r := range saved.AlertRules {
		metrics[r.Metric] = true
		// SUPERSEDED #817: war kind=absolute, jetzt kind=delta
		if r.Kind != model.AlertRuleKindDelta {
			t.Errorf("SUPERSEDED #817: rule %s: want kind=delta, got %s", r.Metric, r.Kind)
		}
		if !r.Enabled {
			t.Errorf("rule %s: want enabled=true", r.Metric)
		}
	}
	if !metrics[model.AlertMetricWindGust] {
		t.Error("want wind_gust alert rule")
	}
	if !metrics[model.AlertMetricPrecipitationSum] {
		t.Error("want precipitation_sum alert rule")
	}
	if metrics[model.AlertMetricTemperatureChange] {
		t.Error("temperature_change must NOT get an alert rule (delta-only)")
	}
}

// AC-4 (SUPERSEDED #817): Absolute Regel wird zu Delta migriert; neue Metrik bekommt Delta-Default.
// Issue #817: absoluter Threshold 70 war nie alert-wirksam → Migration auf Delta-Default kein Verlust.
func TestPutTripWeatherConfig_PreservesExistingThreshold(t *testing.T) {
	s := newTestStore(t)
	// Trip mit bestehender wind_gust-Regel (Threshold absolut 70, war nie alert-wirksam)
	// + display_config mit wind_gust aktiv
	trip := model.Trip{
		ID:   "trip-preserve-test",
		Name: "Preserve Threshold Trip",
		Stages: []model.Stage{{
			ID: "S1", Name: "D1", Date: "2026-06-15",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}},
		}},
		DisplayConfig: map[string]interface{}{
			"metrics": []interface{}{
				map[string]interface{}{"metric_id": "gust", "enabled": true},
			},
		},
		AlertRules: []model.AlertRule{
			{ID: "existing-rule", Kind: model.AlertRuleKindAbsolute, Metric: model.AlertMetricWindGust, Threshold: 70, Unit: "km/h", Enabled: true},
		},
	}
	s.SaveTrip(&trip)

	r := chi.NewRouter()
	r.Put("/api/trips/{id}/weather-config", PutTripWeatherConfigHandler(s))

	// gust bleibt aktiv + snowfall_limit NEU hinzugefügt (Issue #1257: echte Katalog-IDs)
	body := `{"metrics":[{"metric_id":"gust","enabled":true,"use_friendly_format":true,"horizons":{"today":true,"tomorrow":true,"day_after":true}},{"metric_id":"snowfall_limit","enabled":true,"use_friendly_format":false,"horizons":{"today":true,"tomorrow":true,"day_after":true}}]}`
	req := httptest.NewRequest("PUT", "/api/trips/trip-preserve-test/weather-config", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("want 200, got %d: %s", w.Code, w.Body.String())
	}

	saved, _ := s.LoadTrip("trip-preserve-test")

	// Sync muss stattgefunden haben: 2 Regeln (wind_gust migriert + snow_line neu)
	if len(saved.AlertRules) != 2 {
		t.Fatalf("want 2 rules after sync (wind_gust migrated + snow_line new), got %d", len(saved.AlertRules))
	}

	var windRule *model.AlertRule
	for i := range saved.AlertRules {
		if saved.AlertRules[i].Metric == model.AlertMetricWindGust {
			windRule = &saved.AlertRules[i]
		}
	}
	if windRule == nil {
		t.Fatal("want wind_gust rule to still exist")
	}
	// SUPERSEDED #817: absoluter Threshold 70 → Delta-Default 20. Threshold war nie wirksam.
	deltaDefault := model.DefaultDeltaThreshold[model.AlertMetricWindGust].Threshold
	if windRule.Threshold != deltaDefault {
		t.Errorf("SUPERSEDED #817: want threshold=%v (Delta-Default; absolute 70 war nie wirksam), got %f",
			deltaDefault, windRule.Threshold)
	}
	// ID muss erhalten bleiben
	if windRule.ID != "existing-rule" {
		t.Errorf("rule ID must be preserved: want existing-rule, got %s", windRule.ID)
	}
}

// AC-6: Mandantentrennung — zwei Nutzer, unabhängige Sync-Operationen
func TestPutTripWeatherConfig_TenantIsolation(t *testing.T) {
	sA := newTestStore(t) // User A
	sB := newTestStore(t) // User B (eigenes TempDir → isoliert)

	// User A: Trip mit wind_gust-Regel
	tripA := model.Trip{
		ID:   "trip-user-a",
		Name: "Trip A",
		Stages: []model.Stage{{
			ID: "S1", Name: "D1", Date: "2026-06-15",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}},
		}},
	}
	sA.SaveTrip(&tripA)

	// User B: Trip ohne Metriken
	tripB := model.Trip{
		ID:   "trip-user-b",
		Name: "Trip B",
		Stages: []model.Stage{{
			ID: "S1", Name: "D1", Date: "2026-06-15",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 48.0, Lon: 12.0, ElevationM: 300}},
		}},
	}
	sB.SaveTrip(&tripB)

	rA := chi.NewRouter()
	rA.Put("/api/trips/{id}/weather-config", PutTripWeatherConfigHandler(sA))

	// User A speichert gust (Issue #1257: echte Katalog-ID)
	bodyA := `{"metrics":[{"metric_id":"gust","enabled":true,"use_friendly_format":true,"horizons":{"today":true,"tomorrow":true,"day_after":true}}]}`
	reqA := httptest.NewRequest("PUT", "/api/trips/trip-user-a/weather-config", strings.NewReader(bodyA))
	reqA.Header.Set("Content-Type", "application/json")
	wA := httptest.NewRecorder()
	rA.ServeHTTP(wA, reqA)

	if wA.Code != 200 {
		t.Fatalf("user A: want 200, got %d", wA.Code)
	}

	// User B's Trip bleibt unberührt
	savedB, _ := sB.LoadTrip("trip-user-b")
	if savedB == nil {
		t.Fatal("user B trip should still exist")
	}
	if len(savedB.AlertRules) != 0 {
		t.Errorf("user B alert_rules must be untouched, got %d rules", len(savedB.AlertRules))
	}

	// Seitencheck: user A's Trip hat die Regel
	savedA, _ := sA.LoadTrip("trip-user-a")
	if len(savedA.AlertRules) != 1 {
		t.Errorf("user A: want 1 alert rule, got %d", len(savedA.AlertRules))
	}
}

// Hilfsfunktion: JSON-Decode für Tests
func decodeJSON(t *testing.T, data []byte) map[string]interface{} {
	t.Helper()
	var result map[string]interface{}
	if err := json.Unmarshal(data, &result); err != nil {
		t.Fatalf("JSON decode failed: %v\nData: %s", err, data)
	}
	return result
}
