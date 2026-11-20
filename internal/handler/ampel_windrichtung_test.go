package handler

// Issue #3222 S1 (ADR-0126) — Windrichtung modus/sektoren in der Profil-Ampel.
// Spec: docs/specs/modules/feat_3222_windrichtung.md AC-7 (API-Teil), AC-9, AC-10.
//
// Echte Handler, echter Store im Temp-Verzeichnis, zwei Nutzer. Gemeinsame
// Faelle mit Python (tests/fixtures/ampel_windrichtung_cases.json). Kein Mock.

import (
	"encoding/json"
	"net/http"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"

	"github.com/go-chi/chi/v5"

	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
)

type windrichtungFall struct {
	Name    string                 `json:"name"`
	Kontext string                 `json:"kontext"`
	Grund   *string                `json:"grund"`
	Ampel   map[string]interface{} `json:"ampel"`
}

func windrichtungFaelle(t *testing.T) []windrichtungFall {
	t.Helper()
	dir, _ := os.Getwd()
	for i := 0; i < 8; i++ { // Pfadanker go.mod (-trimpath-fest)
		if _, err := os.Stat(filepath.Join(dir, "go.mod")); err == nil {
			break
		}
		dir = filepath.Dir(dir)
	}
	raw, err := os.ReadFile(filepath.Join(dir, "tests", "fixtures", "ampel_windrichtung_cases.json"))
	if err != nil {
		t.Fatal(err)
	}
	var datei struct {
		Faelle []windrichtungFall `json:"faelle"`
	}
	if err := json.Unmarshal(raw, &datei); err != nil || len(datei.Faelle) < 15 {
		t.Fatalf("Faelle nicht lesbar (%v, %d)", err, len(datei.Faelle))
	}
	return datei.Faelle
}

// AC-9: dieselben Faelle, dieselbe Entscheidung und derselbe Grund wie Python.
func TestAmpelWindrichtung_GemeinsameFaelleMitPython(t *testing.T) {
	for _, f := range windrichtungFaelle(t) {
		vergleich := f.Kontext == "vergleich"
		if got := validateAmpelIm(f.Ampel, vergleich); got != (f.Grund == nil) {
			t.Errorf("%s: validateAmpelIm = %v, erwartet %v", f.Name, got, f.Grund == nil)
		}
		grund := ""
		for mid, e := range f.Ampel["metrics"].(map[string]interface{}) {
			if g := ampelWindrichtungGrund(mid, e.(map[string]interface{}), vergleich); g != "" {
				grund = g
			}
		}
		want := ""
		if f.Grund != nil {
			want = *f.Grund
		}
		if grund != want {
			t.Errorf("%s: Grund %q, erwartet %q (wie Python)", f.Name, grund, want)
		}
	}
}

func windAmpel(modus string, sektoren ...string) obj {
	e := obj{"modus": modus, "upper": obj{"yellow": 10.0, "orange": 20.0, "red": 30.0}}
	if len(sektoren) > 0 {
		liste := []interface{}{}
		for _, s := range sektoren {
			liste = append(liste, s)
		}
		e["sektoren"] = liste
	}
	return obj{"template": "radtour", "metrics": obj{"wind_direction": e}}
}

// AC-7 (API) / AC-9: Gegenwind im Ortsvergleich auf allen Schreibwegen 400,
// nichts gespeichert; ungueltiger Sektor/Modus auch im Trip 400.
func TestAmpelWindrichtung_UngueltigAufAllenWegenAbgelehnt(t *testing.T) {
	faelle := []struct {
		name  string
		ampel obj
		wege  []int // Index in ampelSchreibwege
	}{
		{"gegenwind_im_vergleich", windAmpel("gegenwind"), []int{2, 3}},
		{"sektor_nno", windAmpel("sektoren", "NNO"), []int{0, 1, 2, 3, 4}},
		{"modus_rueckenwind", windAmpel("rueckenwind"), []int{0, 1, 2, 3, 4}},
	}
	for _, f := range faelle {
		alle := ampelSchreibwege(f.ampel)
		for _, i := range f.wege {
			weg := alle[i]
			s := newTestStore(t)
			ampelSeed(t, s, "alice")
			ampelSeed(t, s, "bob")
			vorherA, vorherB := ampelStand(t, s, "alice"), ampelStand(t, s, "bob")
			w := ampelAnfrage(t, ampelRouter(s), weg.method, weg.path, "alice", "de", weg.body)
			if w.Code != http.StatusBadRequest || !strings.Contains(w.Body.String(), `"code":"ampel_ungueltig"`) {
				t.Fatalf("%s %s %s: %d %s", f.name, weg.method, weg.path, w.Code, w.Body.String())
			}
			if ampelStand(t, s, "alice") != vorherA || ampelStand(t, s, "bob") != vorherB {
				t.Fatalf("%s %s: gespeicherte Daten trotz Ablehnung geaendert", f.name, weg.path)
			}
		}
	}
	// Anlage eines Vergleichs mit Gegenwind ebenso.
	s := newTestStore(t)
	ampelSeed(t, s, "alice")
	w := ampelAnfrage(t, ampelRouter(s), "POST", "/api/compare/presets", "alice", "de",
		obj{"name": "Neu", "schedule": "daily", "profil": "ALLGEMEIN", "location_ids": []string{},
			"display_config": obj{"ampel": windAmpel("gegenwind")}})
	if w.Code != http.StatusBadRequest || !strings.Contains(w.Body.String(), `"code":"ampel_ungueltig"`) {
		t.Fatalf("POST Vergleich mit Gegenwind: %d %s", w.Code, w.Body.String())
	}
	if presets, _ := s.WithUser("alice").LoadComparePresets(); len(presets) != 1 {
		t.Fatalf("Vergleich trotz Ablehnung angelegt: %d", len(presets))
	}
}

// Gueltige Richtungs-Einstellungen werden auf Trip- und Vergleichswegen gespeichert.
func TestAmpelWindrichtung_GueltigWirdGespeichert(t *testing.T) {
	faelle := []struct {
		ampel obj
		wege  []int
	}{
		{windAmpel("gegenwind"), []int{0, 1, 4}},
		{windAmpel("sektoren", "N", "NO"), []int{0, 1, 2, 3, 4}},
	}
	for _, f := range faelle {
		alle := ampelSchreibwege(f.ampel)
		for _, i := range f.wege {
			weg := alle[i]
			s := newTestStore(t)
			ampelSeed(t, s, "alice")
			w := ampelAnfrage(t, ampelRouter(s), weg.method, weg.path, "alice", "de", weg.body)
			if w.Code != http.StatusOK && w.Code != http.StatusCreated {
				t.Fatalf("%s %s: %d %s", weg.method, weg.path, w.Code, w.Body.String())
			}
		}
	}
	// Anlage eines Trips mit Gegenwind ist erlaubt (Trip-Kontext).
	s := newTestStore(t)
	w := ampelAnfrage(t, ampelRouter(s), "POST", "/api/trips", "alice", "de", obj{"id": "rad", "name": "Rad",
		"display_config": obj{"ampel": windAmpel("gegenwind")},
		"stages": []obj{{"id": "S1", "name": "D1", "date": "2026-05-01",
			"waypoints": []obj{{"id": "W1", "name": "P", "lat": 47.0, "lon": 11.0, "elevation_m": 500}}}}})
	if w.Code != http.StatusCreated {
		t.Fatalf("POST Trip mit Gegenwind: %d %s", w.Code, w.Body.String())
	}
	if trip, _ := s.WithUser("alice").LoadTrip("rad"); trip == nil || !strings.Contains(mustJSON(trip.DisplayConfig), `"modus":"gegenwind"`) {
		t.Fatalf("Trip ohne gespeicherten Gegenwind: %+v", trip)
	}
}

func mustJSON(v interface{}) string {
	raw, _ := json.Marshal(v)
	return string(raw)
}

// AC-10: zwei Nutzer, A mit Gegenwind und B mit „aus"; jeder liest nur die
// eigene Einstellung, fremde Trips sind nicht erreichbar.
func TestAmpelWindrichtung_ZweiNutzerSehenNurEigeneEinstellung(t *testing.T) {
	s := newTestStore(t)
	ampelSeed(t, s, "alice")
	ampelSeed(t, s, "bob")
	nurBob := model.Trip{ID: "nur-bob", Name: "Bob allein",
		Stages: []model.Stage{{ID: "S1", Name: "D1", Date: "2026-05-01",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}}}},
		DisplayConfig: obj{"ampel": windAmpel("aus")}}
	if err := s.WithUser("bob").SaveTrip(&nurBob); err != nil {
		t.Fatal(err)
	}
	r := chi.NewRouter()
	r.Use(middleware.Lang(s))
	r.Put("/api/trips/{id}/weather-config", PutTripWeatherConfigHandler(s))
	r.Get("/api/trips/{id}/weather-config", GetTripWeatherConfigHandler(s))

	einstellung := map[string]obj{"alice": windAmpel("gegenwind"), "bob": windAmpel("aus")}
	for user, ampel := range einstellung {
		if w := ampelAnfrage(t, r, "PUT", "/api/trips/t1/weather-config", user, "de", obj{"ampel": ampel}); w.Code != http.StatusOK {
			t.Fatalf("PUT %s: %d %s", user, w.Code, w.Body.String())
		}
	}
	for user, ampel := range einstellung {
		w := ampelAnfrage(t, r, "GET", "/api/trips/t1/weather-config", user, "de", nil)
		var dc obj
		_ = json.Unmarshal(w.Body.Bytes(), &dc)
		want, _ := json.Marshal(ampel)
		got, _ := json.Marshal(dc["ampel"])
		if w.Code != http.StatusOK || string(got) != string(want) {
			t.Fatalf("GET %s: %d, Ampel %s, erwartet %s", user, w.Code, got, want)
		}
		trip, _ := s.WithUser(user).LoadTrip("t1")
		if !reflect.DeepEqual(trip.DisplayConfig["preset_name"], "skitouren") {
			t.Fatalf("%s: Restfelder der display_config verloren: %v", user, trip.DisplayConfig)
		}
	}
	if w := ampelAnfrage(t, r, "GET", "/api/trips/nur-bob/weather-config", "alice", "de", nil); w.Code != http.StatusNotFound {
		t.Fatalf("alice liest bobs Trip: %d %s", w.Code, w.Body.String())
	}
	if w := ampelAnfrage(t, r, "PUT", "/api/trips/nur-bob/weather-config", "alice", "de",
		obj{"ampel": windAmpel("gegenwind")}); w.Code != http.StatusNotFound {
		t.Fatalf("alice schreibt bobs Trip: %d %s", w.Code, w.Body.String())
	}
	bobTrip, _ := s.WithUser("bob").LoadTrip("nur-bob")
	if got, _ := json.Marshal(bobTrip.DisplayConfig["ampel"]); !strings.Contains(string(got), `"modus":"aus"`) {
		t.Fatalf("bobs Trip veraendert: %s", got)
	}
}
