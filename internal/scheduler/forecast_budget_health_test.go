package scheduler

import (
	"os"
	"path/filepath"
	"testing"

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
	writeForecastBudgetFile(t, tmpDir,
		`{"date":"2026-08-05","calls":{"openmeteo":900},"cache_hits":10,"cache_misses":5}`)

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
	writeForecastBudgetFile(t, tmpDir,
		`{"date":"2026-08-05","calls":{"openmeteo":42},"cache_hits":1,"cache_misses":2}`)
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
