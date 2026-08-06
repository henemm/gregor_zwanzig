package scheduler

import (
	"encoding/json"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/store"
)

// Issue #1329 AC-8 — forecast_budget im /api/scheduler/status.
// Spec: docs/specs/fast/fix-1329-ac8-budget-status.md
// KEINE Mocks: echte JSON-Fixture-Dateien in t.TempDir().

// newForecastBudgetHealthTestScheduler builds a Scheduler backed by tmpDir.
func newForecastBudgetHealthTestScheduler(t *testing.T, tmpDir string) *Scheduler {
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

func writeForecastBudgetFile(t *testing.T, tmpDir, contents string) {
	t.Helper()
	dir := filepath.Join(tmpDir, "diagnostics")
	if err := os.MkdirAll(dir, 0755); err != nil {
		t.Fatalf("mkdir diagnostics: %v", err)
	}
	path := filepath.Join(dir, "forecast_budget.json")
	if err := os.WriteFile(path, []byte(contents), 0644); err != nil {
		t.Fatalf("write forecast_budget.json: %v", err)
	}
}

func TestForecastBudgetSnapshotValidFileReportsFieldsAndRatio(t *testing.T) {
	tmpDir := t.TempDir()
	today := time.Now().UTC().Format("2006-01-02")
	writeForecastBudgetFile(t, tmpDir,
		`{"date":"`+today+`","calls":{"openmeteo":900},"cache_hits":10,"cache_misses":5}`)

	snap := forecastBudgetSnapshot(filepath.Join(tmpDir, "diagnostics", "forecast_budget.json"))

	if got := snap["status"]; got != "ok" {
		t.Errorf("status: want ok, got %v", got)
	}
	if got := snap["calls_today"]; got != 900 {
		t.Errorf("calls_today: want 900, got %v", got)
	}
	if got := snap["daily_budget"]; got != 9000 {
		t.Errorf("daily_budget: want 9000, got %v", got)
	}
	if got, ok := snap["usage_ratio"].(float64); !ok || got != 0.1 {
		t.Errorf("usage_ratio: want 0.1, got %v", snap["usage_ratio"])
	}
	if got := snap["cache_hits"]; got != 10 {
		t.Errorf("cache_hits: want 10, got %v", got)
	}
	if got := snap["cache_misses"]; got != 5 {
		t.Errorf("cache_misses: want 5, got %v", got)
	}
}

func TestForecastBudgetSnapshotMissingFileIsUnavailableNotPanic(t *testing.T) {
	tmpDir := t.TempDir()
	missingPath := filepath.Join(tmpDir, "diagnostics", "forecast_budget.json")

	snap := forecastBudgetSnapshot(missingPath)

	if got := snap["status"]; got != "unavailable" {
		t.Errorf("status: want unavailable, got %v", got)
	}
	if got := snap["calls_today"]; got != 0 {
		t.Errorf("calls_today: want 0, got %v", got)
	}
	if got, ok := snap["usage_ratio"].(float64); !ok || got != 0.0 {
		t.Errorf("usage_ratio: want 0.0, got %v", snap["usage_ratio"])
	}
	if got := snap["cache_hits"]; got != 0 {
		t.Errorf("cache_hits: want 0, got %v", got)
	}
	if got := snap["cache_misses"]; got != 0 {
		t.Errorf("cache_misses: want 0, got %v", got)
	}
}

func TestForecastBudgetSnapshotCorruptJSONIsUnavailable(t *testing.T) {
	tmpDir := t.TempDir()
	writeForecastBudgetFile(t, tmpDir, `{not valid json`)

	snap := forecastBudgetSnapshot(filepath.Join(tmpDir, "diagnostics", "forecast_budget.json"))

	if got := snap["status"]; got != "unavailable" {
		t.Errorf("status: want unavailable, got %v", got)
	}
}

func TestSchedulerStatusIncludesForecastBudgetKey(t *testing.T) {
	tmpDir := t.TempDir()
	today := time.Now().UTC().Format("2006-01-02")
	writeForecastBudgetFile(t, tmpDir,
		`{"date":"`+today+`","calls":{"openmeteo":42},"cache_hits":1,"cache_misses":2}`)
	sched := newForecastBudgetHealthTestScheduler(t, tmpDir)

	status := sched.Status()

	budget, ok := status["forecast_budget"].(map[string]any)
	if !ok {
		t.Fatalf("forecast_budget key missing or wrong type: %v", status["forecast_budget"])
	}
	if got := budget["calls_today"]; got != 42 {
		t.Errorf("calls_today: want 42, got %v", got)
	}
	if got := budget["status"]; got != "ok" {
		t.Errorf("status: want ok, got %v", got)
	}
}

// AC-8: cache_hit_ratio = cache_hits / (cache_hits + cache_misses).
func TestForecastBudgetSnapshotCacheHitRatio(t *testing.T) {
	tmpDir := t.TempDir()
	today := time.Now().UTC().Format("2006-01-02")
	writeForecastBudgetFile(t, tmpDir, `{"date":"`+today+`","calls":{"openmeteo":100},"cache_hits":678,"cache_misses":322}`)

	snap := forecastBudgetSnapshot(filepath.Join(tmpDir, "diagnostics", "forecast_budget.json"))

	want := 678.0 / (678.0 + 322.0)
	got, ok := snap["cache_hit_ratio"].(float64)
	if !ok || got != want {
		t.Errorf("cache_hit_ratio: want %v, got %v", want, snap["cache_hit_ratio"])
	}
}

// Division durch Null: cache_hits UND cache_misses bei 0 muss 0.0 liefern,
// nicht NaN -- NaN killt json.Marshal fuer den GESAMTEN Status-Endpunkt.
func TestForecastBudgetSnapshotZeroCacheCountsGiveZeroRatioAndMarshalableStatus(t *testing.T) {
	tmpDir := t.TempDir()
	today := time.Now().UTC().Format("2006-01-02")
	writeForecastBudgetFile(t, tmpDir, `{"date":"`+today+`","calls":{},"cache_hits":0,"cache_misses":0}`)
	sched := newForecastBudgetHealthTestScheduler(t, tmpDir)

	status := sched.Status()

	budget := status["forecast_budget"].(map[string]any)
	if got, ok := budget["cache_hit_ratio"].(float64); !ok || got != 0.0 {
		t.Errorf("cache_hit_ratio: want 0.0, got %v", budget["cache_hit_ratio"])
	}
	if _, err := json.Marshal(status); err != nil {
		t.Fatalf("json.Marshal(sched.Status()) failed: %v", err)
	}
}

// AC-8: throttle_level-Grenzen exakt wie ForecastBudgetGate.allow()
// (src/services/forecast_budget.py:54-74) -- Python erlaubt bei
// ratio < Schwelle, drosselt also ab ratio >= Schwelle.
func TestForecastBudgetSnapshotThrottleLevelBoundaries(t *testing.T) {
	today := time.Now().UTC().Format("2006-01-02")
	cases := []struct {
		calls int
		want  string
	}{
		{7199, "none"},              // 0.79989 < 0.80
		{7200, "polling_throttled"}, // exakt 0.80
		{8549, "polling_throttled"}, // 0.94989 < 0.95
		{8550, "briefing_only"},     // exakt 0.95
	}
	for _, tc := range cases {
		t.Run(tc.want+"_"+strconv.Itoa(tc.calls), func(t *testing.T) {
			tmpDir := t.TempDir()
			writeForecastBudgetFile(t, tmpDir, `{"date":"`+today+`","calls":{"openmeteo":`+strconv.Itoa(tc.calls)+`},"cache_hits":0,"cache_misses":0}`)
			snap := forecastBudgetSnapshot(filepath.Join(tmpDir, "diagnostics", "forecast_budget.json"))
			if got := snap["throttle_level"]; got != tc.want {
				t.Errorf("calls=%d: throttle_level want %q, got %v", tc.calls, tc.want, got)
			}
		})
	}
}

// Stale-Date: ein gestriger Zaehlerstand (Python setzt erst beim naechsten
// Schreibzugriff zurueck, s. _load_for_today) darf NICHT als "calls_today"
// erscheinen -- Zaehler gelten als zurueckgesetzt, "date" zeigt HEUTE.
func TestForecastBudgetSnapshotStaleDateReportsZeroCounts(t *testing.T) {
	tmpDir := t.TempDir()
	yesterday := time.Now().UTC().AddDate(0, 0, -1).Format("2006-01-02")
	writeForecastBudgetFile(t, tmpDir, `{"date":"`+yesterday+`","calls":{"openmeteo":8000},"cache_hits":500,"cache_misses":10}`)

	snap := forecastBudgetSnapshot(filepath.Join(tmpDir, "diagnostics", "forecast_budget.json"))

	today := time.Now().UTC().Format("2006-01-02")
	if got := snap["date"]; got != today {
		t.Errorf("date: want today %q, got %v (stale date must not leak through)", today, got)
	}
	if got := snap["calls_today"]; got != 0 {
		t.Errorf("calls_today: want 0 for a stale-date file, got %v", got)
	}
	if got := snap["throttle_level"]; got != "none" {
		t.Errorf("throttle_level: want none (reset), got %v", got)
	}
	// F003 (Adversary): cache_hits/cache_misses/cache_hit_ratio muessen an
	// dieselbe Datumspruefung gebunden sein wie calls_today -- sonst
	// widerspraeche sich der Block selbst (date=heute, calls_today=0, aber
	// cache_hit_ratio aus gestrigen Zahlen).
	if got := snap["cache_hits"]; got != 0 {
		t.Errorf("cache_hits: want 0 for a stale-date file, got %v", got)
	}
	if got := snap["cache_misses"]; got != 0 {
		t.Errorf("cache_misses: want 0 for a stale-date file, got %v", got)
	}
	if got, ok := snap["cache_hit_ratio"].(float64); !ok || got != 0.0 {
		t.Errorf("cache_hit_ratio: want 0.0 for a stale-date file, got %v", snap["cache_hit_ratio"])
	}
}

const maxForecastBudgetRepoRootAscent = 6

// findForecastBudgetRepoRoot steigt von os.Getwd() auf, bis go.mod gefunden
// wird -- NICHT runtime.Caller(0) (bricht unter -overlay/-trimpath still,
// Muster internal/mail/recipient_parity_test.go).
func findForecastBudgetRepoRoot(t *testing.T) string {
	t.Helper()
	dir, err := os.Getwd()
	if err != nil {
		t.Fatalf("findForecastBudgetRepoRoot: os.Getwd() fehlgeschlagen: %v", err)
	}
	for i := 0; i < maxForecastBudgetRepoRootAscent; i++ {
		if _, err := os.Stat(filepath.Join(dir, "go.mod")); err == nil {
			return dir
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			break
		}
		dir = parent
	}
	t.Fatalf("findForecastBudgetRepoRoot: kein go.mod innerhalb von %d Ebenen ueber %q gefunden",
		maxForecastBudgetRepoRootAscent, dir)
	return ""
}

// Paritaets-Test (Muster: passkey.go-Paritaet aus #1364): die drei
// gespiegelten Zahlen (DAILY_BUDGET, POLLING_THRESHOLD,
// BRIEFING_ONLY_THRESHOLD) werden zur Laufzeit aus src/services/forecast_budget.py
// gelesen und gegen die Go-Konstanten geprueft -- ein Kommentar ist eine
// Bitte, ein Test ist eine Zusicherung.
func TestForecastBudgetConstantsMatchPython(t *testing.T) {
	repoRoot := findForecastBudgetRepoRoot(t)
	pySrc, err := os.ReadFile(filepath.Join(repoRoot, "src", "services", "forecast_budget.py"))
	if err != nil {
		t.Fatalf("forecast_budget.py nicht lesbar: %v", err)
	}
	text := string(pySrc)

	checks := []struct {
		re   *regexp.Regexp
		name string
		want string
	}{
		{regexp.MustCompile(`DAILY_BUDGET\s*=\s*(\d+)`), "DAILY_BUDGET", "9000"},
		{regexp.MustCompile(`POLLING_THRESHOLD\s*=\s*([\d.]+)`), "POLLING_THRESHOLD", "0.80"},
		{regexp.MustCompile(`BRIEFING_ONLY_THRESHOLD\s*=\s*([\d.]+)`), "BRIEFING_ONLY_THRESHOLD", "0.95"},
	}
	for _, c := range checks {
		m := c.re.FindStringSubmatch(text)
		if m == nil {
			t.Fatalf("%s nicht in forecast_budget.py gefunden — Konstante verschoben/umbenannt?", c.name)
		}
		if m[1] != c.want {
			t.Errorf("%s (Python) = %s, Go-Konstante = %s -- Drift!", c.name, m[1], c.want)
		}
	}
	if forecastDailyBudget != 9000 || forecastPollingThreshold != 0.80 || forecastBriefingOnlyThreshold != 0.95 {
		t.Fatalf("Go-Konstanten selbst weichen von den erwarteten Werten ab: %d/%v/%v",
			forecastDailyBudget, forecastPollingThreshold, forecastBriefingOnlyThreshold)
	}
}
