package handler

import (
	"encoding/json"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/go-chi/chi/v5"
	"github.com/henemm/gregor-api/internal/model"
)

// TDD RED — Issue #701: PutTripWeatherConfigHandler soll nach dem Speichern
// alert_rules automatisch synchronisieren. Noch nicht implementiert → Tests FAIL.

// AC-1 + AC-3: Speichern einer WeatherConfig mit aktiven Metriken → alert_rules automatisch befüllt
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
	s.SaveTrip(trip)

	r := chi.NewRouter()
	r.Put("/api/trips/{id}/weather-config", PutTripWeatherConfigHandler(s))

	// WeatherConfig mit wind_gust + precipitation_sum aktiv senden
	body := `{"metrics":[{"metric_id":"wind_gust","enabled":true,"use_friendly_format":true,"horizons":{"today":true,"tomorrow":true,"day_after":true}},{"metric_id":"precipitation_sum","enabled":true,"use_friendly_format":true,"horizons":{"today":true,"tomorrow":true,"day_after":true}},{"metric_id":"temperature_change","enabled":true,"use_friendly_format":false,"horizons":{"today":true,"tomorrow":true,"day_after":true}}]}`
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
		if r.Kind != model.AlertRuleKindAbsolute {
			t.Errorf("rule %s: want kind=absolute, got %s", r.Metric, r.Kind)
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

// AC-4: Bestehender Threshold bleibt erhalten UND neue Metrik wird angelegt (Sync hat stattgefunden)
func TestPutTripWeatherConfig_PreservesExistingThreshold(t *testing.T) {
	s := newTestStore(t)
	// Trip mit bestehender wind_gust-Regel (Threshold nutzerseitig auf 70 gesetzt)
	trip := model.Trip{
		ID:   "trip-preserve-test",
		Name: "Preserve Threshold Trip",
		Stages: []model.Stage{{
			ID: "S1", Name: "D1", Date: "2026-06-15",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}},
		}},
		AlertRules: []model.AlertRule{
			{ID: "existing-rule", Kind: model.AlertRuleKindAbsolute, Metric: model.AlertMetricWindGust, Threshold: 70, Unit: "km/h", Enabled: true},
		},
	}
	s.SaveTrip(trip)

	r := chi.NewRouter()
	r.Put("/api/trips/{id}/weather-config", PutTripWeatherConfigHandler(s))

	// wind_gust bleibt aktiv + snow_line NEU hinzugefügt
	body := `{"metrics":[{"metric_id":"wind_gust","enabled":true,"use_friendly_format":true,"horizons":{"today":true,"tomorrow":true,"day_after":true}},{"metric_id":"snow_line","enabled":true,"use_friendly_format":false,"horizons":{"today":true,"tomorrow":true,"day_after":true}}]}`
	req := httptest.NewRequest("PUT", "/api/trips/trip-preserve-test/weather-config", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("want 200, got %d: %s", w.Code, w.Body.String())
	}

	saved, _ := s.LoadTrip("trip-preserve-test")

	// Sync muss stattgefunden haben: 2 Regeln (wind_gust + snow_line)
	if len(saved.AlertRules) != 2 {
		t.Fatalf("want 2 rules after sync (wind_gust preserved + snow_line new), got %d", len(saved.AlertRules))
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
	if windRule.Threshold != 70 {
		t.Errorf("want threshold 70 preserved, got %f", windRule.Threshold)
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
	sA.SaveTrip(tripA)

	// User B: Trip ohne Metriken
	tripB := model.Trip{
		ID:   "trip-user-b",
		Name: "Trip B",
		Stages: []model.Stage{{
			ID: "S1", Name: "D1", Date: "2026-06-15",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 48.0, Lon: 12.0, ElevationM: 300}},
		}},
	}
	sB.SaveTrip(tripB)

	rA := chi.NewRouter()
	rA.Put("/api/trips/{id}/weather-config", PutTripWeatherConfigHandler(sA))

	// User A speichert wind_gust
	bodyA := `{"metrics":[{"metric_id":"wind_gust","enabled":true,"use_friendly_format":true,"horizons":{"today":true,"tomorrow":true,"day_after":true}}]}`
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
