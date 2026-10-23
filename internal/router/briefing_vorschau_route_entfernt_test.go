package router

// TDD RED — Issue #1743 AC-30 (Vorschau-Rückbau Backend, Go-Teil).
//
// Spec: docs/specs/modules/feat_1743_reiter_aufraeumen.md (Abschnitt 7, AC-30)
//
// Echter router.New(...) mit zwei angemeldeten Nutzern und einem
// mitschreibenden Fake-Python-Core, der Eigentum prueft (fremde ID -> 404).
//
// (a) GET /api/briefings/{id}/preview ist nicht mehr registriert: 404/405
//     und der Python-Core wird NICHT erreicht — auch fuer den Eigentuemer.
//     RED heute: Route registriert, Eigentuemer bekommt 200 vom Upstream.
// (b) POST /api/briefings/{id}/alert-preview bleibt: Eigentuemer 200 mit
//     eigenen Daten, fremde ID 404 vom Upstream, user_id stammt nur aus der
//     Anmeldung (injiziertes user_id=<anderer> wird verworfen).

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

	"github.com/go-chi/chi/v5"
	"github.com/go-webauthn/webauthn/webauthn"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/handler"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/scheduler"
	"github.com/henemm/gregor-api/internal/store"
)

const (
	vorschauAlice = "vorschau-1743-alice"
	vorschauBob   = "vorschau-1743-bob"
)

type vorschauUpstreamCall struct {
	Method string
	Path   string
	Query  url.Values
}

// vorschauUpstream vertritt den Python-Core: schreibt mit und antwortet nur
// dem Eigentuemer der ID mit 200 + Datenmarker, sonst 404.
type vorschauUpstream struct {
	srv   *httptest.Server
	mu    sync.Mutex
	calls []vorschauUpstreamCall
}

func newVorschauUpstream(t *testing.T, owned map[string]string) *vorschauUpstream {
	t.Helper()
	u := &vorschauUpstream{}
	u.srv = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = io.Copy(io.Discard, r.Body)
		u.mu.Lock()
		u.calls = append(u.calls, vorschauUpstreamCall{r.Method, r.URL.Path, r.URL.Query()})
		u.mu.Unlock()
		w.Header().Set("Content-Type", "application/json")
		uid := r.URL.Query().Get("user_id")
		for id, owner := range owned {
			if strings.Contains(r.URL.Path, "/"+id+"/") && owner == uid {
				_, _ = w.Write([]byte(`{"subject":"Daten-von-` + owner + `"}`))
				return
			}
		}
		w.WriteHeader(http.StatusNotFound)
		_, _ = w.Write([]byte(`{"detail":"not found"}`))
	}))
	t.Cleanup(u.srv.Close)
	return u
}

func (u *vorschauUpstream) take() []vorschauUpstreamCall {
	u.mu.Lock()
	defer u.mu.Unlock()
	out := u.calls
	u.calls = nil
	return out
}

func newVorschauRouter(t *testing.T, pythonURL string) (chi.Router, map[string]*http.Cookie) {
	t.Helper()
	cfg, err := config.Load()
	if err != nil {
		t.Fatalf("config.Load: %v", err)
	}
	cfg.DataDir = t.TempDir()
	cfg.PythonCoreURL = pythonURL

	s := store.New(cfg.DataDir, cfg.UserID)
	cookies := map[string]*http.Cookie{}
	for _, uid := range []string{vorschauAlice, vorschauBob} {
		if err := s.SaveUser(model.User{ID: uid, CreatedAt: time.Now()}); err != nil {
			t.Fatalf("SaveUser %s: %v", uid, err)
		}
		if err := s.AddSession(uid, sessionIDFor(uid)); err != nil {
			t.Fatalf("AddSession %s: %v", uid, err)
		}
		cookies[uid] = sessionCookieFor(uid, cfg.SessionSecret)
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

	r := New(Deps{
		Config:             cfg,
		Store:              s,
		WeatherProvider:    nil,
		WebAuthn:           wa,
		ChallengeStore:     handler.NewChallengeStore(),
		Scheduler:          sched,
		TelegramTokenStore: handler.NewTelegramTokenStore(cfg.DataDir),
		GitCommit:          "test",
	})
	return r, cookies
}

func serveVorschau(r http.Handler, cookie *http.Cookie, method, path, body string) *httptest.ResponseRecorder {
	var rd io.Reader
	if body != "" {
		rd = bytes.NewReader([]byte(body))
	}
	req := httptest.NewRequest(method, path, rd)
	if body != "" {
		req.Header.Set("Content-Type", "application/json")
	}
	req.AddCookie(cookie)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	return w
}

var vorschauOwned = map[string]string{
	"trip-alice": vorschauAlice, "trip-bob": vorschauBob,
	"cmp-alice": vorschauAlice, "cmp-bob": vorschauBob,
}

// AC-30 (a): die Briefing-Vorschau-Route ist entfernt — auch der Eigentuemer
// bekommt 404/405, und der Python-Core wird nicht erreicht.
func TestBriefingVorschauRoute_Entfernt_404OhneUpstream(t *testing.T) {
	py := newVorschauUpstream(t, vorschauOwned)
	r, cookies := newVorschauRouter(t, py.srv.URL)

	cases := []struct{ kind, id string }{{"route", "trip-alice"}, {"vergleich", "cmp-alice"}}
	for _, c := range cases {
		t.Run(c.kind, func(t *testing.T) {
			py.take()
			w := serveVorschau(r, cookies[vorschauAlice], http.MethodGet,
				"/api/briefings/"+c.id+"/preview?kind="+c.kind, "")
			if w.Code != http.StatusNotFound && w.Code != http.StatusMethodNotAllowed {
				t.Errorf("GET /api/briefings/{id}/preview: erwartet 404/405 (Route entfernt), bekommen %d (body=%q)",
					w.Code, w.Body.String())
			}
			if calls := py.take(); len(calls) != 0 {
				t.Errorf("Briefing-Vorschau erreicht weiterhin den Python-Core: %v", calls)
			}
		})
	}
}

// Issue #1743 (PO-Entscheid 22.10.2026): die Kanal-Vorschauen ohne
// Frontend-Aufrufer sind entfernt — email/telegram (Trip) und die
// Orts-Vergleich-Vorschau. Auch der Eigentuemer bekommt 404/405, der
// Python-Core wird nicht erreicht.
func TestKanalVorschauRouten_Entfernt_404OhneUpstream(t *testing.T) {
	py := newVorschauUpstream(t, vorschauOwned)
	r, cookies := newVorschauRouter(t, py.srv.URL)

	cases := []struct{ method, path string }{
		{http.MethodGet, "/api/preview/trip-alice/email?type=morning"},
		{http.MethodGet, "/api/preview/trip-alice/telegram?type=morning"},
		{http.MethodPost, "/api/preview/compare/cmp-alice"},
	}
	for _, c := range cases {
		t.Run(c.method+" "+c.path, func(t *testing.T) {
			py.take()
			body := ""
			if c.method == http.MethodPost {
				body = "{}"
			}
			w := serveVorschau(r, cookies[vorschauAlice], c.method, c.path, body)
			if w.Code != http.StatusNotFound && w.Code != http.StatusMethodNotAllowed {
				t.Errorf("%s %s: erwartet 404/405 (Route entfernt), bekommen %d (body=%q)",
					c.method, c.path, w.Code, w.Body.String())
			}
			if calls := py.take(); len(calls) != 0 {
				t.Errorf("entfernte Vorschau erreicht weiterhin den Python-Core: %v", calls)
			}
		})
	}
}

// Issue #1743: GET /api/preview/{trip}/sms bleibt (Messweg der Staging-Specs)
// und ist mandantengetrennt — user_id stammt nur aus der Anmeldung.
func TestSmsVorschau_BleibtUndIstMandantengetrennt(t *testing.T) {
	py := newVorschauUpstream(t, vorschauOwned)
	r, cookies := newVorschauRouter(t, py.srv.URL)

	py.take()
	w := serveVorschau(r, cookies[vorschauAlice], http.MethodGet, "/api/preview/trip-alice/sms?type=morning", "")
	if w.Code != http.StatusOK || !strings.Contains(w.Body.String(), "Daten-von-"+vorschauAlice) {
		t.Errorf("eigener Trip: Status %d body=%q, erwartet 200 mit eigenen Daten", w.Code, w.Body.String())
	}

	py.take()
	w = serveVorschau(r, cookies[vorschauAlice], http.MethodGet,
		"/api/preview/trip-bob/sms?type=morning&user_id="+vorschauBob, "")
	if w.Code != http.StatusNotFound || strings.Contains(w.Body.String(), "Daten-von-"+vorschauBob) {
		t.Errorf("fremder Trip: Status %d body=%q, erwartet 404 ohne fremde Daten", w.Code, w.Body.String())
	}
	calls := py.take()
	if len(calls) != 1 {
		t.Fatalf("erwartet genau einen Upstream-Aufruf, bekommen %v", calls)
	}
	if got := calls[0].Query["user_id"]; len(got) != 1 || got[0] != vorschauAlice {
		t.Errorf("user_id an Python = %v, erwartet genau [%s] aus der Anmeldung", got, vorschauAlice)
	}
}

// AC-30 (b): die Alarm-Vorschau bleibt erreichbar und mandantengetrennt.
func TestBriefingAlarmVorschau_BleibtUndIstMandantengetrennt(t *testing.T) {
	py := newVorschauUpstream(t, vorschauOwned)
	r, cookies := newVorschauRouter(t, py.srv.URL)
	const body = `{"onset":{"kind":"rain","minutes":20}}`

	cases := []struct{ kind, own, foreign string }{
		{"route", "trip-alice", "trip-bob"},
		{"vergleich", "cmp-alice", "cmp-bob"},
	}
	for _, c := range cases {
		t.Run(c.kind, func(t *testing.T) {
			py.take()
			w := serveVorschau(r, cookies[vorschauAlice], http.MethodPost,
				"/api/briefings/"+c.own+"/alert-preview?kind="+c.kind, body)
			if w.Code != http.StatusOK || !strings.Contains(w.Body.String(), "Daten-von-"+vorschauAlice) {
				t.Errorf("eigener Eintrag: Status %d body=%q, erwartet 200 mit eigenen Daten", w.Code, w.Body.String())
			}

			py.take()
			w = serveVorschau(r, cookies[vorschauAlice], http.MethodPost,
				"/api/briefings/"+c.foreign+"/alert-preview?kind="+c.kind+"&user_id="+vorschauBob, body)
			if w.Code != http.StatusNotFound {
				t.Errorf("fremde ID: Status %d, erwartet 404 (body=%q)", w.Code, w.Body.String())
			}
			if strings.Contains(w.Body.String(), "Daten-von-"+vorschauBob) {
				t.Errorf("Antwort enthaelt Daten von bob: %q", w.Body.String())
			}
			calls := py.take()
			if len(calls) == 0 {
				t.Fatalf("404 kam nicht vom Python-Core (Upstream nie erreicht) — kein Beleg fuer Isolation")
			}
			for _, call := range calls {
				if got := call.Query["user_id"]; len(got) != 1 || got[0] != vorschauAlice {
					t.Errorf("user_id an Python = %v, erwartet genau [%s] aus der Anmeldung", got, vorschauAlice)
				}
			}
		})
	}
}
