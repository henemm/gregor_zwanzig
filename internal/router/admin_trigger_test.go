package router

// TDD RED — Issue #2155 Scheibe S1 (Admin-Rolle), AC-1, AC-2, AC-3, AC-4, AC-7.
//
// Spec: docs/specs/modules/admin_rolle_s1.md
//
// Echter Produktions-Router (router.New, dieselbe Verdrahtung wie
// cmd/server/main.go) inkl. AuthMiddleware und echten gz_session-Cookies.
// Das Python-Ziel ist ein httptest-Server, der Aufrufe je Pfad zaehlt — so
// wird geprueft, ob der Proxy ERREICHT wurde, nicht nur welcher Statuscode
// zurueckkam.
//
// RED-Signal: Config.AdminUserIDs existiert nicht (Uebersetzungsfehler). Nach
// der Umsetzung bleibt der Vertrag an der Stelle bewacht, an der er WIRKT:
// im verdrahteten Router, nicht nur in der Middleware.

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/go-webauthn/webauthn/webauthn"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/handler"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/scheduler"
	"github.com/henemm/gregor-api/internal/store"
)

var triggerPfade = []string{
	"/api/scheduler/trip-reports",
	"/api/scheduler/alert-checks",
	"/api/scheduler/inbound-commands",
}

// pythonZiel zaehlt die Aufrufe je Pfad und antwortet wie der Python-Core.
type pythonZiel struct {
	mu     sync.Mutex
	counts map[string]int
	srv    *httptest.Server
}

func neuesPythonZiel(t *testing.T) *pythonZiel {
	t.Helper()
	z := &pythonZiel{counts: map[string]int{}}
	z.srv = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		z.mu.Lock()
		z.counts[r.URL.Path]++
		z.mu.Unlock()
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"status":"ok","from":"python-core"}`))
	}))
	t.Cleanup(z.srv.Close)
	return z
}

func (z *pythonZiel) n(pfad string) int {
	z.mu.Lock()
	defer z.mu.Unlock()
	return z.counts[pfad]
}

func (z *pythonZiel) gesamt() int {
	z.mu.Lock()
	defer z.mu.Unlock()
	total := 0
	for _, c := range z.counts {
		total += c
	}
	return total
}

// adminTestRouter baut den echten Router mit gesetzter Admin-Liste. Nutzer:
// alice, bob und "ops" (= cfg.UserID), alle mit Konto und Gaesteliste.
func adminTestRouter(t *testing.T, adminUserIDs string) (http.Handler, *store.Store, string, *pythonZiel) {
	t.Helper()

	ziel := neuesPythonZiel(t)

	cfg, err := config.Load()
	if err != nil {
		t.Fatalf("config.Load: %v", err)
	}
	cfg.DataDir = t.TempDir()
	cfg.PythonCoreURL = ziel.srv.URL
	cfg.UserID = "ops"
	cfg.AdminUserIDs = adminUserIDs

	s := store.New(cfg.DataDir, cfg.UserID)
	for _, id := range []string{"alice", "bob", "ops"} {
		if err := s.SaveUser(model.User{ID: id, CreatedAt: time.Now()}); err != nil {
			t.Fatalf("SaveUser %s: %v", id, err)
		}
		if err := s.AddSession(id, sessionIDFor(id)); err != nil {
			t.Fatalf("AddSession %s: %v", id, err)
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
	return r, s, cfg.SessionSecret, ziel
}

// trigger sendet die Anfrage; userID == "" heisst: ohne Cookie.
func trigger(t *testing.T, r http.Handler, secret, method, pfad, userID string) *httptest.ResponseRecorder {
	t.Helper()
	req := httptest.NewRequest(method, pfad, strings.NewReader("{}"))
	req.Header.Set("Content-Type", "application/json")
	if userID != "" {
		req.AddCookie(sessionCookieFor(userID, secret))
	}
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	return w
}

// AC-1: Admin erreicht auf allen drei Trigger-Routen den Python-Proxy.
func TestAdminTrigger_Admin_ReachesProxy_OnAllThreeRoutes(t *testing.T) {
	r, _, secret, ziel := adminTestRouter(t, "alice")

	for _, pfad := range triggerPfade {
		w := trigger(t, r, secret, http.MethodPost, pfad, "alice")
		if w.Code != http.StatusOK {
			t.Errorf("Admin %s: erwartet 200, bekommen %d: %s", pfad, w.Code, w.Body.String())
		}
		if !strings.Contains(w.Body.String(), "python-core") {
			t.Errorf("Admin %s: Antwort muss die des Python-Ziels sein, bekommen %q", pfad, w.Body.String())
		}
		if got := ziel.n(pfad); got != 1 {
			t.Errorf("Admin %s: Python-Ziel muss genau 1x aufgerufen werden, wurde %dx", pfad, got)
		}
	}
}

// AC-2: Zwei-Nutzer-Test — bob (kein Admin) bekommt 403 mit exaktem Body, das
// Ziel bleibt unberuehrt; alice im selben Lauf 200.
func TestAdminTrigger_NormalUser_Forbidden_AdminInSameRunAllowed(t *testing.T) {
	r, _, secret, ziel := adminTestRouter(t, "alice")

	for _, pfad := range triggerPfade {
		w := trigger(t, r, secret, http.MethodPost, pfad, "bob")
		if w.Code != http.StatusForbidden {
			t.Errorf("bob %s: erwartet 403, bekommen %d: %s", pfad, w.Code, w.Body.String())
		}
		if got := strings.TrimSpace(w.Body.String()); got != `{"error":"forbidden"}` {
			t.Errorf("bob %s: Body erwartet %q, bekommen %q", pfad, `{"error":"forbidden"}`, got)
		}
		if ct := w.Header().Get("Content-Type"); !strings.HasPrefix(ct, "application/json") {
			t.Errorf("bob %s: Content-Type erwartet application/json, bekommen %q", pfad, ct)
		}
	}
	if got := ziel.gesamt(); got != 0 {
		t.Fatalf("nach den bob-Anfragen darf das Python-Ziel NICHT aufgerufen worden sein, Zaehler=%d", got)
	}

	for _, pfad := range triggerPfade {
		if w := trigger(t, r, secret, http.MethodPost, pfad, "alice"); w.Code != http.StatusOK {
			t.Errorf("alice %s: erwartet 200, bekommen %d", pfad, w.Code)
		}
	}
	if got := ziel.gesamt(); got != len(triggerPfade) {
		t.Errorf("nach den alice-Anfragen: erwartet %d Aufrufe, Zaehler=%d", len(triggerPfade), got)
	}
}

// AC-3: ohne Cookie 401 (nicht 403) — die Anmeldepflicht bleibt bei der globalen Kette.
func TestAdminTrigger_NoCookie_Returns401_NotForbidden(t *testing.T) {
	r, _, secret, ziel := adminTestRouter(t, "alice")

	for _, pfad := range triggerPfade {
		w := trigger(t, r, secret, http.MethodPost, pfad, "")
		if w.Code != http.StatusUnauthorized {
			t.Errorf("ohne Cookie %s: erwartet 401, bekommen %d", pfad, w.Code)
		}
	}
	if got := ziel.gesamt(); got != 0 {
		t.Errorf("ohne Anmeldung darf das Python-Ziel nicht erreicht werden, Zaehler=%d", got)
	}
}

// AC-4: leere Admin-Liste => JEDER angemeldete Nutzer (auch cfg.UserID) bekommt 403.
func TestAdminTrigger_EmptyAdminList_EveryoneForbidden(t *testing.T) {
	for _, konfig := range []string{"", "   ", " , ,"} {
		r, _, secret, ziel := adminTestRouter(t, konfig)

		for _, uid := range []string{"alice", "bob", "ops"} {
			for _, pfad := range triggerPfade {
				w := trigger(t, r, secret, http.MethodPost, pfad, uid)
				if w.Code != http.StatusForbidden {
					t.Errorf("Liste=%q, %s %s: erwartet 403, bekommen %d", konfig, uid, pfad, w.Code)
				}
			}
		}
		if got := ziel.gesamt(); got != 0 {
			t.Errorf("Liste=%q: Python-Ziel darf nie erreicht werden, Zaehler=%d", konfig, got)
		}
	}
}

// AC-5 im verdrahteten Router: die Liste " alice , ,bob," macht genau alice und
// bob zu Admins; ops (cfg.UserID) bleibt ausgesperrt.
func TestAdminTrigger_ListParsingReachesRouter(t *testing.T) {
	r, _, secret, ziel := adminTestRouter(t, " alice , ,bob,")

	pfad := triggerPfade[0]
	if w := trigger(t, r, secret, http.MethodPost, pfad, "alice"); w.Code != http.StatusOK {
		t.Errorf("alice: erwartet 200, bekommen %d", w.Code)
	}
	if w := trigger(t, r, secret, http.MethodPost, pfad, "bob"); w.Code != http.StatusOK {
		t.Errorf("bob: erwartet 200, bekommen %d", w.Code)
	}
	if w := trigger(t, r, secret, http.MethodPost, pfad, "ops"); w.Code != http.StatusForbidden {
		t.Errorf("ops: erwartet 403, bekommen %d", w.Code)
	}
	if got := ziel.n(pfad); got != 2 {
		t.Errorf("erwartet 2 Aufrufe (alice, bob), Zaehler=%d", got)
	}
}

// AC-7: S1 aendert NUR die drei Trigger. Ein normaler Nutzer bekommt weiterhin
// GET /api/scheduler/status und POST /api/trips/{id}/send fuer den eigenen Trip.
func TestAdminTrigger_NormalUser_StatusAndTripSendUnchanged(t *testing.T) {
	r, s, secret, ziel := adminTestRouter(t, "alice")
	seedRouteTrip(t, s, "bob", "t1")

	status := trigger(t, r, secret, http.MethodGet, "/api/scheduler/status", "bob")
	if status.Code != http.StatusOK {
		t.Errorf("bob GET /api/scheduler/status: erwartet 200, bekommen %d", status.Code)
	}

	send := trigger(t, r, secret, http.MethodPost, "/api/trips/t1/send?report_type=morning", "bob")
	if send.Code != http.StatusOK {
		t.Fatalf("bob POST /api/trips/t1/send: erwartet 200 (Proxy erreicht), bekommen %d: %s", send.Code, send.Body.String())
	}
	if got := ziel.n("/api/scheduler/trips/t1/send"); got != 1 {
		t.Errorf("/send muss das Python-Ziel genau 1x erreichen, Zaehler=%d", got)
	}
	// ... und ruft dabei KEINEN der drei Sammel-Trigger.
	for _, pfad := range triggerPfade {
		if got := ziel.n(pfad); got != 0 {
			t.Errorf("/send darf %s nicht aufrufen, Zaehler=%d", pfad, got)
		}
	}
}
