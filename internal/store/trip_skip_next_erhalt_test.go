package store_test

// Rework #3020 R1, AC-5: ein von Telegram/SMS gesetztes `report_config.skip_next` darf ein
// Speichervorgang der Oberflaeche, der das Feld nicht mitsendet, nie still zuruecksetzen.
// Ersatz fuer den mit #3357 geloeschten trip_python_skip_next_ohne_412.test.ts, jetzt dort, wo die
// Zusicherung wirkt: im Go-Speicherpfad (PUT /api/trips/{id} -> UpdateTripHandler -> echter Store).
//
// Spec: docs/specs/modules/rework_3020_pruefungen_wiederherstellen.md (AC-5)
// Mandantentrennung: zwei Nutzer mit derselben Trip-ID; B bleibt byte-gleich.
// Keine Mocks: echter Store im t.TempDir(), echter Handler, echter chi-Router.

import (
	"context"
	"encoding/json"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/go-chi/chi/v5"
	"github.com/henemm/gregor-api/internal/handler"
	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

const (
	rw3020NutzerA = "nutzer-a-3020"
	rw3020NutzerB = "nutzer-b-3020"
	rw3020TripID  = "trip-3020"
)

// rw3020Store: echter Store im Temp-Verzeichnis; der Basis-Nutzer ist bewusst keiner der beiden.
func rw3020Store(t *testing.T) (*store.Store, string) {
	t.Helper()
	dir := t.TempDir()
	return store.New(dir, "basis-ohne-daten"), dir
}

// rw3020Seed legt den Trip eines Nutzers an (Etappe mit Wegpunkt wie die Handler-Tests).
func rw3020Seed(t *testing.T, s *store.Store, nutzer string, rc, dc map[string]interface{}) {
	t.Helper()
	trip := model.Trip{
		ID: rw3020TripID, Name: "Trip " + nutzer,
		Stages: []model.Stage{{ID: "S1", Name: "D1", Date: "2026-05-01",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}},
		}},
		ReportConfig:  rc,
		DisplayConfig: dc,
	}
	if err := s.WithUser(nutzer).SaveTrip(&trip); err != nil {
		t.Fatalf("seed %s: %v", nutzer, err)
	}
}

// rw3020Put: PUT /api/trips/{id} als angemeldeter Nutzer ueber den echten Handler.
func rw3020Put(t *testing.T, s *store.Store, nutzer, body string) {
	t.Helper()
	r := chi.NewRouter()
	r.Put("/api/trips/{id}", handler.UpdateTripHandler(s))
	req := httptest.NewRequest("PUT", "/api/trips/"+rw3020TripID, strings.NewReader(body))
	req = req.WithContext(middleware.ContextWithUserID(context.Background(), nutzer))
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	if w.Code != 200 {
		t.Fatalf("PUT als %s: Status %d: %s", nutzer, w.Code, w.Body.String())
	}
}

// rw3020Datei: der gespeicherte Rohstand eines Nutzers (Byte-Vergleich fuer den Unbeteiligten).
func rw3020Datei(t *testing.T, dir, nutzer string) []byte {
	t.Helper()
	b, err := os.ReadFile(filepath.Join(dir, "users", nutzer, "briefings", rw3020TripID+".json"))
	if err != nil {
		t.Fatalf("Datei von %s: %v", nutzer, err)
	}
	return b
}

// rw3020Roh: der gespeicherte Rohstand als Objekt (ohne Ableitungen des Ladepfads).
func rw3020Roh(t *testing.T, dir, nutzer string) map[string]interface{} {
	t.Helper()
	var m map[string]interface{}
	if err := json.Unmarshal(rw3020Datei(t, dir, nutzer), &m); err != nil {
		t.Fatalf("JSON von %s: %v", nutzer, err)
	}
	return m
}

func rw3020Teil(t *testing.T, m map[string]interface{}, feld string) map[string]interface{} {
	t.Helper()
	teil, ok := m[feld].(map[string]interface{})
	if !ok {
		t.Fatalf("%s fehlt oder ist kein Objekt: %v", feld, m[feld])
	}
	return teil
}

func TestRework3020_SkipNextBleibtBeimSpeichernOhneFeld_ZweiNutzer(t *testing.T) {
	s, dir := rw3020Store(t)
	rw3020Seed(t, s, rw3020NutzerA, map[string]interface{}{
		"enabled": true, "morning_time": "07:00:00", "send_email": true,
		"skip_next": map[string]interface{}{"morning": true, "set_by": "telegram"},
	}, nil)
	rw3020Seed(t, s, rw3020NutzerB, map[string]interface{}{
		"enabled": true, "morning_time": "06:00:00", "send_email": true,
		"skip_next": map[string]interface{}{"evening": true, "set_by": "sms"},
	}, nil)
	vorherB := rw3020Datei(t, dir, rw3020NutzerB)

	// Zustellung-Reiter von A speichert nur seine Eigenfelder -- skip_next steht nicht in der Nutzlast.
	rw3020Put(t, s, rw3020NutzerA, `{"report_config":{"morning_time":"08:00:00","send_telegram":true}}`)

	rcA := rw3020Teil(t, rw3020Roh(t, dir, rw3020NutzerA), "report_config")
	if rcA["morning_time"] != "08:00:00" || rcA["send_telegram"] != true {
		t.Fatalf("Vorbedingung: die gesendeten Felder muessen ankommen, report_config = %v", rcA)
	}
	skip, ok := rcA["skip_next"].(map[string]interface{})
	if !ok || skip["morning"] != true || skip["set_by"] != "telegram" {
		t.Errorf("skip_next von A wurde durch das Speichern verändert/gelöscht: %v", rcA["skip_next"])
	}
	if nachherB := rw3020Datei(t, dir, rw3020NutzerB); string(nachherB) != string(vorherB) {
		t.Errorf("Trip von Nutzer B wurde durch das Speichern von A verändert:\nvorher %s\nnachher %s", vorherB, nachherB)
	}
}
