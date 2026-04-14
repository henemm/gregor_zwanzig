package handler

import (
	"bytes"
	"encoding/json"
	"io"
	"mime/multipart"
	"net/http"
	"net/http/httptest"
	"testing"
)

// startFakeGpxPython starts a fake Python backend that handles POST /api/gpx/parse.
func startFakeGpxPython() *httptest.Server {
	mux := http.NewServeMux()

	mux.HandleFunc("/api/gpx/parse", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			w.WriteHeader(405)
			return
		}

		// Check Content-Type contains multipart
		ct := r.Header.Get("Content-Type")
		if ct == "" {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(400)
			w.Write([]byte(`{"detail":"no content-type"}`))
			return
		}

		// Check query params are forwarded
		stageDate := r.URL.Query().Get("stage_date")

		resp := map[string]interface{}{
			"name": "Test Stage",
			"date": "2026-04-14",
			"waypoints": []map[string]interface{}{
				{
					"id":           "G1",
					"name":         "Gipfel",
					"lat":          39.752,
					"lon":          2.785,
					"elevation_m":  1064,
					"time_window":  "08:00-10:00",
				},
			},
		}
		if stageDate != "" {
			resp["date"] = stageDate
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(resp)
	})

	return httptest.NewServer(mux)
}

func TestGpxProxyHandlerSuccess(t *testing.T) {
	py := startFakeGpxPython()
	defer py.Close()

	h := GpxProxyHandler(py.URL)

	// Build multipart request
	var body bytes.Buffer
	writer := multipart.NewWriter(&body)
	part, err := writer.CreateFormFile("file", "test.gpx")
	if err != nil {
		t.Fatal(err)
	}
	part.Write([]byte(`<?xml version="1.0"?><gpx><trk><name>Test</name></trk></gpx>`))
	writer.Close()

	req := httptest.NewRequest("POST", "/api/gpx/parse", &body)
	req.Header.Set("Content-Type", writer.FormDataContentType())
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	var result map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &result); err != nil {
		t.Fatalf("expected valid JSON, got error: %v", err)
	}

	if result["name"] == nil {
		t.Error("expected name in response")
	}
	if result["waypoints"] == nil {
		t.Error("expected waypoints in response")
	}
}

func TestGpxProxyHandlerForwardsQueryParams(t *testing.T) {
	py := startFakeGpxPython()
	defer py.Close()

	h := GpxProxyHandler(py.URL)

	var body bytes.Buffer
	writer := multipart.NewWriter(&body)
	part, _ := writer.CreateFormFile("file", "test.gpx")
	part.Write([]byte(`<?xml version="1.0"?><gpx><trk><name>Test</name></trk></gpx>`))
	writer.Close()

	req := httptest.NewRequest("POST", "/api/gpx/parse?stage_date=2026-06-15&start_hour=7", &body)
	req.Header.Set("Content-Type", writer.FormDataContentType())
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d", w.Code)
	}

	var result map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &result)

	if result["date"] != "2026-06-15" {
		t.Errorf("expected date 2026-06-15, got %v", result["date"])
	}
}

func TestGpxProxyHandlerPythonDown(t *testing.T) {
	h := GpxProxyHandler("http://127.0.0.1:19999")

	var body bytes.Buffer
	writer := multipart.NewWriter(&body)
	part, _ := writer.CreateFormFile("file", "test.gpx")
	part.Write([]byte(`<gpx/>`))
	writer.Close()

	req := httptest.NewRequest("POST", "/api/gpx/parse", &body)
	req.Header.Set("Content-Type", writer.FormDataContentType())
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 503 {
		t.Fatalf("expected 503, got %d", w.Code)
	}

	var result map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &result)
	if result["error"] != "core_unavailable" {
		t.Errorf("expected error core_unavailable, got %v", result["error"])
	}
}

func TestGpxProxyHandlerContentTypeForwarded(t *testing.T) {
	// Verify the Content-Type header (with multipart boundary) is forwarded to Python
	var receivedCT string
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		receivedCT = r.Header.Get("Content-Type")
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"name":"test","date":"2026-01-01","waypoints":[]}`))
	}))
	defer ts.Close()

	h := GpxProxyHandler(ts.URL)

	var body bytes.Buffer
	writer := multipart.NewWriter(&body)
	part, _ := writer.CreateFormFile("file", "test.gpx")
	part.Write([]byte(`<gpx/>`))
	writer.Close()

	expectedCT := writer.FormDataContentType()
	req := httptest.NewRequest("POST", "/api/gpx/parse", &body)
	req.Header.Set("Content-Type", expectedCT)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if receivedCT != expectedCT {
		t.Errorf("Content-Type not forwarded.\nExpected: %s\nGot:      %s", expectedCT, receivedCT)
	}

	// Suppress unused import
	_ = io.Discard
}
