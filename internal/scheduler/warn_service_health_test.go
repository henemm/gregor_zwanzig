package scheduler

import (
	"os"
	"path/filepath"
	"strconv"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/store"
)

// TDD RED: Issue #1422 S2 — WarnServiceHealth() im /api/scheduler/status
//
// Spec: docs/specs/modules/fix_1422_warn_ausfall_alarm.md
//
// KEINE Mocks: echte JSONL-/JSON-Fixture-Dateien in t.TempDir(),
// WarnServiceHealth() wird real aufgerufen.

// newWarnServiceHealthTestScheduler builds a Scheduler backed by tmpDir.
func newWarnServiceHealthTestScheduler(t *testing.T, tmpDir string) *Scheduler {
	t.Helper()
	s := store.New(tmpDir, "default")
	cfg := &config.Config{
		PythonCoreURL:     "http://localhost:8000",
		SchedulerTimezone: "Europe/Vienna",
	}
	sched, err := New(cfg, s)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	return sched
}

// writeWarnServiceCallsJournal writes data/diagnostics/warn_service_calls.jsonl
// with the given raw JSONL lines (already newline-joined by the caller).
func writeWarnServiceCallsJournal(t *testing.T, tmpDir, contents string) {
	t.Helper()
	dir := filepath.Join(tmpDir, "diagnostics")
	if err := os.MkdirAll(dir, 0755); err != nil {
		t.Fatalf("mkdir diagnostics: %v", err)
	}
	path := filepath.Join(dir, "warn_service_calls.jsonl")
	if err := os.WriteFile(path, []byte(contents), 0644); err != nil {
		t.Fatalf("write warn_service_calls.jsonl: %v", err)
	}
}

// AC-4: repeated real failures over 24h, no success -> stale/missing success,
// fresh attempt.
func TestWarnServiceHealthReportsStaleSuccessAfterRepeatedFailures(t *testing.T) {
	tmpDir := t.TempDir()
	sched := newWarnServiceHealthTestScheduler(t, tmpDir)

	now := time.Now().UTC()
	line := func(hoursAgo float64) string {
		ts := now.Add(-time.Duration(hoursAgo * float64(time.Hour))).Format(time.RFC3339)
		return `{"service":"meteoalarm:AT:p1","cache_hit":false,"ok":false,` +
			`"self_throttled":false,"ts":"` + ts + `"}`
	}
	contents := line(24) + "\n" + line(12) + "\n" + line(0.1) + "\n"
	writeWarnServiceCallsJournal(t, tmpDir, contents)

	health := sched.WarnServiceHealth()

	meteoalarm, ok := health["meteoalarm"].(map[string]any)
	if !ok {
		t.Fatalf("meteoalarm key missing or wrong type: %v", health["meteoalarm"])
	}
	if got := meteoalarm["last_success_at"]; got != nil {
		t.Errorf("last_success_at: want nil (no success ever), got %v", got)
	}
	lastAttempt, ok := meteoalarm["last_attempt_at"].(string)
	if !ok || lastAttempt == "" {
		t.Fatalf("last_attempt_at missing or wrong type: %v", meteoalarm["last_attempt_at"])
	}
	attemptTs, err := time.Parse(time.RFC3339, lastAttempt)
	if err != nil {
		t.Fatalf("last_attempt_at not RFC3339: %v", err)
	}
	if age := now.Sub(attemptTs); age < 0 || age > time.Hour {
		t.Errorf("last_attempt_at not recent: %v old", age)
	}
}

// AC-5: a service never called does not appear as a key at all.
func TestWarnServiceHealthOmitsServiceWithoutAnyCalls(t *testing.T) {
	tmpDir := t.TempDir()
	sched := newWarnServiceHealthTestScheduler(t, tmpDir)

	now := time.Now().UTC().Format(time.RFC3339)
	contents := `{"service":"meteoalarm:AT:p1","cache_hit":false,"ok":true,` +
		`"self_throttled":false,"ts":"` + now + `"}` + "\n"
	writeWarnServiceCallsJournal(t, tmpDir, contents)

	health := sched.WarnServiceHealth()

	if _, exists := health["massif_closure"]; exists {
		t.Errorf("massif_closure must not appear as a key when never called, got: %v",
			health["massif_closure"])
	}
}

// AC-6: meteoalarm_budget block appears independent of the journal's
// self_throttled flag.
func TestWarnServiceHealthDistinguishesSelfThrottleFromBudgetFile(t *testing.T) {
	tmpDir := t.TempDir()
	sched := newWarnServiceHealthTestScheduler(t, tmpDir)

	now := time.Now().UTC().Format(time.RFC3339)
	contents := `{"service":"meteoalarm:AT:p1","cache_hit":false,"ok":false,` +
		`"self_throttled":false,"ts":"` + now + `"}` + "\n"
	writeWarnServiceCallsJournal(t, tmpDir, contents)

	futureReset := time.Now().UTC().Add(6 * time.Hour).Unix()
	diagDir := filepath.Join(tmpDir, "diagnostics")
	budgetPath := filepath.Join(diagDir, "meteoalarm_budget.json")
	body := []byte(`{"date":"2026-07-30","calls":200,"observed_reset_ts":` +
		strconv.FormatInt(futureReset, 10) + `}`)
	if err := os.WriteFile(budgetPath, body, 0644); err != nil {
		t.Fatalf("write meteoalarm_budget.json: %v", err)
	}

	health := sched.WarnServiceHealth()

	meteoalarm, ok := health["meteoalarm"].(map[string]any)
	if !ok {
		t.Fatalf("meteoalarm key missing or wrong type: %v", health["meteoalarm"])
	}
	if got := meteoalarm["self_throttled"]; got != false {
		t.Errorf("journal self_throttled: want false, got %v", got)
	}

	budget, ok := health["meteoalarm_budget"].(map[string]any)
	if !ok {
		t.Fatalf("meteoalarm_budget key missing or wrong type: %v", health["meteoalarm_budget"])
	}
	if got := budget["status"]; got != "ok" {
		t.Errorf("meteoalarm_budget.status: want ok, got %v", got)
	}
	if got := budget["calls_today"]; got != float64(200) && got != 200 {
		t.Errorf("meteoalarm_budget.calls_today: want 200, got %v", got)
	}
	if got, ok := budget["observed_reset_ts"].(float64); !ok || int64(got) != futureReset {
		t.Errorf("meteoalarm_budget.observed_reset_ts: want %d, got %v", futureReset, budget["observed_reset_ts"])
	}
}

// AC-7: journal path pointing at a directory is a genuine read error,
// distinct from a missing file.
func TestWarnServiceHealthFlagsUnreadableJournalDistinctFromMissing(t *testing.T) {
	tmpDir := t.TempDir()
	sched := newWarnServiceHealthTestScheduler(t, tmpDir)

	// No diagnostics dir at all yet -> missing file, no error flag.
	health := sched.WarnServiceHealth()
	if _, exists := health["journal_read_error"]; exists {
		t.Errorf("journal_read_error must not be set when the file is simply missing, got: %v",
			health["journal_read_error"])
	}

	// Now make the journal PATH itself a directory -> genuine read error,
	// no rights manipulation needed.
	diagDir := filepath.Join(tmpDir, "diagnostics")
	if err := os.MkdirAll(diagDir, 0755); err != nil {
		t.Fatalf("mkdir diagnostics: %v", err)
	}
	journalAsDir := filepath.Join(diagDir, "warn_service_calls.jsonl")
	if err := os.MkdirAll(journalAsDir, 0755); err != nil {
		t.Fatalf("mkdir journal-as-dir: %v", err)
	}

	health = sched.WarnServiceHealth()
	if got := health["journal_read_error"]; got != true {
		t.Errorf("journal_read_error: want true when path is a directory, got %v", got)
	}
}
