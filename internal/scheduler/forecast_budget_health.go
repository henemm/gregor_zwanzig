package scheduler

import (
	"encoding/json"
	"os"
	"path/filepath"
	"time"
)

// forecastDailyBudget mirrors ForecastBudgetGate.DAILY_BUDGET
// (src/services/forecast_budget.py:40) — a plain constant, not
// env-overridable (unlike meteoalarmDailyBudget). Mini-Spec #1329 AC-8.
// Guarded at runtime by TestForecastBudgetConstantsMatchPython.
const forecastDailyBudget = 9000

// forecastPollingThreshold/forecastBriefingOnlyThreshold mirror
// ForecastBudgetGate.POLLING_THRESHOLD/.BRIEFING_ONLY_THRESHOLD
// (src/services/forecast_budget.py:41-42). Display-only: Python's
// allow() remains the sole decision-maker; Go derives throttle_level
// purely for observability (Spec fix_1329_forecast_cache_budget.md:303-309).
// Python allows while ratio < threshold, i.e. it throttles from
// ratio >= threshold on — Go mirrors that exact boundary.
const forecastPollingThreshold = 0.80
const forecastBriefingOnlyThreshold = 0.95

// forecastThrottleLevel derives the AC-8 display stage from usage_ratio.
func forecastThrottleLevel(usageRatio float64) string {
	if usageRatio >= forecastBriefingOnlyThreshold {
		return "briefing_only"
	}
	if usageRatio >= forecastPollingThreshold {
		return "polling_throttled"
	}
	return "none"
}

// forecastBudgetFile mirrors the shape written by ForecastBudgetGate._write
// (data/diagnostics/forecast_budget.json): {"date", "calls": {"openmeteo": N},
// "cache_hits", "cache_misses"}. Unlike meteoalarmBudgetFile.Calls (a plain
// int), Calls here is a per-provider map.
type forecastBudgetFile struct {
	Date        string         `json:"date"`
	Calls       map[string]int `json:"calls"`
	CacheHits   int            `json:"cache_hits"`
	CacheMisses int            `json:"cache_misses"`
}

// forecastBudgetSnapshot reads path (data/diagnostics/forecast_budget.json)
// and returns the same field set as ForecastBudgetGate.snapshot() (Python),
// fail-soft exactly like snapshot() itself ("unavailable" instead of
// raising). path=="" (no s.store) is treated the same as a read failure,
// analog meteoalarmBudgetSnapshot.
func forecastBudgetSnapshot(path string) map[string]any {
	unavailable := map[string]any{
		"date":            nil,
		"calls_today":     0,
		"daily_budget":    forecastDailyBudget,
		"usage_ratio":     0.0,
		"cache_hits":      0,
		"cache_misses":    0,
		"cache_hit_ratio": 0.0,
		"throttle_level":  "none",
		"status":          "unavailable",
	}
	if path == "" {
		return unavailable
	}
	// Adversary-Fund F001/F002 (feat-1329-ac8-budget-sichtbar): kein
	// separater os.ReadFile-Fehlercheck jenseits dieses -- gemessen liefert
	// os.ReadFile bei jedem real erreichbaren Lesefehler len(data) == 0, was
	// json.Unmarshal ohnehin auf denselben Default-Zweig scheitern laesst;
	// der Schreibpfad ist zudem atomar (ForecastBudgetGate._write, mkstemp +
	// os.replace, src/services/forecast_budget.py:159-171), ein Leser sieht
	// also nie eine halb geschriebene Datei.
	data, err := os.ReadFile(path)
	if err != nil {
		return unavailable
	}
	var file forecastBudgetFile
	if err := json.Unmarshal(data, &file); err != nil {
		return unavailable
	}

	// Stale-Date (mirrors ForecastBudgetGate._load_for_today,
	// src/services/forecast_budget.py:139-159): Python resets the counters
	// lazily, only on the next write. A persisted date that isn't today's
	// UTC date means the counters are logically reset -- reporting
	// yesterday's calls_today as "heute" would be factually wrong.
	today := time.Now().UTC().Format("2006-01-02")
	calls, cacheHits, cacheMisses := 0, 0, 0
	if file.Date == today {
		calls = file.Calls["openmeteo"] // zero value if key absent, s. spec
		cacheHits = file.CacheHits
		cacheMisses = file.CacheMisses
	}

	ratio := 0.0
	if forecastDailyBudget > 0 {
		ratio = float64(calls) / float64(forecastDailyBudget)
	}
	hitRatio := 0.0
	if total := cacheHits + cacheMisses; total > 0 {
		hitRatio = float64(cacheHits) / float64(total)
	}
	return map[string]any{
		"date":            today,
		"calls_today":     calls,
		"daily_budget":    forecastDailyBudget,
		"usage_ratio":     ratio,
		"cache_hits":      cacheHits,
		"cache_misses":    cacheMisses,
		"cache_hit_ratio": hitRatio,
		"throttle_level":  forecastThrottleLevel(ratio),
		"status":          "ok",
	}
}

// ForecastBudgetHealth reads the open-meteo daily-call budget snapshot from
// data/diagnostics/forecast_budget.json directly — no Python-Core HTTP call,
// analog WarnServiceHealth's meteoalarm_budget field. Issue #1329 AC-8.
func (s *Scheduler) ForecastBudgetHealth() map[string]any {
	if s.store == nil {
		return forecastBudgetSnapshot("")
	}
	path := filepath.Join(s.store.DataDir, "diagnostics", "forecast_budget.json")
	return forecastBudgetSnapshot(path)
}
