package handler

// Issue #3275/#3237 (Spec feat_3237_altpfad_entfernen, AC-1, AC-2, AC-4,
// AC-10): die Anlage eines Trips und eines Orts-Vergleichs schreibt sofort
// die volle Tabelle "Was steht wo". Go bildet KEINE Zeilen selbst: nach dem
// Speichern fragt die Anlage den Kern (GET .../placements/erstanlage, gleiche
// Python-Funktion fuer beide Arten) und schreibt dessen "placements" per
// Read-Modify-Write ins Abo. Mitgeschickte placements mit rows bleiben
// unangetastet (kein Kern-Aufruf). Ist der Kern nicht erreichbar, bleibt die
// Anlage gueltig (201): ein Abo ohne rows liest dieselbe Grundauswahl-Tabelle.
// Das Speichern der Tabelle (PUT) fragt den Kern nicht mehr nach Begleitfeldern
// (show_stability_off entfaellt, AC-4).
//
// Echter Store, echte Dateien, zwei Nutzer. Der Kern ist ein Test-Server mit
// fester Antwort, der mitschreibt, was ankommt -- keine Fachlogik.
//
//   go test ./internal/handler/ -run Anlage3237

import (
	"encoding/json"
	"net/http"
	"os"
	"reflect"
	"testing"

	"github.com/go-chi/chi/v5"

	"github.com/henemm/gregor-api/internal/store"
)

// kernTabelle3237 ist die Antwort des Kerns (Form wie
// get_placements_erstanlage: {"placements": {...}}).
const kernTabelle3237 = `{"placements": {"version": 1, "rows": [
  {"metric_id": "wind", "places": {"email": true, "telegram": true, "sms": true, "outlook": true}},
  {"metric_id": "gust", "places": {"email": true, "telegram": true, "sms": true, "outlook": true}}],
  "outlook_reports": ["evening"]}}`

func anlageRouter3237(s *store.Store, pythonURL string) *chi.Mux {
	r := chi.NewRouter()
	r.Post("/api/trips", CreateTripHandler(s, pythonURL))
	r.Post("/api/compare/presets", CreateComparePresetHandler(s, pythonURL))
	r.Put("/api/briefings/{id}/placements", BriefingPlacementsPutHandler(s, pythonURL))
	return r
}

func tripBody3237(id string, extraDC map[string]interface{}) string {
	dc := map[string]interface{}{
		"metrics": []interface{}{map[string]interface{}{"metric_id": "wind", "enabled": true}},
	}
	for k, v := range extraDC {
		dc[k] = v
	}
	body := map[string]interface{}{
		"id": id, "name": "Anlage 3237",
		"stages": []interface{}{map[string]interface{}{
			"id": "S1", "name": "D1", "date": "2026-08-01",
			"waypoints": []interface{}{map[string]interface{}{
				"id": "W1", "name": "P", "lat": 47.0, "lon": 11.0, "elevation_m": 800}},
		}},
		"display_config": dc,
	}
	buf, _ := json.Marshal(body)
	return string(buf)
}

func orteBody3237(id string) string {
	body := orteBody3155("Orte 3237", slots3155(true, false))
	body["id"] = id
	buf, _ := json.Marshal(body)
	return string(buf)
}

func gespeicherteTabelle3237(t *testing.T, s *store.Store, user, id string) map[string]interface{} {
	t.Helper()
	dc, _ := roheDatei(t, aboDatei(s, user, id))["display_config"].(map[string]interface{})
	tab, _ := dc["placements"].(map[string]interface{})
	return tab
}

func kernSoll3237(t *testing.T) map[string]interface{} {
	t.Helper()
	var antwort map[string]interface{}
	if err := json.Unmarshal([]byte(kernTabelle3237), &antwort); err != nil {
		t.Fatal(err)
	}
	return antwort["placements"].(map[string]interface{})
}

func TestAnlage3237TripUndOrteSchreibenKernTabelleZweiNutzer(t *testing.T) {
	faelle := []struct {
		name, pfad, kind, id string
		body                 func(string) string
	}{
		{"trip", "/api/trips", "route", "t3237", func(id string) string { return tripBody3237(id, nil) }},
		{"orte", "/api/compare/presets", "vergleich", "o3237", orteBody3237},
	}
	for _, f := range faelle {
		t.Run(f.name, func(t *testing.T) {
			s := newTestStore(t)
			kern := neuerErstanlageKern(t, http.StatusOK, []byte(kernTabelle3237))
			r := anlageRouter3237(s, kern.srv.URL)
			for _, nutzer := range []string{"a3237", "b3237"} {
				w := doReq(r, http.MethodPost, f.pfad+"?user_id=fremd", f.body(f.id), "", nutzer)
				if w.Code != http.StatusCreated {
					t.Fatalf("%s POST: %d %s", nutzer, w.Code, w.Body.String())
				}
			}
			if len(kern.anfragen) != 2 {
				t.Fatalf("Kern %d-mal gefragt, erwartet einmal je Anlage", len(kern.anfragen))
			}
			for i, nutzer := range []string{"a3237", "b3237"} {
				a := kern.anfragen[i]
				if a.Path != "/api/briefings/"+f.id+"/placements/erstanlage" || a.Query().Get("kind") != f.kind {
					t.Errorf("Abfrage beim Kern: %s", a.String())
				}
				if got := a.Query()["user_id"]; !reflect.DeepEqual(got, []string{nutzer}) {
					t.Errorf("user_id zum Kern %v, erwartet nur %s (nie default/fremd)", got, nutzer)
				}
				if got := gespeicherteTabelle3237(t, s, nutzer, f.id); !reflect.DeepEqual(got, kernSoll3237(t)) {
					t.Errorf("%s: gespeicherte Tabelle %#v, erwartet die Kern-Antwort", nutzer, got)
				}
			}
		})
	}
}

// Read-Modify-Write: die Anlage-Tabelle ergaenzt das Abo, die uebrigen
// Felder (Grundauswahl, Etappen) bleiben so, wie die Anlage sie geschrieben hat.
func TestAnlage3237TabelleLaesstUebrigeFelderStehen(t *testing.T) {
	sOhne, sMit := newTestStore(t), newTestStore(t)
	ohne := anlageRouter3237(sOhne, "http://127.0.0.1:1")
	kern := neuerErstanlageKern(t, http.StatusOK, []byte(kernTabelle3237))
	mit := anlageRouter3237(sMit, kern.srv.URL)
	for _, r := range []*chi.Mux{ohne, mit} {
		if w := doReq(r, http.MethodPost, "/api/trips", tripBody3237("t3237", nil), "", "a3237"); w.Code != http.StatusCreated {
			t.Fatalf("POST: %d %s", w.Code, w.Body.String())
		}
	}
	a, b := roheDatei(t, aboDatei(sOhne, "a3237", "t3237")), roheDatei(t, aboDatei(sMit, "a3237", "t3237"))
	for _, m := range []map[string]interface{}{a, b} {
		ohnePlacements(m)
		delete(m, "created_at")
		delete(m, "updated_at")
	}
	if !reflect.DeepEqual(a, b) {
		t.Errorf("Anlage-Tabelle hat andere Felder veraendert:\nohne %#v\nmit  %#v", a, b)
	}
}

func TestAnlage3237MitgeschickteTabelleBleibtOhneKernAufruf(t *testing.T) {
	s := newTestStore(t)
	kern := neuerErstanlageKern(t, http.StatusOK, []byte(kernTabelle3237))
	r := anlageRouter3237(s, kern.srv.URL)
	eigene := map[string]interface{}{"version": float64(1), "rows": []interface{}{
		map[string]interface{}{"metric_id": "wind", "places": map[string]interface{}{"sms": false}}},
		"outlook_reports": []interface{}{"morning"}}
	body := tripBody3237("t3237", map[string]interface{}{"placements": eigene})
	if w := doReq(r, http.MethodPost, "/api/trips", body, "", "a3237"); w.Code != http.StatusCreated {
		t.Fatalf("POST: %d %s", w.Code, w.Body.String())
	}
	if len(kern.anfragen) != 0 {
		t.Errorf("Kern gefragt trotz mitgeschickter Tabelle: %v", kern.anfragen)
	}
	if got := gespeicherteTabelle3237(t, s, "a3237", "t3237"); !reflect.DeepEqual(got, eigene) {
		t.Errorf("mitgeschickte Tabelle veraendert: %#v", got)
	}
}

func TestAnlage3237KernNichtErreichbarAnlageBleibtGueltig(t *testing.T) {
	for _, f := range []struct{ pfad, id, body string }{
		{"/api/trips", "t3237", tripBody3237("t3237", nil)},
		{"/api/compare/presets", "o3237", orteBody3237("o3237")},
	} {
		s := newTestStore(t)
		r := anlageRouter3237(s, "http://127.0.0.1:1")
		if w := doReq(r, http.MethodPost, f.pfad, f.body, "", "a3237"); w.Code != http.StatusCreated {
			t.Fatalf("%s: Anlage bei Kern-Ausfall %d %s, erwartet 201", f.pfad, w.Code, w.Body.String())
		}
		if _, err := os.Stat(aboDatei(s, "a3237", f.id)); err != nil {
			t.Errorf("%s: Abo nicht gespeichert: %v", f.pfad, err)
		}
		if tab := gespeicherteTabelle3237(t, s, "a3237", f.id); tab != nil {
			if _, hatRows := tab["rows"]; hatRows {
				t.Errorf("%s: ohne Kern darf Go keine Zeilen erfinden: %#v", f.pfad, tab)
			}
		}
	}
}

// AC-4: das Speichern der Tabelle fragt den Kern nicht mehr nach
// Begleitfeldern und laesst report_config unveraendert.
func TestAnlage3237PutFragtKernNichtMehrNachBegleitfeldern(t *testing.T) {
	s := newTestStore(t)
	kern := neuerErstanlageKern(t, http.StatusOK, aufgezeichneteAntwort(t))
	r := anlageRouter3237(s, kern.srv.URL)
	seedAltTrip(t, s, "a3237", "alt")
	vorher := roheDatei(t, aboDatei(s, "a3237", "alt"))
	if w := doReq(r, http.MethodPut, placementsPfad("alt", "route"), placementsB2Neu, "", "a3237"); w.Code != http.StatusOK {
		t.Fatalf("PUT: %d %s", w.Code, w.Body.String())
	}
	if len(kern.anfragen) != 0 {
		t.Errorf("PUT hat den Kern gefragt: %v", kern.anfragen)
	}
	nachher := roheDatei(t, aboDatei(s, "a3237", "alt"))
	if !reflect.DeepEqual(nachher["report_config"], vorher["report_config"]) {
		t.Errorf("report_config veraendert: %#v", nachher["report_config"])
	}
}
