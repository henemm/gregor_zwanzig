package handler_test

// TDD RED — Issue #2283 Scheibe S4: kind-neutrale Alarm-Vorschau
// POST /api/briefings/{id}/alert-preview?kind=route|vergleich.
//
// Spec: docs/specs/modules/shared_preview_tab.md (AC-16 Go-Teil).
//
// Bauart wie briefing_preview_test.go: echter router.New(...) + echter
// httptest-Python-Core, der jede Anfrage mitschreibt (Helfer newVBUpstream,
// newVBEnv, vbAssertSingleUserID, vbInvalidIDs stehen dort).
//
// Python-Ziel (vom Python-Teil von S4 festgelegt), beide kinds:
//   POST /api/briefings/{id}/alert-preview?kind=<kind>&user_id=<auth>
// Python prueft kind selbst. Der Alarm-Koerper (changes/onset/official/...)
// geht unveraendert durch. Die Alt-Route /api/trips/{id}/alert-preview bleibt
// auf ihrem bisherigen Python-Ziel.

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

const vbAlertBody = `{"onset":{"kind":"rain","minutes":20}}`

func TestBriefingAlertPreview_KindPflicht_400OhneUpstream(t *testing.T) {
	py := newVBUpstream(t, nil)
	env := newVBEnv(t, py.srv.URL, "alice")

	cases := []struct {
		name, query  string
		wantStatus   int
		wantUpstream int
		wantCode     string
	}{
		{"kind fehlt", "", 400, 0, "kind_required"},
		{"kind leer", "?kind=", 400, 0, "kind_required"},
		{"kind falsch trip", "?kind=trip", 400, 0, "kind_required"},
		{"kind falsch compare", "?kind=compare", 400, 0, "kind_required"},
		{"Kontrolle route", "?kind=route", 200, 1, ""},
		{"Kontrolle vergleich", "?kind=vergleich", 200, 1, ""},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			py.reset()
			w := env.do(t, "POST", "/api/briefings/t-2283/alert-preview"+c.query, "alice", vbAlertBody)
			if w.Code != c.wantStatus {
				t.Errorf("Status %d, erwartet %d (body=%q)", w.Code, c.wantStatus, w.Body.String())
			}
			if c.wantCode != "" && !strings.Contains(w.Body.String(), `"`+c.wantCode+`"`) {
				t.Errorf("Body %q enthaelt keinen Fehlercode %q", w.Body.String(), c.wantCode)
			}
			if got := py.count(); got != c.wantUpstream {
				t.Errorf("Python-Core %d-mal erreicht, erwartet %d", got, c.wantUpstream)
			}
		})
	}
}

func TestBriefingAlertPreview_UngueltigeID_400OhneUpstream(t *testing.T) {
	py := newVBUpstream(t, nil)
	env := newVBEnv(t, py.srv.URL, "alice")

	for _, id := range vbInvalidIDs {
		vbAssertIDReachesValidation(t, env, id, "alice")
		for _, kind := range []string{"route", "vergleich"} {
			t.Run(kind+"/"+id, func(t *testing.T) {
				py.reset()
				w := env.do(t, "POST", "/api/briefings/"+id+"/alert-preview?kind="+kind, "alice", vbAlertBody)
				if w.Code != http.StatusBadRequest {
					t.Errorf("Status %d, erwartet 400 bei ungueltiger ID %q (body=%q)", w.Code, id, w.Body.String())
				}
				if got := py.count(); got != 0 {
					t.Errorf("Python-Core %d-mal erreicht — ungueltige ID darf nicht weitergereicht werden", got)
				}
			})
		}
	}
}

func TestBriefingAlertPreview_ZweiNutzer_UserIDNurAusAnmeldung(t *testing.T) {
	py := newVBUpstream(t, nil)
	env := newVBEnv(t, py.srv.URL, "alice", "bob")

	for _, kind := range []string{"route", "vergleich"} {
		for _, pair := range [][2]string{{"alice", "bob"}, {"bob", "alice"}} {
			self, other := pair[0], pair[1]
			for _, inject := range []string{"", "&user_id=" + other, "&user_id=default"} {
				t.Run(kind+"/"+self+"/inject="+inject, func(t *testing.T) {
					py.reset()
					w := env.do(t, "POST", "/api/briefings/b-2283/alert-preview?kind="+kind+inject, self, vbAlertBody)
					if w.Code != http.StatusOK {
						t.Fatalf("Status %d, erwartet 200 (body=%q)", w.Code, w.Body.String())
					}
					c, ok := py.last()
					if !ok {
						t.Fatalf("Python-Core nicht erreicht")
					}
					vbAssertSingleUserID(t, c, self)
				})
			}
		}
	}
}

func TestBriefingAlertPreview_FremdeID_404DurchgereichtOhneFremdeDaten(t *testing.T) {
	owned := map[string]string{"trip-alice": "alice", "trip-bob": "bob", "cmp-alice": "alice", "cmp-bob": "bob"}
	py := newVBUpstream(t, vbOwnershipResponder(owned))
	env := newVBEnv(t, py.srv.URL, "alice", "bob")

	cases := []struct{ kind, own, foreign string }{
		{"route", "trip-alice", "trip-bob"},
		{"vergleich", "cmp-alice", "cmp-bob"},
	}
	for _, c := range cases {
		t.Run(c.kind, func(t *testing.T) {
			py.reset()
			w := env.do(t, "POST", "/api/briefings/"+c.foreign+"/alert-preview?kind="+c.kind+"&user_id=bob", "alice", vbAlertBody)
			if w.Code != http.StatusNotFound {
				t.Errorf("fremde ID: Status %d, erwartet 404 (body=%q)", w.Code, w.Body.String())
			}
			if strings.Contains(w.Body.String(), "Daten-von-bob") {
				t.Errorf("Antwort enthaelt Daten von bob: %q", w.Body.String())
			}
			if py.count() < 1 {
				t.Errorf("404 kam nicht vom Python-Core (Upstream nie erreicht) — kein Beleg fuer Isolation")
			}
			py.reset()
			w = env.do(t, "POST", "/api/briefings/"+c.own+"/alert-preview?kind="+c.kind, "alice", vbAlertBody)
			if w.Code != http.StatusOK || !strings.Contains(w.Body.String(), "Daten-von-alice") {
				t.Errorf("eigener Eintrag: Status %d body=%q, erwartet 200 mit eigenen Daten", w.Code, w.Body.String())
			}
		})
	}
}

func TestBriefingAlertPreview_KindLenktAufPythonZiel_KoerperUnveraendert(t *testing.T) {
	const answer = `{"email":{"subject":"Alarm"},"sms":{"text":"Regen in 20 min"}}`
	py := newVBUpstream(t, func(vbUpstreamCall) (int, string, string) {
		return 200, "application/json", answer
	})
	env := newVBEnv(t, py.srv.URL, "alice")

	cases := []struct{ kind, id, wantPath string }{
		{"route", "gr20", "/api/briefings/gr20/alert-preview"},
		{"vergleich", "cmp-7", "/api/briefings/cmp-7/alert-preview"},
	}
	for _, c := range cases {
		t.Run(c.kind, func(t *testing.T) {
			py.reset()
			w := env.do(t, "POST", "/api/briefings/"+c.id+"/alert-preview?kind="+c.kind, "alice", vbAlertBody)
			if w.Code != 200 {
				t.Fatalf("Status %d, erwartet 200 (body=%q)", w.Code, w.Body.String())
			}
			up, _ := py.last()
			if up.Method != "POST" || up.Path != c.wantPath {
				t.Errorf("Upstream %s %s, erwartet POST %s", up.Method, up.Path, c.wantPath)
			}
			if up.Query.Get("kind") != c.kind {
				t.Errorf("kind=%s nicht an Python weitergereicht (Upstream-Query %v)", c.kind, up.Query)
			}
			if up.Body != vbAlertBody {
				t.Errorf("Alarm-Koerper veraendert: %q, erwartet %q", up.Body, vbAlertBody)
			}
			if !strings.HasPrefix(up.ContentType, "application/json") {
				t.Errorf("Content-Type %q nicht weitergereicht", up.ContentType)
			}
			if w.Body.String() != answer {
				t.Errorf("Antwort veraendert: %q", w.Body.String())
			}
		})
	}
}

// AC-16: POST /api/trips/{id}/alert-preview bleibt Delegate mit unveraendertem
// Verhalten — dieselbe Eingabe ueber Alt-Route und kind=route kommt beim
// Python-Core gleich an und gleich zurueck. Grenze wie AC-5: belegt gleiches
// Verhalten, nicht dieselbe Funktion.
func TestBriefingAlertPreview_TripAltRouteIstDelegate(t *testing.T) {
	py := newVBUpstream(t, func(vbUpstreamCall) (int, string, string) {
		return 200, "application/json; charset=utf-8", `{"email":{"subject":"Alarm"}}`
	})
	env := newVBEnv(t, py.srv.URL, "alice")

	py.reset()
	wAlt := env.do(t, "POST", "/api/trips/gr20/alert-preview?user_id=mallory", "alice", vbAlertBody)
	alt, okAlt := py.last()
	py.reset()
	wNeu := env.do(t, "POST", "/api/briefings/gr20/alert-preview?kind=route&user_id=mallory", "alice", vbAlertBody)
	neu, okNeu := py.last()

	if !okAlt {
		t.Fatalf("Alt-Route /api/trips/{id}/alert-preview erreicht den Python-Core nicht mehr (Status %d)", wAlt.Code)
	}
	if !okNeu {
		t.Fatalf("Buendelweg kind=route erreicht den Python-Core nicht (Status %d)", wNeu.Code)
	}
	// Ziel-Pfad bewusst verschieden (Alt-Route bleibt auf /api/trips/...);
	// verglichen wird die Proxy-Behandlung: Methode, Koerper, Content-Type.
	if alt.Path != "/api/trips/gr20/alert-preview" {
		t.Errorf("Alt-Route zielt auf %s, erwartet unveraendert /api/trips/gr20/alert-preview", alt.Path)
	}
	if alt.Method != neu.Method || alt.Body != neu.Body || alt.ContentType != neu.ContentType {
		t.Errorf("Upstream-Behandlung unterschiedlich: alt %s %q %q, neu %s %q %q",
			alt.Method, alt.Body, alt.ContentType, neu.Method, neu.Body, neu.ContentType)
	}
	vbAssertSingleUserID(t, alt, "alice")
	vbAssertSingleUserID(t, neu, "alice")
	if wAlt.Code != wNeu.Code || wAlt.Body.String() != wNeu.Body.String() ||
		wAlt.Header().Get("Content-Type") != wNeu.Header().Get("Content-Type") {
		t.Errorf("Antwort unterschiedlich: alt %d %q, neu %d %q", wAlt.Code, wAlt.Body.String(), wNeu.Code, wNeu.Body.String())
	}
}

// AC-16 Delegate, Fehlerweg: 404 vom Python-Core und toter Upstream (502)
// kommen auf Alt-Route und kind=route identisch beim Client an.
func TestBriefingAlertPreview_TripAltRoute_GleicherFehlerweg(t *testing.T) {
	py := newVBUpstream(t, func(vbUpstreamCall) (int, string, string) {
		return 404, "application/json", `{"detail":"trip not found"}`
	})
	env := newVBEnv(t, py.srv.URL, "alice")

	py.reset()
	wAlt := env.do(t, "POST", "/api/trips/missing/alert-preview", "alice", vbAlertBody)
	nAlt := py.count()
	py.reset()
	wNeu := env.do(t, "POST", "/api/briefings/missing/alert-preview?kind=route", "alice", vbAlertBody)
	nNeu := py.count()
	if wNeu.Code != 404 || nNeu < 1 {
		t.Errorf("neu Status %d, Upstream %d — erwartet durchgereichtes 404 vom Python-Core", wNeu.Code, nNeu)
	}
	if wAlt.Code != wNeu.Code || wAlt.Body.String() != wNeu.Body.String() || nAlt != nNeu {
		t.Errorf("404-Weg unterschiedlich: alt %d %q (Upstream %d), neu %d %q (Upstream %d)",
			wAlt.Code, wAlt.Body.String(), nAlt, wNeu.Code, wNeu.Body.String(), nNeu)
	}

	dead := httptest.NewServer(http.HandlerFunc(func(http.ResponseWriter, *http.Request) {}))
	deadURL := dead.URL
	dead.Close()
	envDead := newVBEnv(t, deadURL, "alice")
	wAlt = envDead.do(t, "POST", "/api/trips/gr20/alert-preview", "alice", vbAlertBody)
	wNeu = envDead.do(t, "POST", "/api/briefings/gr20/alert-preview?kind=route", "alice", vbAlertBody)
	if wNeu.Code != http.StatusBadGateway {
		t.Errorf("toter Upstream: neu Status %d, erwartet 502", wNeu.Code)
	}
	if wAlt.Code != wNeu.Code || wAlt.Body.String() != wNeu.Body.String() {
		t.Errorf("Fehlerweg unterschiedlich: alt %d %q, neu %d %q", wAlt.Code, wAlt.Body.String(), wNeu.Code, wNeu.Body.String())
	}
}
