package handler

// Issue #3154 F002 (Spec feat_3122_was_steht_wo Teil A Nr. 8, AC-11): das
// erste Speichern der Tabelle schreibt report_config.show_stability=false im
// selben Vorgang mit, wenn der Kern das meldet. Echter Store, echte Dateien,
// zwei Nutzer. Der Kern ist ein Test-Server, der die AUFGEZEICHNETE Antwort
// des echten Python-Endpoints ausliefert (Fixture, gegen den Kern geprueft in
// tests/tdd/test_placements_erstes_speichern_3154.py) und mitschreibt, was
// ankommt -- keine Fachlogik.
//
//   go test ./internal/handler/ -run Placements3154

import (
	"bytes"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"reflect"
	"sync"
	"testing"

	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

const erstanlageFixture = "../../tests/fixtures/placements_erstanlage_3154/stabilitaet_aus.json"

type erstanlageKern struct {
	mu       sync.Mutex
	anfragen []*url.URL
	srv      *httptest.Server
}

func neuerErstanlageKern(t *testing.T, status int, antwort []byte) *erstanlageKern {
	t.Helper()
	k := &erstanlageKern{}
	k.srv = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		k.mu.Lock()
		k.anfragen = append(k.anfragen, r.URL)
		k.mu.Unlock()
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(status)
		_, _ = w.Write(antwort)
	}))
	t.Cleanup(k.srv.Close)
	return k
}

func aufgezeichneteAntwort(t *testing.T) []byte {
	t.Helper()
	data, err := os.ReadFile(erstanlageFixture)
	if err != nil {
		t.Fatal(err)
	}
	return data
}

// seedAltTrip legt einen Trip OHNE Tabelle mit Ausblick aus an.
func seedAltTrip(t *testing.T, s *store.Store, u, id string) {
	t.Helper()
	trip := model.Trip{
		ID: id, Name: "Alt-Trip",
		Stages: []model.Stage{{ID: "S1", Name: "D1", Date: "2026-05-01",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}},
		}},
		DisplayConfig: map[string]interface{}{
			"metrics": []interface{}{map[string]interface{}{"metric_id": "wind", "enabled": true}},
		},
		ReportConfig: map[string]interface{}{
			"show_outlook": false, "email_format": "full", "send_email": true,
			"multi_day_trend_reports": []interface{}{"evening"},
		},
	}
	if err := s.WithUser(u).SaveTrip(&trip); err != nil {
		t.Fatalf("SaveTrip: %v", err)
	}
}

func ohneTabelleUndStabilitaet(m map[string]interface{}) map[string]interface{} {
	ohnePlacements(m)
	if rc, ok := m["report_config"].(map[string]interface{}); ok {
		delete(rc, "show_stability")
	}
	return m
}

func TestPlacements3154ErstesSpeichernSchreibtStabilitaetAusZweiNutzer(t *testing.T) {
	s := newTestStore(t)
	kern := neuerErstanlageKern(t, http.StatusOK, aufgezeichneteAntwort(t))
	r := placementsRouter(s, kern.srv.URL)
	seedAltTrip(t, s, "e3154-a", "alt")
	seedAltTrip(t, s, "e3154-b", "alt")
	dateiA, dateiB := aboDatei(s, "e3154-a", "alt"), aboDatei(s, "e3154-b", "alt")
	vorherA := roheDatei(t, dateiA)
	vorherB, _ := os.ReadFile(dateiB)

	w := doReq(r, http.MethodPut, placementsPfad("alt", "route")+"&user_id=e3154-b", placementsB2Neu, "", "e3154-a")
	if w.Code != http.StatusOK {
		t.Fatalf("PUT: %d %s", w.Code, w.Body.String())
	}
	if len(kern.anfragen) != 1 {
		t.Fatalf("Kern %d-mal gefragt, erwartet einmal", len(kern.anfragen))
	}
	a := kern.anfragen[0]
	if a.Path != "/api/briefings/alt/placements/erstanlage" || a.Query().Get("kind") != "route" {
		t.Errorf("Abfrage beim Kern: %s", a.String())
	}
	if got := a.Query()["user_id"]; !reflect.DeepEqual(got, []string{"e3154-a"}) {
		t.Errorf("user_id zum Kern %v, erwartet nur den angemeldeten Nutzer", got)
	}
	nachherA := roheDatei(t, dateiA)
	if got := nachherA["report_config"].(map[string]interface{})["show_stability"]; got != false {
		t.Errorf("report_config.show_stability = %#v, erwartet false", got)
	}
	if nachherA["display_config"].(map[string]interface{})["placements"] == nil {
		t.Errorf("placements nicht geschrieben")
	}
	if !reflect.DeepEqual(ohneTabelleUndStabilitaet(nachherA), ohneTabelleUndStabilitaet(vorherA)) {
		t.Errorf("andere Felder veraendert:\nvorher  %#v\nnachher %#v", vorherA, nachherA)
	}
	if nachherB, _ := os.ReadFile(dateiB); !bytes.Equal(nachherB, vorherB) {
		t.Errorf("Datei von B veraendert")
	}
}

func TestPlacements3154KernOhneMeldungLaesstReportConfig(t *testing.T) {
	s := newTestStore(t)
	kern := neuerErstanlageKern(t, http.StatusOK, []byte(`{"show_stability_off": false}`))
	r := placementsRouter(s, kern.srv.URL)
	seedAltTrip(t, s, "e3154-a", "alt")
	vorher := roheDatei(t, aboDatei(s, "e3154-a", "alt"))
	if w := doReq(r, http.MethodPut, placementsPfad("alt", "route"), placementsB2Neu, "", "e3154-a"); w.Code != http.StatusOK {
		t.Fatalf("PUT: %d %s", w.Code, w.Body.String())
	}
	nachher := roheDatei(t, aboDatei(s, "e3154-a", "alt"))
	if !reflect.DeepEqual(nachher["report_config"], vorher["report_config"]) {
		t.Errorf("report_config veraendert: %#v", nachher["report_config"])
	}
}

// Ohne gueltige Antwort des Kerns wird nichts geschrieben (sonst schaltete
// das Speichern die Grosswetterlage unbemerkt ein).
func TestPlacements3154KernFehlerSchreibtNichts(t *testing.T) {
	faelle := map[string]struct {
		status  int
		antwort string
	}{
		"500":          {http.StatusInternalServerError, `{"show_stability_off": false}`},
		"ohne Feld":    {http.StatusOK, `{"rows": []}`},
		"kein JSON":    {http.StatusOK, `<html>`},
		"nicht da":     {0, ""},
		"falscher Typ": {http.StatusOK, `{"show_stability_off": "ja"}`},
	}
	for name, f := range faelle {
		t.Run(name, func(t *testing.T) {
			s := newTestStore(t)
			ziel := "http://127.0.0.1:1"
			if f.status != 0 {
				ziel = neuerErstanlageKern(t, f.status, []byte(f.antwort)).srv.URL
			}
			r := placementsRouter(s, ziel)
			seedAltTrip(t, s, "e3154-a", "alt")
			vorher, _ := os.ReadFile(aboDatei(s, "e3154-a", "alt"))
			if w := doReq(r, http.MethodPut, placementsPfad("alt", "route"), placementsB2Neu, "", "e3154-a"); w.Code != http.StatusBadGateway {
				t.Errorf("Status %d, erwartet 502 (%s)", w.Code, w.Body.String())
			}
			if nachher, _ := os.ReadFile(aboDatei(s, "e3154-a", "alt")); !bytes.Equal(nachher, vorher) {
				t.Errorf("bei Kern-Fehler wurde geschrieben")
			}
		})
	}
}

// Orte haben keine Grosswetterlage: kein Kern-Aufruf, report_config bleibt.
func TestPlacements3154OrteFragenNicht(t *testing.T) {
	s := newTestStore(t)
	kern := neuerErstanlageKern(t, http.StatusOK, aufgezeichneteAntwort(t))
	r := placementsRouter(s, kern.srv.URL)
	seedPlacementsB2(t, s, "e3154-a")
	vorher := roheDatei(t, aboDatei(s, "e3154-a", "orte-e3154-a"))
	if w := doReq(r, http.MethodPut, placementsPfad("orte-e3154-a", "vergleich"), placementsB2Neu, "", "e3154-a"); w.Code != http.StatusOK {
		t.Fatalf("PUT: %d %s", w.Code, w.Body.String())
	}
	if len(kern.anfragen) != 0 {
		t.Errorf("Orte-PUT hat den Kern gefragt: %v", kern.anfragen)
	}
	if nachher := roheDatei(t, aboDatei(s, "e3154-a", "orte-e3154-a")); !reflect.DeepEqual(ohnePlacements(nachher), ohnePlacements(vorher)) {
		t.Errorf("Orte-PUT hat andere Felder veraendert")
	}
}
