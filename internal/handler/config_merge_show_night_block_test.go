package handler

// Issue #1721 (Epic #2259), AC-6: das Feld display_config.show_night_block
// laeuft generisch durch den Read-Modify-Write-Merge (Teil-PUT ohne das Feld
// erhaelt es, PUT mit dem Feld setzt es). Zwei Nutzer, getrennte Stores.
//
// Spec: docs/specs/modules/fix_1721_nachtausgabe.md
// KEINE Mocks — echter httptest-Handler gegen echten Store.

import (
	"bytes"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/go-chi/chi/v5"
	"github.com/henemm/gregor-api/internal/model"
)

func putTripWeatherConfig(t *testing.T, handler http.HandlerFunc, id, body string) {
	t.Helper()
	r := chi.NewRouter()
	r.Put("/api/trips/{id}/weather-config", handler)
	req := httptest.NewRequest("PUT", "/api/trips/"+id+"/weather-config", bytes.NewReader([]byte(body)))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
}

func TestShowNightBlockSurvivesPartialPut(t *testing.T) {
	// Nutzer A: Schalter aus; Nutzer B: Schalter an (eigene Stores = eigene user_id).
	storeA := newTestStore(t)
	storeB := newTestStore(t)
	seed := func(st interface{ SaveTrip(*model.Trip) error }, id string, wert bool) {
		trip := model.Trip{
			ID: id, Name: id,
			Stages: []model.Stage{{
				ID: "S1", Name: "D1", Date: "2026-05-01",
				Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}},
			}},
			DisplayConfig: map[string]interface{}{"show_night_block": wert, "region": "Ortler"},
		}
		if err := st.SaveTrip(&trip); err != nil {
			t.Fatalf("seed SaveTrip failed: %v", err)
		}
	}
	seed(storeA, "night-a", true)
	seed(storeB, "night-b", true)

	// 1) PUT mit dem Feld setzt es (A: aus).
	putTripWeatherConfig(t, PutTripWeatherConfigHandler(storeA), "night-a", `{"show_night_block":false}`)
	got, err := storeA.LoadTrip("night-a")
	if err != nil || got == nil {
		t.Fatalf("reload A failed: %v", err)
	}
	if v, ok := got.DisplayConfig["show_night_block"].(bool); !ok || v {
		t.Fatalf("A: show_night_block muss false sein, war %v", got.DisplayConfig["show_night_block"])
	}

	// 2) Teil-PUT ohne das Feld (anderer Reiter) laesst es unveraendert.
	putTripWeatherConfig(t, PutTripWeatherConfigHandler(storeA), "night-a", `{"region":"Zermatt"}`)
	got, err = storeA.LoadTrip("night-a")
	if err != nil || got == nil {
		t.Fatalf("reload A (2) failed: %v", err)
	}
	if v, ok := got.DisplayConfig["show_night_block"].(bool); !ok || v {
		t.Fatalf("A: Teil-PUT darf show_night_block=false nicht veraendern, war %v", got.DisplayConfig["show_night_block"])
	}
	if got.DisplayConfig["region"] != "Zermatt" {
		t.Fatalf("A: region muss aktualisiert sein, war %v", got.DisplayConfig["region"])
	}

	// 3) Nutzer B bleibt "an".
	gotB, err := storeB.LoadTrip("night-b")
	if err != nil || gotB == nil {
		t.Fatalf("reload B failed: %v", err)
	}
	if v, ok := gotB.DisplayConfig["show_night_block"].(bool); !ok || !v {
		t.Fatalf("B: show_night_block muss true bleiben, war %v", gotB.DisplayConfig["show_night_block"])
	}
}
