package scheduler

// Issue #2439 (Fix-Schleife, Staging-Befund 15.10.): Der SMS-Nachversuch lief
// 0/3/8 s; die Luecke 3->8 s entspricht dem uvicorn-Keep-Alive-Default (5 s).
// Go hat die vom Core gerade geschlossene Idle-Verbindung wiederverwendet ->
// `Post ".../inbound-sms": EOF`, der Lauf wurde als "error" gebucht.
//
// Dieser Test bildet das deterministisch nach, ohne Timing-Rennen: der
// Fake-Core beantwortet die ERSTE Anfrage einer TCP-Verbindung normal (mit
// Keep-Alive) und schliesst die Verbindung ohne Antwort, sobald auf DERSELBEN
// Verbindung eine weitere Anfrage kommt. Anfragen auf einer neuen Verbindung
// beantwortet er normal. Getrieben wird der echte Cron-Pfad (cronPoll ->
// recordRun -> s.client) mit dem vom echten Konstruktor gebauten Client;
// s.client wird NICHT ersetzt. Zugesichert wird dort, wo es wirkt: last_run
// des Jobs im Status und die Zahl der beim Core angekommenen Anfragen.
//
// Produktivreihenfolge (Adversary F001/F002): wie cmd/server/main.go
// installGuards() laufen ZUERST coreauth.Install, DANN egress.Install und erst
// danach scheduler.New. Beide ersetzen http.DefaultTransport durch Wrapper;
// der Core-Client muss darauf aufsetzen (kein Panic, Auth-Header #2142 bleibt).
// Der Fake-Core antwortet ohne gueltigen X-GZ-Core-Auth mit 401.

import (
	"context"
	"fmt"
	"net"
	"net/http"
	"net/http/httptest"
	"sync"
	"sync/atomic"
	"testing"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/coreauth"
	"github.com/henemm/gregor-api/internal/egress"
)

const testCoreSecret = "test-core-secret-2439-keepalive-0123456789"

type connZaehlerKey struct{}

// einmalProVerbindungCore beantwortet je TCP-Verbindung genau eine Anfrage;
// jede weitere auf derselben Verbindung wird gelesen und die Verbindung dann
// ohne Antwort geschlossen (wie ein Server, dessen Keep-Alive abgelaufen ist).
type einmalProVerbindungCore struct {
	srv *httptest.Server

	mu          sync.Mutex
	beantwortet map[string]int
	abgewiesen  int
	ohneAuth    int
}

func newEinmalProVerbindungCore(t *testing.T) *einmalProVerbindungCore {
	t.Helper()
	c := &einmalProVerbindungCore{beantwortet: map[string]int{}}
	srv := httptest.NewUnstartedServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		zaehler := r.Context().Value(connZaehlerKey{}).(*int32)
		if atomic.AddInt32(zaehler, 1) > 1 {
			c.mu.Lock()
			c.abgewiesen++
			c.mu.Unlock()
			hj, ok := w.(http.Hijacker)
			if !ok {
				t.Errorf("ResponseWriter kann nicht hijacken")
				return
			}
			conn, _, err := hj.Hijack()
			if err != nil {
				t.Errorf("Hijack: %v", err)
				return
			}
			conn.Close()
			return
		}
		if r.Header.Get(coreauth.HeaderName) != testCoreSecret {
			c.mu.Lock()
			c.ohneAuth++
			c.mu.Unlock()
			http.Error(w, `{"detail":"unauthorized"}`, http.StatusUnauthorized)
			return
		}
		c.mu.Lock()
		c.beantwortet[r.URL.Path]++
		c.mu.Unlock()
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		fmt.Fprint(w, `{"status":"ok","processed":0,"count":0}`)
	}))
	srv.Config.ConnContext = func(ctx context.Context, _ net.Conn) context.Context {
		return context.WithValue(ctx, connZaehlerKey{}, new(int32))
	}
	srv.Start()
	t.Cleanup(srv.Close)
	c.srv = srv
	return c
}

func (c *einmalProVerbindungCore) zahl(p string) (int, int, int) {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.beantwortet[p], c.abgewiesen, c.ohneAuth
}

// installiereGuardsWieProd stellt cmd/server/main.go installGuards() nach:
// ZUERST coreauth.Install, DANN egress.Install. Beide sind paketglobal;
// Cleanup in umgekehrter Reihenfolge.
func installiereGuardsWieProd(t *testing.T, cfg *config.Config) {
	t.Helper()
	if !coreauth.Install(cfg) {
		t.Fatal("coreauth.Install() hat nicht installiert (schon aktiv oder cfg unvollstaendig)")
	}
	t.Cleanup(coreauth.Uninstall)
	if !egress.Install(cfg) {
		t.Fatal("egress.Install() hat nicht installiert (schon aktiv oder Env != staging)")
	}
	t.Cleanup(egress.Uninstall) // laeuft VOR coreauth.Uninstall (LIFO)
}

func lastRunStatus(t *testing.T, s *Scheduler, jobID string) (string, any) {
	t.Helper()
	jobs, ok := s.Status()["jobs"].([]map[string]any)
	if !ok {
		t.Fatalf("Status()[\"jobs\"] hat unerwarteten Typ")
	}
	for _, j := range jobs {
		if j["id"] != jobID {
			continue
		}
		lr, ok := j["last_run"].(map[string]any)
		if !ok {
			t.Fatalf("%s: kein last_run nach dem Lauf: %v", jobID, j["last_run"])
		}
		st, _ := lr["status"].(string)
		return st, lr["error"]
	}
	t.Fatalf("Job %q nicht im Status", jobID)
	return "", nil
}

func TestCoreVerbindung_ZweiterPollLaufScheitertNichtAnGeschlossenerIdleVerbindung(t *testing.T) {
	for _, tc := range []struct{ job, pfad string }{
		{jobSMS, pfadSMS},
		{jobMail, pfadMail},
	} {
		t.Run(tc.job, func(t *testing.T) {
			core := newEinmalProVerbindungCore(t)
			cfg := &config.Config{
				PythonCoreURL:     core.srv.URL,
				SchedulerTimezone: "Europe/Vienna",
				CoreSharedSecret:  testCoreSecret,
				Env:               "staging",
			}
			installiereGuardsWieProd(t, cfg)
			s, err := New(cfg, testStoreWithUsers(t, "alice"))
			if err != nil {
				t.Fatalf("New() error: %v", err)
			}

			for lauf := 1; lauf <= 2; lauf++ {
				s.cronPoll(tc.job)
				st, fehler := lastRunStatus(t, s, tc.job)
				if st != "ok" {
					t.Fatalf("%s Lauf %d: last_run.status = %q (error=%v), erwartet \"ok\" -- "+
						"der Client hat eine vom Core geschlossene Idle-Verbindung wiederverwendet",
						tc.job, lauf, st, fehler)
				}
			}
			if n, abgewiesen, ohneAuth := core.zahl(tc.pfad); n != 2 || ohneAuth != 0 {
				t.Fatalf("%s: Core hat %d Anfragen beantwortet (abgewiesen auf alter Verbindung: %d, "+
					"ohne gueltigen %s: %d), erwartet 2 beantwortet und 0 ohne Auth",
					tc.job, n, abgewiesen, coreauth.HeaderName, ohneAuth)
			}
		})
	}
}
