package handler

// Issue #3122 (Spec feat_3122_was_steht_wo, AC-14 Go-Teil, AC-15 Mandantentrennung):
// display_config.placements ist ein undurchsichtiges Roh-Objekt (ADR-0077). Jeder
// andere Go-Speicherweg desselben Abos laesst es strukturgleich stehen; ein zweiter
// Nutzer sieht und aendert nichts davon. Echter Store, echte Dateien, zwei Nutzer.
//
//   go test ./internal/handler/ -run Placements3122

import (
	"bytes"
	"encoding/json"
	"net/http"
	"os"
	"path/filepath"
	"reflect"
	"testing"

	"github.com/henemm/gregor-api/internal/model"
)

const placements3122JSON = `{"version": 1,
  "rows": [{"metric_id": "wind", "places": {"email": true, "sms": false},
            "formats": {"email": "simplified"}},
           {"metric_id": "gust", "places": {"telegram": false}}],
  "outlook_reports": ["morning", "evening"]}`

func placements3122(t *testing.T) map[string]interface{} {
	t.Helper()
	var p map[string]interface{}
	if err := json.Unmarshal([]byte(placements3122JSON), &p); err != nil {
		t.Fatal(err)
	}
	return p
}

func placementsVonPlatte(t *testing.T, dataDir, user, id string) interface{} {
	t.Helper()
	dc, _ := ketteRohVonPlatte(t, dataDir, user, id)["display_config"].(map[string]interface{})
	return dc["placements"]
}

func TestPlacements3122TripBleibtUeberAndereSpeicherwegeZweiNutzer(t *testing.T) {
	s := newTestStore(t)
	r := etagRouter(s)
	nutzerA, nutzerB := "p3122-nutzer-a", "p3122-nutzer-b"
	for _, u := range []string{nutzerA, nutzerB} {
		trip := model.Trip{
			ID: "trip-" + u, Name: "Placements-Trip",
			Stages: []model.Stage{{ID: "S1", Name: "D1", Date: "2026-05-01",
				Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}},
			}},
			DisplayConfig: map[string]interface{}{
				"metrics": []interface{}{
					map[string]interface{}{"metric_id": "wind", "enabled": true},
					map[string]interface{}{"metric_id": "gust", "enabled": true},
				},
				"placements": placements3122(t),
			},
		}
		if err := s.WithUser(u).SaveTrip(&trip); err != nil {
			t.Fatalf("SaveTrip: %v", err)
		}
	}
	idA, idB := "trip-"+nutzerA, "trip-"+nutzerB
	dateiB := filepath.Join(s.DataDir, "users", nutzerB, "briefings", idB+".json")
	vorherB, err := os.ReadFile(dateiB)
	if err != nil {
		t.Fatal(err)
	}
	soll := placements3122(t)
	if got := placementsVonPlatte(t, s.DataDir, nutzerA, idA); !reflect.DeepEqual(got, soll) {
		t.Fatalf("SaveTrip: placements auf der Platte %#v", got)
	}

	schritte := []struct{ pfad, body string }{
		{"/api/trips/" + idA, `{"name": "Umbenannt"}`},
		{"/api/trips/" + idA, `{"display_config": {"show_night_block": false}}`},
		{"/api/trips/" + idA + "/weather-config", `{"show_night_block": true}`},
	}
	for _, sch := range schritte {
		if w := doReq(r, http.MethodPut, sch.pfad, sch.body, "", nutzerA); w.Code != http.StatusOK {
			t.Fatalf("PUT %s: %d %s", sch.pfad, w.Code, w.Body.String())
		}
		if got := placementsVonPlatte(t, s.DataDir, nutzerA, idA); !reflect.DeepEqual(got, soll) {
			t.Errorf("PUT %s %s: placements veraendert: %#v", sch.pfad, sch.body, got)
		}
	}

	// Nutzer B: kann den Trip von A weder lesen noch schreiben; seine Datei bleibt bytegleich.
	if w := doReq(r, http.MethodGet, "/api/trips/"+idA, "", "", nutzerB); w.Code == http.StatusOK {
		t.Errorf("Nutzer B darf den Trip von A nicht lesen, Status %d", w.Code)
	}
	if w := doReq(r, http.MethodPut, "/api/trips/"+idA,
		`{"display_config": {"placements": {"rows": []}}}`, "", nutzerB); w.Code == http.StatusOK {
		t.Errorf("Nutzer B darf den Trip von A nicht aendern, Status %d", w.Code)
	}
	if got := placementsVonPlatte(t, s.DataDir, nutzerA, idA); !reflect.DeepEqual(got, soll) {
		t.Errorf("Nutzer A: placements nach Fremd-PUT %#v", got)
	}
	if nachherB, _ := os.ReadFile(dateiB); !bytes.Equal(nachherB, vorherB) {
		t.Errorf("Nutzer B: Datei darf durch die PUTs von A nicht beruehrt werden")
	}
}

func TestPlacements3122OrteBleibtUeberBeideSchreibwegeZweiNutzer(t *testing.T) {
	const presetJSON = `{
  "id": "%ID%", "name": "Orte 3122", "kind": "vergleich",
  "location_ids": ["loc-a", "loc-b"], "schedule": "daily", "profil": "ALLGEMEIN",
  "forecast_hours": 48, "morning_enabled": true, "morning_time": "07:00:00",
  "created_at": "2026-09-01T00:00:00Z", "corridors": [], "empfaenger": [],
  "display_config": {"active_metrics": ["wind_max_kmh", "gust_max_kmh"],
                     "placements": ` + placements3122JSON + `}
}`
	for _, weg := range []string{"compare", "briefing"} {
		weg := weg
		t.Run(weg, func(t *testing.T) {
			s := newTestStore(t)
			r := briefingVergleichEtagRouter(s)
			nutzerA, nutzerB := "p3122-orte-a", "p3122-orte-b"
			idA, idB := "p3122-a", "p3122-b"
			writeRawComparePresetFixture(t, s, nutzerA, idA, string(bytes.ReplaceAll([]byte(presetJSON), []byte("%ID%"), []byte(idA))))
			writeRawComparePresetFixture(t, s, nutzerB, idB, string(bytes.ReplaceAll([]byte(presetJSON), []byte("%ID%"), []byte(idB))))
			dateiB := filepath.Join(s.DataDir, "users", nutzerB, "briefings", idB+".json")
			vorherB, _ := os.ReadFile(dateiB)
			soll := placements3122(t)

			for _, body := range []string{
				`{"name": "Umbenannt"}`,
				`{"display_config": {"hourly_metrics": ["wind"]}}`,
				`{"location_ids": ["loc-b", "loc-a"]}`,
			} {
				kettePut(t, r, weg, idA, nutzerA, body)
				if got := placementsVonPlatte(t, s.DataDir, nutzerA, idA); !reflect.DeepEqual(got, soll) {
					t.Errorf("PUT %s: placements veraendert: %#v", body, got)
				}
			}
			pfad := "/api/compare/presets/" + idA
			if weg == "briefing" {
				pfad = "/api/briefings/" + idA + "?kind=vergleich"
			}
			if w := doReq(r, http.MethodPut, pfad, `{"display_config": {"placements": {"rows": []}}}`, "", nutzerB); w.Code == http.StatusOK {
				t.Errorf("Nutzer B darf das Abo von A nicht aendern, Status %d", w.Code)
			}
			if got := placementsVonPlatte(t, s.DataDir, nutzerA, idA); !reflect.DeepEqual(got, soll) {
				t.Errorf("Nutzer A: placements nach Fremd-PUT %#v", got)
			}
			if nachherB, _ := os.ReadFile(dateiB); !bytes.Equal(nachherB, vorherB) {
				t.Errorf("Nutzer B: Datei darf durch die PUTs von A nicht beruehrt werden")
			}
		})
	}
}
