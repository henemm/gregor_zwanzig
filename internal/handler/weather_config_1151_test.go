package handler

import (
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/go-chi/chi/v5"
	"github.com/henemm/gregor-api/internal/model"
)

// Issue #1151: PutTripWeatherConfigHandler ersetzte trip.DisplayConfig blind
// (trip.DisplayConfig = cfg) statt feldweise zu mergen. Ein Teil-Update (nur
// `metrics` gesendet) loeschte dadurch alle anderen zuvor gespeicherten Keys
// von display_config. Gleiche Fehlerklasse wie #1129/#1103 (BUG-DATALOSS-GR221).
//
// AC-1: Teil-PUT (nur metrics) darf einen zuvor gespeicherten Top-Level-Key
// (theme) NICHT loeschen, sondern nur die gesendeten Keys aktualisieren.
func TestPutTripWeatherConfigMergesDisplayConfig(t *testing.T) {
	s := newTestStore(t)

	// Seed: Trip mit display_config aus >=2 Top-Level-Keys.
	trip := model.Trip{
		ID:   "merge-wc-1151",
		Name: "Merge WC 1151",
		Stages: []model.Stage{{
			ID: "S1", Name: "D1", Date: "2026-05-01",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}},
		}},
		DisplayConfig: map[string]interface{}{
			"theme":   "compact",
			"metrics": []interface{}{map[string]interface{}{"metric_id": "temperature", "enabled": true}},
		},
	}
	if err := s.SaveTrip(trip); err != nil {
		t.Fatalf("seed SaveTrip failed: %v", err)
	}

	r := chi.NewRouter()
	r.Put("/api/trips/{id}/weather-config", PutTripWeatherConfigHandler(s))

	// Teil-PUT: NUR metrics, kein theme.
	body := `{"metrics":[{"metric_id":"wind","enabled":true}]}`
	req := httptest.NewRequest("PUT", "/api/trips/merge-wc-1151/weather-config", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	got, err := s.LoadTrip("merge-wc-1151")
	if err != nil || got == nil {
		t.Fatalf("failed to load trip: %v", err)
	}

	// theme wurde NICHT gesendet -> muss erhalten bleiben (Feld-Level-Merge).
	if got.DisplayConfig["theme"] != "compact" {
		t.Errorf("display_config.theme: expected to be preserved (compact), got %v", got.DisplayConfig["theme"])
	}

	// metrics reflektiert den neuen Payload (wind statt temperature).
	metrics, ok := got.DisplayConfig["metrics"].([]interface{})
	if !ok || len(metrics) != 1 {
		t.Fatalf("display_config.metrics: expected 1 metric, got %v", got.DisplayConfig["metrics"])
	}
	m0, _ := metrics[0].(map[string]interface{})
	if m0["metric_id"] != "wind" {
		t.Errorf("display_config.metrics[0].metric_id: expected wind (new payload), got %v", m0["metric_id"])
	}
}
