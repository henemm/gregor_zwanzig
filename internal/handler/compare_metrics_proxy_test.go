package handler

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

// TestCompareMetricsProxyHandlerPassthrough (Issue #1350 AC-5): der generische
// ProxyHandler(pythonURL, "/api/compare/metrics") reicht Status + Body vom
// Python-Core 1:1 durch — analog zum bestehenden /api/metrics-Proxy
// (TestProxyHandlerSuccess). Lokaler httptest.NewServer-Mock als
// PythonCoreURL, kein Live-Netz, kein echter Python-Core.
func TestCompareMetricsProxyHandlerPassthrough(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("/api/compare/metrics", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"metrics":[{"key":"snow_depth_cm","label":"Schneehöhe"}]}`))
	})
	py := httptest.NewServer(mux)
	defer py.Close()

	h := ProxyHandler(py.URL, "/api/compare/metrics")
	req := httptest.NewRequest("GET", "/api/compare/metrics", nil)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d", w.Code)
	}

	var body map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &body); err != nil {
		t.Fatalf("invalid JSON body: %v", err)
	}
	metrics, ok := body["metrics"].([]interface{})
	if !ok || len(metrics) != 1 {
		t.Fatalf("expected metrics array with 1 entry, got %v", body["metrics"])
	}
}
