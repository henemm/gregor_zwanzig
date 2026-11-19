package handler

import (
	"encoding/json"
	"net/http/httptest"
	"strings"
	"testing"
)

// AC-2: Dezimalkoordinaten über HTTP-Endpoint auflösen
func TestResolveHandlerDecimalCoordinates(t *testing.T) {
	fx := hoehenDienstAuf(t, 1234.6)
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
	// AC-1 (#3158): Hoehe kommt aus dem echten Nachschlag-Pfad gegen den
	// lokalen Open-Elevation-Nachbau, gerundet 1234.6 -> 1235.
	pruefeHoeheUndKoordinaten(t, resp, fx, "47.078900,11.685600")
}

// pruefeHoeheUndKoordinaten: die Antwort traegt die gerundete Fixture-Hoehe,
// und der Fixture-Server hat genau eine Abfrage mit den erwarteten
// Koordinaten erhalten (Issue #3158).
func pruefeHoeheUndKoordinaten(t *testing.T, resp map[string]interface{}, fx *hoehenFixture, locations string) {
	t.Helper()
	if got, ok := resp["elevation_m"].(float64); !ok || got != 1235 {
		t.Errorf("expected elevation_m 1235 (gerundeter Fixture-Wert 1234.6), got %v", resp["elevation_m"])
	}
	angekommen := fx.locations()
	if len(angekommen) != 1 || angekommen[0] != locations {
		t.Errorf("Fixture muss genau die Abfrage locations=%s erhalten, bekam %v", locations, angekommen)
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
	fx := hoehenDienstAuf(t, 1234.6)
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
	// AC-2 (#3158): 47 Grad 04'44.0" = 47.078889, 11 Grad 41'08.2" = 11.685611
	pruefeHoeheUndKoordinaten(t, resp, fx, "47.078889,11.685611")
}

// Content-Type Header wird korrekt gesetzt
func TestResolveHandlerContentType(t *testing.T) {
	fx := hoehenDienstAuf(t, 1234.6)
	body := `{"input": "47.0, 11.0"}`

	h := ResolveLocationHandler()
	req := httptest.NewRequest("POST", "/api/locations/resolve", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	ct := w.Header().Get("Content-Type")
	if ct != "application/json" {
		t.Errorf("expected Content-Type application/json, got %q", ct)
	}

	// AC-2 (#3158): auch ohne Content-Type im Request kommt die Hoehe aus dem Fixture.
	var resp map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("expected valid JSON, got error: %v", err)
	}
	pruefeHoeheUndKoordinaten(t, resp, fx, "47.000000,11.000000")
}
