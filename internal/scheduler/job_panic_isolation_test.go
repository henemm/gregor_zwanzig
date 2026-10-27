package scheduler

// Issue #2217 — Stapellaeufe abschotten (Go-Teil, AC-1..AC-3).
// Spec: docs/specs/modules/fix_2217_stapellaeufe_abschotten.md
//
// Echte Panics, kein Mock des Prueflings: die Naht ist die Job-Funktion
// (recordRun), der HTTP-Transport (Nutzer-Aufruf) bzw. der echte Cron-Takt.

import (
	"net/http"
	"sync/atomic"
	"testing"
	"time"
)

// AC-1: Panic in der Job-Funktion reisst den Prozess nicht mit, Status "error"
// mit exakt "panic in <jobID>" (PO-Entscheid 2026-10-07: Status-Text ohne
// Interna, Panic-Wert nur im Server-Log), Sperre frei (zweiter Aufruf wird ausgefuehrt).
func TestRecordRun_PanicInJob_RecordedAsErrorAndLockReleased(t *testing.T) {
	sched := newOverlapTestScheduler(t)

	sched.recordRun("panic_job", func() error {
		panic("kaputte Daten")
	})

	lr := lastRunOf(sched, "panic_job")
	if lr == nil {
		t.Fatal("expected a lastRuns entry for the panicking job (AC-1), got none")
	}
	if lr.Status != "error" {
		t.Fatalf("expected status 'error' after panic (AC-1), got %q", lr.Status)
	}
	if lr.Error != "panic in panic_job" {
		t.Fatalf("expected exact error %q without panic value (AC-1, PO-Entscheid 2026-10-07), got %q", "panic in panic_job", lr.Error)
	}

	var ran atomic.Int32
	sched.recordRun("panic_job", func() error {
		ran.Add(1)
		return nil
	})
	if ran.Load() != 1 {
		t.Fatal("expected the second call to actually run -- lock must be released after panic (AC-1)")
	}
	if lr := lastRunOf(sched, "panic_job"); lr == nil || lr.Status != "ok" {
		t.Fatalf("expected status 'ok' after the healthy second run (AC-1), got %+v", lr)
	}
}

// panicTransport loest fuer den Nutzer "alice" eine echte Panic im
// HTTP-Transport aus (Naht des Nutzer-Aufrufs), alle anderen laufen echt durch.
type panicTransport struct {
	next http.RoundTripper
}

func (p panicTransport) RoundTrip(r *http.Request) (*http.Response, error) {
	if r.URL.Query().Get("user_id") == "alice" {
		panic("alice-Aufruf kaputt")
	}
	return p.next.RoundTrip(r)
}

// AC-2: Panic im Aufruf fuer Nutzer A -> A fehlgeschlagen, B trotzdem bedient.
func TestCallUser_PanicForOneUser_OtherUserStillServed(t *testing.T) {
	bs := newBudgetServer(t)
	sched, _, _ := newBudgetScheduler(t, bs.srv.URL, "alice", "bob")
	sched.client = &http.Client{
		Timeout:   5 * time.Second,
		Transport: panicTransport{next: http.DefaultTransport},
	}

	sched.alertChecks()

	if got := bs.count("bob"); got != 1 {
		t.Fatalf("expected bob served exactly once despite alice's panic (AC-2), got %d", got)
	}
	if got := bs.count("alice"); got != 0 {
		t.Fatalf("expected no POST for alice (panic before the wire), got %d", got)
	}
	alice := mustUserRecord(t, sched, "alert_checks", "alice")
	if alice.ConsecutiveFailures != 1 {
		t.Fatalf("expected alice counted as failed (AC-2), got %+v", alice)
	}
	bob := mustUserRecord(t, sched, "alert_checks", "bob")
	if bob.ConsecutiveFailures != 0 {
		t.Fatalf("expected bob not failed (AC-2), got %+v", bob)
	}
}

// AC-3: Eintrag ausserhalb von recordRun, der ueber den echten Cron-Takt
// panikt -> aeussere Cron-Kette faengt ab, Prozess und Takt laufen weiter.
func TestNew_CronChainRecoversPanicOutsideRecordRun(t *testing.T) {
	sched := newOverlapTestScheduler(t)

	var ticks atomic.Int32
	if _, err := sched.cron.AddFunc("@every 1s", func() {
		ticks.Add(1)
		panic("ausserhalb recordRun")
	}); err != nil {
		t.Fatalf("AddFunc: %v", err)
	}
	sched.cron.Start()
	defer sched.cron.Stop()

	deadline := time.Now().Add(5 * time.Second)
	for time.Now().Before(deadline) {
		if ticks.Load() >= 2 {
			return // zwei Ticks trotz Panic: Kette hat gefangen, Prozess lebt
		}
		time.Sleep(50 * time.Millisecond)
	}
	t.Fatalf("expected >=2 cron ticks despite panics (AC-3), got %d", ticks.Load())
}
