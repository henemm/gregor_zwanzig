package handler

// Issue #202: Trip.Region — optionales Freitext-Feld.
// TDD RED — Tests fallen, bis Region im Struct + DTO + Merge-Block implementiert ist.
//
// Spec: docs/specs/modules/issue_202_region_feld.md
// AC-1: Region nach POST wieder via GET abrufbar.
// AC-3: Region bleibt nach PUT ohne region-Feld erhalten (Read-Modify-Write).

import (
	"encoding/json"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/go-chi/chi/v5"
	"github.com/henemm/gregor-api/internal/model"
)

// AC-1: POST mit "region":"Korsika" → gespeicherte Region wieder lesbar.
func TestTripRegion_CreateAndRead(t *testing.T) {
	s := newTestStore(t)

	body := `{"id":"region-create","name":"Korsika-Trip","region":"Korsika","stages":[` +
		`{"id":"S1","name":"Tag 1","date":"2026-05-01","waypoints":[` +
		`{"id":"W1","name":"Start","lat":42.0,"lon":9.0,"elevation_m":100}` +
		`]}]}`

	h := CreateTripHandler(s)
	req := httptest.NewRequest("POST", "/api/trips", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 201 {
		t.Fatalf("expected 201, got %d: %s", w.Code, w.Body.String())
	}

	// Direkt aus Store lesen (Persistenz-Check).
	got, err := s.LoadTrip("region-create")
	if err != nil || got == nil {
		t.Fatalf("trip nicht gefunden: %v", err)
	}
	if got.Region != "Korsika" {
		t.Errorf("AC-1 FAIL: got.Region = %q, want %q", got.Region, "Korsika")
	}

	// Auch via HTTP-GET pruefen, dass das Feld in der JSON-Antwort steht.
	r := chi.NewRouter()
	r.Get("/api/trips/{id}", TripHandler(s))
	req2 := httptest.NewRequest("GET", "/api/trips/region-create", nil)
	w2 := httptest.NewRecorder()
	r.ServeHTTP(w2, req2)

	if w2.Code != 200 {
		t.Fatalf("expected 200, got %d", w2.Code)
	}
	var resp map[string]interface{}
	if err := json.Unmarshal(w2.Body.Bytes(), &resp); err != nil {
		t.Fatalf("invalid JSON: %v", err)
	}
	if resp["region"] != "Korsika" {
		t.Errorf("AC-1 FAIL: JSON response region = %v, want %q", resp["region"], "Korsika")
	}
}

// AC-3: Trip mit region:"Korsika" + PUT ohne region-Feld → region bleibt erhalten.
func TestTripRegion_PreservedOnUpdate(t *testing.T) {
	s := newTestStore(t)

	// Seed Trip mit Region direkt im Store.
	seed := model.Trip{
		ID: "region-keep", Name: "Korsika-Trip", Region: "Korsika",
		Stages: []model.Stage{{ID: "S1", Name: "Tag 1", Date: "2026-05-01",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "Start", Lat: 42.0, Lon: 9.0, ElevationM: 100}},
		}},
	}
	if err := s.SaveTrip(&seed); err != nil {
		t.Fatalf("seed failed: %v", err)
	}

	// PUT mit nur name+stages — kein region-Feld im Body.
	body := `{"id":"region-keep","name":"Korsika-Renamed","stages":[` +
		`{"id":"S1","name":"Tag 1","date":"2026-05-01","waypoints":[` +
		`{"id":"W1","name":"Start","lat":42.0,"lon":9.0,"elevation_m":100}` +
		`]}]}`

	r := chi.NewRouter()
	r.Put("/api/trips/{id}", UpdateTripHandler(s))
	req := httptest.NewRequest("PUT", "/api/trips/region-keep", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	got, err := s.LoadTrip("region-keep")
	if err != nil || got == nil {
		t.Fatalf("trip nicht gefunden: %v", err)
	}
	if got.Region != "Korsika" {
		t.Errorf("AC-3 FAIL: Region nach PUT ohne region-Feld = %q, want %q (Read-Modify-Write greift nicht)",
			got.Region, "Korsika")
	}
	if got.Name != "Korsika-Renamed" {
		t.Errorf("Name wurde nicht aktualisiert: got %q", got.Name)
	}
}

// Bonus-Test: PUT mit explizitem region-Wert ersetzt das Feld.
func TestTripRegion_UpdateReplacesWhenSent(t *testing.T) {
	s := newTestStore(t)

	seed := model.Trip{
		ID: "region-replace", Name: "Trip", Region: "Korsika",
		Stages: []model.Stage{{ID: "S1", Name: "Tag 1", Date: "2026-05-01",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "Start", Lat: 42.0, Lon: 9.0, ElevationM: 100}},
		}},
	}
	if err := s.SaveTrip(&seed); err != nil {
		t.Fatalf("seed failed: %v", err)
	}

	body := `{"region":"Mallorca"}`
	r := chi.NewRouter()
	r.Put("/api/trips/{id}", UpdateTripHandler(s))
	req := httptest.NewRequest("PUT", "/api/trips/region-replace", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	got, err := s.LoadTrip("region-replace")
	if err != nil || got == nil {
		t.Fatalf("trip nicht gefunden: %v", err)
	}
	if got.Region != "Mallorca" {
		t.Errorf("Region nach PUT mit region:\"Mallorca\" = %q, want %q", got.Region, "Mallorca")
	}
}
