package handler

// Issue #3304 (Teil A von #3041; Spec feat_3304_was_steht_wo_vorschau,
// AC-4, AC-5, AC-6, AC-7, AC-8, AC-10): Vorschau der Tabelle "Was steht wo"
// fuer einen noch nicht angelegten Trip bzw. Orts-Vergleich.
// POST /api/briefings/placements/vorschau?kind=route|vergleich reicht den
// Entwurf mit der user_id der Anmeldung an den Python-Kern weiter. Der Kern ist
// ein Test-Server, der Pfad, Query und Koerper mitschreibt (Transport-Stub,
// keine Fachlogik).
//
//   go test ./internal/handler/ -run 3304

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"reflect"
	"strings"
	"sync"
	"testing"

	"github.com/go-chi/chi/v5"
)

const vorschauPfad3304 = "/api/briefings/placements/vorschau"

type vorschauAnfrage3304 struct {
	methode, pfad string
	query         map[string][]string
	koerper       []byte
}

type vorschauKern3304 struct {
	mu       sync.Mutex
	anfragen []vorschauAnfrage3304
	srv      *httptest.Server
}

func neuerVorschauKern3304(t *testing.T) *vorschauKern3304 {
	t.Helper()
	k := &vorschauKern3304{}
	k.srv = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		koerper, _ := io.ReadAll(r.Body)
		k.mu.Lock()
		k.anfragen = append(k.anfragen, vorschauAnfrage3304{
			methode: r.Method, pfad: r.URL.Path, query: r.URL.Query(), koerper: koerper})
		k.mu.Unlock()
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"stored": false, "kern": "vorschau"}`))
	}))
	t.Cleanup(k.srv.Close)
	return k
}

func (k *vorschauKern3304) zahl() int {
	k.mu.Lock()
	defer k.mu.Unlock()
	return len(k.anfragen)
}

// vorschauRouter3304: Vorschau-Route neben den bestehenden {id}-Routen der
// Tabelle, damit ein Fehlgriff auf den GET-/PUT-Handler sichtbar wird.
func vorschauRouter3304(t *testing.T, pythonURL string) *chi.Mux {
	t.Helper()
	s := newTestStore(t)
	r := chi.NewRouter()
	r.Post(vorschauPfad3304, BriefingPlacementsPreviewHandler(pythonURL))
	r.Get("/api/briefings/{id}/placements", BriefingPlacementsGetHandler(s, pythonURL))
	r.Put("/api/briefings/{id}/placements", BriefingPlacementsPutHandler(s, pythonURL))
	return r
}

const tripEntwurf3304 = `{"id": "entwurf-3304", "name": "Entwurf", "user_id": "fremd-b",
  "stages": [{"id": "S1", "name": "D1", "date": "2026-08-01",
    "waypoints": [{"id": "W1", "name": "P", "lat": 47.0, "lon": 11.0, "elevation_m": 500}]}],
  "display_config": {"metrics": [{"metric_id": "wind", "enabled": true}]}}`

const orteEntwurf3304 = `{"id": "entwurf-orte-3304", "name": "Orte", "kind": "vergleich",
  "user_id": "fremd-b", "location_ids": ["loc-b-1", "loc-a-1"],
  "display_config": {"active_metrics": [{"metric_id": "wind", "aggregation": "max"}]}}`

func fehlerCode3304(t *testing.T, w *httptest.ResponseRecorder) string {
	t.Helper()
	var body map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &body); err != nil {
		t.Fatalf("Fehlerantwort kein JSON: %q", w.Body.String())
	}
	code, _ := body["code"].(string)
	return code
}

func jsonGleich3304(t *testing.T, a, b []byte) bool {
	t.Helper()
	var x, y interface{}
	if err := json.Unmarshal(a, &x); err != nil {
		t.Fatalf("Koerper am Kern kein JSON: %q", a)
	}
	if err := json.Unmarshal(b, &y); err != nil {
		t.Fatal(err)
	}
	return reflect.DeepEqual(x, y)
}

// AC-5 / AC-10 / AC-4: Der Entwurf geht unveraendert per POST an den Kern-Pfad
// der Vorschau; user_id kommt allein aus der Anmeldung (Query-user_id von
// aussen wird ersetzt); der Pfad wird nie als Abo "placements" gelesen; die
// Antwort traegt keinen ETag.
func TestPlacementsVorschau3304ReichtEntwurfMitAnmeldungWeiter(t *testing.T) {
	for _, f := range []struct{ kind, entwurf string }{
		{"route", tripEntwurf3304}, {"vergleich", orteEntwurf3304},
	} {
		t.Run(f.kind, func(t *testing.T) {
			kern := neuerVorschauKern3304(t)
			r := vorschauRouter3304(t, kern.srv.URL)

			w := doReq(r, http.MethodPost, vorschauPfad3304+"?kind="+f.kind+"&user_id=fremd-b",
				f.entwurf, "", "nutzer-a")
			if w.Code != http.StatusOK {
				t.Fatalf("Vorschau: %d %s", w.Code, w.Body.String())
			}
			if !strings.Contains(w.Body.String(), `"kern": "vorschau"`) {
				t.Errorf("Antwort des Kerns nicht durchgereicht: %s", w.Body.String())
			}
			if et := w.Header().Get("ETag"); et != "" {
				t.Errorf("Vorschau darf keinen ETag tragen, hat %q", et)
			}
			if kern.zahl() != 1 {
				t.Fatalf("Kern %d-mal erreicht, erwartet genau einmal", kern.zahl())
			}
			a := kern.anfragen[0]
			if a.methode != http.MethodPost || a.pfad != vorschauPfad3304 {
				t.Errorf("Kern-Aufruf %s %s, erwartet POST %s", a.methode, a.pfad, vorschauPfad3304)
			}
			if got := a.query["user_id"]; !reflect.DeepEqual(got, []string{"nutzer-a"}) {
				t.Errorf("user_id zum Kern %v, erwartet nur den angemeldeten Nutzer", got)
			}
			if got := a.query["kind"]; !reflect.DeepEqual(got, []string{f.kind}) {
				t.Errorf("kind zum Kern %v", got)
			}
			if !jsonGleich3304(t, a.koerper, []byte(f.entwurf)) {
				t.Errorf("Entwurf am Kern veraendert: %s", a.koerper)
			}
		})
	}
}

// AC-6: ohne Anmeldung 401, der Kern wird nicht erreicht.
func TestPlacementsVorschau3304OhneAnmeldungIst401(t *testing.T) {
	kern := neuerVorschauKern3304(t)
	r := vorschauRouter3304(t, kern.srv.URL)
	w := doReq(r, http.MethodPost, vorschauPfad3304+"?kind=route", tripEntwurf3304, "", "")
	if w.Code != http.StatusUnauthorized {
		t.Errorf("ohne Anmeldung: Status %d, erwartet 401 (%s)", w.Code, w.Body.String())
	}
	if code := fehlerCode3304(t, w); code != "unauthorized" {
		t.Errorf("Code %q, erwartet unauthorized", code)
	}
	if kern.zahl() != 0 {
		t.Errorf("Kern ohne Anmeldung %d-mal erreicht", kern.zahl())
	}
}

// AC-7: kind fehlt oder unbekannt -> 400 kind_required, Kern nicht erreicht.
func TestPlacementsVorschau3304OhneGueltigeArtIst400(t *testing.T) {
	kern := neuerVorschauKern3304(t)
	r := vorschauRouter3304(t, kern.srv.URL)
	for _, q := range []string{"", "?kind=foo", "?kind=trip", "?kind="} {
		w := doReq(r, http.MethodPost, vorschauPfad3304+q, tripEntwurf3304, "", "nutzer-a")
		if w.Code != http.StatusBadRequest {
			t.Errorf("Query %q: Status %d, erwartet 400 (%s)", q, w.Code, w.Body.String())
			continue
		}
		if code := fehlerCode3304(t, w); code != "kind_required" {
			t.Errorf("Query %q: Code %q, erwartet kind_required", q, code)
		}
	}
	if kern.zahl() != 0 {
		t.Errorf("ungueltige Art hat den Kern %d-mal erreicht", kern.zahl())
	}
}

// AC-8: zu grosser Koerper -> 413 payload_too_large, kein JSON-Objekt -> 400
// bad_request; beides ohne Kern-Aufruf.
func TestPlacementsVorschau3304KoerperGrenzeUndKaputtesJSON(t *testing.T) {
	kern := neuerVorschauKern3304(t)
	r := vorschauRouter3304(t, kern.srv.URL)
	gross := `{"id": "x", "pad": "` + strings.Repeat("x", 300*1024) + `"}`

	faelle := []struct {
		name, body, code string
		status           int
	}{
		{"300 KB", gross, "payload_too_large", http.StatusRequestEntityTooLarge},
		{"kaputt", `{kaputt`, "bad_request", http.StatusBadRequest},
		{"Liste", `[]`, "bad_request", http.StatusBadRequest},
		{"null", `null`, "bad_request", http.StatusBadRequest},
		{"Zahl", `42`, "bad_request", http.StatusBadRequest},
		{"leer", ``, "bad_request", http.StatusBadRequest},
	}
	for _, f := range faelle {
		for _, kind := range []string{"route", "vergleich"} {
			w := doReq(r, http.MethodPost, vorschauPfad3304+"?kind="+kind, f.body, "", "nutzer-a")
			if w.Code != f.status {
				t.Errorf("%s/%s: Status %d, erwartet %d (%.200s)", f.name, kind, w.Code, f.status, w.Body.String())
				continue
			}
			if code := fehlerCode3304(t, w); code != f.code {
				t.Errorf("%s/%s: Code %q, erwartet %q", f.name, kind, code, f.code)
			}
		}
	}
	if kern.zahl() != 0 {
		t.Errorf("abgewiesene Koerper haben den Kern %d-mal erreicht", kern.zahl())
	}
}

// AC-8: ein Koerper knapp unter der Grenze (256 KB) geht durch.
func TestPlacementsVorschau3304KoerperUnterGrenzeGehtDurch(t *testing.T) {
	kern := neuerVorschauKern3304(t)
	r := vorschauRouter3304(t, kern.srv.URL)
	body := `{"id": "x", "pad": "` + strings.Repeat("x", 200*1024) + `"}`
	w := doReq(r, http.MethodPost, vorschauPfad3304+"?kind=route", body, "", "nutzer-a")
	if w.Code != http.StatusOK {
		t.Fatalf("200 KB: Status %d, erwartet 200 (%.200s)", w.Code, w.Body.String())
	}
	if kern.zahl() != 1 || len(kern.anfragen[0].koerper) != len(body) {
		t.Errorf("Koerper nicht vollstaendig weitergereicht")
	}
}

// Adversary F003: der Kern erhaelt GENAU die Query-Parameter kind und
// user_id (= angemeldeter Nutzer); weitere Client-Parameter, doppelte kind-
// und fremde user_id-Werte kommen nicht an.
func TestPlacementsVorschau3304KernErhaeltNurKindUndUserID(t *testing.T) {
	kern := neuerVorschauKern3304(t)
	r := vorschauRouter3304(t, kern.srv.URL)
	pfad := vorschauPfad3304 + "?kind=route&user_id=fremd&x=1&kind=vergleich&user_id=nutzer-b"
	w := doReq(r, http.MethodPost, pfad, tripEntwurf3304, "", "nutzer-a")
	if w.Code != http.StatusOK {
		t.Fatalf("Status %d, erwartet 200 (%.200s)", w.Code, w.Body.String())
	}
	if kern.zahl() != 1 {
		t.Fatalf("Kern-Aufrufe %d, erwartet 1", kern.zahl())
	}
	want := map[string][]string{"kind": {"route"}, "user_id": {"nutzer-a"}}
	if got := kern.anfragen[0].query; !reflect.DeepEqual(got, want) {
		t.Errorf("Query zum Kern %v, erwartet genau %v", got, want)
	}
}

// AC-8: Fehlerantworten des Kerns (422 invalid_preset) gehen unveraendert durch.
func TestPlacementsVorschau3304KernFehlerWirdDurchgereicht(t *testing.T) {
	kern := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusUnprocessableEntity)
		_, _ = w.Write([]byte(`{"code": "invalid_preset", "detail": "x"}`))
	}))
	t.Cleanup(kern.Close)
	r := vorschauRouter3304(t, kern.URL)
	w := doReq(r, http.MethodPost, vorschauPfad3304+"?kind=route", `{"stages": "kaputt"}`, "", "nutzer-a")
	if w.Code != http.StatusUnprocessableEntity {
		t.Errorf("Status %d, erwartet 422 vom Kern", w.Code)
	}
	if code := fehlerCode3304(t, w); code != "invalid_preset" {
		t.Errorf("Code %q, erwartet invalid_preset", code)
	}
}
