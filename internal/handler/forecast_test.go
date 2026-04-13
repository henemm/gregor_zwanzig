package handler

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/henemm/gregor-api/internal/provider/openmeteo"
)

// =============================================================================
// Tests 14-16: Forecast Handler
// =============================================================================

func TestForecastHandler_ValidRequest_Returns200(t *testing.T) {
	if testing.Short() {
		t.Skip("skipping integration test in short mode")
	}
	// GIVEN: ForecastHandler mit echtem Provider
	// WHEN: GET /api/forecast?lat=39.7&lon=3.0&hours=24
	// THEN: 200 OK mit gueltigem JSON
	p := openmeteo.NewProvider(openmeteo.ProviderConfig{
		BaseURL:    "https://api.open-meteo.com",
		AQURL:      "https://air-quality-api.open-meteo.com",
		TimeoutSec: 30,
		Retries:    5,
		CacheDir:   t.TempDir(),
	})
	h := ForecastHandler(p)

	req := httptest.NewRequest("GET", "/api/forecast?lat=39.7&lon=3.0&hours=24", nil)
	rec := httptest.NewRecorder()

	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected 200, got %d: %s", rec.Code, rec.Body.String())
	}

	var result map[string]interface{}
	if err := json.NewDecoder(rec.Body).Decode(&result); err != nil {
		t.Fatalf("invalid JSON response: %v", err)
	}
	if _, ok := result["meta"]; !ok {
		t.Error("expected 'meta' key in response")
	}
	if _, ok := result["data"]; !ok {
		t.Error("expected 'data' key in response")
	}
	if _, ok := result["timezone"]; !ok {
		t.Error("expected 'timezone' key in response")
	}
}

func TestForecastHandler_MissingLat_Returns400(t *testing.T) {
	// GIVEN: ForecastHandler
	// WHEN: GET /api/forecast?lon=3.0 (lat fehlt)
	// THEN: 400 mit error=invalid_params
	h := ForecastHandler(nil)

	req := httptest.NewRequest("GET", "/api/forecast?lon=3.0", nil)
	rec := httptest.NewRecorder()

	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d", rec.Code)
	}

	var result map[string]interface{}
	if err := json.NewDecoder(rec.Body).Decode(&result); err != nil {
		t.Fatalf("invalid JSON response: %v", err)
	}
	if result["error"] != "invalid_params" {
		t.Errorf("expected error='invalid_params', got '%v'", result["error"])
	}
}

func TestForecastHandler_InvalidLat_Returns400(t *testing.T) {
	// GIVEN: ForecastHandler
	// WHEN: GET /api/forecast?lat=999&lon=3.0 (lat ausserhalb [-90,90])
	// THEN: 400 mit error=invalid_params
	h := ForecastHandler(nil)

	req := httptest.NewRequest("GET", "/api/forecast?lat=999&lon=3.0", nil)
	rec := httptest.NewRecorder()

	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d", rec.Code)
	}

	var result map[string]interface{}
	if err := json.NewDecoder(rec.Body).Decode(&result); err != nil {
		t.Fatalf("invalid JSON response: %v", err)
	}
	if result["error"] != "invalid_params" {
		t.Errorf("expected error='invalid_params', got '%v'", result["error"])
	}
}
