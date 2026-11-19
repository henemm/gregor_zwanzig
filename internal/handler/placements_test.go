package handler

// Issue #3122 B2 (Spec feat_3122_was_steht_wo, Teil A Nr. 9; AC-14, AC-15,
// AC-20): Lese- und Schreib-Endpoint der Tabelle "Was steht wo" unter der
// Briefing-Route, fuer Trip und Orte EIN Code-Pfad. Echter Store, echte
// Dateien, zwei Nutzer. Der Python-Core ist ein Test-Server, der nur
// mitschreibt, was ankommt (Transport-Stub, keine Fachlogik).
//
//   go test ./internal/handler/ -run Placements3122B2

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"reflect"
	"strconv"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/go-chi/chi/v5"

	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

const placementsB2Neu = `{"version": 1,
  "rows": [{"metric_id": "gust", "places": {"sms": false}},
           {"metric_id": "wind", "formats": {"telegram": "simplified"}}],
  "outlook_reports": ["morning"]}`

type kernMitschrift struct {
	mu       sync.Mutex
	anfragen []*url.URL
	srv      *httptest.Server
}

func neuerKern(t *testing.T) *kernMitschrift {
	t.Helper()
	k := &kernMitschrift{}
	k.srv = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if strings.HasSuffix(r.URL.Path, "/placements/erstanlage") {
			// #3154: Begleitfeld-Abfrage des PUT -- hier nichts mitzuschreiben.
			w.Header().Set("Content-Type", "application/json")
			_, _ = w.Write([]byte(`{"show_stability_off": false}`))
			return
		}
		k.mu.Lock()
		k.anfragen = append(k.anfragen, r.URL)
		k.mu.Unlock()
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"rows": [], "kern": "antwort"}`))
	}))
	t.Cleanup(k.srv.Close)
	return k
}

func (k *kernMitschrift) zahl() int {
	k.mu.Lock()
	defer k.mu.Unlock()
	return len(k.anfragen)
}

func placementsRouter(s *store.Store, pythonURL string) *chi.Mux {
	r := chi.NewRouter()
	r.Get("/api/briefings/{id}/placements", BriefingPlacementsGetHandler(s, pythonURL))
	r.Put("/api/briefings/{id}/placements", BriefingPlacementsPutHandler(s, pythonURL))
	r.Get("/api/briefings/{id}", GetBriefingHandler(s))
	r.Put("/api/briefings/{id}", UpdateBriefingHandler(s))
	r.Put("/api/trips/{id}", UpdateTripHandler(s))
	r.Put("/api/trips/{id}/weather-config", PutTripWeatherConfigHandler(s))
	r.Put("/api/compare/presets/{id}", UpdateComparePresetHandler(s))
	return r
}

const placementsB2PresetJSON = `{
  "id": "%ID%", "name": "Orte B2", "kind": "vergleich",
  "location_ids": ["loc-a", "loc-b"], "schedule": "daily", "profil": "ALLGEMEIN",
  "forecast_hours": 48, "morning_enabled": true, "morning_time": "07:00:00",
  "created_at": "2026-09-01T00:00:00Z", "corridors": [], "empfaenger": [],
  "display_config": {"active_metrics": ["wind_max_kmh", "gust_max_kmh"],
                     "placements": ` + placements3122JSON + `}
}`

// seedPlacementsB2 legt je Nutzer einen Trip "trip-<u>" und ein Orte-Abo
// "orte-<u>" mit gespeicherter Tabelle an.
func seedPlacementsB2(t *testing.T, s *store.Store, nutzer ...string) {
	t.Helper()
	for _, u := range nutzer {
		seedPlacementsB2Als(t, s, u, "trip-"+u, "orte-"+u)
	}
}

// seedPlacementsB2Als legt fuer einen Nutzer Trip und Orte-Abo unter frei
// gewaehlten Kennungen an (zwei Nutzer koennen dieselbe Kennung tragen).
func seedPlacementsB2Als(t *testing.T, s *store.Store, u, tripID, orteID string) {
	t.Helper()
	trip := model.Trip{
		ID: tripID, Name: "Placements-Trip",
		Stages: []model.Stage{{ID: "S1", Name: "D1", Date: "2026-05-01",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}},
		}},
		DisplayConfig: map[string]interface{}{
			"metrics": []interface{}{
				map[string]interface{}{"metric_id": "wind", "enabled": true},
				map[string]interface{}{"metric_id": "gust", "enabled": true},
			},
			"show_night_block": true,
			"placements":       placements3122(t),
		},
	}
	if err := s.WithUser(u).SaveTrip(&trip); err != nil {
		t.Fatalf("SaveTrip: %v", err)
	}
	writeRawComparePresetFixture(t, s, u, orteID,
		strings.ReplaceAll(placementsB2PresetJSON, "%ID%", orteID))
}

func aboDatei(s *store.Store, user, id string) string {
	return filepath.Join(s.DataDir, "users", user, "briefings", id+".json")
}

func roheDatei(t *testing.T, pfad string) map[string]interface{} {
	t.Helper()
	data, err := os.ReadFile(pfad)
	if err != nil {
		t.Fatal(err)
	}
	var m map[string]interface{}
	if err := json.Unmarshal(data, &m); err != nil {
		t.Fatal(err)
	}
	return m
}

func ohnePlacements(m map[string]interface{}) map[string]interface{} {
	dc, _ := m["display_config"].(map[string]interface{})
	delete(dc, "placements")
	return m
}

func placementsPfad(id, kind string) string {
	return "/api/briefings/" + id + "/placements?kind=" + kind
}

var placementsB2Faelle = []struct{ kind, praefix string }{
	{"route", "trip-"}, {"vergleich", "orte-"},
}

// GET reicht mit dem Nutzer aus der Anmeldung an den Kern weiter (eine von
// aussen gesetzte user_id wird ersetzt) und liefert den Stempel des Abos.
func TestPlacements3122B2GetReichtMitAnmeldungWeiter(t *testing.T) {
	for _, f := range placementsB2Faelle {
		t.Run(f.kind, func(t *testing.T) {
			s := newTestStore(t)
			kern := neuerKern(t)
			r := placementsRouter(s, kern.srv.URL)
			seedPlacementsB2(t, s, "b2-a")
			id := f.praefix + "b2-a"

			w := doReq(r, http.MethodGet, placementsPfad(id, f.kind)+"&user_id=b2-b", "", "", "b2-a")
			if w.Code != http.StatusOK {
				t.Fatalf("GET: %d %s", w.Code, w.Body.String())
			}
			if !strings.Contains(w.Body.String(), `"kern": "antwort"`) {
				t.Errorf("Antwort des Kerns nicht durchgereicht: %s", w.Body.String())
			}
			fp, _ := s.WithUser("b2-a").BriefingFingerprint(id)
			if got := w.Header().Get("ETag"); got != `"`+fp+`"` {
				t.Errorf("ETag %q, erwartet Stempel des Abos %q", got, fp)
			}
			if kern.zahl() != 1 {
				t.Fatalf("Kern %d-mal erreicht", kern.zahl())
			}
			a := kern.anfragen[0]
			if a.Path != "/api/briefings/"+id+"/placements" {
				t.Errorf("Pfad zum Kern %q", a.Path)
			}
			if got := a.Query()["user_id"]; !reflect.DeepEqual(got, []string{"b2-a"}) {
				t.Errorf("user_id zum Kern %v, erwartet nur den angemeldeten Nutzer", got)
			}
			if a.Query().Get("kind") != f.kind {
				t.Errorf("kind zum Kern %q", a.Query().Get("kind"))
			}
		})
	}
}

// AC-15: A liest/speichert die Tabelle von B -> abgewiesen; B bleibt bytegleich.
func TestPlacements3122B2FremdeTabelleZweiNutzer(t *testing.T) {
	for _, f := range placementsB2Faelle {
		t.Run(f.kind, func(t *testing.T) {
			s := newTestStore(t)
			kern := neuerKern(t)
			r := placementsRouter(s, kern.srv.URL)
			seedPlacementsB2(t, s, "b2-a", "b2-b")
			idA, idB := f.praefix+"b2-a", f.praefix+"b2-b"
			dateiB := aboDatei(s, "b2-b", idB)
			vorherB, _ := os.ReadFile(dateiB)

			if w := doReq(r, http.MethodGet, placementsPfad(idB, f.kind), "", "", "b2-a"); w.Code != http.StatusNotFound {
				t.Errorf("A liest B: Status %d, erwartet 404", w.Code)
			}
			if kern.zahl() != 0 {
				t.Errorf("fremdes Abo darf den Kern nicht erreichen (%d Anfragen)", kern.zahl())
			}
			if w := doReq(r, http.MethodPut, placementsPfad(idB, f.kind), placementsB2Neu, "", "b2-a"); w.Code != http.StatusNotFound {
				t.Errorf("A speichert B: Status %d, erwartet 404", w.Code)
			}
			if w := doReq(r, http.MethodPut, placementsPfad(idA, f.kind), placementsB2Neu, "", "b2-a"); w.Code != http.StatusOK {
				t.Fatalf("A speichert eigene Tabelle: %d %s", w.Code, w.Body.String())
			}
			if nachherB, _ := os.ReadFile(dateiB); !bytes.Equal(nachherB, vorherB) {
				t.Errorf("Datei von B veraendert")
			}
			if _, err := os.Stat(aboDatei(s, "b2-a", idB)); !os.IsNotExist(err) {
				t.Errorf("unter A darf keine Datei mit der Kennung von B entstehen")
			}
		})
	}
}

// AC-14: PUT der Tabelle aendert nur placements; danach lassen die anderen
// Speicherwege placements unveraendert.
func TestPlacements3122B2PutAendertNurPlacements(t *testing.T) {
	andereWege := map[string][]struct{ pfad, body string }{
		"route": {
			{"/api/trips/trip-b2-a", `{"name": "Umbenannt"}`},
			{"/api/trips/trip-b2-a/weather-config", `{"show_night_block": false}`},
			{"/api/briefings/trip-b2-a?kind=route", `{"display_config": {"show_night_block": true}}`},
		},
		"vergleich": {
			{"/api/compare/presets/orte-b2-a", `{"name": "Umbenannt"}`},
			{"/api/briefings/orte-b2-a?kind=vergleich", `{"display_config": {"hourly_metrics": ["wind"]}}`},
		},
	}
	for _, f := range placementsB2Faelle {
		t.Run(f.kind, func(t *testing.T) {
			s := newTestStore(t)
			r := placementsRouter(s, neuerKern(t).srv.URL)
			seedPlacementsB2(t, s, "b2-a")
			id := f.praefix + "b2-a"
			datei := aboDatei(s, "b2-a", id)
			vorher := roheDatei(t, datei)
			fp, _ := s.WithUser("b2-a").BriefingFingerprint(id)

			w := doReq(r, http.MethodPut, placementsPfad(id, f.kind), placementsB2Neu, `"`+fp+`"`, "b2-a")
			if w.Code != http.StatusOK {
				t.Fatalf("PUT placements: %d %s", w.Code, w.Body.String())
			}
			neuFp, _ := s.WithUser("b2-a").BriefingFingerprint(id)
			if w.Header().Get("ETag") != `"`+neuFp+`"` || neuFp == fp {
				t.Errorf("ETag nach dem Speichern %q, Stempel %q (vorher %q)", w.Header().Get("ETag"), neuFp, fp)
			}
			var soll map[string]interface{}
			_ = json.Unmarshal([]byte(placementsB2Neu), &soll)
			nachher := roheDatei(t, datei)
			if got := nachher["display_config"].(map[string]interface{})["placements"]; !reflect.DeepEqual(got, soll) {
				t.Fatalf("placements auf der Platte %#v", got)
			}
			if !reflect.DeepEqual(ohnePlacements(nachher), ohnePlacements(vorher)) {
				t.Errorf("PUT placements hat andere Felder veraendert:\nvorher  %#v\nnachher %#v", vorher, nachher)
			}
			for _, weg := range andereWege[f.kind] {
				if w := doReq(r, http.MethodPut, weg.pfad, weg.body, "", "b2-a"); w.Code != http.StatusOK {
					t.Fatalf("PUT %s: %d %s", weg.pfad, w.Code, w.Body.String())
				}
				got := roheDatei(t, datei)["display_config"].(map[string]interface{})["placements"]
				if !reflect.DeepEqual(got, soll) {
					t.Errorf("PUT %s %s: placements veraendert: %#v", weg.pfad, weg.body, got)
				}
			}
		})
	}
}

// AC-20: veralteter Stand -> Konflikt, nichts wird ueberschrieben.
func TestPlacements3122B2VeralteterStandKonflikt(t *testing.T) {
	aendern := map[string]struct{ pfad, body string }{
		"route":     {"/api/trips/trip-b2-a", `{"name": "Inzwischen geaendert"}`},
		"vergleich": {"/api/compare/presets/orte-b2-a", `{"name": "Inzwischen geaendert"}`},
	}
	for _, f := range placementsB2Faelle {
		t.Run(f.kind, func(t *testing.T) {
			s := newTestStore(t)
			r := placementsRouter(s, neuerKern(t).srv.URL)
			seedPlacementsB2(t, s, "b2-a")
			id := f.praefix + "b2-a"
			alt := mustETag(t, doReq(r, http.MethodGet, placementsPfad(id, f.kind), "", "", "b2-a"))

			if w := doReq(r, http.MethodPut, aendern[f.kind].pfad, aendern[f.kind].body, "", "b2-a"); w.Code != http.StatusOK {
				t.Fatalf("Zwischen-Aenderung: %d %s", w.Code, w.Body.String())
			}
			vorher, _ := os.ReadFile(aboDatei(s, "b2-a", id))
			w := doReq(r, http.MethodPut, placementsPfad(id, f.kind), placementsB2Neu, alt, "b2-a")
			if w.Code != http.StatusPreconditionFailed {
				t.Fatalf("veralteter Stand: Status %d, erwartet 412", w.Code)
			}
			if !strings.Contains(w.Body.String(), "precondition_failed") {
				t.Errorf("Konflikt-Antwort ohne Code: %s", w.Body.String())
			}
			if nachher, _ := os.ReadFile(aboDatei(s, "b2-a", id)); !bytes.Equal(nachher, vorher) {
				t.Errorf("bei Konflikt wurde geschrieben")
			}
		})
	}
}

// Robustheit: falsche kind, kaputter Rumpf, unbekannte/ungueltige Kennung,
// falsche Art, fehlende Anmeldung -- nie wird etwas geschrieben.
func TestPlacements3122B2Robustheit(t *testing.T) {
	s := newTestStore(t)
	kern := neuerKern(t)
	r := placementsRouter(s, kern.srv.URL)
	seedPlacementsB2(t, s, "b2-a")
	vorher, _ := os.ReadFile(aboDatei(s, "b2-a", "trip-b2-a"))

	faelle := []struct {
		name, methode, pfad, body, user string
		status                          int
	}{
		{"GET ohne kind", http.MethodGet, "/api/briefings/trip-b2-a/placements", "", "b2-a", 400},
		{"PUT falsche kind", http.MethodPut, placementsPfad("trip-b2-a", "trip"), placementsB2Neu, "b2-a", 400},
		{"PUT Liste", http.MethodPut, placementsPfad("trip-b2-a", "route"), `[1, 2]`, "b2-a", 400},
		{"PUT kaputt", http.MethodPut, placementsPfad("trip-b2-a", "route"), `{"rows": [`, "b2-a", 400},
		{"PUT null", http.MethodPut, placementsPfad("trip-b2-a", "route"), `null`, "b2-a", 400},
		{"PUT Zahl", http.MethodPut, placementsPfad("trip-b2-a", "route"), `42`, "b2-a", 400},
		{"PUT Trip als Orte", http.MethodPut, placementsPfad("trip-b2-a", "vergleich"), placementsB2Neu, "b2-a", 404},
		{"GET Orte als Trip", http.MethodGet, placementsPfad("orte-b2-a", "route"), "", "b2-a", 404},
		{"PUT unbekannt", http.MethodPut, placementsPfad("gibt-es-nicht", "route"), placementsB2Neu, "b2-a", 404},
		{"GET unbekannt", http.MethodGet, placementsPfad("gibt-es-nicht", "vergleich"), "", "b2-a", 404},
		{"GET ungueltige Kennung", http.MethodGet, placementsPfad(".versteckt", "route"), "", "b2-a", 400},
		{"GET ohne Anmeldung", http.MethodGet, placementsPfad("trip-b2-a", "route"), "", "", 401},
		{"PUT ohne Anmeldung", http.MethodPut, placementsPfad("trip-b2-a", "route"), placementsB2Neu, "", 401},
	}
	for _, f := range faelle {
		if w := doReq(r, f.methode, f.pfad, f.body, "", f.user); w.Code != f.status {
			t.Errorf("%s: Status %d, erwartet %d (%s)", f.name, w.Code, f.status, w.Body.String())
		}
	}
	if kern.zahl() != 0 {
		t.Errorf("abgewiesene Anfragen haben den Kern %d-mal erreicht", kern.zahl())
	}
	if nachher, _ := os.ReadFile(aboDatei(s, "b2-a", "trip-b2-a")); !bytes.Equal(nachher, vorher) {
		t.Errorf("abgewiesene Anfragen haben die Datei veraendert")
	}
	if _, err := os.Stat(aboDatei(s, "b2-a", "gibt-es-nicht")); !os.IsNotExist(err) {
		t.Errorf("PUT auf unbekannte Kennung hat eine Datei angelegt")
	}
}

// T1: der Store wird an die Anmeldung gebunden, nie an eine user_id der Query.
// Beide Nutzer tragen DIESELBE Kennung -- ein an die Query gebundener Store
// schriebe die Datei von B.
func TestPlacements3122B2PutBindetAnAnmeldungNichtAnQuery(t *testing.T) {
	for _, f := range placementsB2Faelle {
		t.Run(f.kind, func(t *testing.T) {
			s := newTestStore(t)
			r := placementsRouter(s, neuerKern(t).srv.URL)
			id := f.praefix + "gleich"
			seedPlacementsB2Als(t, s, "b2-a", "trip-gleich", "orte-gleich")
			seedPlacementsB2Als(t, s, "b2-b", "trip-gleich", "orte-gleich")
			vorherB, _ := os.ReadFile(aboDatei(s, "b2-b", id))

			w := doReq(r, http.MethodPut, placementsPfad(id, f.kind)+"&user_id=b2-b", placementsB2Neu, "", "b2-a")
			if w.Code != http.StatusOK {
				t.Fatalf("PUT: %d %s", w.Code, w.Body.String())
			}
			var soll map[string]interface{}
			_ = json.Unmarshal([]byte(placementsB2Neu), &soll)
			gotA := roheDatei(t, aboDatei(s, "b2-a", id))["display_config"].(map[string]interface{})["placements"]
			if !reflect.DeepEqual(gotA, soll) {
				t.Errorf("geschrieben werden muss bei A (Anmeldung), dort steht %#v", gotA)
			}
			if nachherB, _ := os.ReadFile(aboDatei(s, "b2-b", id)); !bytes.Equal(nachherB, vorherB) {
				t.Errorf("Datei von B (user_id der Query) wurde veraendert")
			}
		})
	}
}

// T4: PUT ersetzt placements vollstaendig -- Schluessel und Zeilen des alten
// Stands, die im neuen fehlen, sind danach weg (kein tiefer Merge).
func TestPlacements3122B2PutErsetztVollstaendig(t *testing.T) {
	const kleiner = `{"version": 1, "rows": [{"metric_id": "gust"}]}`
	for _, f := range placementsB2Faelle {
		t.Run(f.kind, func(t *testing.T) {
			s := newTestStore(t)
			r := placementsRouter(s, neuerKern(t).srv.URL)
			seedPlacementsB2(t, s, "b2-a")
			id := f.praefix + "b2-a"
			alt := roheDatei(t, aboDatei(s, "b2-a", id))["display_config"].(map[string]interface{})["placements"].(map[string]interface{})
			if _, ok := alt["outlook_reports"]; !ok || len(alt["rows"].([]interface{})) != 2 {
				t.Fatalf("Ausgangslage: outlook_reports und zwei Zeilen erwartet, war %#v", alt)
			}
			if w := doReq(r, http.MethodPut, placementsPfad(id, f.kind), kleiner, "", "b2-a"); w.Code != http.StatusOK {
				t.Fatalf("PUT: %d %s", w.Code, w.Body.String())
			}
			var soll map[string]interface{}
			_ = json.Unmarshal([]byte(kleiner), &soll)
			got := roheDatei(t, aboDatei(s, "b2-a", id))["display_config"].(map[string]interface{})["placements"]
			if !reflect.DeepEqual(got, soll) {
				t.Errorf("placements nicht vollstaendig ersetzt: %#v", got)
			}
		})
	}
}

// T3 (Sperre, strukturell): solange die Briefing-Sperre gehalten wird,
// schreibt kein PUT. Aendert sich das Abo waehrenddessen, bekommen die
// wartenden PUTs mit dem alten Stempel 412 und ueberschreiben nichts.
func TestPlacements3122B2PutWartetAufSperreUndPrueftDanach(t *testing.T) {
	for _, f := range placementsB2Faelle {
		t.Run(f.kind, func(t *testing.T) {
			s := newTestStore(t)
			r := placementsRouter(s, neuerKern(t).srv.URL)
			seedPlacementsB2(t, s, "b2-a")
			id := f.praefix + "b2-a"
			datei := aboDatei(s, "b2-a", id)
			nutzerStore := s.WithUser("b2-a")
			fp, _ := nutzerStore.BriefingFingerprint(id)
			vorher, _ := os.ReadFile(datei)

			unlock := nutzerStore.LockBriefing(id)
			freigegeben := false
			defer func() {
				if !freigegeben {
					unlock()
				}
			}()
			const n = 4
			gestartet := make(chan struct{}, n)
			fertig := make(chan *httptest.ResponseRecorder, n)
			for i := 0; i < n; i++ {
				go func() {
					gestartet <- struct{}{}
					fertig <- doReq(r, http.MethodPut, placementsPfad(id, f.kind), placementsB2Neu, `"`+fp+`"`, "b2-a")
				}()
			}
			for i := 0; i < n; i++ {
				<-gestartet
			}
			// Unter gehaltener Sperre darf die Datei nicht angefasst werden
			// (ohne Sperre liefe der PUT sofort durch).
			frist := time.Now().Add(250 * time.Millisecond)
			for time.Now().Before(frist) {
				if jetzt, _ := os.ReadFile(datei); !bytes.Equal(jetzt, vorher) {
					t.Fatalf("PUT hat geschrieben, obwohl die Briefing-Sperre gehalten wurde")
				}
				select {
				case w := <-fertig:
					t.Fatalf("PUT hat unter gehaltener Sperre geantwortet: %d", w.Code)
				case <-time.After(5 * time.Millisecond):
				}
			}
			// Ein anderer Schreiber aendert das Abo, waehrend die PUTs warten.
			zwischen := bytes.Replace(vorher, []byte("Placements-Trip"), []byte("Zwischenzeitlich"), 1)
			zwischen = bytes.Replace(zwischen, []byte("Orte B2"), []byte("Zwischenzeitlich"), 1)
			if bytes.Equal(zwischen, vorher) {
				t.Fatal("Testaufbau: Zwischen-Aenderung ohne Wirkung")
			}
			if err := os.WriteFile(datei, zwischen, 0o660); err != nil {
				t.Fatal(err)
			}
			unlock()
			freigegeben = true
			for i := 0; i < n; i++ {
				if w := <-fertig; w.Code != http.StatusPreconditionFailed {
					t.Errorf("wartender PUT mit altem Stempel: Status %d, erwartet 412", w.Code)
				}
			}
			if nachher, _ := os.ReadFile(datei); !bytes.Equal(nachher, zwischen) {
				t.Errorf("wartender PUT hat den zwischenzeitlichen Stand ueberschrieben")
			}
		})
	}
}

// T3: gleichzeitige PUTs mit demselben If-Match -- genau einer schreibt, alle
// anderen bekommen 412.
func TestPlacements3122B2GleichzeitigePutsGenauEinerSchreibt(t *testing.T) {
	for _, f := range placementsB2Faelle {
		t.Run(f.kind, func(t *testing.T) {
			s := newTestStore(t)
			r := placementsRouter(s, neuerKern(t).srv.URL)
			seedPlacementsB2(t, s, "b2-a")
			id := f.praefix + "b2-a"
			fp, _ := s.WithUser("b2-a").BriefingFingerprint(id)

			const n = 10
			var wg sync.WaitGroup
			start := make(chan struct{})
			codes := make([]int, n)
			for i := 0; i < n; i++ {
				wg.Add(1)
				go func(i int) {
					defer wg.Done()
					<-start
					body := `{"version": 1, "rows": [{"metric_id": "wind"}], "schreiber": ` + strconv.Itoa(i) + `}`
					codes[i] = doReq(r, http.MethodPut, placementsPfad(id, f.kind), body, `"`+fp+`"`, "b2-a").Code
				}(i)
			}
			close(start)
			wg.Wait()
			ok, konflikt := 0, 0
			for _, c := range codes {
				switch c {
				case http.StatusOK:
					ok++
				case http.StatusPreconditionFailed:
					konflikt++
				}
			}
			if ok != 1 || konflikt != n-1 {
				t.Errorf("erwartet genau 1x200 und %dx412, war %v", n-1, codes)
			}
		})
	}
}

// F003: eine ueberlange Kennung ist ein Eingabefehler (400), kein 500.
func TestPlacements3122B2UeberlangeKennungIst400(t *testing.T) {
	s := newTestStore(t)
	kern := neuerKern(t)
	r := placementsRouter(s, kern.srv.URL)
	seedPlacementsB2(t, s, "b2-a")
	for _, laenge := range []int{300, 5000} {
		lang := strings.Repeat("x", laenge)
		for _, f := range placementsB2Faelle {
			for _, m := range []string{http.MethodGet, http.MethodPut} {
				body := ""
				if m == http.MethodPut {
					body = placementsB2Neu
				}
				if w := doReq(r, m, placementsPfad(lang, f.kind), body, "", "b2-a"); w.Code != http.StatusBadRequest {
					t.Errorf("%s %s Kennung mit %d Zeichen: Status %d, erwartet 400", m, f.kind, laenge, w.Code)
				}
			}
		}
		// Gleiches Verhalten wie die bestehende Abo-Route.
		if w := doReq(r, http.MethodGet, "/api/briefings/"+lang+"?kind=route", "", "", "b2-a"); w.Code != http.StatusBadRequest {
			t.Errorf("GET /api/briefings/{id} mit %d Zeichen: Status %d, erwartet 400", laenge, w.Code)
		}
	}
	if kern.zahl() != 0 {
		t.Errorf("ueberlange Kennung hat den Kern erreicht")
	}
}
