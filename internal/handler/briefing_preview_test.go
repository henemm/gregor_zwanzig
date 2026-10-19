package handler_test

// TDD RED — Issue #2283 Scheibe S1 (Epic #2345 P3): kind-neutraler
// Vorschau-Dispatcher GET /api/briefings/{id}/preview?kind=route|vergleich.
//
// Spec: docs/specs/modules/shared_preview_tab.md (AC-1 Go-Teil, AC-3, AC-4
// Go-Teil, AC-5, AC-15 Go-Zeitlimit).
//
// Bauart: externes Testpaket (handler_test), damit der ECHTE Produktions-Router
// router.New(...) samt AuthMiddleware gebaut werden kann — dieselbe Verdrahtung
// wie cmd/server. Der Python-Core ist ein echter httptest-Server, der jede
// empfangene Anfrage (Methode, Pfad, Query, Body) mitschreibt und zaehlt. Kein
// Mock einer Go-Funktion; geprueft wird das tatsaechlich abgesetzte
// Upstream-Request.
//
// Warum nicht package handler: ein Test, der den noch nicht existierenden
// Konstruktor referenziert, braeche den Build des ganzen Pakets. Ueber den
// Router kompiliert alles heute schon und wird ueber HTTP-Verhalten rot
// (Route fehlt -> 404, Upstream-Zaehler 0).
//
// Python-Ziel (vom Python-Teil von S1 festgelegt): ein kind-neutraler
// Endpoint, der kind selbst prueft und die Antwortform vereinheitlicht:
//   GET /api/briefings/{id}/preview?kind=<kind>&user_id=<auth>[&type&date&demo]
// type/date/demo reicht Go bei kind=route durch; bei vergleich ignoriert
// Python sie (Go darf sie weglassen oder durchreichen — nicht gepinnt).

import (
	"bytes"
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/go-webauthn/webauthn/webauthn"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/handler"
	authmw "github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/router"
	"github.com/henemm/gregor-api/internal/scheduler"
	"github.com/henemm/gregor-api/internal/store"
)

// ---------------------------------------------------------------------------
// Gemeinsame Test-Infrastruktur (auch von briefing_alert_preview_test.go genutzt)
// ---------------------------------------------------------------------------

// vbUpstreamCall ist eine vom Fake-Python-Core empfangene Anfrage.
type vbUpstreamCall struct {
	Method      string
	Path        string
	Query       url.Values
	Body        string
	ContentType string
}

// vbUpstream ist ein echter HTTP-Server, der den Python-Core vertritt.
// respond entscheidet je Anfrage ueber Status, Content-Type und Body; delay
// verzoegert die Antwort (Zeitlimit-Tests).
type vbUpstream struct {
	srv     *httptest.Server
	mu      sync.Mutex
	calls   []vbUpstreamCall
	respond func(c vbUpstreamCall) (int, string, string)
	delay   time.Duration
}

func newVBUpstream(t *testing.T, respond func(c vbUpstreamCall) (int, string, string)) *vbUpstream {
	t.Helper()
	u := &vbUpstream{respond: respond}
	if u.respond == nil {
		u.respond = func(vbUpstreamCall) (int, string, string) {
			return http.StatusOK, "application/json", `{"ok":true}`
		}
	}
	u.srv = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		buf := new(bytes.Buffer)
		_, _ = buf.ReadFrom(r.Body)
		c := vbUpstreamCall{
			Method:      r.Method,
			Path:        r.URL.Path,
			Query:       r.URL.Query(),
			Body:        buf.String(),
			ContentType: r.Header.Get("Content-Type"),
		}
		u.mu.Lock()
		u.calls = append(u.calls, c)
		delay := u.delay
		u.mu.Unlock()
		if delay > 0 {
			select {
			case <-time.After(delay):
			case <-r.Context().Done():
				return
			}
		}
		status, ct, body := u.respond(c)
		if ct != "" {
			w.Header().Set("Content-Type", ct)
		}
		w.WriteHeader(status)
		_, _ = io.WriteString(w, body)
	}))
	t.Cleanup(u.srv.Close)
	return u
}

func (u *vbUpstream) count() int {
	u.mu.Lock()
	defer u.mu.Unlock()
	return len(u.calls)
}

func (u *vbUpstream) reset() {
	u.mu.Lock()
	defer u.mu.Unlock()
	u.calls = nil
}

func (u *vbUpstream) last() (vbUpstreamCall, bool) {
	u.mu.Lock()
	defer u.mu.Unlock()
	if len(u.calls) == 0 {
		return vbUpstreamCall{}, false
	}
	return u.calls[len(u.calls)-1], true
}

// vbEnv ist der echte Produktions-Router mit angemeldeten Test-Nutzern.
type vbEnv struct {
	router http.Handler
	secret string
}

func vbSessionID(uid string) string { return "sess-vb-" + uid }

// newVBEnv baut router.New(...) mit PythonCoreURL auf pythonURL und legt fuer
// jeden Nutzer Konto + Anmeldung an (sonst laesst die AuthMiddleware das
// Merkmal nicht durch, Issue #2129).
func newVBEnv(t *testing.T, pythonURL string, users ...string) *vbEnv {
	t.Helper()
	cfg, err := config.Load()
	if err != nil {
		t.Fatalf("config.Load: %v", err)
	}
	cfg.DataDir = t.TempDir()
	cfg.PythonCoreURL = pythonURL

	s := store.New(cfg.DataDir, cfg.UserID)
	for _, uid := range users {
		if err := s.SaveUser(model.User{ID: uid, CreatedAt: time.Now()}); err != nil {
			t.Fatalf("SaveUser(%s): %v", uid, err)
		}
		if err := s.AddSession(uid, vbSessionID(uid)); err != nil {
			t.Fatalf("AddSession(%s): %v", uid, err)
		}
	}

	wa, err := webauthn.New(&webauthn.Config{
		RPID:          cfg.WebAuthnRPID,
		RPDisplayName: cfg.WebAuthnRPDisplayName,
		RPOrigins:     []string{"http://localhost:5173"},
	})
	if err != nil {
		t.Fatalf("webauthn.New: %v", err)
	}
	sched, err := scheduler.New(cfg, s)
	if err != nil {
		t.Fatalf("scheduler.New: %v", err)
	}
	t.Cleanup(sched.Stop)

	r := router.New(router.Deps{
		Config:             cfg,
		Store:              s,
		WeatherProvider:    nil,
		WebAuthn:           wa,
		ChallengeStore:     handler.NewChallengeStore(),
		Scheduler:          sched,
		TelegramTokenStore: handler.NewTelegramTokenStore(cfg.DataDir),
		GitCommit:          "test",
	})
	return &vbEnv{router: r, secret: cfg.SessionSecret}
}

func (e *vbEnv) do(t *testing.T, method, path, uid, body string) *httptest.ResponseRecorder {
	t.Helper()
	var rdr io.Reader
	if body != "" {
		rdr = strings.NewReader(body)
	}
	req := httptest.NewRequest(method, path, rdr)
	if body != "" {
		req.Header.Set("Content-Type", "application/json")
	}
	if uid != "" {
		req.AddCookie(&http.Cookie{
			Name:  "gz_session",
			Value: authmw.SignSessionWithID(uid, vbSessionID(uid), e.secret),
		})
	}
	w := httptest.NewRecorder()
	e.router.ServeHTTP(w, req)
	return w
}

// vbInvalidIDs sind Kennungen, die chi als EIN {id}-Segment aufloest, die aber
// store.ValidEntityID verletzen (fuehrender Punkt, Backslash). Kalibriert in
// vbAssertIDReachesValidation gegen die bestehende Route GET /api/briefings/{id}.
var vbInvalidIDs = []string{".hidden", "..", "a%5Cb"}

// vbAssertIDReachesValidation beweist, dass eine ID die Handler-Pruefung
// erreicht (400 an der bestehenden Briefing-Route) — sonst waere ein 400/404 an
// der neuen Route kein Beleg fuer ValidEntityID.
func vbAssertIDReachesValidation(t *testing.T, e *vbEnv, id, uid string) {
	t.Helper()
	w := e.do(t, "GET", "/api/briefings/"+id+"?kind=route", uid, "")
	if w.Code != http.StatusBadRequest {
		t.Fatalf("Kalibrierung: ID %q liefert an GET /api/briefings/{id} %d statt 400 — "+
			"taugt nicht als ungueltige-ID-Probe", id, w.Code)
	}
}

// vbAssertSingleUserID: die Upstream-Query traegt genau EINEN user_id-Wert,
// und das ist die Kennung aus der Anmeldung (ADR-0003, nie "default").
func vbAssertSingleUserID(t *testing.T, c vbUpstreamCall, want string) {
	t.Helper()
	got := c.Query["user_id"]
	if len(got) != 1 || got[0] != want {
		t.Errorf("Upstream-user_id = %v, erwartet genau [%s] (aus Auth-Kontext, Client-Wert verworfen)", got, want)
	}
}

// ---------------------------------------------------------------------------
// AC-3: kind Pflicht, ungueltige ID -> 400, Python nicht erreicht
// ---------------------------------------------------------------------------

func TestBriefingPreview_KindPflicht_400OhneUpstream(t *testing.T) {
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
		{"kind Grossschreibung", "?kind=ROUTE", 400, 0, "kind_required"},
		// Positiv-Kontrolle: beweist, dass Route + Zaehler ueberhaupt greifen.
		{"Kontrolle route", "?kind=route", 200, 1, ""},
		{"Kontrolle vergleich", "?kind=vergleich", 200, 1, ""},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			py.reset()
			w := env.do(t, "GET", "/api/briefings/t-2283/preview"+c.query, "alice", "")
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

func TestBriefingPreview_UngueltigeID_400OhneUpstream(t *testing.T) {
	py := newVBUpstream(t, nil)
	env := newVBEnv(t, py.srv.URL, "alice")

	for _, id := range vbInvalidIDs {
		vbAssertIDReachesValidation(t, env, id, "alice")
		for _, kind := range []string{"route", "vergleich"} {
			t.Run(kind+"/"+id, func(t *testing.T) {
				py.reset()
				w := env.do(t, "GET", "/api/briefings/"+id+"/preview?kind="+kind, "alice", "")
				if w.Code != http.StatusBadRequest {
					t.Errorf("Status %d, erwartet 400 bei ungueltiger ID %q (body=%q)", w.Code, id, w.Body.String())
				}
				if got := py.count(); got != 0 {
					t.Errorf("Python-Core %d-mal erreicht — ungueltige ID darf nicht weitergereicht werden", got)
				}
			})
		}
	}
	// Positiv-Kontrolle: gueltige ID erreicht Python.
	py.reset()
	if w := env.do(t, "GET", "/api/briefings/t-2283/preview?kind=route", "alice", ""); w.Code != 200 || py.count() != 1 {
		t.Errorf("Kontrolle gueltige ID: Status %d, Upstream %d — erwartet 200 und 1", w.Code, py.count())
	}
}

// ---------------------------------------------------------------------------
// AC-4: zwei Nutzer, user_id aus Auth-Kontext, fremde ID -> 404 durchgereicht
// ---------------------------------------------------------------------------

func TestBriefingPreview_ZweiNutzer_UserIDNurAusAnmeldung(t *testing.T) {
	py := newVBUpstream(t, nil)
	env := newVBEnv(t, py.srv.URL, "alice", "bob")

	for _, kind := range []string{"route", "vergleich"} {
		for _, pair := range [][2]string{{"alice", "bob"}, {"bob", "alice"}} {
			self, other := pair[0], pair[1]
			for _, inject := range []string{"", "&user_id=" + other, "&user_id=default", "&user_id=" + other + "&user_id=default"} {
				t.Run(kind+"/"+self+"/inject="+inject, func(t *testing.T) {
					py.reset()
					w := env.do(t, "GET", "/api/briefings/b-2283/preview?kind="+kind+inject, self, "")
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

// Fake-Python mit nutzerbezogenem Besitz: antwortet 404, wenn die angefragte
// ID nicht dem user_id der Query gehoert — wie die user-scoped Loader.
func vbOwnershipResponder(owned map[string]string) func(c vbUpstreamCall) (int, string, string) {
	return func(c vbUpstreamCall) (int, string, string) {
		uid := c.Query.Get("user_id")
		for id, owner := range owned {
			if strings.Contains(c.Path, "/"+id+"/") || strings.HasSuffix(c.Path, "/"+id) {
				if owner == uid {
					return 200, "application/json", `{"subject":"Daten-von-` + owner + `"}`
				}
				return 404, "application/json", `{"detail":"not found"}`
			}
		}
		return 404, "application/json", `{"detail":"not found"}`
	}
}

func TestBriefingPreview_FremdeID_404DurchgereichtOhneFremdeDaten(t *testing.T) {
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
			w := env.do(t, "GET", "/api/briefings/"+c.foreign+"/preview?kind="+c.kind+"&user_id=bob", "alice", "")
			if w.Code != http.StatusNotFound {
				t.Errorf("fremde ID: Status %d, erwartet 404 (body=%q)", w.Code, w.Body.String())
			}
			if strings.Contains(w.Body.String(), "Daten-von-bob") {
				t.Errorf("Antwort enthaelt Daten von bob: %q", w.Body.String())
			}
			if py.count() < 1 {
				t.Errorf("404 kam nicht vom Python-Core (Upstream nie erreicht) — kein Beleg fuer Isolation")
			}
			// Gegenprobe: eigener Eintrag liefert die eigenen Daten.
			py.reset()
			w = env.do(t, "GET", "/api/briefings/"+c.own+"/preview?kind="+c.kind, "alice", "")
			if w.Code != http.StatusOK || !strings.Contains(w.Body.String(), "Daten-von-alice") {
				t.Errorf("eigener Eintrag: Status %d body=%q, erwartet 200 mit eigenen Daten", w.Code, w.Body.String())
			}
		})
	}
}

// ---------------------------------------------------------------------------
// AC-1 (Go-Teil): kind lenkt auf das Python-Buendel, Antwort unveraendert
// ---------------------------------------------------------------------------

func TestBriefingPreview_KindLenktAufPythonBuendel(t *testing.T) {
	const bundle = `{"subject":"GR20 Morgen","email_html":"<p>x</p>","sms":{"text":"GR20 T12","char_count":8},"telegram":{"body":"GR20"}}`
	py := newVBUpstream(t, func(vbUpstreamCall) (int, string, string) {
		return 200, "application/json; charset=utf-8", bundle
	})
	env := newVBEnv(t, py.srv.URL, "alice")

	t.Run("route", func(t *testing.T) {
		py.reset()
		w := env.do(t, "GET", "/api/briefings/gr20/preview?kind=route&type=evening&date=2026-07-17&demo=1", "alice", "")
		if w.Code != 200 {
			t.Fatalf("Status %d, erwartet 200 (body=%q)", w.Code, w.Body.String())
		}
		c, _ := py.last()
		if c.Method != "GET" || c.Path != "/api/briefings/gr20/preview" {
			t.Errorf("Upstream %s %s, erwartet GET /api/briefings/gr20/preview", c.Method, c.Path)
		}
		if c.Query.Get("kind") != "route" {
			t.Errorf("kind=route nicht an Python weitergereicht (Upstream-Query %v)", c.Query)
		}
		for k, v := range map[string]string{"type": "evening", "date": "2026-07-17", "demo": "1"} {
			if c.Query.Get(k) != v {
				t.Errorf("Option %s=%q nicht durchgereicht (Upstream-Query %v)", k, v, c.Query)
			}
		}
		if w.Body.String() != bundle {
			t.Errorf("Antwort veraendert: %q, erwartet Python-Buendel unveraendert", w.Body.String())
		}
		if ct := w.Header().Get("Content-Type"); !strings.HasPrefix(ct, "application/json") {
			t.Errorf("Content-Type %q nicht durchgereicht", ct)
		}
	})

	t.Run("vergleich", func(t *testing.T) {
		py.reset()
		w := env.do(t, "GET", "/api/briefings/cmp-7/preview?kind=vergleich&date=2026-07-17", "alice", "")
		if w.Code != 200 {
			t.Fatalf("Status %d, erwartet 200 (body=%q)", w.Code, w.Body.String())
		}
		c, _ := py.last()
		if c.Method != "GET" || c.Path != "/api/briefings/cmp-7/preview" {
			t.Errorf("Upstream %s %s, erwartet GET /api/briefings/cmp-7/preview", c.Method, c.Path)
		}
		if c.Query.Get("kind") != "vergleich" {
			t.Errorf("kind=vergleich nicht an Python weitergereicht (Upstream-Query %v)", c.Query)
		}
		if w.Body.String() != bundle {
			t.Errorf("Antwort veraendert: %q", w.Body.String())
		}
	})
}

// ---------------------------------------------------------------------------
// AC-5: Alt-Routen und Buendelaufruf laufen durch dieselbe Proxy-Behandlung
// ---------------------------------------------------------------------------
//
// Verhaltensbeleg (kein Quelltext-Grep): dieselbe Eingabe ueber Alt-Route und
// neuen Buendelaufruf erfaehrt dieselbe Proxy-Behandlung: user_id aus der
// Anmeldung, Client-user_id verworfen, Optionen durchgereicht, Status und
// Content-Type durchgereicht, 404 durchgereicht, gleicher 502-Koerper bei
// totem Upstream. Das Python-ZIEL ist bewusst verschieden (Alt-Routen bleiben,
// Buendel geht an /api/briefings/{id}/preview) und wird hier nicht verglichen.
// Grenze: ein Handler, der die Logik kopiert statt teilt, besteht diesen Test
// ebenfalls — er belegt gleiches Verhalten, nicht dieselbe Funktion.

func TestVorschauAltRouteUndBuendel_GleicheProxyBehandlung_Trip(t *testing.T) {
	py := newVBUpstream(t, func(vbUpstreamCall) (int, string, string) {
		return 200, "text/html; charset=utf-8", "<!doctype html><p>preview</p>"
	})
	env := newVBEnv(t, py.srv.URL, "alice")
	const q = "type=evening&date=2026-07-17&user_id=mallory"

	py.reset()
	wAlt := env.do(t, "GET", "/api/preview/gr20/email?"+q, "alice", "")
	alt, okAlt := py.last()
	py.reset()
	wNeu := env.do(t, "GET", "/api/briefings/gr20/preview?kind=route&"+q, "alice", "")
	neu, okNeu := py.last()

	if !okAlt || !okNeu {
		t.Fatalf("Python-Core nicht auf beiden Wegen erreicht (alt=%v neu=%v, Status alt=%d neu=%d)",
			okAlt, okNeu, wAlt.Code, wNeu.Code)
	}
	vbAssertSingleUserID(t, alt, "alice")
	vbAssertSingleUserID(t, neu, "alice")
	for _, k := range []string{"type", "date"} {
		if alt.Query.Get(k) != neu.Query.Get(k) {
			t.Errorf("Option %s: alt=%q neu=%q — unterschiedliche Durchreichung", k, alt.Query.Get(k), neu.Query.Get(k))
		}
	}
	if alt.Method != neu.Method {
		t.Errorf("Upstream-Methode alt=%s neu=%s", alt.Method, neu.Method)
	}
	if wAlt.Code != wNeu.Code || wAlt.Header().Get("Content-Type") != wNeu.Header().Get("Content-Type") {
		t.Errorf("Antwort unterschiedlich: alt %d %q, neu %d %q", wAlt.Code, wAlt.Header().Get("Content-Type"),
			wNeu.Code, wNeu.Header().Get("Content-Type"))
	}
}

func TestVorschauAltRouteUndBuendel_GleicheProxyBehandlung_Vergleich(t *testing.T) {
	py := newVBUpstream(t, nil)
	env := newVBEnv(t, py.srv.URL, "alice")
	const q = "date=2026-07-17&user_id=mallory"

	py.reset()
	wAlt := env.do(t, "POST", "/api/preview/compare/cmp-7?"+q, "alice", "{}")
	alt, okAlt := py.last()
	py.reset()
	wNeu := env.do(t, "GET", "/api/briefings/cmp-7/preview?kind=vergleich&"+q, "alice", "")
	neu, okNeu := py.last()

	if !okAlt || !okNeu {
		t.Fatalf("Python-Core nicht auf beiden Wegen erreicht (alt=%v neu=%v, Status alt=%d neu=%d)",
			okAlt, okNeu, wAlt.Code, wNeu.Code)
	}
	vbAssertSingleUserID(t, alt, "alice")
	vbAssertSingleUserID(t, neu, "alice")
	if wAlt.Code != wNeu.Code || wAlt.Header().Get("Content-Type") != wNeu.Header().Get("Content-Type") ||
		wAlt.Body.String() != wNeu.Body.String() {
		t.Errorf("Antwort unterschiedlich: alt %d %q, neu %d %q", wAlt.Code, wAlt.Body.String(), wNeu.Code, wNeu.Body.String())
	}
}

func TestVorschauAltRouteUndBuendel_GleicherFehlerweg(t *testing.T) {
	// 404 vom Python-Core: beide Wege reichen ihn unveraendert durch.
	py := newVBUpstream(t, func(vbUpstreamCall) (int, string, string) {
		return 404, "application/json", `{"detail":"trip not found"}`
	})
	env := newVBEnv(t, py.srv.URL, "alice")
	paare := []struct{ name, altM, altP, neuP string }{
		{"route", "GET", "/api/preview/missing/sms", "/api/briefings/missing/preview?kind=route"},
		{"vergleich", "POST", "/api/preview/compare/missing", "/api/briefings/missing/preview?kind=vergleich"},
	}
	for _, p := range paare {
		py.reset()
		wAlt := env.do(t, p.altM, p.altP, "alice", vbBodyFor(p.altM))
		nAlt := py.count()
		py.reset()
		wNeu := env.do(t, "GET", p.neuP, "alice", "")
		nNeu := py.count()
		if wNeu.Code != 404 || nNeu < 1 {
			t.Errorf("%s: neu Status %d, Upstream %d — erwartet durchgereichtes 404 vom Python-Core", p.name, wNeu.Code, nNeu)
		}
		if wAlt.Code != wNeu.Code || wAlt.Body.String() != wNeu.Body.String() || nAlt != nNeu {
			t.Errorf("%s: 404-Weg unterschiedlich: alt %d %q (Upstream %d), neu %d %q (Upstream %d)",
				p.name, wAlt.Code, wAlt.Body.String(), nAlt, wNeu.Code, wNeu.Body.String(), nNeu)
		}
	}

	// Toter Python-Core: beide Wege antworten mit demselben 502-Koerper.
	dead := httptest.NewServer(http.HandlerFunc(func(http.ResponseWriter, *http.Request) {}))
	deadURL := dead.URL
	dead.Close()
	envDead := newVBEnv(t, deadURL, "alice")
	for _, p := range paare {
		wAlt := envDead.do(t, p.altM, p.altP, "alice", vbBodyFor(p.altM))
		wNeu := envDead.do(t, "GET", p.neuP, "alice", "")
		if wNeu.Code != http.StatusBadGateway {
			t.Errorf("%s: toter Upstream neu Status %d, erwartet 502", p.name, wNeu.Code)
		}
		if wAlt.Code != wNeu.Code || wAlt.Body.String() != wNeu.Body.String() {
			t.Errorf("%s: Fehlerweg unterschiedlich: alt %d %q, neu %d %q",
				p.name, wAlt.Code, wAlt.Body.String(), wNeu.Code, wNeu.Body.String())
		}
	}
}

// vbBodyFor: POST-Aufrufe tragen einen leeren JSON-Koerper, GET keinen.
func vbBodyFor(method string) string {
	if method == "POST" {
		return "{}"
	}
	return ""
}

// ---------------------------------------------------------------------------
// AC-15 (Go-Teil): Zeitlimit 30 s fuer route, 60 s fuer vergleich
// ---------------------------------------------------------------------------
//
// Am Wirkort gemessen: ein echter, langsamer Python-Core antwortet erst nach
// 32 s. route muss vorher mit 502 abbrechen (Grenze 30 s), vergleich muss die
// Antwort abwarten (Grenze 60 s, wie POST /api/preview/compare). Beide
// Teiltests laufen parallel, Gesamtdauer ~32 s. Die Obergrenze 60 s wird
// bewusst nicht ausgemessen (kostete > 60 s Laufzeit).

func TestBriefingPreview_Zeitlimit_Route30sVergleich60s(t *testing.T) {
	if testing.Short() {
		t.Skip("Zeitlimit-Messung dauert ~32 s")
	}
	py := newVBUpstream(t, nil)
	py.delay = 32 * time.Second
	env := newVBEnv(t, py.srv.URL, "alice")

	t.Run("route bricht nach 30 s ab", func(t *testing.T) {
		t.Parallel()
		start := time.Now()
		w := env.do(t, "GET", "/api/briefings/gr20/preview?kind=route", "alice", "")
		took := time.Since(start)
		if w.Code != http.StatusBadGateway || took < 29*time.Second || took > 31*time.Second {
			t.Errorf("kind=route: Status %d nach %v, erwartet 502 nach ~30 s", w.Code, took)
		}
	})
	t.Run("vergleich wartet laenger als 30 s", func(t *testing.T) {
		t.Parallel()
		start := time.Now()
		w := env.do(t, "GET", "/api/briefings/cmp-7/preview?kind=vergleich", "alice", "")
		took := time.Since(start)
		if w.Code != http.StatusOK || took < 31*time.Second {
			t.Errorf("kind=vergleich: Status %d nach %v, erwartet 200 nach ~32 s (Zeitlimit 60 s)", w.Code, took)
		}
	})
}
