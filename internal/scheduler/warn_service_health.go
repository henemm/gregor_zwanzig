package scheduler

import (
	"bufio"
	"encoding/json"
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

// warnServiceCallEntry mirrors one line of data/diagnostics/warn_service_calls.jsonl
// (written by src/services/official_alerts/warn_egress.py's cached_fetch(),
// Issue #1348 / #1422 S1). Only the fields needed for WarnServiceHealth are
// decoded. Ok is a pointer so older, pre-#1422-S1 lines (no "ok" key) are
// distinguishable from an explicit false and can be skipped (s. spec Known
// Limitations "Übergangsfenster nach Deploy").
// Drift/HasWarning belong to the zone-drift event lines written by
// warn_egress.py's log_zone_drift() (Issue #1434 S1): those carry no "ok" but
// a non-empty "drift" — that pair is what tells them apart from pre-#1422-S1
// lines, which also lack "ok" and must stay silently skipped.
type warnServiceCallEntry struct {
	Service       string `json:"service"`
	CacheHit      bool   `json:"cache_hit"`
	Ok            *bool  `json:"ok"`
	SelfThrottled bool   `json:"self_throttled"`
	Ts            string `json:"ts"`
	Drift         string `json:"drift"`
	HasWarning    bool   `json:"has_warning"`
}

// canonicalWarnServiceName returns the prefix before the first ':' in a warn
// service identifier (e.g. "meteoalarm:AT:p1" -> "meteoalarm"); a service
// name without ':' is returned unchanged. Issue #1422 S2.
func canonicalWarnServiceName(service string) string {
	if idx := strings.IndexByte(service, ':'); idx >= 0 {
		return service[:idx]
	}
	return service
}

// warnServiceAgg accumulates the per-canonical-service aggregate while
// scanning the journal once.
type warnServiceAgg struct {
	lastSuccessAt string
	haveSuccess   bool
	lastAttemptAt string
	haveAttempt   bool
	selfThrottled bool

	// Zone-drift counters (Issue #1434 S2), fed by a separate line kind and
	// deliberately kept apart from the outage fields above: a drift line is
	// neither an attempt nor a success.
	//
	// One timestamp PER category, never a shared maximum (F001): the counters
	// are cumulative and the journal never rotates, so check-gregor20.sh can
	// only escape a permanently hot ERROR threshold via a freshness check —
	// and a shared maximum would make a long-fixed occurrence with warning
	// look fresh as soon as a harmless one without warning arrives.
	driftWithWarning     int
	driftWithoutWarning  int
	lastWithWarningAt    string
	lastWithoutWarningAt string
	haveDrift            bool
}

// aggregateWarnServiceCalls scans path (data/diagnostics/warn_service_calls.jsonl)
// and returns one warnServiceAgg per canonical service name, plus whether the
// file exists but could not be read (Issue #1422 AC-7: a genuine read error —
// e.g. path is a directory — must be distinguishable from "file does not
// exist yet"). Fail-soft on individual corrupt lines, exactly like
// findLastBriefingProviderError.
//
// Only lines with cache_hit=false AND a present "ok" field count (a cache hit
// is not a new answer from the provider; pre-#1422-S1 lines without "ok" are
// skipped entirely — s. spec "Übergangsfenster nach Deploy").
//
// The same single scan also picks up the zone-drift event lines of Issue #1434
// S1 (no "ok", but a "drift" direction) into separate counters; they never
// touch the outage fields (s. AC-7).
func aggregateWarnServiceCalls(path string) (map[string]*warnServiceAgg, bool) {
	aggs := map[string]*warnServiceAgg{}

	f, err := os.Open(path)
	if err != nil {
		return aggs, false // missing file: legitimate empty state, no error flag
	}
	defer f.Close()

	aggFor := func(service string) *warnServiceAgg {
		name := canonicalWarnServiceName(service)
		agg, ok := aggs[name]
		if !ok {
			agg = &warnServiceAgg{}
			aggs[name] = agg
		}
		return agg
	}

	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		var entry warnServiceCallEntry
		if err := json.Unmarshal(scanner.Bytes(), &entry); err != nil {
			continue // skip corrupt line, keep scanning
		}
		// Zone-drift event line (Issue #1434 S2): no "ok" AND a "drift"
		// direction. Counted separately and never as attempt/success — a
		// pre-#1422-S1 line (no "ok", no "drift") still falls through to
		// the skip below.
		if entry.Ok == nil && entry.Drift != "" {
			// No usable ts — missing, empty or whitespace only — drops the
			// line like a corrupt one (F004/F005). It is not producible via
			// log_zone_drift() at all (ts is mandatory there), so this only
			// happens on journal corruption — and of the two possible states,
			// "no finding" is the honest one: a count without a point in time
			// is a call to action a freshness filter cannot act on, so the
			// finding would vanish silently. Whitespace would even sort as
			// "ancient" in the lexicographic comparisons below.
			if strings.TrimSpace(entry.Ts) == "" {
				continue
			}
			agg := aggFor(entry.Service)
			if entry.HasWarning {
				agg.driftWithWarning++
				if entry.Ts > agg.lastWithWarningAt {
					agg.lastWithWarningAt = entry.Ts
				}
			} else {
				agg.driftWithoutWarning++
				if entry.Ts > agg.lastWithoutWarningAt {
					agg.lastWithoutWarningAt = entry.Ts
				}
			}
			agg.haveDrift = true
			continue
		}
		if entry.CacheHit || entry.Ok == nil {
			continue
		}

		agg := aggFor(entry.Service)
		if !agg.haveAttempt || entry.Ts > agg.lastAttemptAt {
			agg.lastAttemptAt = entry.Ts
			agg.haveAttempt = true
			agg.selfThrottled = entry.SelfThrottled
		}
		if *entry.Ok && (!agg.haveSuccess || entry.Ts > agg.lastSuccessAt) {
			agg.lastSuccessAt = entry.Ts
			agg.haveSuccess = true
		}
	}
	// A path pointing at a directory opens fine but fails on the first Read
	// (Linux: EISDIR) — that surfaces here as a Scan error, distinct from
	// os.IsNotExist above.
	if scanner.Err() != nil {
		return aggs, true
	}
	return aggs, false
}

// nilIfEmpty renders an unset timestamp as JSON null instead of "", which
// would read like a timestamp to a consumer.
func nilIfEmpty(ts string) any {
	if ts == "" {
		return nil
	}
	return ts
}

// meteoalarmDefaultDailyBudget mirrors MeteoAlarmBudgetGate.DEFAULT_DAILY_BUDGET
// (src/services/official_alerts/meteoalarm_budget.py).
const meteoalarmDefaultDailyBudget = 100

// meteoalarmDailyBudget mirrors MeteoAlarmBudgetGate.daily_budget: the
// GZ_METEOALARM_DAILY_BUDGET env var (positive integer) overrides the
// default, deployable without a Go rebuild.
func meteoalarmDailyBudget() int {
	if raw := os.Getenv("GZ_METEOALARM_DAILY_BUDGET"); raw != "" {
		if v, err := strconv.Atoi(raw); err == nil && v > 0 {
			return v
		}
	}
	return meteoalarmDefaultDailyBudget
}

// meteoalarmBudgetFile mirrors the persisted shape written by
// MeteoAlarmBudgetGate._write (data/diagnostics/meteoalarm_budget.json):
// {"date": ..., "calls": ..., "observed_reset_ts": ...}.
type meteoalarmBudgetFile struct {
	Date            string   `json:"date"`
	Calls           int      `json:"calls"`
	ObservedResetTs *float64 `json:"observed_reset_ts"`
}

// meteoalarmBudgetSnapshot reads path (data/diagnostics/meteoalarm_budget.json)
// and returns the same field set as MeteoAlarmBudgetGate.snapshot() (Python):
// calls_today, daily_budget, usage_ratio, observed_reset_ts, status — a
// direct passthrough of the persisted counters, fail-soft exactly like
// snapshot() itself ("unavailable" instead of raising). path=="" (no
// s.store) is treated the same as a read failure.
func meteoalarmBudgetSnapshot(path string) map[string]any {
	budget := meteoalarmDailyBudget()
	unavailable := map[string]any{
		"calls_today":       0,
		"daily_budget":      budget,
		"usage_ratio":       0.0,
		"observed_reset_ts": nil,
		"status":            "unavailable",
	}
	if path == "" {
		return unavailable
	}
	data, err := os.ReadFile(path)
	if err != nil {
		return unavailable
	}
	var file meteoalarmBudgetFile
	if err := json.Unmarshal(data, &file); err != nil {
		return unavailable
	}

	ratio := 0.0
	if budget > 0 {
		ratio = float64(file.Calls) / float64(budget)
	}
	var resetTs any
	if file.ObservedResetTs != nil {
		resetTs = *file.ObservedResetTs
	}
	return map[string]any{
		"calls_today":       file.Calls,
		"daily_budget":      budget,
		"usage_ratio":       ratio,
		"observed_reset_ts": resetTs,
		"status":            "ok",
	}
}

// WarnServiceHealth aggregates raw call outcomes per canonical warn service
// (Issue #1422 S2) directly from data/diagnostics/warn_service_calls.jsonl
// plus the MeteoAlarm daily-budget snapshot from
// data/diagnostics/meteoalarm_budget.json — both read from s.store.DataDir,
// analog BriefingHealth(): no Python HTTP call, no login required.
//
// Deliberately raw timestamps/flags only, no threshold decision (s. spec
// "Bewusste Design-Entscheidung — nur Rohdaten, keine Schwelle"): the 3h
// alarming threshold lives in henemm-infra's check-gregor20.sh (Teil B),
// exactly like the existing provider_error_streak_since pattern.
//
// A service that was never called in the entire journal does not appear as
// a key at all (no fabricated failure, s. AC-5). A missing journal file
// yields an empty map (s. AC-... legitimate fresh-deploy state); an
// existing-but-unreadable journal additionally sets "journal_read_error":
// true (s. AC-7) — explicitly distinct from "never written".
//
// Issue #1434 S2 adds, per service and only when at least one occurrence was
// observed, "zone_drift": {unmapped_with_warning, unmapped_without_warning,
// last_with_warning_at, last_without_warning_at} — raw counters again, the
// ERROR/WARN threshold stays in henemm-infra's check-gregor20.sh. The
// timestamps are per category so that side can tell a stale finding from a
// fresh one (F001).
func (s *Scheduler) WarnServiceHealth() map[string]any {
	result := map[string]any{}

	if s.store == nil {
		result["meteoalarm_budget"] = meteoalarmBudgetSnapshot("")
		return result
	}

	journalPath := filepath.Join(s.store.DataDir, "diagnostics", "warn_service_calls.jsonl")
	aggs, readErr := aggregateWarnServiceCalls(journalPath)
	if readErr {
		result["journal_read_error"] = true
	}
	for name, agg := range aggs {
		entry := map[string]any{
			"last_attempt_at": nil,
			"self_throttled":  agg.selfThrottled,
			"last_success_at": nil,
		}
		if agg.haveAttempt {
			// A service known only from drift lines has no attempt at all;
			// nil says so honestly instead of an empty string that reads
			// like a timestamp.
			entry["last_attempt_at"] = agg.lastAttemptAt
		}
		if agg.haveSuccess {
			entry["last_success_at"] = agg.lastSuccessAt
		}
		if agg.haveDrift {
			// The whole block is absent without a single occurrence (s. AC-6):
			// a zero would be indistinguishable from a real finding. INSIDE
			// the block, a category without occurrence is nil next to its 0 —
			// unambiguous, and it keeps a freshness check from reading a
			// stamp that belongs to the other category (F001).
			entry["zone_drift"] = map[string]any{
				"unmapped_with_warning":    agg.driftWithWarning,
				"unmapped_without_warning": agg.driftWithoutWarning,
				"last_with_warning_at":     nilIfEmpty(agg.lastWithWarningAt),
				"last_without_warning_at":  nilIfEmpty(agg.lastWithoutWarningAt),
			}
		}
		result[name] = entry
	}

	budgetPath := filepath.Join(s.store.DataDir, "diagnostics", "meteoalarm_budget.json")
	result["meteoalarm_budget"] = meteoalarmBudgetSnapshot(budgetPath)

	return result
}
