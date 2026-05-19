// TDD RED — HTTP-Handler-Tests für POST /api/compare/run (Issue #250).
// Erwartet: FAIL (package compare does not exist) bis Engine implementiert ist.
//
// Ausführung:
//   go test ./internal/handler/... -run "TestCompareRun" -v
package handler

import (
	"encoding/json"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/henemm/gregor-api/internal/compare"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

func seedCompareLocation(t *testing.T, s *store.Store, id, name string, lat, lon float64, ele int) {
	t.Helper()
	loc := model.Location{
		ID: id, Name: name, Lat: lat, Lon: lon, ElevationM: &ele,
	}
	if err := s.SaveLocation(loc); err != nil {
		t.Fatalf("seedCompareLocation(%s): %v", id, err)
	}
}

// --- AC-1: Zwei valide Locations → Ranking --------------------------------

func TestCompareRunHandler_TwoLocations_ReturnsRanking(t *testing.T) {
	// GIVEN: Store mit zwei gespeicherten Locations, gültiges Datum + Profil
	// WHEN:  POST /api/compare/run
	// THEN:  rows hat 2 Einträge, rank 1+2, score 0–100
	s := newTestStore(t)
	seedCompareLocation(t, s, "loc-a", "Ort A", 47.0, 11.0, 500)
	seedCompareLocation(t, s, "loc-b", "Ort B", 46.5, 13.5, 800)

	engine := compare.New(s, nil)
	h := CompareRunHandler(engine)

	body := `{"location_ids":["loc-a","loc-b"],"date":"2026-06-15","profile":"ALLGEMEIN"}`
	req := httptest.NewRequest("POST", "/api/compare/run", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	var result compare.CompareResult
	if err := json.NewDecoder(w.Body).Decode(&result); err != nil {
		t.Fatalf("JSON-Decode fehlgeschlagen: %v", err)
	}
	if len(result.Rows) != 2 {
		t.Fatalf("erwartet 2 rows, got %d", len(result.Rows))
	}
	for _, row := range result.Rows {
		if row.Score < 0 || row.Score > 100 {
			t.Errorf("Score %d außerhalb [0,100]", row.Score)
		}
	}
	if result.Rows[0].Rank != 1 {
		t.Errorf("erste Row sollte rank 1 haben, got %d", result.Rows[0].Rank)
	}
}

// --- AC-4: Partial-Result bei nicht existenter Location ------------------

func TestCompareRunHandler_OneLocationMissing_PartialResult(t *testing.T) {
	// GIVEN: Store mit einer Location, zweite ID existiert nicht
	// WHEN:  POST /api/compare/run mit beiden IDs
	// THEN:  200 mit nur einer Row, kein 500
	s := newTestStore(t)
	seedCompareLocation(t, s, "loc-exists", "Existiert", 47.0, 11.0, 500)

	engine := compare.New(s, nil)
	h := CompareRunHandler(engine)

	body := `{"location_ids":["loc-exists","loc-ghost"],"date":"2026-06-15","profile":"ALLGEMEIN"}`
	req := httptest.NewRequest("POST", "/api/compare/run", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200 (partial), got %d: %s", w.Code, w.Body.String())
	}
	var result compare.CompareResult
	json.NewDecoder(w.Body).Decode(&result)
	if len(result.Rows) != 1 {
		t.Errorf("erwartet 1 Row (partial), got %d", len(result.Rows))
	}
}

// --- AC-5: Validierung — zu wenige Locations bzw. ungültiges Profil -------

func TestCompareRunHandler_TooFewLocations_Returns400(t *testing.T) {
	// GIVEN: Request mit nur einer Location-ID
	// WHEN:  POST /api/compare/run
	// THEN:  HTTP 400
	s := newTestStore(t)
	engine := compare.New(s, nil)
	h := CompareRunHandler(engine)

	body := `{"location_ids":["only-one"],"date":"2026-06-15","profile":"ALLGEMEIN"}`
	req := httptest.NewRequest("POST", "/api/compare/run", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 400 {
		t.Errorf("expected 400, got %d", w.Code)
	}
}

func TestCompareRunHandler_InvalidProfile_Returns400(t *testing.T) {
	// GIVEN: Request mit unbekanntem Profil-Wert
	// WHEN:  POST /api/compare/run
	// THEN:  HTTP 400
	s := newTestStore(t)
	engine := compare.New(s, nil)
	h := CompareRunHandler(engine)

	body := `{"location_ids":["a","b"],"date":"2026-06-15","profile":"INVALID_PROFILE"}`
	req := httptest.NewRequest("POST", "/api/compare/run", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 400 {
		t.Errorf("expected 400, got %d", w.Code)
	}
}

// --- AC-2: Cache-Hit-Verhalten -------------------------------------------

func TestCompareRunHandler_SecondRequest_ReturnsSameScore(t *testing.T) {
	// GIVEN: Gleicher Request zweimal mit gleichem Store
	// WHEN:  Beide Requests nacheinander gesendet
	// THEN:  Beide Responses geben identische scores zurück (Cache-Hit übt den Pfad aus)
	s := newTestStore(t)
	seedCompareLocation(t, s, "loc-x", "Ort X", 47.0, 11.0, 600)
	seedCompareLocation(t, s, "loc-y", "Ort Y", 47.5, 11.5, 700)

	engine := compare.New(s, nil)
	h := CompareRunHandler(engine)

	makeRequest := func() []compare.CompareRow {
		body := `{"location_ids":["loc-x","loc-y"],"date":"2026-07-01","profile":"ALLGEMEIN"}`
		req := httptest.NewRequest("POST", "/api/compare/run", strings.NewReader(body))
		req.Header.Set("Content-Type", "application/json")
		w := httptest.NewRecorder()
		h.ServeHTTP(w, req)
		if w.Code != 200 {
			t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
		}
		var result compare.CompareResult
		json.NewDecoder(w.Body).Decode(&result)
		return result.Rows
	}

	rows1 := makeRequest()
	rows2 := makeRequest()

	if len(rows1) != len(rows2) {
		t.Fatalf("row count mismatch: first=%d, second=%d", len(rows1), len(rows2))
	}
	for i := range rows1 {
		if rows1[i].Score != rows2[i].Score {
			t.Errorf("row %d: score mismatch first=%d second=%d", i, rows1[i].Score, rows2[i].Score)
		}
	}
}
