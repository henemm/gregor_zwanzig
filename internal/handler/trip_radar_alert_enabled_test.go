package handler

// Issue #2800 (Epic #2791, Scheibe S8) — Trip-Radar-Alarm-Schalter, Go-Teil.
//
// Spec: docs/specs/modules/feat_2800_trip_radar_alarm.md (AC-7, AC-8)
//
// model.Trip bekommt das Pointer-Feld RadarAlertEnabled
// (`json:"radar_alert_enabled,omitempty"`), der PUT nutzt den Dreizustand
// (Optional[bool] + ApplyPtr): fehlt das Feld im Body, bleibt der Bestand
// (Read-Modify-Write, BUG-DATALOSS-GR221); true/false setzen es.
//
// Bewusst OHNE Zugriff auf das (noch fehlende) Struct-Feld: der Bestand wird
// als Roh-JSON in model.Trip geladen und ueber den echten Store gespeichert,
// gelesen wird ueber das JSON des geladenen Trips (= was GET ausliefert).
// So kompiliert das Paket heute und der Test ist ROT aus dem fachlichen
// Grund (Go verwirft das Feld), nicht wegen eines Compile-Fehlers.

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/go-chi/chi/v5"

	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

// seedTripRadarRaw speichert einen Trip mit optional gesetztem
// radar_alert_enabled (nil = Feld fehlt, Bestandstrip) ueber den echten Store.
func seedTripRadarRaw(t *testing.T, s *store.Store, id, name string, radar *bool) {
	t.Helper()
	doc := map[string]interface{}{
		"id":   id,
		"name": name,
		"stages": []interface{}{map[string]interface{}{
			"id": "S1", "name": "D1", "date": "2026-05-01",
			"waypoints": []interface{}{map[string]interface{}{
				"id": "W1", "name": "P", "lat": 47.0, "lon": 11.0, "elevation_m": 500,
			}},
		}},
		"alert_cooldown_minutes": 45,
		"official_alerts_enabled": false,
	}
	if radar != nil {
		doc["radar_alert_enabled"] = *radar
	}
	raw, _ := json.Marshal(doc)
	var trip model.Trip
	if err := json.Unmarshal(raw, &trip); err != nil {
		t.Fatalf("Unmarshal Seed: %v", err)
	}
	if err := s.SaveTrip(&trip); err != nil {
		t.Fatalf("SaveTrip: %v", err)
	}
}

// radarFeld liest radar_alert_enabled aus dem JSON des gespeicherten Trips.
func radarFeld(t *testing.T, s *store.Store, id string) (interface{}, bool, map[string]interface{}) {
	t.Helper()
	loaded, err := s.LoadTrip(id)
	if err != nil || loaded == nil {
		t.Fatalf("LoadTrip %s: %v (nil=%v)", id, err, loaded == nil)
	}
	raw, _ := json.Marshal(loaded)
	var m map[string]interface{}
	if err := json.Unmarshal(raw, &m); err != nil {
		t.Fatalf("Marshal-Rueckweg: %v", err)
	}
	v, ok := m["radar_alert_enabled"]
	return v, ok, m
}

func putTripRadar(t *testing.T, s *store.Store, userID, id string, body map[string]interface{}) *httptest.ResponseRecorder {
	t.Helper()
	buf, _ := json.Marshal(body)
	r := chi.NewRouter()
	r.Put("/api/trips/{id}", UpdateTripHandler(s))
	req := httptest.NewRequest(http.MethodPut, "/api/trips/"+id, bytes.NewReader(buf))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, userID)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	return w
}

func assertAndereFelderErhalten(t *testing.T, m map[string]interface{}, wantName string) {
	t.Helper()
	if m["name"] != wantName {
		t.Errorf("name = %v, erwartet %q", m["name"], wantName)
	}
	if m["alert_cooldown_minutes"] != float64(45) {
		t.Errorf("alert_cooldown_minutes verloren: %v", m["alert_cooldown_minutes"])
	}
	if m["official_alerts_enabled"] != false {
		t.Errorf("official_alerts_enabled verloren: %v", m["official_alerts_enabled"])
	}
	stages, _ := m["stages"].([]interface{})
	if len(stages) != 1 {
		t.Errorf("Etappen verloren: %v", m["stages"])
	}
}

// AC-7 Fall 1: PUT ohne Feld laesst den gespeicherten Schalter (false) stehen.
func TestUpdateTripHandler_RadarAlertEnabled_FehltImBody_BestandBleibt(t *testing.T) {
	s := newTestStore(t)
	falseVal := false
	seedTripRadarRaw(t, s, "trip-radar-rwm-1", "Radar-Schalter", &falseVal)

	w := putTripRadar(t, s, "test", "trip-radar-rwm-1", map[string]interface{}{
		"name": "Radar-Schalter (umbenannt)",
	})
	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
	v, ok, m := radarFeld(t, s, "trip-radar-rwm-1")
	if !ok || v != false {
		t.Errorf("AC-7: radar_alert_enabled=false muss PUT ohne Feld ueberstehen, got present=%v value=%v", ok, v)
	}
	assertAndereFelderErhalten(t, m, "Radar-Schalter (umbenannt)")
}

// AC-7 Fall 2/3: PUT mit true bzw. false setzt den Schalter, andere Felder bleiben.
func TestUpdateTripHandler_RadarAlertEnabled_TrueUndFalseSetzen(t *testing.T) {
	for _, tc := range []struct {
		name  string
		start *bool
		put   bool
	}{
		{"bestand-ohne-feld_put-false", nil, false},
		{"bestand-false_put-true", func() *bool { b := false; return &b }(), true},
		{"bestand-true_put-false", func() *bool { b := true; return &b }(), false},
	} {
		t.Run(tc.name, func(t *testing.T) {
			s := newTestStore(t)
			seedTripRadarRaw(t, s, "trip-radar-set", "Radar-Set", tc.start)
			w := putTripRadar(t, s, "test", "trip-radar-set", map[string]interface{}{
				"radar_alert_enabled": tc.put,
			})
			if w.Code != http.StatusOK {
				t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
			}
			v, ok, m := radarFeld(t, s, "trip-radar-set")
			if !ok || v != tc.put {
				t.Errorf("AC-7: PUT radar_alert_enabled=%v muss gespeichert werden, got present=%v value=%v", tc.put, ok, v)
			}
			assertAndereFelderErhalten(t, m, "Radar-Set")
		})
	}
}

// AC-8: zwei Nutzer. A schaltet seinen Trip-Radar aus, B bleibt unveraendert,
// und A erreicht B's Trip nicht (nicht gefunden).
func TestUpdateTripHandler_RadarAlertEnabled_ZweiNutzer(t *testing.T) {
	baseDir := t.TempDir()
	sA := store.New(baseDir, "usera-2800")
	sB := store.New(baseDir, "userb-2800")

	trueVal := true
	seedTripRadarRaw(t, sA, "trip-radar-usera", "Nutzer A Trip", &trueVal)
	seedTripRadarRaw(t, sB, "trip-radar-userb", "Nutzer B Trip", &trueVal)

	w := putTripRadar(t, sA, "usera-2800", "trip-radar-usera", map[string]interface{}{
		"radar_alert_enabled": false,
	})
	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
	if v, ok, _ := radarFeld(t, sA, "trip-radar-usera"); !ok || v != false {
		t.Errorf("AC-8: A's Trip muss radar_alert_enabled=false tragen, got present=%v value=%v", ok, v)
	}
	if v, ok, m := radarFeld(t, sB, "trip-radar-userb"); !ok || v != true || m["name"] != "Nutzer B Trip" {
		t.Errorf("AC-8: B's Trip muss unveraendert radar_alert_enabled=true tragen, got present=%v value=%v name=%v", ok, v, m["name"])
	}

	// A versucht B's Trip-ID zu schalten: nicht gefunden, B unveraendert.
	w = putTripRadar(t, sA, "usera-2800", "trip-radar-userb", map[string]interface{}{
		"radar_alert_enabled": false,
	})
	if w.Code != http.StatusNotFound {
		t.Errorf("AC-8: A darf B's Trip nicht erreichen, expected 404, got %d: %s", w.Code, w.Body.String())
	}
	if v, ok, _ := radarFeld(t, sB, "trip-radar-userb"); !ok || v != true {
		t.Errorf("AC-8: B's Schalter nach Fremdzugriff veraendert, got present=%v value=%v", ok, v)
	}
}
