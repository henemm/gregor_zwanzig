package scheduler

// TDD RED — Issue #2155 Scheibe S1 (Admin-Rolle), AC-6.
//
// Spec: docs/specs/modules/admin_rolle_s1.md § "4. Cron-Betrieb"
//
// Der geplante Betrieb ruft den Python-Core DIREKT (nicht ueber den Router) und
// darf von GZ_ADMIN_USER_IDS nicht abhaengen. Der Test setzt die Admin-Liste
// ausdruecklich leer bzw. auf einen fremden Eintrag und verlangt, dass alle drei
// Jobs ihr Ziel trotzdem erreichen.
//
// RED-Signal: Config.AdminUserIDs existiert noch nicht (Uebersetzungsfehler).
// Nach der Umsetzung ist das ein Regressions-Waechter gegen den Fehler
// "RequireAdmin versehentlich in den Scheduler verdrahtet".

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"sync"
	"testing"

	"github.com/henemm/gregor-api/internal/config"
)

func TestScheduler_CronJobsReachPython_RegardlessOfAdminList(t *testing.T) {
	for _, adminListe := range []string{"", "niemand-aus-der-testwelt"} {
		var mu sync.Mutex
		aufrufe := map[string]int{}
		server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			mu.Lock()
			aufrufe[r.URL.Path]++
			mu.Unlock()
			w.WriteHeader(http.StatusOK)
			fmt.Fprint(w, `{"status":"ok"}`)
		}))

		cfg := &config.Config{
			PythonCoreURL:     server.URL,
			SchedulerTimezone: "Europe/Vienna",
			AdminUserIDs:      adminListe,
		}
		sched, err := New(cfg, testStore(t))
		if err != nil {
			server.Close()
			t.Fatalf("New() error: %v", err)
		}

		sched.tripReports()
		sched.alertChecks()
		sched.inboundCommands()
		server.Close()

		mu.Lock()
		for _, pfad := range []string{
			"/api/scheduler/trip-reports",
			"/api/scheduler/alert-checks",
			"/api/scheduler/inbound-commands",
		} {
			if aufrufe[pfad] < 1 {
				t.Errorf("AdminUserIDs=%q: Scheduler-Lauf muss %s erreichen, Aufrufe=%d (alle: %v)",
					adminListe, pfad, aufrufe[pfad], aufrufe)
			}
		}
		mu.Unlock()
	}
}
