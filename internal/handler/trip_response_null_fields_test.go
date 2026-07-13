package handler

// Issue #1244 Fix-Loop (F001/F002 — Adversary BROKEN-Verdict): die bisherige
// Nil-Coercion in store.SaveTrip mutierte nur die lokale Kopie (Value-
// Empfänger), so dass die HTTP-Response von POST/PUT weiterhin
// "corridors":null/"stages":null enthielt, obwohl die Datei auf Platte
// bereits korrekt war. Und der Lesepfad (LoadTrip) heilte nur AlertRules,
// nicht Corridors/Stages — GET auf eine unmigrierte Legacy-Datei lieferte
// deshalb ebenfalls null zurück (Frontend-Crash-Pfad, siehe
// alertPreviewHelpers.ts).
//
// Diese Tests prüfen den tatsächlichen HTTP-Response-Body, nicht nur die
// geschriebene Datei — genau die Lücke, die die bisherigen Datei-Tests
// (trip_nil_coercion_test.go) nicht abgedeckt haben.
//
// Spec: docs/specs/modules/fix_1244_null_list_fields.md
// Keine Mocks — echte httptest-Handler, echte Dateien via t.TempDir().

import (
	"encoding/json"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/go-chi/chi/v5"
)

// TestCreateTripHandler_ResponseHasEmptyListsNotNull covers F001: POST
// /api/trips without corridors/stages in the body must not echo back
// "corridors":null/"stages":null/"alert_rules":null in the response.
func TestCreateTripHandler_ResponseHasEmptyListsNotNull(t *testing.T) {
	s := newTestStore(t)

	body := `{"id":"probe-trip-2","name":"Probe Trip 2"}`

	h := CreateTripHandler(s)
	req := httptest.NewRequest("POST", "/api/trips", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 201 {
		t.Fatalf("expected 201, got %d: %s", w.Code, w.Body.String())
	}

	raw := w.Body.String()
	if strings.Contains(raw, `"corridors":null`) {
		t.Errorf("F001: response enthält \"corridors\":null, war: %s", raw)
	}
	if strings.Contains(raw, `"stages":null`) {
		t.Errorf("F001: response enthält \"stages\":null, war: %s", raw)
	}
	if strings.Contains(raw, `"alert_rules":null`) {
		t.Errorf("F001: response enthält \"alert_rules\":null, war: %s", raw)
	}

	var resp map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if _, ok := resp["corridors"].([]interface{}); !ok {
		t.Errorf("F001: response.corridors ist keine Liste, war: %v", resp["corridors"])
	}
	if _, ok := resp["stages"].([]interface{}); !ok {
		t.Errorf("F001: response.stages ist keine Liste, war: %v", resp["stages"])
	}
}

// TestUpdateTripHandler_MinimalBodyOnLegacyFile_ResponseHasEmptyLists covers
// F001 for PUT: a legacy file on disk with "corridors": null gets loaded,
// updated with a minimal body, and the response must not carry null back.
func TestUpdateTripHandler_MinimalBodyOnLegacyFile_ResponseHasEmptyLists(t *testing.T) {
	s := newTestStore(t)
	writeLegacyTripFile(t, s, "legacy-put", `{
		"id": "legacy-put",
		"name": "Legacy Put Trip",
		"stages": null,
		"corridors": null,
		"alert_rules": null
	}`)

	body := `{"id":"legacy-put","name":"Legacy Put Trip Renamed","stages":[{"id":"S1","name":"D1","date":"2026-05-01","waypoints":[{"id":"W1","name":"P","lat":47.0,"lon":11.0,"elevation_m":500}]}]}`

	r := chi.NewRouter()
	r.Put("/api/trips/{id}", UpdateTripHandler(s))
	req := httptest.NewRequest("PUT", "/api/trips/legacy-put", strings.NewReader(body))
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	raw := w.Body.String()
	if strings.Contains(raw, `"corridors":null`) {
		t.Errorf("F001: PUT-Response enthält \"corridors\":null, war: %s", raw)
	}
}

// TestTripHandler_GetOnUnmigratedLegacyFile_ResponseHasEmptyLists covers
// F002: GET /api/trips/{id} on a not-yet-migrated legacy file with
// "corridors": null, "stages": null must return empty lists, not null —
// otherwise the frontend crashes on stages[0]?.id (alertPreviewHelpers.ts).
func TestTripHandler_GetOnUnmigratedLegacyFile_ResponseHasEmptyLists(t *testing.T) {
	s := newTestStore(t)
	writeLegacyTripFile(t, s, "legacy-get", `{
		"id": "legacy-get",
		"name": "Legacy Get Trip",
		"stages": null,
		"corridors": null,
		"alert_rules": null
	}`)

	r := chi.NewRouter()
	r.Get("/api/trips/{id}", TripHandler(s))
	req := httptest.NewRequest("GET", "/api/trips/legacy-get", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	raw := w.Body.String()
	if strings.Contains(raw, `"corridors":null`) {
		t.Errorf("F002: GET-Response enthält \"corridors\":null, war: %s", raw)
	}
	if strings.Contains(raw, `"stages":null`) {
		t.Errorf("F002: GET-Response enthält \"stages\":null, war: %s", raw)
	}

	var resp map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if _, ok := resp["stages"].([]interface{}); !ok {
		t.Errorf("F002: response.stages ist keine Liste, war: %v", resp["stages"])
	}
	if _, ok := resp["corridors"].([]interface{}); !ok {
		t.Errorf("F002: response.corridors ist keine Liste, war: %v", resp["corridors"])
	}
}

// writeLegacyTripFile writes a raw JSON file directly to the trips dir,
// bypassing SaveTrip entirely — simulates a trip persisted before this fix
// (or before any coercion existed at all).
func writeLegacyTripFile(t *testing.T, s interface{ TripsDir() string }, id, rawJSON string) {
	t.Helper()
	dir := s.TripsDir()
	if err := os.MkdirAll(dir, 0755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	if err := os.WriteFile(filepath.Join(dir, id+".json"), []byte(rawJSON), 0644); err != nil {
		t.Fatalf("write legacy file: %v", err)
	}
}
