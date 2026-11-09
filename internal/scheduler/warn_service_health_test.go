package scheduler

import (
	"os"
	"path/filepath"
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

// The former AC-6 test (meteoalarm_budget block next to self_throttled) was
// removed with the budget mirror (#2266). Its successor, which asserts the
// block is GONE while self_throttled is still passed through, lives in
// warn_service_health_no_budget_test.go.

// TDD RED: Issue #1434 S2 — Zonen-Drift im Status-Endpunkt (AC-5/AC-6/AC-7).
//
// Spec: docs/specs/modules/fix_1434_dpc_zonen_drift.md, Scheibe S2.
// Die Ereigniszeilen schreibt S1 (src/services/official_alerts/warn_egress.py,
// log_zone_drift): kein "ok"-Feld, dafuer "zone_code", "has_warning", "drift".
//
// KEINE Mocks: echte JSONL-Fixture in t.TempDir(), WarnServiceHealth() real.

// driftLine renders one zone-drift event line exactly as log_zone_drift writes it.
func driftLine(service, zoneCode string, hasWarning bool, drift, ts string) string {
	warn := "false"
	if hasWarning {
		warn = "true"
	}
	return `{"ts":"` + ts + `","service":"` + service + `","zone_code":"` + zoneCode +
		`","has_warning":` + warn + `,"drift":"` + drift + `"}`
}

// callLine renders one real call line (log_warn_service_call, since #1422 S1).
func callLine(service string, ok bool, ts string) string {
	okStr := "false"
	if ok {
		okStr = "true"
	}
	return `{"service":"` + service + `","host":"x","status":200,"cache_hit":false,"ok":` +
		okStr + `,"self_throttled":false,"ts":"` + ts + `"}`
}

// serviceEntry fetches health[name] as a map, failing the test if absent.
func serviceEntry(t *testing.T, health map[string]any, name string) map[string]any {
	t.Helper()
	entry, ok := health[name].(map[string]any)
	if !ok {
		t.Fatalf("%s key missing or wrong type: %v", name, health[name])
	}
	return entry
}

// driftBlock fetches health[name].zone_drift as a map, failing if absent.
func driftBlock(t *testing.T, health map[string]any, name string) map[string]any {
	t.Helper()
	drift, ok := serviceEntry(t, health, name)["zone_drift"].(map[string]any)
	if !ok {
		t.Fatalf("%s.zone_drift missing or wrong type: %v", name, health[name])
	}
	return drift
}

// AC-5: unmappable warn zones appear split by "with warning" / "without
// warning", each with its OWN most recent timestamp, counted per canonical
// service name.
func TestWarnServiceHealthReportsZoneDriftSplitByWarning(t *testing.T) {
	tmpDir := t.TempDir()
	sched := newWarnServiceHealthTestScheduler(t, tmpDir)

	contents := callLine("dpc", true, "2026-07-31T08:00:00+00:00") + "\n" +
		driftLine("dpc", "Vene-A", true, "geometry_only", "2026-07-31T10:00:00+00:00") + "\n" +
		driftLine("dpc:bulletin", "Vene-B", true, "bulletin_only", "2026-07-31T12:00:00+00:00") + "\n" +
		driftLine("dpc", "Vene-C", false, "bulletin_only", "2026-07-31T09:00:00+00:00") + "\n"
	writeWarnServiceCallsJournal(t, tmpDir, contents)

	drift := driftBlock(t, sched.WarnServiceHealth(), "dpc")
	if got := drift["unmapped_with_warning"]; got != 2 {
		t.Errorf("unmapped_with_warning: want 2, got %v", got)
	}
	if got := drift["unmapped_without_warning"]; got != 1 {
		t.Errorf("unmapped_without_warning: want 1, got %v", got)
	}
	if got := drift["last_with_warning_at"]; got != "2026-07-31T12:00:00+00:00" {
		t.Errorf("last_with_warning_at: want 2026-07-31T12:00:00+00:00, got %v", got)
	}
	if got := drift["last_without_warning_at"]; got != "2026-07-31T09:00:00+00:00" {
		t.Errorf("last_without_warning_at: want 2026-07-31T09:00:00+00:00, got %v", got)
	}
	if _, exists := drift["last_at"]; exists {
		t.Errorf("last_at was replaced by the two per-category stamps, must be gone")
	}
}

// F001: the timestamps must be per category, not a shared maximum. Counters
// are cumulative and the journal never rotates, so a freshness check in
// check-gregor20.sh is the only way out of a permanently hot ERROR threshold —
// a shared maximum would actively mislead it: a long-fixed occurrence WITH
// warning plus a recent harmless one WITHOUT warning would look like a fresh
// ERROR. Deliberately different timestamps per category, otherwise the test
// proves nothing.
func TestWarnServiceHealthZoneDriftTimestampsArePerCategory(t *testing.T) {
	tmpDir := t.TempDir()
	sched := newWarnServiceHealthTestScheduler(t, tmpDir)

	const oldWithWarning = "2026-05-31T10:00:00+00:00"  // long fixed
	const newWithoutWarning = "2026-07-30T10:00:00+00:00" // recent, harmless
	contents := driftLine("dpc", "Zone-A", true, "geometry_only", oldWithWarning) + "\n" +
		driftLine("dpc", "Zone-B", false, "bulletin_only", newWithoutWarning) + "\n"
	writeWarnServiceCallsJournal(t, tmpDir, contents)

	drift := driftBlock(t, sched.WarnServiceHealth(), "dpc")
	if got := drift["last_with_warning_at"]; got != oldWithWarning {
		t.Errorf("last_with_warning_at: want the OLD stamp %s, got %v — a shared "+
			"maximum would fake a fresh ERROR", oldWithWarning, got)
	}
	if got := drift["last_without_warning_at"]; got != newWithoutWarning {
		t.Errorf("last_without_warning_at: want %s, got %v", newWithoutWarning, got)
	}
}

// F004/F005: a drift line without a usable ts — missing key, empty string or
// whitespace only — is dropped like a corrupt line;
// counting it would yield "count > 0, point in time unknown", which a
// freshness filter cannot act on, so the finding would be lost silently:
// exactly the failure class this issue exists for, one level down.
func TestWarnServiceHealthDropsDriftLineWithoutTimestamp(t *testing.T) {
	tmpDir := t.TempDir()
	sched := newWarnServiceHealthTestScheduler(t, tmpDir)

	const valid = "2026-07-31T10:00:00+00:00"
	contents := driftLine("dpc", "Vene-A", true, "geometry_only", valid) + "\n" +
		driftLine("dpc", "Vene-B", true, "geometry_only", "") + "\n" + // empty ts
		driftLine("dpc", "Vene-D", true, "geometry_only", " ") + "\n" + // whitespace only
		// ts key missing entirely
		`{"service":"dpc","zone_code":"Vene-C","has_warning":true,"drift":"geometry_only"}` + "\n"
	writeWarnServiceCallsJournal(t, tmpDir, contents)

	drift := driftBlock(t, sched.WarnServiceHealth(), "dpc")
	if got := drift["unmapped_with_warning"]; got != 1 {
		t.Errorf("unmapped_with_warning: want 1 (the three unusable lines dropped), got %v", got)
	}
	if got := drift["last_with_warning_at"]; got != valid {
		t.Errorf("last_with_warning_at: want %s, got %v", valid, got)
	}
}

// F004, second half: if the ts-less line is the ONLY drift line, AC-6 takes
// over — no zone_drift block at all, rather than a finding without a point in
// time. The real call line keeps the service key itself present, so this
// asserts the block's absence and not merely the service's.
func TestWarnServiceHealthOmitsZoneDriftWhenOnlyDriftLineLacksTimestamp(t *testing.T) {
	tmpDir := t.TempDir()
	sched := newWarnServiceHealthTestScheduler(t, tmpDir)

	contents := callLine("dpc", true, "2026-07-31T08:00:00+00:00") + "\n" +
		driftLine("dpc", "Vene-B", true, "geometry_only", "") + "\n"
	writeWarnServiceCallsJournal(t, tmpDir, contents)

	dpc := serviceEntry(t, sched.WarnServiceHealth(), "dpc")
	if got, exists := dpc["zone_drift"]; exists {
		t.Errorf("zone_drift must be absent when the only drift line has no ts, got: %v", got)
	}
	// The outage aggregate stays untouched by the dropped line (AC-7).
	if got := dpc["last_attempt_at"]; got != "2026-07-31T08:00:00+00:00" {
		t.Errorf("last_attempt_at: want the real call ts, got %v", got)
	}
}

// AC-6: no drift line at all -> no fabricated finding, key absent entirely
// (a zero would be indistinguishable from a real occurrence).
func TestWarnServiceHealthOmitsZoneDriftWithoutAnyDriftLines(t *testing.T) {
	tmpDir := t.TempDir()
	sched := newWarnServiceHealthTestScheduler(t, tmpDir)

	contents := callLine("dpc", true, "2026-07-31T08:00:00+00:00") + "\n" +
		callLine("meteoalarm:IT:p1", false, "2026-07-31T09:00:00+00:00") + "\n" +
		// pre-#1422-S1 line: no "ok", no "drift" -> neither call nor drift
		`{"service":"dpc","host":"x","status":200,"cache_hit":false,"ts":"2026-07-31T07:00:00+00:00"}` + "\n"
	writeWarnServiceCallsJournal(t, tmpDir, contents)

	health := sched.WarnServiceHealth()
	for _, name := range []string{"dpc", "meteoalarm"} {
		entry := serviceEntry(t, health, name)
		if got, exists := entry["zone_drift"]; exists {
			t.Errorf("%s.zone_drift must be absent without any drift line, got: %v", name, got)
		}
	}
}

// AC-7: the existing outage aggregate must stay byte-identical when drift
// lines are interleaved — compared against a second run WITHOUT them, not
// against hardcoded expectations.
func TestWarnServiceHealthCallAggregateUnaffectedByDriftLines(t *testing.T) {
	base := callLine("dpc", false, "2026-07-31T06:00:00+00:00") + "\n" +
		callLine("dpc", true, "2026-07-31T07:00:00+00:00") + "\n" +
		callLine("dpc", false, "2026-07-31T11:00:00+00:00") + "\n" +
		callLine("meteoalarm:IT:p1", true, "2026-07-31T08:30:00+00:00") + "\n" +
		// pre-#1422-S1 line without "ok": skipped now and after the change
		`{"service":"dpc","host":"x","status":200,"cache_hit":false,"ts":"2026-07-31T23:00:00+00:00"}` + "\n"
	mixed := base +
		driftLine("dpc", "Vene-A", true, "geometry_only", "2026-07-31T23:30:00+00:00") + "\n" +
		driftLine("dpc", "Vene-C", false, "bulletin_only", "2026-07-31T23:45:00+00:00") + "\n" +
		driftLine("meteoalarm:IT:p1", "IT007", true, "bulletin_only", "2026-07-31T23:50:00+00:00") + "\n"

	run := func(contents string) map[string]any {
		tmpDir := t.TempDir()
		sched := newWarnServiceHealthTestScheduler(t, tmpDir)
		writeWarnServiceCallsJournal(t, tmpDir, contents)
		return sched.WarnServiceHealth()
	}
	withoutDrift := run(base)
	withDrift := run(mixed)

	if a, b := withoutDrift["journal_read_error"], withDrift["journal_read_error"]; a != b {
		t.Errorf("journal_read_error changed by drift lines: %v -> %v", a, b)
	}
	for _, name := range []string{"dpc", "meteoalarm"} {
		want := serviceEntry(t, withoutDrift, name)
		got := serviceEntry(t, withDrift, name)
		for _, field := range []string{"last_success_at", "last_attempt_at", "self_throttled"} {
			if want[field] != got[field] {
				t.Errorf("%s.%s changed by drift lines: %v -> %v", name, field, want[field], got[field])
			}
		}
	}
}

// Sonderfall: a service seen ONLY in drift lines is a real observation and
// must appear — but its call timestamps stay honestly nil, no empty string
// masquerading as a timestamp.
func TestWarnServiceHealthDriftOnlyServiceHasNilTimestamps(t *testing.T) {
	tmpDir := t.TempDir()
	sched := newWarnServiceHealthTestScheduler(t, tmpDir)

	contents := callLine("meteoalarm:IT:p1", true, "2026-07-31T08:00:00+00:00") + "\n" +
		driftLine("dpc", "Vene-A", true, "geometry_only", "2026-07-31T10:00:00+00:00") + "\n"
	writeWarnServiceCallsJournal(t, tmpDir, contents)

	dpc := serviceEntry(t, sched.WarnServiceHealth(), "dpc")
	if got := dpc["last_attempt_at"]; got != nil {
		t.Errorf("last_attempt_at: want nil (no real call in journal), got %#v", got)
	}
	if got := dpc["last_success_at"]; got != nil {
		t.Errorf("last_success_at: want nil (no real call in journal), got %#v", got)
	}
	drift, ok := dpc["zone_drift"].(map[string]any)
	if !ok {
		t.Fatalf("dpc.zone_drift missing or wrong type: %v", dpc["zone_drift"])
	}
	if got := drift["unmapped_with_warning"]; got != 1 {
		t.Errorf("unmapped_with_warning: want 1, got %v", got)
	}
	// Category without any occurrence: nil, present as a key — inside an
	// existing zone_drift block that is unambiguous next to count 0.
	if got := drift["unmapped_without_warning"]; got != 0 {
		t.Errorf("unmapped_without_warning: want 0, got %v", got)
	}
	stamp, exists := drift["last_without_warning_at"]
	if !exists {
		t.Errorf("last_without_warning_at must be present as nil, not omitted")
	}
	if stamp != nil {
		t.Errorf("last_without_warning_at: want nil (no such occurrence), got %#v", stamp)
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

// TDD RED: Issue #2224 — Rotation des Warn-Dienst-Journals, Lese-Seite.
//
// Spec: docs/specs/modules/fix_2224_warn_journal_rotation.md
//
// KEINE Mocks: echte Dateien in t.TempDir(); die Vorgaenger-Generation
// warn_service_calls.jsonl.1 wird so angelegt, wie die Python-Rotation
// (os.replace) sie hinterlaesst.

// writeWarnServiceCallsPrev writes the predecessor generation
// data/diagnostics/warn_service_calls.jsonl.1.
func writeWarnServiceCallsPrev(t *testing.T, tmpDir, contents string) {
	t.Helper()
	dir := filepath.Join(tmpDir, "diagnostics")
	if err := os.MkdirAll(dir, 0755); err != nil {
		t.Fatalf("mkdir diagnostics: %v", err)
	}
	path := filepath.Join(dir, "warn_service_calls.jsonl.1")
	if err := os.WriteFile(path, []byte(contents), 0644); err != nil {
		t.Fatalf("write warn_service_calls.jsonl.1: %v", err)
	}
}

// AC-6: last success only in .1, current file holds only later failures ->
// last_success_at from .1, newer last_attempt_at from the current file.
func TestWarnServiceHealth_LetzterErfolgNurInEins(t *testing.T) {
	tmpDir := t.TempDir()
	sched := newWarnServiceHealthTestScheduler(t, tmpDir)

	writeWarnServiceCallsPrev(t, tmpDir,
		callLine("dwd:x", false, "2026-11-01T08:00:00Z")+"\n"+
			callLine("dwd:x", true, "2026-11-01T09:00:00Z")+"\n")
	writeWarnServiceCallsJournal(t, tmpDir,
		callLine("dwd:x", false, "2026-11-01T10:00:00Z")+"\n"+
			callLine("dwd:x", false, "2026-11-01T11:00:00Z")+"\n")

	health := sched.WarnServiceHealth()
	dwd := serviceEntry(t, health, "dwd")
	if got := dwd["last_success_at"]; got != "2026-11-01T09:00:00Z" {
		t.Errorf("last_success_at: want success from .1, got %v", got)
	}
	if got := dwd["last_attempt_at"]; got != "2026-11-01T11:00:00Z" {
		t.Errorf("last_attempt_at: want newest attempt from current file, got %v", got)
	}
	if _, exists := health["journal_read_error"]; exists {
		t.Errorf("journal_read_error must not be set, got %v", health["journal_read_error"])
	}
}

// AC-6/AC-8: current file missing (rotation just happened, nothing written
// yet), only .1 present -> data from .1, no error.
func TestWarnServiceHealth_NurEinsOhneAktuelle(t *testing.T) {
	tmpDir := t.TempDir()
	sched := newWarnServiceHealthTestScheduler(t, tmpDir)

	writeWarnServiceCallsPrev(t, tmpDir, callLine("dwd:x", true, "2026-11-01T09:00:00Z")+"\n")

	health := sched.WarnServiceHealth()
	dwd := serviceEntry(t, health, "dwd")
	if got := dwd["last_success_at"]; got != "2026-11-01T09:00:00Z" {
		t.Errorf("last_success_at: want value from .1, got %v", got)
	}
	if _, exists := health["journal_read_error"]; exists {
		t.Errorf("missing current file must not be an error, got %v", health["journal_read_error"])
	}
}

// AC-8: no .1 at all -> identical to the pre-rotation behaviour, no error.
// Regressionsschutz: bereits heute gruen, muss es nach der Umstellung bleiben.
func TestWarnServiceHealth_KeineEins(t *testing.T) {
	tmpDir := t.TempDir()
	sched := newWarnServiceHealthTestScheduler(t, tmpDir)

	writeWarnServiceCallsJournal(t, tmpDir,
		callLine("dwd:x", true, "2026-11-01T09:00:00Z")+"\n"+
			callLine("dwd:x", false, "2026-11-01T10:00:00Z")+"\n"+
			driftLine("dpc", "IT-1", true, "unmapped", "2026-11-01T10:30:00Z")+"\n")

	health := sched.WarnServiceHealth()
	if _, exists := health["journal_read_error"]; exists {
		t.Errorf("missing .1 must not be an error, got %v", health["journal_read_error"])
	}
	dwd := serviceEntry(t, health, "dwd")
	if dwd["last_success_at"] != "2026-11-01T09:00:00Z" || dwd["last_attempt_at"] != "2026-11-01T10:00:00Z" {
		t.Errorf("aggregate changed without .1: %v", dwd)
	}
	if got := driftBlock(t, health, "dpc")["unmapped_with_warning"]; got != 1 {
		t.Errorf("unmapped_with_warning: want 1, got %v", got)
	}
}

// AC-9: .1 exists but is unreadable (a directory) -> journal_read_error,
// while the readable current file is still delivered.
func TestWarnServiceHealth_LesefehlerInEins(t *testing.T) {
	tmpDir := t.TempDir()
	sched := newWarnServiceHealthTestScheduler(t, tmpDir)

	writeWarnServiceCallsJournal(t, tmpDir, callLine("dwd:x", true, "2026-11-01T09:00:00Z")+"\n")
	prevAsDir := filepath.Join(tmpDir, "diagnostics", "warn_service_calls.jsonl.1")
	if err := os.MkdirAll(prevAsDir, 0755); err != nil {
		t.Fatalf("mkdir .1-as-dir: %v", err)
	}

	health := sched.WarnServiceHealth()
	if got := health["journal_read_error"]; got != true {
		t.Errorf("journal_read_error: want true when .1 is unreadable, got %v", got)
	}
	dwd := serviceEntry(t, health, "dwd")
	if got := dwd["last_success_at"]; got != "2026-11-01T09:00:00Z" {
		t.Errorf("readable current file must still be delivered, got %v", got)
	}
}

// AC-7: .1 is the very same file as the already opened current one (rotation
// between the two opens, reproduced via hardlink) -> nothing counted twice.
// Waechter fuer die SameFile-Pruefung: heute gruen (Go liest .1 noch nicht),
// wird ohne SameFile nach der Umstellung rot.
func TestWarnServiceHealth_HardlinkEinsGleichAktuell(t *testing.T) {
	tmpDir := t.TempDir()
	sched := newWarnServiceHealthTestScheduler(t, tmpDir)

	writeWarnServiceCallsJournal(t, tmpDir,
		callLine("dwd:x", true, "2026-11-01T09:00:00Z")+"\n"+
			driftLine("dpc", "IT-1", true, "unmapped", "2026-11-01T10:00:00Z")+"\n"+
			driftLine("dpc", "IT-2", false, "unmapped", "2026-11-01T10:05:00Z")+"\n")
	cur := filepath.Join(tmpDir, "diagnostics", "warn_service_calls.jsonl")
	if err := os.Link(cur, cur+".1"); err != nil {
		t.Fatalf("hardlink .1: %v", err)
	}

	health := sched.WarnServiceHealth()
	drift := driftBlock(t, health, "dpc")
	if got := drift["unmapped_with_warning"]; got != 1 {
		t.Errorf("unmapped_with_warning: want 1 (single read), got %v", got)
	}
	if got := drift["unmapped_without_warning"]; got != 1 {
		t.Errorf("unmapped_without_warning: want 1 (single read), got %v", got)
	}
	if _, exists := health["journal_read_error"]; exists {
		t.Errorf("journal_read_error must not be set, got %v", health["journal_read_error"])
	}
}

// AC-9 (Fix-Loop F002): .1 exists but cannot be OPENED (permission denied)
// -> journal_read_error, while the readable current file is still delivered.
func TestWarnServiceHealth_EinsNichtOeffenbar(t *testing.T) {
	if os.Geteuid() == 0 {
		t.Skip("root ignores file permissions")
	}
	tmpDir := t.TempDir()
	sched := newWarnServiceHealthTestScheduler(t, tmpDir)

	writeWarnServiceCallsJournal(t, tmpDir, callLine("dwd:x", true, "2026-11-01T09:00:00Z")+"\n")
	writeWarnServiceCallsPrev(t, tmpDir, callLine("dwd:x", true, "2026-11-01T12:00:00Z")+"\n")
	prev := filepath.Join(tmpDir, "diagnostics", "warn_service_calls.jsonl.1")
	if err := os.Chmod(prev, 0o000); err != nil {
		t.Fatalf("chmod .1: %v", err)
	}
	t.Cleanup(func() { _ = os.Chmod(prev, 0o644) })

	health := sched.WarnServiceHealth()
	if got := health["journal_read_error"]; got != true {
		t.Errorf("journal_read_error: want true when .1 cannot be opened, got %v", got)
	}
	dwd := serviceEntry(t, health, "dwd")
	if got := dwd["last_success_at"]; got != "2026-11-01T09:00:00Z" {
		t.Errorf("readable current file must still be delivered, got %v", got)
	}
}

// AC-6/AC-7 (Fix-Loop F003): a real rotation happens between the two opens.
// Opening the current file FIRST keeps its data (it becomes .1, detected via
// SameFile and read once); opening .1 first would lose the renamed file.
func TestWarnServiceHealth_RotationZwischenDenOeffnungen(t *testing.T) {
	tmpDir := t.TempDir()
	sched := newWarnServiceHealthTestScheduler(t, tmpDir)

	writeWarnServiceCallsJournal(t, tmpDir,
		callLine("dwd:x", true, "2026-11-01T09:00:00Z")+"\n"+
			driftLine("dpc", "IT-1", true, "unmapped", "2026-11-01T09:30:00Z")+"\n")
	cur := filepath.Join(tmpDir, "diagnostics", "warn_service_calls.jsonl")

	rotated := false
	journalBetweenOpens = func() {
		rotated = true
		if err := os.Rename(cur, cur+".1"); err != nil {
			t.Errorf("rotate: %v", err)
			return
		}
		if err := os.WriteFile(cur, []byte(callLine("dwd:x", false, "2026-11-01T10:00:00Z")+"\n"), 0644); err != nil {
			t.Errorf("write new current: %v", err)
		}
	}
	t.Cleanup(func() { journalBetweenOpens = nil })

	health := sched.WarnServiceHealth()
	if !rotated {
		t.Fatalf("test seam was not called between the opens")
	}
	if _, exists := health["journal_read_error"]; exists {
		t.Errorf("journal_read_error must not be set, got %v", health["journal_read_error"])
	}
	dwd := serviceEntry(t, health, "dwd")
	if got := dwd["last_success_at"]; got != "2026-11-01T09:00:00Z" {
		t.Errorf("last_success_at: want success from the file opened first, got %v", got)
	}
	if got := driftBlock(t, health, "dpc")["unmapped_with_warning"]; got != 1 {
		t.Errorf("unmapped_with_warning: want 1 (read once), got %v", got)
	}
}

// AC-11: drift lines spread over .1 and the current file -> counters cover
// both files, timestamps are the newest per category across both.
func TestWarnServiceHealth_DriftUeberBeideDateien(t *testing.T) {
	tmpDir := t.TempDir()
	sched := newWarnServiceHealthTestScheduler(t, tmpDir)

	writeWarnServiceCallsPrev(t, tmpDir,
		driftLine("dpc", "IT-1", true, "unmapped", "2026-11-01T08:00:00Z")+"\n"+
			driftLine("dpc", "IT-2", false, "unmapped", "2026-11-01T12:00:00Z")+"\n")
	writeWarnServiceCallsJournal(t, tmpDir,
		driftLine("dpc", "IT-3", true, "unmapped", "2026-11-02T08:00:00Z")+"\n"+
			driftLine("dpc", "IT-4", false, "unmapped", "2026-11-01T11:00:00Z")+"\n")

	drift := driftBlock(t, sched.WarnServiceHealth(), "dpc")
	if got := drift["unmapped_with_warning"]; got != 2 {
		t.Errorf("unmapped_with_warning: want 2 (both files), got %v", got)
	}
	if got := drift["unmapped_without_warning"]; got != 2 {
		t.Errorf("unmapped_without_warning: want 2 (both files), got %v", got)
	}
	if got := drift["last_with_warning_at"]; got != "2026-11-02T08:00:00Z" {
		t.Errorf("last_with_warning_at: want newest from current file, got %v", got)
	}
	if got := drift["last_without_warning_at"]; got != "2026-11-01T12:00:00Z" {
		t.Errorf("last_without_warning_at: want newest from .1, got %v", got)
	}
}
