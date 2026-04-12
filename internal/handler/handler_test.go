package handler

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/henemm/gregor-api/internal/store"
)

func startFakePython() *httptest.Server {
	mux := http.NewServeMux()

	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"status":"ok"}`))
	})

	mux.HandleFunc("/config", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"providers":["geosphere"]}`))
	})

	mux.HandleFunc("/forecast", func(w http.ResponseWriter, r *http.Request) {
		lat := r.URL.Query().Get("lat")
		if lat == "" {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(422)
			w.Write([]byte(`{"detail":"lat required"}`))
			return
		}
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"lat":"` + lat + `","data":["sunny"]}`))
	})

	return httptest.NewServer(mux)
}

// --- Proxy Handler Tests (migrated from cmd/gregor-api/) ---

func TestHealthHandlerPythonUp(t *testing.T) {
	py := startFakePython()
	defer py.Close()

	h := HealthHandler(py.URL)
	req := httptest.NewRequest("GET", "/api/health", nil)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

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
	if body["version"] == nil {
		t.Error("expected version to be set")
	}
}

func TestHealthHandlerPythonDown(t *testing.T) {
	h := HealthHandler("http://127.0.0.1:19999")
	req := httptest.NewRequest("GET", "/api/health", nil)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d", w.Code)
	}

	var body map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &body)

	if body["status"] != "degraded" {
		t.Errorf("expected degraded, got %v", body["status"])
	}
	if body["python_core"] != "unavailable" {
		t.Errorf("expected unavailable, got %v", body["python_core"])
	}
}

func TestProxyHandlerSuccess(t *testing.T) {
	py := startFakePython()
	defer py.Close()

	h := ProxyHandler(py.URL, "/config")
	req := httptest.NewRequest("GET", "/api/config", nil)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d", w.Code)
	}

	var body map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &body)

	if body["providers"] == nil {
		t.Error("expected providers in response")
	}
}

func TestProxyHandlerPythonDown(t *testing.T) {
	h := ProxyHandler("http://127.0.0.1:19999", "/config")
	req := httptest.NewRequest("GET", "/api/config", nil)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 503 {
		t.Fatalf("expected 503, got %d", w.Code)
	}
}

func TestProxyHandlerForwardsQueryParams(t *testing.T) {
	py := startFakePython()
	defer py.Close()

	h := ProxyHandler(py.URL, "/forecast")
	req := httptest.NewRequest("GET", "/api/forecast?lat=47.27&lon=11.40", nil)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d", w.Code)
	}

	var body map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &body)

	if body["lat"] != "47.27" {
		t.Errorf("expected lat 47.27, got %v", body["lat"])
	}
}

// --- Location Handler Tests ---

func TestLocationsHandler(t *testing.T) {
	// GIVEN: Store pointing to real data
	s := store.New("../../data", "default")

	// WHEN: Calling GET /api/locations
	h := LocationsHandler(s)
	req := httptest.NewRequest("GET", "/api/locations", nil)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	// THEN: Returns 200 with JSON array
	if w.Code != 200 {
		t.Fatalf("expected 200, got %d", w.Code)
	}

	var locations []map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &locations); err != nil {
		t.Fatalf("expected JSON array, got error: %v", err)
	}
	if len(locations) == 0 {
		t.Error("expected at least one location")
	}

	// Verify Content-Type
	ct := w.Header().Get("Content-Type")
	if ct != "application/json" {
		t.Errorf("expected Content-Type application/json, got %s", ct)
	}
}
