package handler

// Issue #2988 S2 (Spec rework_2988_ampel_ableitung, AC-7): POST
// /api/ampel/aufloesung prueft Anmeldung, Groesse und Form und reicht den
// unveraenderten Rumpf mit der user_id der Anmeldung an den Python-Kern. Der
// Kern ist ein Test-Server (Transport-Stub, keine Fachlogik), geteilt mit #3304.
//
//   go test ./internal/handler/ -run 2988

import (
	"net/http"
	"net/http/httptest"
	"reflect"
	"strings"
	"testing"
	"time"

	"github.com/go-chi/chi/v5"
)

const aufloesungPfad2988 = "/api/ampel/aufloesung"

const aufloesungRumpf2988 = `{"eintraege": [
  {"ampel": {"template": "wandern", "metrics": {"gust": {"upper": {"red": 77.5}}}}, "preset_name": null, "profil": "wandern"},
  {"metrics": [{"metric_id": "gust", "enabled": true}], "ampel": null},
  {"ampel": "ungueltiger Inhalt ist kein Formfehler"}]}`

func aufloesungRouter2988(pythonURL string) *chi.Mux {
	r := chi.NewRouter()
	r.Post(aufloesungPfad2988, AmpelAufloesungHandler(pythonURL))
	return r
}

func eintraege2988(n int) string {
	return `{"eintraege": [` + strings.TrimSuffix(strings.Repeat(`{"preset_name": "wandern"},`, n), ",") + `]}`
}

// AC-7: zwei Nutzer, derselbe Rumpf; je Anfrage genau die user_id der Anmeldung,
// Client-user_id und fremde Parameter kommen nicht an, der Rumpf unveraendert.
func TestAmpelAufloesung2988ZweiNutzerUndUnveraenderterRumpf(t *testing.T) {
	kern := neuerVorschauKern3304(t)
	r := aufloesungRouter2988(kern.srv.URL)
	for i, nutzer := range []string{"nutzer-a", "nutzer-b"} {
		pfad := aufloesungPfad2988 + "?user_id=default&user_id=fremd&x=1&kind=route"
		w := doReq(r, http.MethodPost, pfad, aufloesungRumpf2988, "", nutzer)
		if w.Code != http.StatusOK {
			t.Fatalf("%s: %d %s", nutzer, w.Code, w.Body.String())
		}
		if !strings.Contains(w.Body.String(), `"kern": "vorschau"`) {
			t.Errorf("Antwort des Kerns nicht durchgereicht: %s", w.Body.String())
		}
		if et := w.Header().Get("ETag"); et != "" {
			t.Errorf("Aufloesung darf keinen ETag tragen, hat %q", et)
		}
		if kern.zahl() != i+1 {
			t.Fatalf("Kern %d-mal erreicht, erwartet %d", kern.zahl(), i+1)
		}
		a := kern.anfragen[i]
		if a.methode != http.MethodPost || a.pfad != aufloesungPfad2988 {
			t.Errorf("Kern-Aufruf %s %s", a.methode, a.pfad)
		}
		if want := map[string][]string{"user_id": {nutzer}}; !reflect.DeepEqual(a.query, want) {
			t.Errorf("Query zum Kern %v, erwartet genau %v", a.query, want)
		}
		if !jsonGleich3304(t, a.koerper, []byte(aufloesungRumpf2988)) {
			t.Errorf("Rumpf am Kern veraendert: %s", a.koerper)
		}
	}
}

// AC-7: ohne Anmeldung 401 vor allem anderen (auch vor Groesse und Form).
func TestAmpelAufloesung2988OhneAnmeldungIst401(t *testing.T) {
	kern := neuerVorschauKern3304(t)
	r := aufloesungRouter2988(kern.srv.URL)
	gross := `{"pad": "` + strings.Repeat("x", 300*1024) + `"}`
	for name, body := range map[string]string{"gueltig": aufloesungRumpf2988, "kaputt": `{kaputt`, "gross": gross} {
		w := doReq(r, http.MethodPost, aufloesungPfad2988+"?user_id=nutzer-a", body, "", "")
		if w.Code != http.StatusUnauthorized {
			t.Errorf("%s: Status %d, erwartet 401", name, w.Code)
			continue
		}
		if code := fehlerCode3304(t, w); code != "unauthorized" {
			t.Errorf("%s: Code %q, erwartet unauthorized", name, code)
		}
	}
	if kern.zahl() != 0 {
		t.Errorf("Kern ohne Anmeldung %d-mal erreicht", kern.zahl())
	}
}

// AC-7: Formfehler 400 und Uebergroesse 413, der Kern wird nicht erreicht.
func TestAmpelAufloesung2988FormfehlerOhneKernAufruf(t *testing.T) {
	kern := neuerVorschauKern3304(t)
	r := aufloesungRouter2988(kern.srv.URL)
	faelle := []struct {
		name, body, code string
		status           int
	}{
		{"300 KB", `{"eintraege": [], "pad": "` + strings.Repeat("x", 300*1024) + `"}`, "payload_too_large", 413},
		{"leer", ``, "bad_request", 400},
		{"kaputt", `{kaputt`, "bad_request", 400},
		{"Liste", `[]`, "bad_request", 400},
		{"null", `null`, "bad_request", 400},
		{"Zahl", `42`, "bad_request", 400},
		{"ohne eintraege", `{}`, "bad_request", 400},
		{"eintraege null", `{"eintraege": null}`, "bad_request", 400},
		{"eintraege Objekt", `{"eintraege": {}}`, "bad_request", 400},
		{"eintraege Text", `{"eintraege": "x"}`, "bad_request", 400},
		{"33 Eintraege", eintraege2988(33), "bad_request", 400},
		{"Eintrag null", `{"eintraege": [null]}`, "bad_request", 400},
		{"Eintrag Text", `{"eintraege": ["x"]}`, "bad_request", 400},
		{"Eintrag Liste", `{"eintraege": [[]]}`, "bad_request", 400},
		{"zweiter Eintrag falsch", `{"eintraege": [{}, 5]}`, "bad_request", 400},
		{"preset_name Zahl", `{"eintraege": [{"preset_name": 7}]}`, "bad_request", 400},
		{"profil Wahrheitswert", `{"eintraege": [{"profil": true}]}`, "bad_request", 400},
		{"profil Objekt", `{"eintraege": [{"profil": {}}]}`, "bad_request", 400},
		{"metrics Objekt", `{"eintraege": [{"metrics": {}}]}`, "bad_request", 400},
		{"metrics Text", `{"eintraege": [{"metrics": "gust"}]}`, "bad_request", 400},
	}
	for _, f := range faelle {
		w := doReq(r, http.MethodPost, aufloesungPfad2988, f.body, "", "nutzer-a")
		if w.Code != f.status {
			t.Errorf("%s: Status %d, erwartet %d (%.200s)", f.name, w.Code, f.status, w.Body.String())
			continue
		}
		if code := fehlerCode3304(t, w); code != f.code {
			t.Errorf("%s: Code %q, erwartet %q", f.name, code, f.code)
		}
	}
	if kern.zahl() != 0 {
		t.Errorf("abgewiesene Ruempfe haben den Kern %d-mal erreicht", kern.zahl())
	}
}

// AC-7: die Grenzen selbst gehen durch (32 Eintraege, leere Liste, null-Felder,
// beliebiger Inhalt von ampel, 200 KB).
func TestAmpelAufloesung2988GueltigeGrenzfaelleErreichenDenKern(t *testing.T) {
	kern := neuerVorschauKern3304(t)
	r := aufloesungRouter2988(kern.srv.URL)
	faelle := []string{
		eintraege2988(32),
		`{"eintraege": []}`,
		`{"eintraege": [{}]}`,
		`{"eintraege": [{"ampel": null, "preset_name": null, "profil": null, "metrics": null}]}`,
		`{"eintraege": [{"ampel": 7}, {"ampel": []}, {"ampel": {"metrics": 1}}]}`,
		`{"eintraege": [{"metrics": [null, 7, {"metric_id": 3}]}]}`,
		`{"eintraege": [], "pad": "` + strings.Repeat("x", 200*1024) + `"}`,
	}
	for i, body := range faelle {
		w := doReq(r, http.MethodPost, aufloesungPfad2988, body, "", "nutzer-a")
		if w.Code != http.StatusOK {
			t.Errorf("Fall %d: Status %d (%.200s)", i, w.Code, w.Body.String())
			continue
		}
		if kern.zahl() != i+1 || string(kern.anfragen[i].koerper) != body {
			t.Fatalf("Fall %d: Rumpf nicht unveraendert am Kern", i)
		}
	}
}

// AC-7: Fehler des Kerns gehen unveraendert durch; ein haengender Kern endet am
// Zeitlimit der Vorschau-Proxys mit 502.
func TestAmpelAufloesung2988KernFehlerUndZeitlimit(t *testing.T) {
	kern := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusBadRequest)
		_, _ = w.Write([]byte(`{"code": "bad_request", "detail": "vom Kern"}`))
	}))
	t.Cleanup(kern.Close)
	w := doReq(aufloesungRouter2988(kern.URL), http.MethodPost, aufloesungPfad2988, aufloesungRumpf2988, "", "nutzer-a")
	if w.Code != http.StatusBadRequest || !strings.Contains(w.Body.String(), "vom Kern") {
		t.Errorf("Kern-Fehler nicht durchgereicht: %d %s", w.Code, w.Body.String())
	}

	frei := make(chan struct{})
	haengt := httptest.NewServer(http.HandlerFunc(func(http.ResponseWriter, *http.Request) { <-frei }))
	t.Cleanup(haengt.Close)
	t.Cleanup(func() { close(frei) })
	alt := previewProxyTimeout
	previewProxyTimeout = 50 * time.Millisecond
	t.Cleanup(func() { previewProxyTimeout = alt })
	w = doReq(aufloesungRouter2988(haengt.URL), http.MethodPost, aufloesungPfad2988, aufloesungRumpf2988, "", "nutzer-a")
	if w.Code != http.StatusBadGateway {
		t.Errorf("haengender Kern: Status %d, erwartet 502", w.Code)
	}
}
