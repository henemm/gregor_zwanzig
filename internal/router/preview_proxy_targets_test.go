package router

// TDD RED — Issue #2283 AC-6 (Scheibe S1): toter /signal-Proxy entfernt, und
// jede registrierte Vorschau-Proxy-Route hat ein Ziel im Python-Core.
//
// Spec: docs/specs/modules/shared_preview_tab.md (AC-6)
//
// (a) Muster legacy_subscription_routes_removed_test.go: echter router.New(...)
//     mit gueltigem Session-Cookie — 404 heisst "Route nicht registriert",
//     nicht "Auth fehlt" (401) oder "Upstream sagt nein".
//
// (b) Waechter, beobachtet statt behauptet:
//     - Go-Seite: alle Routen des ECHTEN chi-Routers per chi.Walk (kein
//       Text-Grep von router.go), gefiltert auf Pfade mit "preview".
//     - Jede Route wird ueber den Router tatsaechlich aufgerufen; ein
//       mitschreibender Fake-Python-Core haelt fest, welche Methode und welchen
//       Pfad Go WIRKLICH anfragt. Kein von Hand gepflegtes Go->Python-Mapping.
//     - Python-Seite: versioniertes Abbild der echten FastAPI-Routentabelle
//       (testdata/python_preview_routes.json). Der go-test-Job hat kein
//       Python; das Abbild wird von tests/test_vorschau_proxy_ziel_snapshot.py
//       gegen api.main:app.routes geprueft und mit
//       `uv run python tests/test_vorschau_proxy_ziel_snapshot.py --write`
//       neu erzeugt. Damit ist es keine eigene Annahme, sondern ein geprueftes
//       Abbild der gebauten App.
//
// RED heute: /signal ist registriert und zielt auf eine Python-Route, die es
// nicht gibt; /api/briefings/{id}/alert-preview fehlt.

import (
	"bytes"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"regexp"
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

const previewTargetsUser = "preview-targets-user"

type previewTargetCall struct{ Method, Path string }

// previewTargetRecorder vertritt den Python-Core und schreibt jede Anfrage mit.
type previewTargetRecorder struct {
	srv   *httptest.Server
	mu    sync.Mutex
	calls []previewTargetCall
}

func newPreviewTargetRecorder(t *testing.T) *previewTargetRecorder {
	t.Helper()
	rec := &previewTargetRecorder{}
	rec.srv = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = io.Copy(io.Discard, r.Body)
		rec.mu.Lock()
		rec.calls = append(rec.calls, previewTargetCall{r.Method, r.URL.Path})
		rec.mu.Unlock()
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{}`))
	}))
	t.Cleanup(rec.srv.Close)
	return rec
}

func (rec *previewTargetRecorder) take() []previewTargetCall {
	rec.mu.Lock()
	defer rec.mu.Unlock()
	out := rec.calls
	rec.calls = nil
	return out
}

func newPreviewTargetsRouter(t *testing.T, pythonURL string) (chi.Router, *http.Cookie) {
	t.Helper()
	cfg, err := config.Load()
	if err != nil {
		t.Fatalf("config.Load: %v", err)
	}
	cfg.DataDir = t.TempDir()
	cfg.PythonCoreURL = pythonURL

	s := store.New(cfg.DataDir, cfg.UserID)
	if err := s.SaveUser(model.User{ID: previewTargetsUser, CreatedAt: time.Now()}); err != nil {
		t.Fatalf("SaveUser: %v", err)
	}
	if err := s.AddSession(previewTargetsUser, sessionIDFor(previewTargetsUser)); err != nil {
		t.Fatalf("AddSession: %v", err)
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
	return r, sessionCookieFor(previewTargetsUser, cfg.SessionSecret)
}

func servePreviewProbe(r http.Handler, cookie *http.Cookie, method, path string) int {
	var body io.Reader
	if method == http.MethodPost || method == http.MethodPut || method == http.MethodPatch {
		body = bytes.NewReader([]byte(`{}`))
	}
	req := httptest.NewRequest(method, path, body)
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	req.AddCookie(cookie)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	return w.Code
}

// AC-6 (a): der tote Signal-Proxy ist nicht mehr registriert.
func TestPreviewSignalRouteRemoved_404(t *testing.T) {
	py := newPreviewTargetRecorder(t)
	r, cookie := newPreviewTargetsRouter(t, py.srv.URL)

	code := servePreviewProbe(r, cookie, http.MethodGet, "/api/preview/gr20/signal?type=morning")
	if code != http.StatusNotFound {
		t.Errorf("GET /api/preview/{trip_id}/signal: erwartet 404 (Route entfernt), bekommen %d", code)
	}
	if calls := py.take(); len(calls) != 0 {
		t.Errorf("Signal-Vorschau erreicht weiterhin den Python-Core: %v", calls)
	}
}

type pythonRoute struct {
	Method string `json:"method"`
	Path   string `json:"path"`
	re     *regexp.Regexp
}

var fastAPIParam = regexp.MustCompile(`\\\{[^}]*\\\}`)

func loadPythonPreviewRoutes(t *testing.T) []pythonRoute {
	t.Helper()
	raw, err := os.ReadFile("testdata/python_preview_routes.json")
	if err != nil {
		t.Fatalf("Abbild der Python-Routen fehlt (uv run python tests/test_vorschau_proxy_ziel_snapshot.py --write): %v", err)
	}
	var routes []pythonRoute
	if err := json.Unmarshal(raw, &routes); err != nil {
		t.Fatalf("Abbild unlesbar: %v", err)
	}
	if len(routes) == 0 {
		t.Fatalf("Abbild der Python-Routen ist leer")
	}
	for i := range routes {
		// {name} -> ein Segment; {name:path} -> beliebig viele Segmente.
		pat := regexp.QuoteMeta(routes[i].Path)
		pat = fastAPIParam.ReplaceAllStringFunc(pat, func(m string) string {
			if strings.Contains(m, ":path") {
				return `.+`
			}
			return `[^/]+`
		})
		routes[i].re = regexp.MustCompile("^" + pat + "$")
	}
	return routes
}

func hasPythonTarget(routes []pythonRoute, c previewTargetCall) bool {
	for _, pr := range routes {
		if pr.Method == c.Method && pr.re.MatchString(c.Path) {
			return true
		}
	}
	return false
}

var chiParam = regexp.MustCompile(`\{[^}]*\}`)

// AC-6 (b): jede Vorschau-Proxy-Route im echten Router hat ein Python-Ziel.
func TestPreviewProxyRoutesHavePythonTarget(t *testing.T) {
	py := newPreviewTargetRecorder(t)
	r, cookie := newPreviewTargetsRouter(t, py.srv.URL)
	pyRoutes := loadPythonPreviewRoutes(t)

	type goRoute struct{ method, pattern string }
	var walked []goRoute
	err := chi.Walk(r, func(method, route string, _ http.Handler, _ ...func(http.Handler) http.Handler) error {
		if strings.Contains(route, "preview") {
			walked = append(walked, goRoute{method, route})
		}
		return nil
	})
	if err != nil {
		t.Fatalf("chi.Walk: %v", err)
	}

	// Geltungsbereich + Nicht-Vakuitaet: diese Routen MUESSEN im Router stehen.
	pflicht := []goRoute{
		{"GET", "/api/preview/{trip_id}/sms"},
		{"POST", "/api/trips/{id}/alert-preview"},
		{"POST", "/api/briefings/{id}/alert-preview"},
	}
	for _, p := range pflicht {
		found := false
		for _, w := range walked {
			if w == p {
				found = true
				break
			}
		}
		if !found {
			t.Errorf("Vorschau-Route %s %s ist im Router nicht registriert", p.method, p.pattern)
		}
	}

	for _, gr := range walked {
		path := chiParam.ReplaceAllString(gr.pattern, "gzprobe1")
		var probes []string
		if strings.HasPrefix(gr.pattern, "/api/briefings/") {
			probes = []string{path + "?kind=route", path + "?kind=vergleich"}
		} else {
			probes = []string{path}
		}
		for _, probe := range probes {
			py.take()
			code := servePreviewProbe(r, cookie, gr.method, probe)
			calls := py.take()
			if len(calls) == 0 {
				t.Errorf("%s %s (Probe %s): Python-Core nie erreicht (Status %d) — kein beobachtbares Ziel",
					gr.method, gr.pattern, probe, code)
				continue
			}
			for _, c := range calls {
				if !hasPythonTarget(pyRoutes, c) {
					t.Errorf("%s %s (Probe %s) zielt auf %s %s — diese Route gibt es im Python-Core nicht",
						gr.method, gr.pattern, probe, c.Method, c.Path)
				}
			}
		}
	}
}
