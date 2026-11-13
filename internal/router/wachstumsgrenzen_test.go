package router

// Issue #2961 (Spec security_haertung_2026_11_go_schnittstellen.md AC-10):
// Wachstumsgrenzen fuer gespeicherte Trips, Orte und Ortsvergleiche, gemessen
// am echten Router und an der Datei auf der Platte. Bestandsdaten bleiben
// lesbar und bestehende Schluessel schreibbar.

import (
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

func vieleSchluessel(n int, praefix string) string {
	m := map[string]int{}
	for i := 0; i < n; i++ {
		m[fmt.Sprintf("%s%d", praefix, i)] = i
	}
	b, _ := json.Marshal(m)
	return string(b)
}

func erwarteCode(t *testing.T, fall string, w interface {
	Result() *http.Response
}, status int, code string) {
	t.Helper()
	res := w.Result()
	var body map[string]any
	_ = json.NewDecoder(res.Body).Decode(&body)
	if res.StatusCode != status || body["code"] != code {
		t.Fatalf("%s: erwartet %d/%s, bekommen %d/%v", fall, status, code, res.StatusCode, body["code"])
	}
	if msg, _ := body["message"].(string); msg == "" || strings.HasPrefix(msg, "Unbekannter Fehler") {
		t.Fatalf("%s: kein Katalogtext: %v", fall, body)
	}
}

func seedGrenzTrip(t *testing.T, s *store.Store, uid string, display map[string]interface{}) {
	t.Helper()
	trip := model.Trip{ID: "grenz-1", Name: "Grenz", DisplayConfig: display,
		Stages: []model.Stage{{ID: "S1", Name: "T1", Date: "2026-05-01",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47, Lon: 11, ElevationM: 500}}}}}
	if err := s.WithUser(uid).SaveTrip(&trip); err != nil {
		t.Fatalf("SaveTrip: %v", err)
	}
}

func tripDatei(t *testing.T, s *store.Store, uid string) []byte {
	t.Helper()
	b, err := os.ReadFile(filepath.Join(s.WithUser(uid).BriefingsDir(), "grenz-1.json"))
	if err != nil {
		t.Fatal(err)
	}
	return b
}

func TestWachstumsgrenzen_ConfigSchluessel(t *testing.T) {
	e := neueBremsUmgebung(t, nil)
	c := e.konto(t, "mia-grenze", "de")
	seedGrenzTrip(t, e.s, "mia-grenze", map[string]interface{}{"LegacyKey": 1, "metrics": []interface{}{}})
	vorher := tripDatei(t, e.s, "mia-grenze")

	erwarteCode(t, "201 neue Schluessel", e.rufe(t, http.MethodPut, "/api/trips/grenz-1/weather-config",
		[]byte(vieleSchluessel(201, "k")), c), http.StatusBadRequest, "limit_exceeded")
	erwarteCode(t, "ungueltiger Schluessel", e.rufe(t, http.MethodPut, "/api/trips/grenz-1/weather-config",
		[]byte(`{"Boeser Schluessel!":1}`), c), http.StatusBadRequest, "limit_exceeded")
	erwarteCode(t, "Trip-PUT report_config", e.rufe(t, http.MethodPut, "/api/trips/grenz-1",
		[]byte(`{"report_config":`+vieleSchluessel(201, "r")+`}`), c), http.StatusBadRequest, "limit_exceeded")
	if string(tripDatei(t, e.s, "mia-grenze")) != string(vorher) {
		t.Fatal("abgelehnte Aenderung hat die Datei veraendert")
	}

	// Bestandsschutz: vorhandener Alt-Schluessel bleibt schreibbar, 198 neue
	// zulaessige Schluessel passen noch (2 + 198 = 200).
	if w := e.rufe(t, http.MethodPut, "/api/trips/grenz-1/weather-config", []byte(`{"LegacyKey":2}`), c); w.Code != http.StatusOK {
		t.Fatalf("Bestandsschluessel: %d %s", w.Code, w.Body.String())
	}
	if w := e.rufe(t, http.MethodPut, "/api/trips/grenz-1/weather-config", []byte(vieleSchluessel(198, "k")), c); w.Code != http.StatusOK {
		t.Fatalf("200 Schluessel muessen passen: %d %s", w.Code, w.Body.String())
	}
	erwarteCode(t, "201. Schluessel", e.rufe(t, http.MethodPut, "/api/trips/grenz-1/weather-config",
		[]byte(`{"noch_einer":1}`), c), http.StatusBadRequest, "limit_exceeded")
}

func TestWachstumsgrenzen_EtappenUndWegpunkte(t *testing.T) {
	e := neueBremsUmgebung(t, nil)
	c := e.konto(t, "nils-grenze", "de")
	seedGrenzTrip(t, e.s, "nils-grenze", nil)

	stages := func(n, wp int) string {
		var st []model.Stage
		for i := 0; i < n; i++ {
			s := model.Stage{ID: fmt.Sprintf("S%d", i), Name: "T", Date: "2026-05-01"}
			for j := 0; j < wp; j++ {
				s.Waypoints = append(s.Waypoints, model.Waypoint{ID: fmt.Sprintf("W%d", j), Name: "P", Lat: 47, Lon: 11, ElevationM: 1})
			}
			st = append(st, s)
		}
		b, _ := json.Marshal(st)
		return string(b)
	}
	erwarteCode(t, "101 Etappen (PUT)", e.rufe(t, http.MethodPut, "/api/trips/grenz-1",
		[]byte(`{"stages":`+stages(101, 1)+`}`), c), http.StatusBadRequest, "limit_exceeded")
	erwarteCode(t, "501 Wegpunkte (PUT)", e.rufe(t, http.MethodPut, "/api/trips/grenz-1",
		[]byte(`{"stages":`+stages(1, 501)+`}`), c), http.StatusBadRequest, "limit_exceeded")
	erwarteCode(t, "101 Etappen (POST)", e.rufe(t, http.MethodPost, "/api/trips",
		[]byte(`{"id":"neu-grenz","name":"N","stages":`+stages(101, 1)+`}`), c), http.StatusBadRequest, "limit_exceeded")
	if w := e.rufe(t, http.MethodPut, "/api/trips/grenz-1", []byte(`{"stages":`+stages(100, 5)+`}`), c); w.Code != http.StatusOK {
		t.Fatalf("100 Etappen muessen passen: %d %s", w.Code, w.Body.String())
	}
}

func TestWachstumsgrenzen_DateigroesseUndBestandLesbar(t *testing.T) {
	e := neueBremsUmgebung(t, nil)
	c := e.konto(t, "olga-grenze", "de")
	seedGrenzTrip(t, e.s, "olga-grenze", nil)
	vorher := tripDatei(t, e.s, "olga-grenze")

	// Ein einzelner Rumpf ueber der globalen Rumpfgrenze (1 MB) scheitert schon
	// an der Schutzschicht des Routers, bevor der Store gefragt wird.
	gross := `{"riesig":"` + strings.Repeat("x", store.MaxEntityFileBytes) + `"}`
	erwarteCode(t, "Rumpf > 1 MB", e.rufe(t, http.MethodPut, "/api/trips/grenz-1/weather-config", []byte(gross), c),
		http.StatusRequestEntityTooLarge, "payload_too_large")
	if string(tripDatei(t, e.s, "olga-grenze")) != string(vorher) {
		t.Fatal("zu grosser Rumpf hat die Datei veraendert")
	}

	// Die Dateigrenze (2 MB) greift, wenn eine fast volle Bestandsdatei durch
	// einen zulaessig grossen Rumpf ueber die Grenze wachsen wuerde.
	var fastVoll map[string]interface{}
	_ = json.Unmarshal(vorher, &fastVoll)
	fastVoll["display_config"] = map[string]interface{}{"bestand": strings.Repeat("b", store.MaxEntityFileBytes-(600<<10))}
	fv, _ := json.Marshal(fastVoll)
	if err := os.WriteFile(filepath.Join(e.s.WithUser("olga-grenze").BriefingsDir(), "grenz-1.json"), fv, 0o600); err != nil {
		t.Fatal(err)
	}
	vorher = tripDatei(t, e.s, "olga-grenze")
	zuwachs := `{"riesig":"` + strings.Repeat("x", 900<<10) + `"}`
	erwarteCode(t, "Datei > 2 MB", e.rufe(t, http.MethodPut, "/api/trips/grenz-1/weather-config", []byte(zuwachs), c),
		http.StatusRequestEntityTooLarge, "entity_too_large")
	if string(tripDatei(t, e.s, "olga-grenze")) != string(vorher) {
		t.Fatal("zu grosse Aenderung hat die Datei veraendert")
	}

	// Eine (z. B. aelter entstandene) Bestandsdatei ueber der Grenze bleibt lesbar.
	var roh map[string]interface{}
	_ = json.Unmarshal(vorher, &roh)
	roh["display_config"] = map[string]interface{}{"altlast": strings.Repeat("y", store.MaxEntityFileBytes)}
	b, _ := json.Marshal(roh)
	if err := os.WriteFile(filepath.Join(e.s.WithUser("olga-grenze").BriefingsDir(), "grenz-1.json"), b, 0o600); err != nil {
		t.Fatal(err)
	}
	if w := e.rufe(t, http.MethodGet, "/api/trips/grenz-1", nil, c); w.Code != http.StatusOK {
		t.Fatalf("Bestandsdatei > 2 MB nicht mehr lesbar: %d", w.Code)
	}
}

func TestWachstumsgrenzen_OrtUndOrtsvergleich(t *testing.T) {
	e := neueBremsUmgebung(t, nil)
	c := e.konto(t, "paul-grenze", "de")
	if err := e.s.WithUser("paul-grenze").SaveLocation(model.Location{ID: "ort-1", Name: "Ort", Lat: 47, Lon: 11}); err != nil {
		t.Fatal(err)
	}
	erwarteCode(t, "Ort weather-config", e.rufe(t, http.MethodPut, "/api/locations/ort-1/weather-config",
		[]byte(vieleSchluessel(201, "k")), c), http.StatusBadRequest, "limit_exceeded")

	w := e.rufe(t, http.MethodPost, "/api/compare/presets", []byte(`{"name":"V","location_ids":["ort-1"],"schedule":"manual","profil":"allgemein","forecast_hours":48,"hour_from":6,"hour_to":20}`), c)
	if w.Code != http.StatusCreated && w.Code != http.StatusOK {
		t.Fatalf("Preset-Anlage: %d %s", w.Code, w.Body.String())
	}
	var p struct {
		ID string `json:"id"`
	}
	_ = json.Unmarshal(w.Body.Bytes(), &p)
	erwarteCode(t, "Ortsvergleich display_config", e.rufe(t, http.MethodPut, "/api/compare/presets/"+p.ID,
		[]byte(`{"display_config":`+vieleSchluessel(201, "k")+`}`), c), http.StatusBadRequest, "limit_exceeded")
	erwarteCode(t, "Ortsvergleich ueber /api/briefings", e.rufe(t, http.MethodPut, "/api/briefings/"+p.ID+"?kind=vergleich",
		[]byte(`{"display_config":`+vieleSchluessel(201, "k")+`}`), c), http.StatusBadRequest, "limit_exceeded")
}
