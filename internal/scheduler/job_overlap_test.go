package scheduler

import (
	"sync/atomic"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/config"
)

// ---------------------------------------------------------------------------
// Issue #1447 Scheibe S2a — Ueberlappungsschutz + Teilerfolg im Go-Scheduler
//
// Spec: docs/specs/modules/fix_1447_s2a_scheduler_ueberlappung_teilerfolg.md
//
// Diese Datei prueft Teil A (Ueberlappungsschutz): recordRun() muss den
// zweiten Aufruf fuer eine noch laufende jobID uebergehen (TryLock statt
// Lock), den uebersprungenen Tick als eigenen overlapState verbuchen und
// dabei lastRuns[jobID] (den zuletzt tatsaechlich ausgefuehrten Lauf)
// unangetastet lassen.
//
// Alle vier Tests bauen GENAU EINE *Scheduler-Instanz auf und fahren
// recordRun-Aufrufe fuer dieselbe jobID echt nebenlaeufig (ungepufferter
// Signal-Kanal statt time.Sleep) — ein Scheduler pro Fall wuerde getrennte
// Sperren messen und faelschlich gruen werden, obwohl der Schutz fehlt.
// ---------------------------------------------------------------------------

func newOverlapTestScheduler(t *testing.T) *Scheduler {
	t.Helper()
	cfg := &config.Config{
		PythonCoreURL:     "http://localhost:8000",
		SchedulerTimezone: "Europe/Vienna",
	}
	sched, err := New(cfg, testStore(t))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}
	return sched
}

// TestRecordRun_SecondCallDuringOverlap_NotExecuted (AC-1) — der heikelste
// Test dieser Scheibe. Gegenprobe: vor der TryLock-Sperre in recordRun ist
// dieser Test nachweislich rot, weil recordRun jede fn() bedingungslos
// ausfuehrt — der Zaehler steht dann auf 2 statt 1.
func TestRecordRun_SecondCallDuringOverlap_NotExecuted(t *testing.T) {
	sched := newOverlapTestScheduler(t)

	var execCount atomic.Int32
	entered := make(chan struct{})
	release := make(chan struct{})
	done := make(chan struct{})

	go func() {
		sched.recordRun("overlap_job", func() error {
			execCount.Add(1)
			close(entered)
			<-release
			return nil
		})
		close(done)
	}()

	<-entered // die erste fn ist garantiert bereits innerhalb ihres Rumpfs

	// Zweiter, synchroner Aufruf fuer dieselbe jobID, waehrend der erste
	// noch blockiert.
	sched.recordRun("overlap_job", func() error {
		execCount.Add(1)
		return nil
	})

	close(release)
	select {
	case <-done:
	case <-time.After(2 * time.Second):
		t.Fatal("first recordRun goroutine never finished")
	}

	if got := execCount.Load(); got != 1 {
		t.Fatalf("expected fn executed exactly once (second call must be skipped "+
			"due to overlap), got %d", got)
	}
}

// TestRecordRun_ConsecutiveOverlapSkips_CountDistinguishesFromSingleSkip
// (AC-2) — der Zaehler steigt nachweislich 1 -> 2 -> 3, nicht nur
// "vorhanden".
func TestRecordRun_ConsecutiveOverlapSkips_CountDistinguishesFromSingleSkip(t *testing.T) {
	sched := newOverlapTestScheduler(t)

	entered := make(chan struct{})
	release := make(chan struct{})
	done := make(chan struct{})

	go func() {
		sched.recordRun("overlap_job2", func() error {
			close(entered)
			<-release
			return nil
		})
		close(done)
	}()
	<-entered

	skippedCount := func() int {
		sched.mu.RLock()
		defer sched.mu.RUnlock()
		st, ok := sched.overlapState["overlap_job2"]
		if !ok {
			return 0
		}
		return st.SkippedSinceLastRun
	}

	sched.recordRun("overlap_job2", func() error { return nil })
	if got := skippedCount(); got != 1 {
		t.Fatalf("after 1st extra tick: expected SkippedSinceLastRun=1, got %d", got)
	}
	sched.recordRun("overlap_job2", func() error { return nil })
	if got := skippedCount(); got != 2 {
		t.Fatalf("after 2nd extra tick: expected SkippedSinceLastRun=2, got %d", got)
	}
	sched.recordRun("overlap_job2", func() error { return nil })
	if got := skippedCount(); got != 3 {
		t.Fatalf("after 3rd extra tick: expected SkippedSinceLastRun=3, got %d", got)
	}

	close(release)
	select {
	case <-done:
	case <-time.After(2 * time.Second):
		t.Fatal("first recordRun goroutine never finished")
	}
}

// TestRecordRun_OverlapSkip_DoesNotOverwriteLastExecutedRun (AC-3) — Design-
// Korrektur v1.1: ein Overlap-Skip darf den letzten tatsaechlich
// ausgefuehrten Lauf (last_run) nicht ueberschreiben, sonst sieht ein
// Dauerhaenger "frisch" aus (#1434-Muster).
func TestRecordRun_OverlapSkip_DoesNotOverwriteLastExecutedRun(t *testing.T) {
	sched := newOverlapTestScheduler(t)
	sched.Start()
	defer sched.Stop()

	// Erster Lauf schliesst vollstaendig und erfolgreich ab.
	sched.recordRun("alert_checks", func() error { return nil })

	sched.mu.RLock()
	firstRun, ok := sched.lastRuns["alert_checks"]
	sched.mu.RUnlock()
	if !ok || firstRun == nil {
		t.Fatal("expected alert_checks to have a recorded run after the first call")
	}
	firstTime := firstRun.Time

	entered := make(chan struct{})
	release := make(chan struct{})
	done := make(chan struct{})
	go func() {
		sched.recordRun("alert_checks", func() error {
			close(entered)
			<-release
			return nil
		})
		close(done)
	}()
	<-entered

	// Mehrere Skips, waehrend der zweite Lauf blockiert.
	sched.recordRun("alert_checks", func() error { return nil })
	sched.recordRun("alert_checks", func() error { return nil })

	status := sched.Status()
	jobs, ok := status["jobs"].([]map[string]any)
	if !ok {
		t.Fatalf("status jobs should be []map[string]any, got %T", status["jobs"])
	}
	var job map[string]any
	for _, j := range jobs {
		if j["id"] == "alert_checks" {
			job = j
		}
	}
	if job == nil {
		t.Fatal("alert_checks job not found in status")
	}

	lr, ok := job["last_run"].(map[string]any)
	if !ok || lr == nil {
		t.Fatal("expected last_run to be present")
	}
	if lr["status"] != "ok" {
		t.Fatalf("expected last_run.status to remain 'ok', got %v", lr["status"])
	}
	// Status() formats last_run.time as RFC3339 (second precision) — compare
	// as formatted strings so the assertion isn't tripped by the format's own
	// sub-second truncation, which would be a false failure unrelated to the
	// behavior under test.
	lrTimeStr, _ := lr["time"].(string)
	wantTimeStr := firstTime.Format(time.RFC3339)
	if lrTimeStr != wantTimeStr {
		t.Fatalf("expected last_run.time unchanged at %q (the first, fully executed "+
			"run), got %q — a skip must never overwrite the last executed run", wantTimeStr, lrTimeStr)
	}

	overlap, ok := job["overlap"].(map[string]any)
	if !ok || overlap == nil {
		t.Fatal("expected overlap field to be present after skips occurred")
	}
	if overlap["skipped_since_last_run"] != 2 {
		t.Fatalf("expected overlap.skipped_since_last_run=2, got %v",
			overlap["skipped_since_last_run"])
	}

	close(release)
	select {
	case <-done:
	case <-time.After(2 * time.Second):
		t.Fatal("second recordRun goroutine never finished")
	}
}

// TestRecordRun_DifferentJobsDoNotBlockEachOther (AC-4) — Beweis, dass
// Sperre und Overlap-Zustand je jobID gefuehrt werden, nicht global.
func TestRecordRun_DifferentJobsDoNotBlockEachOther(t *testing.T) {
	sched := newOverlapTestScheduler(t)

	var jobBCount atomic.Int32

	enteredA := make(chan struct{})
	releaseA := make(chan struct{})
	doneA := make(chan struct{})

	go func() {
		sched.recordRun("job_a", func() error {
			close(enteredA)
			<-releaseA
			return nil
		})
		close(doneA)
	}()
	<-enteredA

	// job_b muss vollstaendig durchlaufen, waehrend job_a noch blockiert.
	sched.recordRun("job_b", func() error {
		jobBCount.Add(1)
		return nil
	})

	if got := jobBCount.Load(); got != 1 {
		t.Fatalf("expected job_b to execute fully while job_a is still blocked, got count=%d", got)
	}

	close(releaseA)
	select {
	case <-doneA:
	case <-time.After(2 * time.Second):
		t.Fatal("job_a recordRun goroutine never finished")
	}
}
