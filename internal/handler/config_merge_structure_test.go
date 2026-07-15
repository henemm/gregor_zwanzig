package handler

// Issue #1159 — Config-Merge-Helfer: Blind-Replace-Klasse konsolidieren
// (BUG-DATALOSS-GR221, 6. Wiederholung: #102 -> #1082 -> #1103 -> #1129 ->
// #1151 -> #1159).
//
// Spec: docs/specs/modules/config_merge_helper.md
//
// Diese Datei deckt AC-1 bis AC-3 und AC-7 ab:
//   - mergeConfigMap Helfer-Unit-Tests (AC-1, AC-2, Overwrite+Preserve)
//   - table-driven Struktur-Test ueber die drei echten HTTP-Handler
//     (Trip, Location, ComparePreset), jeweils mit eigenem Store-Pfad
//     (Pointer/Value/Slice) — der Location-Fall ist der Bug-Repro fuer den
//     aktiven Datenverlust (AC-3), rot vor dem Fix in weather_config.go:132.
//
// KEINE Mocks — echte httptest-Handler gegen echten (temp-dir-basierten) Store.

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/henemm/gregor-api/internal/model"
)

// ============================================================================
// Helfer-Unit-Tests
// ============================================================================

// TestMergeConfigMap_NilSrcReturnsDstUnchanged deckt AC-1 ab: src==nil gibt
// dst unveraendert zurueck, egal ob dst selbst nil oder gefuellt ist.
func TestMergeConfigMap_NilSrcReturnsDstUnchanged(t *testing.T) {
	cases := []struct {
		name string
		dst  map[string]interface{}
	}{
		{name: "dst gefuellt", dst: map[string]interface{}{"a": 1}},
		{name: "dst nil", dst: nil},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got := mergeConfigMap(tc.dst, nil)
			if len(got) != len(tc.dst) {
				t.Fatalf("expected dst unchanged (len %d), got len %d: %v", len(tc.dst), len(got), got)
			}
			for k, v := range tc.dst {
				if got[k] != v {
					t.Errorf("expected dst[%q]=%v preserved, got %v", k, v, got[k])
				}
			}
		})
	}
}

// TestMergeConfigMap_NilDstInitializes deckt AC-2 ab: dst==nil mit gefuellter
// src erzeugt eine neue Map mit exakt den src-Keys, ohne dass der Aufrufer
// vorher selbst initialisieren muss.
func TestMergeConfigMap_NilDstInitializes(t *testing.T) {
	src := map[string]interface{}{"metrics": []interface{}{"wind", "temperature"}}
	got := mergeConfigMap(nil, src)
	if got == nil {
		t.Fatal("expected non-nil map when dst=nil and src is filled")
	}
	if len(got) != 1 {
		t.Fatalf("expected exactly 1 key from src, got %d: %v", len(got), got)
	}
	if _, ok := got["metrics"]; !ok {
		t.Errorf("expected 'metrics' key from src, got %v", got)
	}
}

// TestMergeConfigMap_OverwritesAndPreserves prueft ueberlappende + disjunkte
// Keys zwischen dst/src in einem Aufruf: Overwrite + Preserve gemeinsam.
func TestMergeConfigMap_OverwritesAndPreserves(t *testing.T) {
	dst := map[string]interface{}{
		"theme":  "compact",
		"region": "Ortler",
	}
	src := map[string]interface{}{
		"theme":   "expanded", // overlapping key -> overwrite
		"metrics": []interface{}{"wind"}, // disjoint key -> add
	}
	got := mergeConfigMap(dst, src)

	if got["theme"] != "expanded" {
		t.Errorf("expected theme overwritten to 'expanded', got %v", got["theme"])
	}
	if got["region"] != "Ortler" {
		t.Errorf("expected region preserved as 'Ortler', got %v", got["region"])
	}
	if _, ok := got["metrics"]; !ok {
		t.Errorf("expected metrics added from src, got %v", got)
	}
}

// ============================================================================
// Struktur-Test: table-driven ueber die drei echten HTTP-Handler
// ============================================================================

// configMergeCase kapselt einen Endpoint-Fall: Seed, echter PUT ueber
// httptest, und Reload aus dem jeweiligen Store zur Preserve-Assertion.
type configMergeCase struct {
	name string
	// run fuehrt Seed + Teil-PUT + Reload durch und liefert das resultierende
	// display_config zur gemeinsamen Assertion zurueck.
	run func(t *testing.T) map[string]interface{}
}

// TestConfigMergePreservesUnsentDisplayConfigKeys deckt AC-7 ab (und AC-3 fuer
// den Location-Fall): pro Endpoint Seed mit >=2 display_config-Keys, dann ein
// Teil-PUT (ein Key weggelassen) ueber den echten http.HandlerFunc via
// httptest, danach Reload aus dem jeweiligen Store. Weggelassener Key muss
// ueberleben, gesendeter Key muss aktualisiert sein.
func TestConfigMergePreservesUnsentDisplayConfigKeys(t *testing.T) {
	cases := []configMergeCase{
		{
			name: "Trip",
			run: func(t *testing.T) map[string]interface{} {
				s := newTestStore(t)
				trip := model.Trip{
					ID:   "merge-struct-trip",
					Name: "Merge Struct Trip",
					Stages: []model.Stage{{
						ID: "S1", Name: "D1", Date: "2026-05-01",
						Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}},
					}},
					DisplayConfig: map[string]interface{}{
						"theme":  "compact",
						"region": "Ortler",
					},
				}
				if err := s.SaveTrip(&trip); err != nil {
					t.Fatalf("seed SaveTrip failed: %v", err)
				}

				r := chi.NewRouter()
				r.Put("/api/trips/{id}/weather-config", PutTripWeatherConfigHandler(s))

				// Teil-PUT: NUR region, kein theme.
				body := `{"region":"Zermatt"}`
				req := httptest.NewRequest("PUT", "/api/trips/merge-struct-trip/weather-config", bytes.NewReader([]byte(body)))
				req.Header.Set("Content-Type", "application/json")
				w := httptest.NewRecorder()
				r.ServeHTTP(w, req)
				if w.Code != http.StatusOK {
					t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
				}

				got, err := s.LoadTrip("merge-struct-trip")
				if err != nil || got == nil {
					t.Fatalf("failed to reload trip: %v", err)
				}
				return got.DisplayConfig
			},
		},
		{
			name: "Location",
			run: func(t *testing.T) map[string]interface{} {
				s := newTestStore(t)
				loc := model.Location{
					ID: "merge-struct-loc", Name: "Merge Struct Loc", Lat: 47.0, Lon: 11.0,
					DisplayConfig: map[string]interface{}{
						"theme":  "compact",
						"region": "Ortler",
					},
				}
				if err := s.SaveLocation(loc); err != nil {
					t.Fatalf("seed SaveLocation failed: %v", err)
				}

				r := chi.NewRouter()
				r.Put("/api/locations/{id}/weather-config", PutLocationWeatherConfigHandler(s))

				// Teil-PUT (Bug-Repro AC-3): NUR region, kein theme.
				body := `{"region":"Zermatt"}`
				req := httptest.NewRequest("PUT", "/api/locations/merge-struct-loc/weather-config", bytes.NewReader([]byte(body)))
				req.Header.Set("Content-Type", "application/json")
				w := httptest.NewRecorder()
				r.ServeHTTP(w, req)
				if w.Code != http.StatusOK {
					t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
				}

				got, err := s.LoadLocation("merge-struct-loc")
				if err != nil || got == nil {
					t.Fatalf("failed to reload location: %v", err)
				}
				return got.DisplayConfig
			},
		},
		{
			name: "ComparePreset",
			run: func(t *testing.T) map[string]interface{} {
				s := newTestStore(t)
				preset := model.ComparePreset{
					ID:          "merge-struct-cp",
					Name:        "Merge Struct Preset",
					UserID:      "user1",
					LocationIDs: []string{"loc-a"},
					Schedule:    "manual",
					Profil:      "SUMMER_TREKKING",
					HourFrom:    8,
					HourTo:      17,
					Empfaenger:  []string{"test@example.com"},
					CreatedAt:   time.Now().UTC(),
					DisplayConfig: map[string]interface{}{
						"theme":  "compact",
						"region": "Ortler",
					},
				}
				if err := s.WithUser("user1").SaveComparePresets([]model.ComparePreset{preset}); err != nil {
					t.Fatalf("seed SaveComparePresets failed: %v", err)
				}

				r := chi.NewRouter()
				r.Put("/api/compare/presets/{id}", UpdateComparePresetHandler(s))

				// Teil-PUT: gesamter Scheduler-Body noetig (Decode in model.ComparePreset),
				// aber display_config nur mit region — kein theme.
				body := map[string]interface{}{
					"name":         "Merge Struct Preset",
					"schedule":     "manual",
					"profil":       "SUMMER_TREKKING",
					"hour_from":    8,
					"hour_to":      17,
					"location_ids": []string{"loc-a"},
					"empfaenger":   []string{"test@example.com"},
					"display_config": map[string]interface{}{
						"region": "Zermatt",
					},
				}
				buf, err := json.Marshal(body)
				if err != nil {
					t.Fatalf("marshal body: %v", err)
				}
				req := httptest.NewRequest(http.MethodPut, "/api/compare/presets/merge-struct-cp", bytes.NewReader(buf))
				req.Header.Set("Content-Type", "application/json")
				req = addUserToContext(req, "user1")
				w := httptest.NewRecorder()
				r.ServeHTTP(w, req)
				if w.Code != http.StatusOK {
					t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
				}

				loaded, err := s.WithUser("user1").LoadComparePresets()
				if err != nil {
					t.Fatalf("reload LoadComparePresets failed: %v", err)
				}
				idx := findComparePresetIdx(loaded, "merge-struct-cp")
				if idx < 0 {
					t.Fatalf("preset not found after reload")
				}
				return loaded[idx].DisplayConfig
			},
		},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			dc := tc.run(t)
			if dc == nil {
				t.Fatalf("expected display_config to be present after merge, got nil")
			}
			if dc["theme"] != "compact" {
				t.Errorf("display_config.theme: expected preserved (compact), got %v", dc["theme"])
			}
			if dc["region"] != "Zermatt" {
				t.Errorf("display_config.region: expected updated (Zermatt), got %v", dc["region"])
			}
		})
	}
}
