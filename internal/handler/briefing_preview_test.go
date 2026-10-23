package handler_test

// Gemeinsame Test-Infrastruktur der /api/briefings-Proxy-Routen
// (Alarm-Vorschau, Handversand) — Issue #2283 (Epic #2345 P3).
//
// Die kind-neutrale Briefing-Vorschau ist mit #1743
// entfallen; ihre Tests sind mit ihr gegangen. Geblieben sind die Helfer
// (genutzt von briefing_alert_preview_test.go und briefing_send_test.go) und
// die Zeitlimit-Messung der Alarm-Vorschau.
//
// Bauart: externes Testpaket (handler_test), damit der ECHTE Produktions-Router
// router.New(...) samt AuthMiddleware gebaut werden kann — dieselbe Verdrahtung
// wie cmd/server. Der Python-Core ist ein echter httptest-Server, der jede
// empfangene Anfrage (Methode, Pfad, Query, Body) mitschreibt und zaehlt. Kein
// Mock einer Go-Funktion; geprueft wird das tatsaechlich abgesetzte
// Upstream-Request.

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

// ---------------------------------------------------------------------------
// Zeitlimit der Alarm-Vorschau: 30 s, auch bei kind=vergleich
// ---------------------------------------------------------------------------
//
// Am Wirkort gemessen (Adversary-Runde #2283, F002): ein echter, langsamer
// Python-Core antwortet erst nach 32 s; die Alarm-Vorschau bricht nach 30 s
// ab (nicht 60 s wie die frühere, seit #1743 entfernte Vergleichs-Vorschau).

func TestBriefingAlertPreview_Zeitlimit30sAuchBeiVergleich(t *testing.T) {
	if testing.Short() {
		t.Skip("Zeitlimit-Messung dauert ~30 s")
	}
	py := newVBUpstream(t, nil)
	py.delay = 32 * time.Second
	env := newVBEnv(t, py.srv.URL, "alice")

	start := time.Now()
	w := env.do(t, "POST", "/api/briefings/cmp-7/alert-preview?kind=vergleich", "alice", "{}")
	took := time.Since(start)
	if w.Code != http.StatusBadGateway || took < 29*time.Second || took > 31*time.Second {
		t.Errorf("alert-preview kind=vergleich: Status %d nach %v, erwartet 502 nach ~30 s", w.Code, took)
	}
}
