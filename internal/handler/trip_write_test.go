package handler

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/go-chi/chi/v5"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

func newTestStore(t *testing.T) *store.Store {
	return store.New(t.TempDir(), "test")
}

func seedTrip(t *testing.T, s *store.Store, id, name string) {
	trip := model.Trip{
		ID: id, Name: name,
		Stages: []model.Stage{{ID: "S1", Name: "D1", Date: "2026-05-01",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}},
		}},
	}
	s.SaveTrip(trip)
}

func TestCreateTripHandler(t *testing.T) {
	s := newTestStore(t)

	body := `{"id":"new-trip","name":"New Trip","stages":[{"id":"S1","name":"Day 1","date":"2026-05-01","waypoints":[{"id":"W1","name":"Start","lat":47.0,"lon":11.0,"elevation_m":500}]}]}`

	h := CreateTripHandler(s)
	req := httptest.NewRequest("POST", "/api/trips", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 201 {
		t.Fatalf("expected 201, got %d: %s", w.Code, w.Body.String())
	}

	var resp map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &resp)
	if resp["id"] != "new-trip" {
		t.Errorf("expected id new-trip, got %v", resp["id"])
	}
}

func TestCreateTripHandlerInvalid(t *testing.T) {
	s := newTestStore(t)

	body := `{"id":"no-name","stages":[]}`

	h := CreateTripHandler(s)
	req := httptest.NewRequest("POST", "/api/trips", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 400 {
		t.Fatalf("expected 400, got %d", w.Code)
	}
}

func TestCreateTripHandlerZeroCoords(t *testing.T) {
	s := newTestStore(t)

	body := `{"id":"zero","name":"Zero","stages":[{"id":"S1","name":"D1","date":"2026-05-01","waypoints":[{"id":"W1","name":"P","lat":0,"lon":0,"elevation_m":0}]}]}`

	h := CreateTripHandler(s)
	req := httptest.NewRequest("POST", "/api/trips", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 400 {
		t.Fatalf("expected 400 for zero coords, got %d", w.Code)
	}
}

func TestUpdateTripHandler(t *testing.T) {
	s := newTestStore(t)
	seedTrip(t, s, "existing", "Old Name")

	body := `{"id":"existing","name":"Updated Name","stages":[{"id":"S1","name":"Day 1","date":"2026-05-01","waypoints":[{"id":"W1","name":"Start","lat":47.0,"lon":11.0,"elevation_m":500}]}]}`

	r := chi.NewRouter()
	r.Put("/api/trips/{id}", UpdateTripHandler(s))

	req := httptest.NewRequest("PUT", "/api/trips/existing", strings.NewReader(body))
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
}

func TestUpdateTripHandlerNotFound(t *testing.T) {
	s := newTestStore(t)

	body := `{"id":"ghost","name":"Ghost","stages":[{"id":"S1","name":"D1","date":"2026-05-01","waypoints":[{"id":"W1","name":"P","lat":47.0,"lon":11.0,"elevation_m":500}]}]}`

	r := chi.NewRouter()
	r.Put("/api/trips/{id}", UpdateTripHandler(s))

	req := httptest.NewRequest("PUT", "/api/trips/ghost", strings.NewReader(body))
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 404 {
		t.Fatalf("expected 404, got %d", w.Code)
	}
}

func TestDeleteTripHandler(t *testing.T) {
	s := newTestStore(t)
	seedTrip(t, s, "to-delete", "Delete Me")

	r := chi.NewRouter()
	r.Delete("/api/trips/{id}", DeleteTripHandler(s))

	req := httptest.NewRequest("DELETE", "/api/trips/to-delete", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusNoContent {
		t.Fatalf("expected 204, got %d", w.Code)
	}
}

// --- Issue #99: Merge-statt-Replace Tests ---

// seedTripWithConfigs persists a trip carrying every optional field populated.
func seedTripWithConfigs(t *testing.T, s *store.Store, id string) {
	trip := model.Trip{
		ID: id, Name: "Configured Trip",
		Stages: []model.Stage{{ID: "S1", Name: "D1", Date: "2026-05-01",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}},
		}},
		AvalancheRegions: []string{"AT-07-15"},
		Aggregation:      map[string]interface{}{"strategy": "max_per_stage"},
		WeatherConfig:    map[string]interface{}{"profile": "skitouren"},
		DisplayConfig:    map[string]interface{}{"theme": "compact"},
		ReportConfig:     map[string]interface{}{"channels": []interface{}{"email"}},
	}
	if err := s.SaveTrip(trip); err != nil {
		t.Fatalf("seed failed: %v", err)
	}
}

// minimalBody returns a PUT body with only id, name, stages — no optional configs.
func minimalBody(id, name string) string {
	return `{"id":"` + id + `","name":"` + name + `","stages":[{"id":"S1","name":"D1","date":"2026-05-01","waypoints":[{"id":"W1","name":"P","lat":47.0,"lon":11.0,"elevation_m":500}]}]}`
}

func putUpdate(t *testing.T, s *store.Store, id, body string) int {
	r := chi.NewRouter()
	r.Put("/api/trips/{id}", UpdateTripHandler(s))
	req := httptest.NewRequest("PUT", "/api/trips/"+id, strings.NewReader(body))
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	return w.Code
}

func loadTripOrFail(t *testing.T, s *store.Store, id string) *model.Trip {
	got, err := s.LoadTrip(id)
	if err != nil {
		t.Fatalf("LoadTrip failed: %v", err)
	}
	if got == nil {
		t.Fatalf("trip %s not found after PUT", id)
	}
	return got
}

func TestUpdateTripHandlerPreservesAggregation(t *testing.T) {
	s := newTestStore(t)
	seedTripWithConfigs(t, s, "merge-agg")

	if code := putUpdate(t, s, "merge-agg", minimalBody("merge-agg", "Renamed")); code != 200 {
		t.Fatalf("expected 200, got %d", code)
	}

	got := loadTripOrFail(t, s, "merge-agg")
	if got.Aggregation == nil {
		t.Fatalf("aggregation was deleted by minimal-body PUT (expected to be preserved)")
	}
	if got.Aggregation["strategy"] != "max_per_stage" {
		t.Errorf("aggregation.strategy: expected max_per_stage, got %v", got.Aggregation["strategy"])
	}
}

func TestUpdateTripHandlerPreservesReportConfig(t *testing.T) {
	s := newTestStore(t)
	seedTripWithConfigs(t, s, "merge-rc")

	if code := putUpdate(t, s, "merge-rc", minimalBody("merge-rc", "Renamed")); code != 200 {
		t.Fatalf("expected 200, got %d", code)
	}

	got := loadTripOrFail(t, s, "merge-rc")
	if got.ReportConfig == nil {
		t.Fatalf("report_config was deleted by minimal-body PUT")
	}
	if _, ok := got.ReportConfig["channels"]; !ok {
		t.Errorf("report_config.channels missing after PUT, got %v", got.ReportConfig)
	}
}

func TestUpdateTripHandlerPreservesWeatherConfig(t *testing.T) {
	s := newTestStore(t)
	seedTripWithConfigs(t, s, "merge-wc")

	if code := putUpdate(t, s, "merge-wc", minimalBody("merge-wc", "Renamed")); code != 200 {
		t.Fatalf("expected 200, got %d", code)
	}

	got := loadTripOrFail(t, s, "merge-wc")
	if got.WeatherConfig == nil {
		t.Fatalf("weather_config was deleted by minimal-body PUT")
	}
	if got.WeatherConfig["profile"] != "skitouren" {
		t.Errorf("weather_config.profile: expected skitouren, got %v", got.WeatherConfig["profile"])
	}
}

func TestUpdateTripHandlerPreservesDisplayConfig(t *testing.T) {
	s := newTestStore(t)
	seedTripWithConfigs(t, s, "merge-dc")

	if code := putUpdate(t, s, "merge-dc", minimalBody("merge-dc", "Renamed")); code != 200 {
		t.Fatalf("expected 200, got %d", code)
	}

	got := loadTripOrFail(t, s, "merge-dc")
	if got.DisplayConfig == nil {
		t.Fatalf("display_config was deleted by minimal-body PUT")
	}
	if got.DisplayConfig["theme"] != "compact" {
		t.Errorf("display_config.theme: expected compact, got %v", got.DisplayConfig["theme"])
	}
}

func TestUpdateTripHandlerPreservesAvalancheRegions(t *testing.T) {
	s := newTestStore(t)
	seedTripWithConfigs(t, s, "merge-av")

	if code := putUpdate(t, s, "merge-av", minimalBody("merge-av", "Renamed")); code != 200 {
		t.Fatalf("expected 200, got %d", code)
	}

	got := loadTripOrFail(t, s, "merge-av")
	if len(got.AvalancheRegions) == 0 {
		t.Fatalf("avalanche_regions was emptied by minimal-body PUT")
	}
	if got.AvalancheRegions[0] != "AT-07-15" {
		t.Errorf("avalanche_regions[0]: expected AT-07-15, got %v", got.AvalancheRegions[0])
	}
}

func TestUpdateTripHandlerReplacesAggregationWhenSent(t *testing.T) {
	s := newTestStore(t)
	seedTripWithConfigs(t, s, "merge-replace")

	body := `{"id":"merge-replace","name":"Renamed","stages":[{"id":"S1","name":"D1","date":"2026-05-01","waypoints":[{"id":"W1","name":"P","lat":47.0,"lon":11.0,"elevation_m":500}]}],"aggregation":{"strategy":"min_per_stage"}}`
	if code := putUpdate(t, s, "merge-replace", body); code != 200 {
		t.Fatalf("expected 200, got %d", code)
	}

	got := loadTripOrFail(t, s, "merge-replace")
	if got.Aggregation["strategy"] != "min_per_stage" {
		t.Errorf("aggregation.strategy: expected min_per_stage (replaced), got %v", got.Aggregation["strategy"])
	}
	// report_config must still be preserved (not sent → not touched)
	if got.ReportConfig == nil {
		t.Errorf("report_config lost when only aggregation was sent")
	}
}

func TestUpdateTripHandlerKeepsAllConfigsOnNameOnlyUpdate(t *testing.T) {
	s := newTestStore(t)
	seedTripWithConfigs(t, s, "merge-all")

	if code := putUpdate(t, s, "merge-all", minimalBody("merge-all", "Brand New Name")); code != 200 {
		t.Fatalf("expected 200, got %d", code)
	}

	got := loadTripOrFail(t, s, "merge-all")
	if got.Name != "Brand New Name" {
		t.Errorf("name not updated: got %q", got.Name)
	}
	if got.Aggregation == nil {
		t.Errorf("aggregation lost")
	}
	if got.ReportConfig == nil {
		t.Errorf("report_config lost")
	}
	if got.WeatherConfig == nil {
		t.Errorf("weather_config lost")
	}
	if got.DisplayConfig == nil {
		t.Errorf("display_config lost")
	}
	if len(got.AvalancheRegions) == 0 {
		t.Errorf("avalanche_regions lost")
	}
}
