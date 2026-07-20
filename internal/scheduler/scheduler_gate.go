package scheduler

import "github.com/henemm/gregor-api/internal/config"

// SchedulerEnabled reports whether the autonomous cron scheduler may start.
//
// Issue #1329 (Maßnahme A): Staging (GZ_ENV=staging) shares the open-meteo
// daily quota with Prod. The autonomous ticker must not run there. Fail-safe:
// only the exact value "staging" disables it — any other value (unset, typo,
// different case) keeps the scheduler running, defaulting to Prod behavior.
func SchedulerEnabled(cfg *config.Config) bool {
	return cfg.Env != "staging"
}
