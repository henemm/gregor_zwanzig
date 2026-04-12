package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/go-chi/chi/v5"
)

// newTestRouter creates a chi router with the app's handlers
// wired to a given python core URL.
func newTestRouter(pythonURL string) *chi.Mux {
	return setupRouter(pythonURL)
}

// startFakePython spins up an httptest.Server that mimics the Python FastAPI endpoints.
func startFakePython() *httptest.Server {
	mux := http.NewServeMux()

	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"status":"ok"}`))
	})

	mux.HandleFunc("/config", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"providers":["geosphere","open_meteo"],"version":"test"}`))
	})

	mux.HandleFunc("/forecast", func(w http.ResponseWriter, r *http.Request) {
		lat := r.URL.Query().Get("lat")
		lon := r.URL.Query().Get("lon")
		hours := r.URL.Query().Get("hours")

		if lat == "" || lon == "" {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(422)
			w.Write([]byte(`{"detail":"lat and lon required"}`))
			return
		}

		w.Header().Set("Content-Type", "application/json")
		resp := map[string]interface{}{
			"lat":   lat,
			"lon":   lon,
			"hours": hours,
			"data":  []string{"sunny"},
		}
		json.NewEncoder(w).Encode(resp)
	})

	return httptest.NewServer(mux)
}

func TestHealthWithPythonUp(t *testing.T) {
	py := startFakePython()
	defer py.Close()

	r := newTestRouter(py.URL)
	req := httptest.NewRequest("GET", "/api/health", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d", w.Code)
	}

	var body map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &body)

	if body["status"] != "ok" {
		t.Errorf("expected status ok, got %v", body["status"])
	}
	if body["python_core"] != "ok" {
		t.Errorf("expected python_core ok, got %v", body["python_core"])
	}
	if body["version"] == nil || body["version"] == "" {
		t.Error("expected version to be set")
	}
}

func TestHealthWithPythonDown(t *testing.T) {
	// Point to a URL that won't respond
	r := newTestRouter("http://127.0.0.1:19999")
	req := httptest.NewRequest("GET", "/api/health", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200 even when python down, got %d", w.Code)
	}

	var body map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &body)

	if body["status"] != "degraded" {
		t.Errorf("expected status degraded, got %v", body["status"])
	}
	if body["python_core"] != "unavailable" {
		t.Errorf("expected python_core unavailable, got %v", body["python_core"])
	}
}

func TestConfigProxy(t *testing.T) {
	py := startFakePython()
	defer py.Close()

	r := newTestRouter(py.URL)
	req := httptest.NewRequest("GET", "/api/config", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d", w.Code)
	}

	var body map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &body)

	if body["providers"] == nil {
		t.Error("expected providers in config response")
	}
}

func TestConfigProxyPythonDown(t *testing.T) {
	r := newTestRouter("http://127.0.0.1:19999")
	req := httptest.NewRequest("GET", "/api/config", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 503 {
		t.Fatalf("expected 503, got %d", w.Code)
	}

	var body map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &body)

	if body["error"] != "core_unavailable" {
		t.Errorf("expected error core_unavailable, got %v", body["error"])
	}
}

func TestForecastProxy(t *testing.T) {
	py := startFakePython()
	defer py.Close()

	r := newTestRouter(py.URL)
	req := httptest.NewRequest("GET", "/api/forecast?lat=47.27&lon=11.40&hours=24", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d", w.Code)
	}

	var body map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &body)

	if body["lat"] != "47.27" {
		t.Errorf("expected lat 47.27, got %v", body["lat"])
	}
	if body["lon"] != "11.40" {
		t.Errorf("expected lon 11.40, got %v", body["lon"])
	}
}

func TestForecastProxyValidationError(t *testing.T) {
	py := startFakePython()
	defer py.Close()

	r := newTestRouter(py.URL)
	// Missing lat/lon → Python returns 422
	req := httptest.NewRequest("GET", "/api/forecast", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 422 {
		t.Fatalf("expected 422, got %d", w.Code)
	}
}

func TestForecastProxyPythonDown(t *testing.T) {
	r := newTestRouter("http://127.0.0.1:19999")
	req := httptest.NewRequest("GET", "/api/forecast?lat=47.27&lon=11.40&hours=24", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 503 {
		t.Fatalf("expected 503, got %d", w.Code)
	}

	var body map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &body)

	if body["error"] != "core_unavailable" {
		t.Errorf("expected error core_unavailable, got %v", body["error"])
	}
}
