package scheduler

// TDD RED — Issue #2218 Scheibe C, Eintrag C5-15 (AC-8).
//
// Spec: docs/specs/modules/fix_2218_scheibe_c_observability.md
//
// Heute meldet Status() "running": true FEST verdrahtet, auch wenn der
// Scheduler nie gestartet oder schon gestoppt wurde. Gefordert: ehrlicher
// Prozesszustand — false vor Start(), true nach Start(), false nach Stop().
// Echter Scheduler, kein Mock. Der Test prueft nur das JSON-Feld (kein neues
// Symbol), damit er kompiliert und an der ZUSICHERUNG scheitert.

import (
	"testing"

	"github.com/henemm/gregor-api/internal/config"
)

func runningFlag(t *testing.T, sched *Scheduler) bool {
	t.Helper()
	v, ok := sched.Status()["running"]
	if !ok {
		t.Fatal("Status() traegt kein Feld \"running\"")
	}
	b, ok := v.(bool)
	if !ok {
		t.Fatalf("\"running\" ist kein bool: %T", v)
	}
	return b
}

// AC-8: false vor Start(), true nach Start(), false nach Stop().
func TestStatusRunning_FollowsRealLifecycle(t *testing.T) {
	cfg := &config.Config{
		PythonCoreURL:     "http://localhost:8000",
		SchedulerTimezone: "Europe/Vienna",
	}
	sched, err := New(cfg, testStore(t))
	if err != nil {
		t.Fatalf("New() returned error: %v", err)
	}

	if got := runningFlag(t, sched); got {
		t.Errorf("vor Start(): running erwartet false, bekommen true (fest verdrahtet?)")
	}

	sched.Start()
	if got := runningFlag(t, sched); !got {
		t.Errorf("nach Start(): running erwartet true, bekommen false")
	}

	sched.Stop()
	if got := runningFlag(t, sched); got {
		t.Errorf("nach Stop(): running erwartet false, bekommen true")
	}
}
