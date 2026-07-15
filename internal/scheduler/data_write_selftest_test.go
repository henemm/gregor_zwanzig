package scheduler

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/store"
)

// Issue #1120: dataWriteSelftest — Edge-getriggertes Alerting + Status-Sichtbarkeit.

// buildSelftestStore creates a store with one trip file at
// users/default/briefings/trip1.json (Issue #1250 Scheibe 7a: probeDataWritable
// scans briefings/, the real write-location after the Cutover -- was trips/
// before) and returns store + path to that file.
func buildSelftestStore(t *testing.T) (*store.Store, string) {
	t.Helper()
	tmpDir := t.TempDir()
	s := store.New(tmpDir, "default")
	tripDir := filepath.Join(tmpDir, "users", "default", "briefings")
	if err := os.MkdirAll(tripDir, 0755); err != nil {
		t.Fatalf("mkdir briefings: %v", err)
	}
	tripFile := filepath.Join(tripDir, "trip1.json")
	if err := os.WriteFile(tripFile, []byte(`{"id":"trip1"}`), 0644); err != nil {
		t.Fatalf("write trip file: %v", err)
	}
	return s, tripFile
}

func newSelftestScheduler(t *testing.T, st *store.Store) *Scheduler {
	t.Helper()
	cfg := &config.Config{
		PythonCoreURL:     "http://localhost:8000",
		SchedulerTimezone: "Europe/Vienna",
	}
	sched, err := New(cfg, st)
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}
	return sched
}

// AC-1: /api/scheduler/status zeigt status=error mit Pfad wenn Datei nicht
// schreibbar ist.
func TestDataWriteSelftest_StatusShowsErrorWithPath(t *testing.T) {
	if os.Geteuid() == 0 {
		t.Skip("root ignoriert DAC-Permission-Checks")
	}
	st, tripFile := buildSelftestStore(t)
	if err := os.Chmod(tripFile, 0444); err != nil {
		t.Fatalf("chmod: %v", err)
	}
	sched := newSelftestScheduler(t, st)
	sched.notifier = func(_, _, _, _, _ string) error { return nil }
	sched.Start()
	defer sched.Stop()

	sched.dataWriteSelftest()

	status := sched.Status()
	jobs := status["jobs"].([]map[string]any)
	var found bool
	for _, job := range jobs {
		if job["id"] == "data_write_selftest" {
			found = true
			lr, ok := job["last_run"].(map[string]any)
			if !ok || lr == nil {
				t.Fatal("data_write_selftest should have last_run after execution")
			}
			if lr["status"] != "error" {
				t.Fatalf("expected status error, got %v", lr["status"])
			}
			errMsg, _ := lr["error"].(string)
			if !strings.Contains(errMsg, tripFile) {
				t.Fatalf("expected error to contain path %q, got %q", tripFile, errMsg)
			}
		}
	}
	if !found {
		t.Fatal("data_write_selftest job not found in status")
	}
}

// AC-4: ok→error-Übergang sendet genau eine MQ-Nachricht mit Priorität "high".
func TestDataWriteSelftest_OkToErrorSendsOneHighAlert(t *testing.T) {
	if os.Geteuid() == 0 {
		t.Skip("root ignoriert DAC-Permission-Checks")
	}
	st, tripFile := buildSelftestStore(t)
	sched := newSelftestScheduler(t, st)

	type call struct {
		priority string
		body     string
	}
	var calls []call
	sched.notifier = func(_, _, priority, _, body string) error {
		calls = append(calls, call{priority, body})
		return nil
	}

	sched.dataWriteSelftest() // Lauf 1: schreibbar -> ok

	if err := os.Chmod(tripFile, 0444); err != nil {
		t.Fatalf("chmod: %v", err)
	}
	sched.dataWriteSelftest() // Lauf 2: nicht schreibbar -> Übergang ok->error

	if len(calls) != 1 {
		t.Fatalf("expected exactly 1 notifier call on ok->error transition, got %d", len(calls))
	}
	if calls[0].priority != "high" {
		t.Fatalf("expected priority high, got %q", calls[0].priority)
	}
	if !strings.Contains(calls[0].body, tripFile) {
		t.Fatalf("expected body to mention path %q, got %q", tripFile, calls[0].body)
	}
}

// AC-5: mehrere aufeinanderfolgende error-Läufe ohne Übergang lösen KEINEN
// weiteren Alert aus (Flapping-Schutz).
func TestDataWriteSelftest_RepeatedErrorSendsOnlyOnce(t *testing.T) {
	if os.Geteuid() == 0 {
		t.Skip("root ignoriert DAC-Permission-Checks")
	}
	st, tripFile := buildSelftestStore(t)
	if err := os.Chmod(tripFile, 0444); err != nil {
		t.Fatalf("chmod: %v", err)
	}
	sched := newSelftestScheduler(t, st)

	var count int
	sched.notifier = func(_, _, _, _, _ string) error {
		count++
		return nil
	}

	sched.dataWriteSelftest()
	sched.dataWriteSelftest()
	sched.dataWriteSelftest()

	if count != 1 {
		t.Fatalf("expected exactly 1 notifier call across 3 consecutive error runs, got %d", count)
	}
}

// AC-6: error→ok-Übergang sendet Recovery-Notiz mit Priorität "normal";
// bestehende Jobs bleiben unangetastet (geprüft durch parallel laufende
// bestehende scheduler_test.go-Suite).
func TestDataWriteSelftest_ErrorToOkSendsRecoveryNotice(t *testing.T) {
	if os.Geteuid() == 0 {
		t.Skip("root ignoriert DAC-Permission-Checks")
	}
	st, tripFile := buildSelftestStore(t)
	if err := os.Chmod(tripFile, 0444); err != nil {
		t.Fatalf("chmod: %v", err)
	}
	sched := newSelftestScheduler(t, st)

	var priorities []string
	sched.notifier = func(_, _, priority, _, _ string) error {
		priorities = append(priorities, priority)
		return nil
	}

	sched.dataWriteSelftest() // Lauf 1: error (initialer ok->error Alert)

	if err := os.Chmod(tripFile, 0644); err != nil {
		t.Fatalf("chmod: %v", err)
	}
	sched.dataWriteSelftest() // Lauf 2: wieder schreibbar -> error->ok

	if len(priorities) != 2 {
		t.Fatalf("expected 2 notifier calls (ok->error + error->ok), got %d: %v", len(priorities), priorities)
	}
	if priorities[0] != "high" {
		t.Fatalf("expected first call priority high, got %q", priorities[0])
	}
	if priorities[1] != "normal" {
		t.Fatalf("expected second call (recovery) priority normal, got %q", priorities[1])
	}
}
