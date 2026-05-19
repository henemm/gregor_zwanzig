package handler

import (
	"encoding/json"
	"net/http/httptest"
	"strings"
	"testing"
)

// AC-2: Dezimalkoordinaten über HTTP-Endpoint auflösen
func TestResolveHandlerDecimalCoordinates(t *testing.T) {
	// GIVEN: Gültiger POST-Body mit Dezimalkoordinaten
	body := `{"input": "47.0789, 11.6856"}`

	h := ResolveLocationHandler()
	req := httptest.NewRequest("POST", "/api/locations/resolve", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	// THEN: HTTP 200 mit lat/lon/timezone/source_type
	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	var resp map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("expected valid JSON, got error: %v", err)
	}
	if resp["lat"] == nil {
		t.Error("expected lat in response")
	}
	if resp["lon"] == nil {
		t.Error("expected lon in response")
	}
	if resp["source_type"] != "decimal" {
		t.Errorf("expected source_type 'decimal', got %v", resp["source_type"])
	}
	if resp["timezone"] == nil || resp["timezone"] == "" {
		t.Error("expected non-empty timezone in response")
	}
}

// AC-3: Unbekanntes Format → HTTP 422
func TestResolveHandlerUnknownFormat(t *testing.T) {
	// GIVEN: Eingabe die keinem Format entspricht
	body := `{"input": "Gasthof Zum Löwen"}`

	h := ResolveLocationHandler()
	req := httptest.NewRequest("POST", "/api/locations/resolve", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	// THEN: HTTP 422 mit code="unknown_format"
	if w.Code != 422 {
		t.Fatalf("expected 422, got %d: %s", w.Code, w.Body.String())
	}

	var resp map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &resp)
	if resp["code"] != "unknown_format" {
		t.Errorf("expected code 'unknown_format', got %v", resp["code"])
	}
	if resp["message"] == nil || resp["message"] == "" {
		t.Error("expected non-empty message in error response")
	}
}

// AC-4: Komoot Tour-URL → HTTP 422 "unsupported_url"
func TestResolveHandlerKomootTourUnsupported(t *testing.T) {
	body := `{"input": "https://www.komoot.com/de-de/tour/12345"}`

	h := ResolveLocationHandler()
	req := httptest.NewRequest("POST", "/api/locations/resolve", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	// THEN: HTTP 422 mit code="unsupported_url"
	if w.Code != 422 {
		t.Fatalf("expected 422, got %d: %s", w.Code, w.Body.String())
	}

	var resp map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &resp)
	if resp["code"] != "unsupported_url" {
		t.Errorf("expected code 'unsupported_url', got %v", resp["code"])
	}
}

// AC-6: Fehlendes input-Feld → HTTP 400
func TestResolveHandlerMissingInput(t *testing.T) {
	// GIVEN: POST ohne input-Feld
	body := `{}`

	h := ResolveLocationHandler()
	req := httptest.NewRequest("POST", "/api/locations/resolve", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	// THEN: HTTP 400
	if w.Code != 400 {
		t.Fatalf("expected 400, got %d: %s", w.Code, w.Body.String())
	}
}

// AC-6: Leerer input-String → HTTP 400
func TestResolveHandlerEmptyInput(t *testing.T) {
	body := `{"input": ""}`

	h := ResolveLocationHandler()
	req := httptest.NewRequest("POST", "/api/locations/resolve", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 400 {
		t.Fatalf("expected 400, got %d: %s", w.Code, w.Body.String())
	}
}

// AC-6: Kein Body → HTTP 400
func TestResolveHandlerNoBody(t *testing.T) {
	h := ResolveLocationHandler()
	req := httptest.NewRequest("POST", "/api/locations/resolve", nil)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 400 {
		t.Fatalf("expected 400, got %d", w.Code)
	}
}

// AC-5: DMS-Koordinaten über HTTP-Endpoint
func TestResolveHandlerDMSCoordinates(t *testing.T) {
	body := `{"input": "47°04'44.0\"N 11°41'08.2\"E"}`

	h := ResolveLocationHandler()
	req := httptest.NewRequest("POST", "/api/locations/resolve", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	var resp map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &resp)
	if resp["source_type"] != "dms" {
		t.Errorf("expected source_type 'dms', got %v", resp["source_type"])
	}
}

// AC-1: Komoot Highlight über HTTP-Endpoint (echter API-Call)
func TestResolveHandlerKomootHighlight(t *testing.T) {
	// Highlight 126361 = Gavia Pass (verifiziert erreichbar)
	body := `{"input": "https://www.komoot.com/de-de/highlight/126361"}`

	h := ResolveLocationHandler()
	req := httptest.NewRequest("POST", "/api/locations/resolve", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	var resp map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &resp)
	if resp["lat"] == nil {
		t.Error("expected lat in response")
	}
	if resp["source_type"] != "komoot" {
		t.Errorf("expected source_type 'komoot', got %v", resp["source_type"])
	}
	if resp["timezone"] == nil || resp["timezone"] == "" {
		t.Error("expected timezone in response")
	}
}

// Content-Type Header wird korrekt gesetzt
func TestResolveHandlerContentType(t *testing.T) {
	body := `{"input": "47.0, 11.0"}`

	h := ResolveLocationHandler()
	req := httptest.NewRequest("POST", "/api/locations/resolve", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	ct := w.Header().Get("Content-Type")
	if ct != "application/json" {
		t.Errorf("expected Content-Type application/json, got %q", ct)
	}
}
