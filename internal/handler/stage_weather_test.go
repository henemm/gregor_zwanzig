package handler

import (
	"encoding/json"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/provider/openmeteo"
	"github.com/henemm/gregor-api/internal/store"
)

// writeTestTripSW schreibt einen Trip als JSON-Datei in ein temporaeres Datenverzeichnis.
func writeTestTripSW(t *testing.T, dataDir, userID string, trip model.Trip) {
	t.Helper()
	dir := filepath.Join(dataDir, "users", userID, "trips")
	if err := os.MkdirAll(dir, 0755); err != nil {
		t.Fatalf("create trips dir: %v", err)
	}
	b, err := json.Marshal(trip)
	if err != nil {
		t.Fatalf("marshal trip: %v", err)
	}
	if err := os.WriteFile(filepath.Join(dir, trip.ID+".json"), b, 0644); err != nil {
		t.Fatalf("write trip file: %v", err)
	}
}

// =============================================================================
// Handler-Tests
// =============================================================================

// TestStagesWeatherHandler_TripNotFound_Returns404 prueft AC-4:
// Nicht-existierender Trip liefert HTTP 404.
func TestStagesWeatherHandler_TripNotFound_Returns404(t *testing.T) {
	// GIVEN: Kein Trip mit ID "nonexistent-xyz-stage-weather" im Store
	// WHEN: GET /api/trips/nonexistent-xyz-stage-weather/stages/weather
	// THEN: HTTP 404, body.error == "not_found"
	s := newTestStore(t) // leerer Store gibt korrekt 404 zurueck
	r := chi.NewRouter()
	r.Get("/api/trips/{id}/stages/weather", StagesWeatherHandler(s, nil))

	req := httptest.NewRequest("GET", "/api/trips/nonexistent-xyz-stage-weather/stages/weather", nil)
	rec := httptest.NewRecorder()
	r.ServeHTTP(rec, req)

	if rec.Code != 404 {
		t.Fatalf("expected 404, got %d: %s", rec.Code, rec.Body.String())
	}
	var body map[string]interface{}
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatalf("invalid JSON: %v", err)
	}
	if body["error"] != "not_found" {
		t.Errorf("expected error=not_found, got %v", body["error"])
	}
}

// TestStagesWeatherHandler_StageWithoutWaypoints_ReturnsNull prueft AC-2:
// Stage ohne Waypoints liefert null im results-Map, kein 5xx.
func TestStagesWeatherHandler_StageWithoutWaypoints_ReturnsNull(t *testing.T) {
	// GIVEN: Trip mit einer Stage ohne Waypoints
	// WHEN: GET /api/trips/{id}/stages/weather
	// THEN: HTTP 200, results["s1"] == null
	dir := t.TempDir()
	trip := model.Trip{
		ID:   "test-no-waypoints",
		Name: "Test Trip Kein Wegpunkt",
		Stages: []model.Stage{
			{ID: "s1", Name: "Stage 1", Date: "2026-05-25", Waypoints: []model.Waypoint{}},
		},
	}
	writeTestTripSW(t, dir, "default", trip)
	s := store.New(dir, "default")

	r := chi.NewRouter()
	r.Get("/api/trips/{id}/stages/weather", StagesWeatherHandler(s, nil))

	req := httptest.NewRequest("GET", "/api/trips/test-no-waypoints/stages/weather", nil)
	rec := httptest.NewRecorder()
	r.ServeHTTP(rec, req)

	if rec.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", rec.Code, rec.Body.String())
	}
	var resp model.StagesWeatherResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
		t.Fatalf("invalid JSON: %v", err)
	}
	if resp.Results["s1"] != nil {
		t.Errorf("expected null result for stage without waypoints, got %+v", resp.Results["s1"])
	}
}

// TestStagesWeatherHandler_StageWithoutDate_ReturnsNull prueft AC-3:
// Stage ohne Datum liefert null im results-Map, kein 5xx.
func TestStagesWeatherHandler_StageWithoutDate_ReturnsNull(t *testing.T) {
	// GIVEN: Trip mit einer Stage ohne Datum (leerer String)
	// WHEN: GET /api/trips/{id}/stages/weather
	// THEN: HTTP 200, results["s1"] == null
	dir := t.TempDir()
	trip := model.Trip{
		ID:   "test-no-date",
		Name: "Test Trip Kein Datum",
		Stages: []model.Stage{
			{
				ID: "s1", Name: "Stage ohne Datum", Date: "",
				Waypoints: []model.Waypoint{
					{ID: "w1", Lat: 39.7, Lon: 2.6, ElevationM: 100},
				},
			},
		},
	}
	writeTestTripSW(t, dir, "default", trip)
	s := store.New(dir, "default")

	r := chi.NewRouter()
	r.Get("/api/trips/{id}/stages/weather", StagesWeatherHandler(s, nil))

	req := httptest.NewRequest("GET", "/api/trips/test-no-date/stages/weather", nil)
	rec := httptest.NewRecorder()
	r.ServeHTTP(rec, req)

	if rec.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", rec.Code, rec.Body.String())
	}
	var resp model.StagesWeatherResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
		t.Fatalf("invalid JSON: %v", err)
	}
	if resp.Results["s1"] != nil {
		t.Errorf("expected null result for stage without date, got %+v", resp.Results["s1"])
	}
}

// TestStagesWeatherHandler_MultiStage_PartialNullSafe prueft AC-5:
// Bei mehreren Stages liefert eine Stage ohne Waypoints null,
// waehrend andere Stages normal verarbeitet werden (Fail-soft).
func TestStagesWeatherHandler_MultiStage_PartialNullSafe(t *testing.T) {
	// GIVEN: Trip mit 2 Stages: s1 ohne Waypoints, s2 ohne Datum
	// WHEN: GET /api/trips/{id}/stages/weather (kein echter Provider)
	// THEN: HTTP 200, results["s1"]=null, results["s2"]=null — beide null, kein 5xx
	dir := t.TempDir()
	trip := model.Trip{
		ID:   "test-multi-null",
		Name: "Test Multi Stage Null",
		Stages: []model.Stage{
			{ID: "s1", Name: "Ohne Wegpunkte", Date: "2026-05-25", Waypoints: []model.Waypoint{}},
			{ID: "s2", Name: "Ohne Datum", Date: "", Waypoints: []model.Waypoint{
				{ID: "w1", Lat: 47.0, Lon: 11.0, ElevationM: 500},
			}},
		},
	}
	writeTestTripSW(t, dir, "default", trip)
	s := store.New(dir, "default")

	r := chi.NewRouter()
	r.Get("/api/trips/{id}/stages/weather", StagesWeatherHandler(s, nil))

	req := httptest.NewRequest("GET", "/api/trips/test-multi-null/stages/weather", nil)
	rec := httptest.NewRecorder()
	r.ServeHTTP(rec, req)

	if rec.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", rec.Code, rec.Body.String())
	}
	var resp model.StagesWeatherResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
		t.Fatalf("invalid JSON: %v", err)
	}
	if _, ok := resp.Results["s1"]; !ok {
		t.Error("expected results to contain key s1")
	}
	if _, ok := resp.Results["s2"]; !ok {
		t.Error("expected results to contain key s2")
	}
	if resp.Results["s1"] != nil {
		t.Errorf("expected null for s1 (no waypoints), got %+v", resp.Results["s1"])
	}
	if resp.Results["s2"] != nil {
		t.Errorf("expected null for s2 (no date), got %+v", resp.Results["s2"])
	}
}

// TestStagesWeatherHandler_Integration_ReturnsWeather prueft AC-1:
// Stage mit Datum und Waypoints liefert weather_summary und risk (echter API-Call).
func TestStagesWeatherHandler_Integration_ReturnsWeather(t *testing.T) {
	if testing.Short() {
		t.Skip("skipping integration test in short mode")
	}
	// GIVEN: Trip mit einer Stage mit morgen als Datum und 2 Wegpunkten (Mallorca)
	// WHEN: GET /api/trips/{id}/stages/weather mit echtem Provider
	// THEN: HTTP 200, results["s1"].weather_summary != null, results["s1"].risk in {"green","yellow","red"}
	dir := t.TempDir()
	tomorrow := time.Now().UTC().AddDate(0, 0, 1).Format("2006-01-02")
	trip := model.Trip{
		ID:   "test-integration-weather",
		Name: "Integration Test Wetter",
		Stages: []model.Stage{
			{
				ID:   "s1",
				Name: "Mallorca Etappe 1",
				Date: tomorrow,
				Waypoints: []model.Waypoint{
					{ID: "w1", Lat: 39.710564, Lon: 2.622930, ElevationM: 410},
					{ID: "w2", Lat: 39.747657, Lon: 2.648606, ElevationM: 149},
				},
			},
		},
	}
	writeTestTripSW(t, dir, "default", trip)
	s := store.New(dir, "default")

	p := openmeteo.NewProvider(openmeteo.ProviderConfig{
		BaseURL:    "https://api.open-meteo.com",
		AQURL:      "https://air-quality-api.open-meteo.com",
		TimeoutSec: 30,
		Retries:    2,
		CacheDir:   t.TempDir(),
	})

	r := chi.NewRouter()
	r.Get("/api/trips/{id}/stages/weather", StagesWeatherHandler(s, p))

	req := httptest.NewRequest("GET", "/api/trips/test-integration-weather/stages/weather", nil)
	rec := httptest.NewRecorder()
	r.ServeHTTP(rec, req)

	if rec.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", rec.Code, rec.Body.String())
	}
	var resp model.StagesWeatherResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
		t.Fatalf("invalid JSON: %v", err)
	}
	result, ok := resp.Results["s1"]
	if !ok {
		t.Fatal("expected results to contain s1")
	}
	if result == nil {
		t.Fatal("expected non-null result for stage with waypoints")
	}
	if result.WeatherSummary == nil {
		t.Error("expected weather_summary != nil")
	}
	if result.Risk == nil {
		t.Error("expected risk != nil")
	} else {
		r := *result.Risk
		if r != "green" && r != "yellow" && r != "red" {
			t.Errorf("expected risk in {green,yellow,red}, got %q", r)
		}
	}
}

// =============================================================================
// Aggregation-Unit-Tests
// =============================================================================

// TestAggregateForecasts_EmptyPoints_ReturnsNil prueft:
// Leere Punkte-Liste liefert nil.
func TestAggregateForecasts_EmptyPoints_ReturnsNil(t *testing.T) {
	// GIVEN: Leere Forecast-Punkte-Liste
	// WHEN: aggregateForecasts("2026-05-25")
	// THEN: nil
	result := aggregateForecasts([]model.ForecastDataPoint{}, "2026-05-25")
	if result != nil {
		t.Errorf("expected nil for empty points, got %+v", result)
	}
}

// TestAggregateForecasts_FiltersByUTCDate prueft:
// Nur Punkte des Ziel-UTC-Tags werden aggregiert.
func TestAggregateForecasts_FiltersByUTCDate(t *testing.T) {
	// GIVEN: Punkte fuer 2026-05-25 und 2026-05-26
	// WHEN: aggregateForecasts("2026-05-25")
	// THEN: Nur 25.05.-Punkte einfliessen — TempMin=TempMax=15.0
	day1, _ := time.Parse(time.RFC3339, "2026-05-25T12:00:00+00:00")
	day2, _ := time.Parse(time.RFC3339, "2026-05-26T12:00:00+00:00")
	tempDay1 := 15.0
	tempDay2 := 25.0
	points := []model.ForecastDataPoint{
		{Time: model.UTCTime{Time: day1}, T2mC: &tempDay1},
		{Time: model.UTCTime{Time: day2}, T2mC: &tempDay2},
	}
	result := aggregateForecasts(points, "2026-05-25")
	if result == nil {
		t.Fatal("expected non-nil result for day1 points")
	}
	if result.TempMinC == nil || *result.TempMinC != 15.0 {
		t.Errorf("expected TempMinC=15.0, got %v", result.TempMinC)
	}
	if result.TempMaxC == nil || *result.TempMaxC != 15.0 {
		t.Errorf("expected TempMaxC=15.0 (single point), got %v", result.TempMaxC)
	}
}

// TestAggregateForecasts_FiltersByUTCDate_NoMatchReturnsNil prueft:
// Kein Datenpunkt passt zum Ziel-Datum → nil.
func TestAggregateForecasts_FiltersByUTCDate_NoMatchReturnsNil(t *testing.T) {
	// GIVEN: Punkte nur fuer 2026-05-26
	// WHEN: aggregateForecasts("2026-05-25")
	// THEN: nil
	day2, _ := time.Parse(time.RFC3339, "2026-05-26T12:00:00+00:00")
	temp := 20.0
	points := []model.ForecastDataPoint{
		{Time: model.UTCTime{Time: day2}, T2mC: &temp},
	}
	result := aggregateForecasts(points, "2026-05-25")
	if result != nil {
		t.Errorf("expected nil for no matching points, got %+v", result)
	}
}

// TestAggregateForecasts_ComputesMinMaxSum prueft:
// Mehrere Punkte desselben Tags: TempMin=MIN, TempMax=MAX, PrecipSum=SUM, WindMax=MAX.
func TestAggregateForecasts_ComputesMinMaxSum(t *testing.T) {
	// GIVEN: 3 Punkte am 2026-05-25 mit unterschiedlichen Werten
	// WHEN: aggregateForecasts("2026-05-25")
	// THEN: TempMin=8, TempMax=18, WindMax=45, PrecipSum=4.0
	t1, _ := time.Parse(time.RFC3339, "2026-05-25T06:00:00+00:00")
	t2, _ := time.Parse(time.RFC3339, "2026-05-25T12:00:00+00:00")
	t3, _ := time.Parse(time.RFC3339, "2026-05-25T18:00:00+00:00")
	temp1, temp2, temp3 := 8.0, 18.0, 12.0
	wind1, wind2, wind3 := 10.0, 45.0, 30.0
	precip1, precip2, precip3 := 0.0, 2.5, 1.5

	points := []model.ForecastDataPoint{
		{Time: model.UTCTime{Time: t1}, T2mC: &temp1, Wind10mKmh: &wind1, Precip1hMm: &precip1},
		{Time: model.UTCTime{Time: t2}, T2mC: &temp2, Wind10mKmh: &wind2, Precip1hMm: &precip2},
		{Time: model.UTCTime{Time: t3}, T2mC: &temp3, Wind10mKmh: &wind3, Precip1hMm: &precip3},
	}
	result := aggregateForecasts(points, "2026-05-25")
	if result == nil {
		t.Fatal("expected non-nil result")
	}
	if result.TempMinC == nil || *result.TempMinC != 8.0 {
		t.Errorf("expected TempMinC=8.0, got %v", result.TempMinC)
	}
	if result.TempMaxC == nil || *result.TempMaxC != 18.0 {
		t.Errorf("expected TempMaxC=18.0, got %v", result.TempMaxC)
	}
	if result.WindMaxKmh == nil || *result.WindMaxKmh != 45.0 {
		t.Errorf("expected WindMaxKmh=45.0, got %v", result.WindMaxKmh)
	}
	const wantPrecip = 4.0
	if result.PrecipSumMm == nil || *result.PrecipSumMm != wantPrecip {
		t.Errorf("expected PrecipSumMm=%.1f, got %v", wantPrecip, result.PrecipSumMm)
	}
}

// TestAggregateForecasts_ThunderLevelMax prueft:
// ThunderLevelMax = hoechster Wert (NONE < MED < HIGH).
func TestAggregateForecasts_ThunderLevelMax(t *testing.T) {
	// GIVEN: Punkte mit ThunderLevel NONE, MED, HIGH am selben Tag
	// WHEN: aggregateForecasts("2026-05-25")
	// THEN: ThunderLevelMax == ThunderHigh
	t1, _ := time.Parse(time.RFC3339, "2026-05-25T06:00:00+00:00")
	t2, _ := time.Parse(time.RFC3339, "2026-05-25T12:00:00+00:00")
	t3, _ := time.Parse(time.RFC3339, "2026-05-25T18:00:00+00:00")
	points := []model.ForecastDataPoint{
		{Time: model.UTCTime{Time: t1}, ThunderLevel: model.ThunderNone},
		{Time: model.UTCTime{Time: t2}, ThunderLevel: model.ThunderMed},
		{Time: model.UTCTime{Time: t3}, ThunderLevel: model.ThunderHigh},
	}
	result := aggregateForecasts(points, "2026-05-25")
	if result == nil {
		t.Fatal("expected non-nil result")
	}
	if result.ThunderLevelMax != model.ThunderHigh {
		t.Errorf("expected ThunderLevelMax=ThunderHigh, got %v", result.ThunderLevelMax)
	}
}
