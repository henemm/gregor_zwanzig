package handler

// Issue #2792 S1a — Profil-Ampel beim Speichern (AC-16) und eigene Vorlage mit
// Ampel anwenden (AC-14). Spec: docs/specs/modules/feat_2792_s1_profil_ampel.md
//
// Echte Handler, echter Store im Temp-Verzeichnis, Sprache ueber die echte
// Lang-Middleware (Accept-Language, Nutzer ohne gespeicherte Sprache). Jeder
// datenbewegende Endpunkt mit zwei Nutzern (alice schreibt, bob bleibt gleich).
// Kein Mock.

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"reflect"
	"strings"
	"testing"

	"github.com/go-chi/chi/v5"

	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

type obj = map[string]interface{}

func ampelGueltig() obj {
	return obj{"template": "skitouren", "metrics": obj{
		"gust": obj{"upper": obj{"yellow": 42.0, "orange": 55.0, "red": 70.0}, "alarm_ab": "yellow"},
	}}
}

// AC-16: Boeen oben gelb 50 ueber orange 45 bzw. untere Gelbgrenze ueber der oberen.
func ampelUngueltig() map[string]obj {
	return map[string]obj{
		"oben_absteigend": {"metrics": obj{"gust": obj{"upper": obj{"yellow": 50.0, "orange": 45.0, "red": 60.0}}}},
		"unten_ueber_oben": {"metrics": obj{"temperature": obj{
			"lower": obj{"yellow": 30.0}, "upper": obj{"yellow": 20.0}}}},
	}
}

func ampelRouter(s *store.Store) http.Handler {
	r := chi.NewRouter()
	r.Use(middleware.Lang(s))
	r.Put("/api/trips/{id}", UpdateTripHandler(s))
	r.Put("/api/trips/{id}/weather-config", PutTripWeatherConfigHandler(s))
	r.Put("/api/compare/presets/{id}", UpdateComparePresetHandler(s))
	r.Put("/api/briefings/{id}", UpdateBriefingHandler(s))
	r.Get("/api/metric-presets", ListMetricPresetsHandler(s))
	r.Post("/api/metric-presets", CreateMetricPresetHandler(s))
	r.Patch("/api/metric-presets/{id}", PatchMetricPresetHandler(s))
	return r
}

func ampelAnfrage(t *testing.T, h http.Handler, method, path, user, lang string, body interface{}) *httptest.ResponseRecorder {
	t.Helper()
	raw, _ := json.Marshal(body)
	req := httptest.NewRequest(method, path, bytes.NewReader(raw))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept-Language", lang)
	req = req.WithContext(middleware.ContextWithUserID(req.Context(), user))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)
	return w
}

func ampelSeed(t *testing.T, s *store.Store, user string) {
	t.Helper()
	us := s.WithUser(user)
	trip := model.Trip{ID: "t1", Name: "Tour " + user,
		Stages: []model.Stage{{ID: "S1", Name: "D1", Date: "2026-05-01",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}}}},
		DisplayConfig: obj{"preset_name": "skitouren", "metrics": []interface{}{}, "ampel": ampelGueltig()},
		ReportConfig:  obj{"send_email": true, "send_sms": false, "morning_time": "07:00:00"},
	}
	if err := us.SaveTrip(&trip); err != nil {
		t.Fatalf("SaveTrip %s: %v", user, err)
	}
	cp := model.ComparePreset{ID: "c1", Name: "Vergleich " + user, UserID: user, Schedule: "daily",
		Profil: "ALLGEMEIN", ForecastHours: 48, HourFrom: 6, HourTo: 18,
		DisplayConfig: obj{"ideal_ranges": obj{"temp_max_c": obj{"min": 10.0}}, "ampel": ampelGueltig()}}
	if err := us.SaveComparePreset(cp); err != nil {
		t.Fatalf("SaveComparePreset %s: %v", user, err)
	}
}

// ampelStand liefert den gespeicherten Stand von Trip, Vergleich und eigenen
// Vorlagen eines Nutzers als JSON (Vorher/Nachher-Vergleich).
func ampelStand(t *testing.T, s *store.Store, user string) string {
	t.Helper()
	us := s.WithUser(user)
	trip, err := us.LoadTrip("t1")
	if err != nil {
		t.Fatal(err)
	}
	cp, err := us.LoadComparePreset("c1")
	if err != nil {
		t.Fatal(err)
	}
	presets, err := us.LoadMetricPresets()
	if err != nil {
		t.Fatal(err)
	}
	raw, _ := json.Marshal([]interface{}{trip, cp, presets})
	return string(raw)
}

func ampelSchreibwege(ampel obj) []struct{ method, path string; body obj } {
	return []struct{ method, path string; body obj }{
		{"PUT", "/api/trips/t1", obj{"display_config": obj{"ampel": ampel}}},
		{"PUT", "/api/trips/t1/weather-config", obj{"ampel": ampel}},
		{"PUT", "/api/compare/presets/c1", obj{"display_config": obj{"ampel": ampel}}},
		{"PUT", "/api/briefings/c1?kind=vergleich", obj{"display_config": obj{"ampel": ampel}}},
		{"POST", "/api/metric-presets", obj{"name": "Mein Gipfel", "metrics": []string{"wind"}, "ampel": ampel}},
	}
}

func TestAmpelUngueltig_WirdAbgelehntInAnfrageSpracheUndNichtsGeschrieben(t *testing.T) {
	texte := map[string]string{
		"de": "Die Ampel ist ungültig",
		"en": "The traffic light is invalid",
	}
	for fall, kaputt := range ampelUngueltig() {
		for lang, prefix := range texte {
			for _, weg := range ampelSchreibwege(kaputt) {
				s := newTestStore(t)
				ampelSeed(t, s, "alice")
				ampelSeed(t, s, "bob")
				vorherA, vorherB := ampelStand(t, s, "alice"), ampelStand(t, s, "bob")

				w := ampelAnfrage(t, ampelRouter(s), weg.method, weg.path, "alice", lang, weg.body)
				name := fall + " " + lang + " " + weg.method + " " + weg.path
				if w.Code != http.StatusBadRequest {
					t.Fatalf("%s: Status %d, erwartet 400: %s", name, w.Code, w.Body.String())
				}
				var body struct{ Code, Message string }
				_ = json.Unmarshal(w.Body.Bytes(), &body)
				if body.Code != "ampel_ungueltig" || !strings.HasPrefix(body.Message, prefix) {
					t.Fatalf("%s: code=%q message=%q", name, body.Code, body.Message)
				}
				if ampelStand(t, s, "alice") != vorherA || ampelStand(t, s, "bob") != vorherB {
					t.Fatalf("%s: gespeicherte Daten haben sich trotz Ablehnung geaendert", name)
				}
			}
		}
	}
}

func TestAmpelUngueltig_PatchEigeneVorlageAbgelehnt(t *testing.T) {
	s := newTestStore(t)
	ampelSeed(t, s, "alice")
	h := ampelRouter(s)
	w := ampelAnfrage(t, h, "POST", "/api/metric-presets", "alice", "de",
		obj{"name": "Mein Gipfel", "metrics": []string{"wind"}, "ampel": ampelGueltig()})
	if w.Code != http.StatusCreated {
		t.Fatalf("POST gueltig: %d %s", w.Code, w.Body.String())
	}
	var p struct{ ID string }
	_ = json.Unmarshal(w.Body.Bytes(), &p)
	vorher := ampelStand(t, s, "alice")
	for _, lang := range []string{"de", "en"} {
		w = ampelAnfrage(t, h, "PATCH", "/api/metric-presets/"+p.ID, "alice", lang,
			obj{"ampel": ampelUngueltig()["oben_absteigend"]})
		if w.Code != http.StatusBadRequest || !strings.Contains(w.Body.String(), `"code":"ampel_ungueltig"`) {
			t.Fatalf("PATCH %s: %d %s", lang, w.Code, w.Body.String())
		}
	}
	if ampelStand(t, s, "alice") != vorher {
		t.Fatal("PATCH-Ablehnung hat die Vorlage veraendert")
	}
}

// Spec §1 „Speichern": die Ampel wird als ganzer Unterbaum ersetzt, alle
// anderen display_config-Felder bleiben erhalten; bob bleibt unveraendert.
func TestAmpelGueltig_ErsetztUnterbaumUndBehaeltRestfelder(t *testing.T) {
	neu := obj{"template": "wandern", "metrics": obj{"wind": obj{
		"upper": obj{"yellow": 25.0, "orange": 50.0, "red": 70.0}, "alarm_ab": "yellow"}}}
	for _, weg := range ampelSchreibwege(neu)[:4] {
		s := newTestStore(t)
		ampelSeed(t, s, "alice")
		ampelSeed(t, s, "bob")
		vorherB := ampelStand(t, s, "bob")
		w := ampelAnfrage(t, ampelRouter(s), weg.method, weg.path, "alice", "de", weg.body)
		if w.Code != http.StatusOK {
			t.Fatalf("%s: %d %s", weg.path, w.Code, w.Body.String())
		}
		us := s.WithUser("alice")
		var dc obj
		if strings.Contains(weg.path, "trips") {
			trip, _ := us.LoadTrip("t1")
			dc = trip.DisplayConfig
			if dc["preset_name"] != "skitouren" || trip.ReportConfig["send_email"] != true {
				t.Fatalf("%s: Restfelder verloren: %v / %v", weg.path, dc, trip.ReportConfig)
			}
		} else {
			cp, _ := us.LoadComparePreset("c1")
			dc = cp.DisplayConfig
			if _, ok := dc["ideal_ranges"]; !ok {
				t.Fatalf("%s: ideal_ranges verloren: %v", weg.path, dc)
			}
		}
		if !reflect.DeepEqual(dc["ampel"], neu) {
			t.Fatalf("%s: Ampel nicht als ganzer Unterbaum ersetzt: %v", weg.path, dc["ampel"])
		}
		if ampelStand(t, s, "bob") != vorherB {
			t.Fatalf("%s: bob wurde veraendert", weg.path)
		}
	}
}

// AC-14: eigene Vorlage „Mein Gipfel" (Auswahl + Ampel Wind gelb 25 +
// alarm_ab yellow) speichern und auf einen anderen Trip anwenden; Zustellung
// und Etappen des Ziel-Trips bleiben unveraendert, bob sieht nichts davon.
func TestEigeneVorlageMitAmpel_SpeichernUndAnwendenLaesstZustellungUnveraendert(t *testing.T) {
	s := newTestStore(t)
	ampelSeed(t, s, "alice")
	ampelSeed(t, s, "bob")
	h := ampelRouter(s)
	vorlage := obj{"template": "wandern", "metrics": obj{"wind": obj{
		"upper": obj{"yellow": 25.0, "orange": 50.0, "red": 70.0}, "alarm_ab": "yellow"}}}
	w := ampelAnfrage(t, h, "POST", "/api/metric-presets", "alice", "de", obj{
		"name": "Mein Gipfel", "ampel": vorlage, "report_config": obj{"send_sms": true},
		"metrics": []obj{{"metric_id": "wind", "enabled": true, "use_friendly_format": false}}})
	if w.Code != http.StatusCreated {
		t.Fatalf("POST: %d %s", w.Code, w.Body.String())
	}
	if strings.Contains(w.Body.String(), "report_config") {
		t.Fatalf("eigene Vorlage speichert Zustellung: %s", w.Body.String())
	}

	var liste []struct {
		ID      string      `json:"id"`
		Metrics []obj       `json:"metrics"`
		Ampel   interface{} `json:"ampel"`
	}
	_ = json.Unmarshal(ampelAnfrage(t, h, "GET", "/api/metric-presets", "alice", "de", nil).Body.Bytes(), &liste)
	if len(liste) != 1 || !reflect.DeepEqual(liste[0].Ampel, interface{}(vorlage)) {
		t.Fatalf("Vorlage laedt ohne Ampel/alarm_ab: %+v", liste)
	}
	if bob := ampelAnfrage(t, h, "GET", "/api/metric-presets", "bob", "de", nil).Body.String(); strings.Contains(bob, "Mein Gipfel") {
		t.Fatalf("bob sieht die Vorlage von alice: %s", bob)
	}

	vorher, _ := s.WithUser("alice").LoadTrip("t1")
	w = ampelAnfrage(t, h, "PUT", "/api/trips/t1/weather-config", "alice", "de", obj{
		"metrics": liste[0].Metrics, "preset_name": liste[0].ID, "ampel": liste[0].Ampel})
	if w.Code != http.StatusOK {
		t.Fatalf("Anwenden: %d %s", w.Code, w.Body.String())
	}
	nachher, _ := s.WithUser("alice").LoadTrip("t1")
	if !reflect.DeepEqual(nachher.DisplayConfig["ampel"], interface{}(vorlage)) {
		t.Fatalf("Ziel-Trip traegt nicht die Ampel der Vorlage: %v", nachher.DisplayConfig["ampel"])
	}
	if !reflect.DeepEqual(nachher.ReportConfig, vorher.ReportConfig) || !reflect.DeepEqual(nachher.Stages, vorher.Stages) {
		t.Fatal("Anwenden hat Zustellung oder Etappen veraendert")
	}
}
