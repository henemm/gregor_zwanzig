package handler

// Issue #3047 Runde 7, Befund E3: ein `display_config.metrics[]`-Eintrag ohne
// `metric_id` (z. B. eine im Browser gespreizte Zeichenkette
// `{"0":"w","1":"i",...}`) liess den Python-Loader den ganzen Trip verwerfen
// (keine Briefings, keine Alarme). Der Schreibweg weist ihn mit 400 ab.
// Spec: docs/specs/modules/feat_3047_einstellung_gleich_mail_pruefkatalog.md.
//
// Echte Handler, echter Store, zwei Nutzer ueber den echten Auth-Kontext
// (CLAUDE.md: jeder datenbewegende Endpoint mit zwei Nutzern). Kein Mock.

import (
	"net/http"
	"reflect"
	"testing"
)

func e3Gespreizt() obj {
	return obj{"0": "w", "1": "i", "2": "n", "3": "d", "enabled": false}
}

func TestE3_3047_WeatherConfig_MetrikOhneID_400_ZweiNutzer(t *testing.T) {
	s := newTestStore(t)
	teil3SeedTrip(t, s, "nutzer-a", teil3AmpelA(), nil)
	teil3SeedTrip(t, s, "nutzer-b", teil3AmpelBAlt(), nil)
	h := teil3TripRouter(s)
	url := "/api/trips/" + teil3TripID + "/weather-config"

	kaputt := map[string][]interface{}{
		"gespreizte Zeichenkette":      {obj{"metric_id": "gust", "enabled": true}, e3Gespreizt()},
		"leere metric_id":              {obj{"metric_id": "", "enabled": true}},
		"metric_id keine Zeichenkette": {obj{"metric_id": 7.0, "enabled": true}},
		"Zahl statt Eintrag":           {3.0},
	}
	for _, user := range []string{"nutzer-a", "nutzer-b"} {
		fpVorher := teil3Fingerprint(t, s, user, teil3TripID)
		for name, metrics := range kaputt {
			w := ampelAnfrage(t, h, "PUT", url, user, "de", obj{"metrics": metrics})
			if w.Code != http.StatusBadRequest {
				t.Errorf("%s/%s: Status %d, erwartet 400 (%s)", user, name, w.Code, w.Body.String())
			}
		}
		if got := teil3Fingerprint(t, s, user, teil3TripID); got != fpVorher {
			t.Errorf("%s: abgewiesene Anfrage hat die Datei veraendert", user)
		}
	}

	// Gueltig: Objekte mit metric_id und das Altformat Zeichenkette (#1262,
	// Python liest es) bleiben erlaubt; nur der eigene Trip aendert sich.
	vorherB := teil3LoadTrip(t, s, "nutzer-b")
	gut := []interface{}{"wind", obj{"metric_id": "gust", "enabled": true}}
	w := ampelAnfrage(t, h, "PUT", url, "nutzer-a", "de", obj{"metrics": gut})
	if w.Code != http.StatusOK {
		t.Fatalf("A gueltige metrics: %d %s", w.Code, w.Body.String())
	}
	a := teil3LoadTrip(t, s, "nutzer-a")
	if len(a.DisplayConfig["metrics"].([]interface{})) != 2 {
		t.Errorf("A metrics nicht gespeichert: %v", a.DisplayConfig["metrics"])
	}
	b := teil3LoadTrip(t, s, "nutzer-b")
	if !reflect.DeepEqual(b.DisplayConfig["metrics"], vorherB.DisplayConfig["metrics"]) {
		t.Errorf("B metrics durch A veraendert: %v", b.DisplayConfig["metrics"])
	}
}

// E3-Nachgang: `PUT /api/trips/{id}` schreibt `display_config` ebenfalls und
// pruefte `metrics[]` nicht; gleiche Regel wie `/weather-config` (400), zwei
// Nutzer, abgewiesene Anfrage aendert nichts, gueltige nur den eigenen Trip.
func TestE3_3047_TripPut_DisplayConfigMetrikOhneID_400_ZweiNutzer(t *testing.T) {
	s := newTestStore(t)
	teil3SeedTrip(t, s, "nutzer-a", teil3AmpelA(), nil)
	teil3SeedTrip(t, s, "nutzer-b", teil3AmpelBAlt(), nil)
	h := teil3TripRouter(s)
	url := "/api/trips/" + teil3TripID

	kaputt := map[string][]interface{}{
		"gespreizte Zeichenkette": {obj{"metric_id": "gust", "enabled": true}, e3Gespreizt()},
		"leere metric_id":         {obj{"metric_id": "", "enabled": true}},
		"Zahl statt Eintrag":      {3.0},
	}
	for _, user := range []string{"nutzer-a", "nutzer-b"} {
		fpVorher := teil3Fingerprint(t, s, user, teil3TripID)
		for name, metrics := range kaputt {
			w := ampelAnfrage(t, h, "PUT", url, user, "de", obj{"display_config": obj{"metrics": metrics}})
			if w.Code != http.StatusBadRequest {
				t.Errorf("%s/%s: Status %d, erwartet 400 (%s)", user, name, w.Code, w.Body.String())
			}
		}
		if got := teil3Fingerprint(t, s, user, teil3TripID); got != fpVorher {
			t.Errorf("%s: abgewiesene Anfrage hat die Datei veraendert", user)
		}
	}

	vorherB := teil3LoadTrip(t, s, "nutzer-b")
	gut := []interface{}{"wind", obj{"metric_id": "gust", "enabled": true}}
	if w := ampelAnfrage(t, h, "PUT", url, "nutzer-a", "de", obj{"display_config": obj{"metrics": gut}}); w.Code != http.StatusOK {
		t.Fatalf("A gueltige metrics: %d %s", w.Code, w.Body.String())
	}
	if a := teil3LoadTrip(t, s, "nutzer-a"); len(a.DisplayConfig["metrics"].([]interface{})) != 2 {
		t.Errorf("A metrics nicht gespeichert: %v", a.DisplayConfig["metrics"])
	}
	if b := teil3LoadTrip(t, s, "nutzer-b"); !reflect.DeepEqual(b.DisplayConfig["metrics"], vorherB.DisplayConfig["metrics"]) {
		t.Errorf("B metrics durch A veraendert: %v", b.DisplayConfig["metrics"])
	}
}

// Auch die Anlage (`POST /api/trips` mit display_config) speichert keinen
// Eintrag ohne metric_id; je Nutzer wird nichts angelegt.
func TestE3_3047_TripPost_DisplayConfigMetrikOhneID_400_ZweiNutzer(t *testing.T) {
	s := newTestStore(t)
	h := v2794Router(s)
	for _, user := range []string{"nutzer-a", "nutzer-b"} {
		body := v2794NeuerTrip("t-e3")
		body["display_config"] = obj{"metrics": []interface{}{e3Gespreizt()}}
		if w := v2794Anfrage(t, h, "POST", "/api/trips", user, "de", body); w.Code != http.StatusBadRequest {
			t.Errorf("%s: Status %d, erwartet 400 (%s)", user, w.Code, w.Body.String())
		}
		if trip, _ := s.WithUser(user).LoadTrip("t-e3"); trip != nil {
			t.Errorf("%s: abgewiesener Trip wurde angelegt", user)
		}
	}
}
