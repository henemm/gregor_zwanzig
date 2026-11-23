package handler

// Issue #3154 F002, abgeloest durch #3237: der Tabellen-PUT fragt den Kern
// nicht mehr nach Begleitfeldern (show_stability_off entfaellt, Nachweis in
// briefing_anlage_tabelle_3237_test.go). Hier bleiben der Test-Kern (Server,
// der eine feste Antwort ausliefert und mitschreibt, was ankommt -- keine
// Fachlogik), die frueher aufgezeichnete Kern-Antwort als beliebige Antwort
// und der Orte-Fall.
//
//   go test ./internal/handler/ -run Placements3154

import (
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

// Orte-PUT: kein Kern-Aufruf, nur placements wird geschrieben.
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

// ohneKern: Anlage-Handler ohne Python-Kern (pythonURL leer, #3237) fuer
// Tabellen, die Handler der Form func(*store.Store) erwarten.
func ohneKern(h func(*store.Store, string) http.HandlerFunc) func(*store.Store) http.HandlerFunc {
	return func(s *store.Store) http.HandlerFunc { return h(s, "") }
}
