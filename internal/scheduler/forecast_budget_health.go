package scheduler

import (
	"encoding/json"
	"os"
	"path/filepath"
)

// forecastDailyBudget mirrors ForecastBudgetGate.DAILY_BUDGET
// (src/services/forecast_budget.py:40) — a plain constant, not
// env-overridable (unlike meteoalarmDailyBudget). Mini-Spec #1329 AC-8.
const forecastDailyBudget = 9000

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
		"calls_today":  0,
		"daily_budget": forecastDailyBudget,
		"usage_ratio":  0.0,
		"cache_hits":   0,
		"cache_misses": 0,
		"status":       "unavailable",
	}
	if path == "" {
		return unavailable
	}
	data, err := os.ReadFile(path)
	if err != nil {
		return unavailable
	}
	var file forecastBudgetFile
	if err := json.Unmarshal(data, &file); err != nil {
		return unavailable
	}

	calls := file.Calls["openmeteo"] // zero value if key absent, s. spec
	ratio := 0.0
	if forecastDailyBudget > 0 {
		ratio = float64(calls) / float64(forecastDailyBudget)
	}
	return map[string]any{
		"calls_today":  calls,
		"daily_budget": forecastDailyBudget,
		"usage_ratio":  ratio,
		"cache_hits":   file.CacheHits,
		"cache_misses": file.CacheMisses,
		"status":       "ok",
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
