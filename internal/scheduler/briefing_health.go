package scheduler

import (
	"bufio"
	"encoding/json"
	"os"
	"path/filepath"
	"sort"
	"time"

	"github.com/henemm/gregor-api/internal/store"
)

// diagnosticsCallEntry mirrors one line of data/diagnostics/openmeteo_calls.jsonl
// (written by src/providers/call_log.py). Only the fields needed for
// last_provider_error_at are decoded.
type diagnosticsCallEntry struct {
	Ts     string  `json:"ts"`
	Source string  `json:"source"`
	Status *int    `json:"status"`
	Error  *string `json:"error"`
}

// coreBriefingSources is the single, DRY definition of which diagnostics
// sources are CORE briefing weather fetches. Both the daytime briefing fetch
// (source "briefing") and the night briefing fetch (source "briefing_nacht",
// written by src/providers/call_log.py's _fetch_night_weather) are core: a
// persistent outage of either one is a genuine briefing outage (Issue #1115
// F002). Enrichment/other-feature sources (ensemble, vergleich, vorschau, uv,
// trend, geosphere_clouds, alarm) are deliberately NOT here — an outage there
// is not a briefing outage and must not raise a false alarm.
var coreBriefingSources = map[string]bool{
	"briefing":       true,
	"briefing_nacht": true,
}

// isBriefingProviderError reports whether a diagnostics entry represents a
// CORE briefing-channel provider OUTAGE (as opposed to success or a content
// error). Core briefing fetches are "briefing" + "briefing_nacht" (see
// coreBriefingSources).
//
// The production writer (src/providers/call_log.py) records an HTTP status
// failure as {"status": 5xx, "error": null} — error is only ever populated for
// pure network failures (ConnectError/Timeout without a response). The real
// 07./08.07. incident produced exclusively status:503 / error:null lines, so a
// pure `error != nil` check (inherited from #1114) misses every real outage.
//
// 5xx threshold: a 4xx (e.g. #353 date-out-of-range) is a CONTENT error, not an
// outage, and must NOT raise the escalation signal (no false alarm). Pure
// network failures (status nil + error populated) still count.
func (e diagnosticsCallEntry) isBriefingProviderError() bool {
	if !coreBriefingSources[e.Source] {
		return false
	}
	if e.Status != nil && *e.Status >= 500 {
		return true
	}
	return e.Error != nil && *e.Error != ""
}

// BriefingHealth aggregates open pending-briefing catch-up markers across ALL
// users into a privacy-safe, purely numeric summary for the public
// /api/scheduler/status endpoint. Issue #1114.
//
// Privacy (#252): no user_id, trip_id, or other identifying string is ever
// placed into the returned map — only counts, a duration, and a timestamp.
func (s *Scheduler) BriefingHealth() map[string]any {
	var (
		openCount       int
		degradedTotal   int
		oldestCreatedAt time.Time
		haveOldest      bool
	)

	if s.store != nil {
		// Enumerate marker files directly via glob rather than via
		// ListUserIDs(), which only sees directories with a user.json. A
		// pending_briefings.json can outlive an incomplete account deletion
		// and must still be counted (Adversary F001, issue #1114).
		matches, _ := filepath.Glob(filepath.Join(s.store.DataDir, "users", "*", "pending_briefings.json"))
		for _, match := range matches {
			uid := filepath.Base(filepath.Dir(match))
			entries, err := store.LoadPendingBriefingsForUser(s.store.DataDir, uid)
			if err != nil {
				continue // fail-soft: one corrupt user must not break the aggregate
			}
			for _, e := range entries {
				openCount++
				degradedTotal += len(e.FailedSegmentIDs)
				createdAt, err := time.Parse(time.RFC3339, e.CreatedAt)
				if err != nil {
					continue
				}
				if !haveOldest || createdAt.Before(oldestCreatedAt) {
					oldestCreatedAt = createdAt
					haveOldest = true
				}
			}
		}
	}

	oldestAgeHours := 0.0
	if haveOldest {
		oldestAgeHours = time.Since(oldestCreatedAt).Hours()
	}

	var lastProviderErrorAt any
	var providerErrorStreakSince any
	providerErrorsRecentCount := 0
	if s.store != nil {
		if ts := findLastBriefingProviderError(s.store.DataDir); ts != "" {
			lastProviderErrorAt = ts
		}
		// Issue #1115 AC-4: a duration-growing signal so a persistently failing
		// model channel stays visible even while briefings keep going out via
		// the intra-Open-Meteo fallback. An external monitor computes
		// now - provider_error_streak_since to escalate with outage duration.
		if since, recent := analyzeBriefingProviderErrors(s.store.DataDir, time.Now().UTC()); recent > 0 {
			// Issue #1421 AC-4: since is "" when the streak has ended (see
			// analyzeBriefingProviderErrors) — only assign it when non-empty,
			// so the map carries a real nil rather than the empty string.
			if since != "" {
				providerErrorStreakSince = since
			}
			providerErrorsRecentCount = recent
		}
	}

	var corruptTripsLastRunAt any
	corruptTripsTotal := 0
	if s.store != nil {
		total, lastRun := aggregateCorruptTrips(s.store.DataDir)
		corruptTripsTotal = total
		if lastRun != "" {
			corruptTripsLastRunAt = lastRun
		}
	}

	// Issue #1629 AC-8: derselbe Bauart-Zwilling für den bislang unerfassten
	// Ausfallpfad "Versand wirft eine Ausnahme" (am 08.08. ein ganzer Tag ohne
	// Abweichungs-Alarm, sichtbar nur als Zeile im Dauerrauschen). Namens- und
	// Formelanalogie zu provider_error_* ist Absicht: die externe Eskalation
	// rechnet unverändert now - <streak_since>.
	var dispatchErrorStreakSince any
	dispatchErrorsRecentCount := 0
	if s.store != nil {
		if since, recent := analyzeBriefingDispatchErrors(s.store.DataDir, time.Now().UTC()); since != "" || recent > 0 {
			if since != "" {
				dispatchErrorStreakSince = since
			}
			dispatchErrorsRecentCount = recent
		}
	}

	// Issue #1661 AC-11/AC-12: derselbe Bauart-Zwilling für den bislang
	// unerfassten Ausfallpfad "Alarm-Anker vom falschen Tag / zu alt / fehlt".
	// Am 08.08.2026 lief die Abweichungs-Wache einer laufenden Tour dadurch
	// ~16 h ins Leere, ohne dass es irgendwo sichtbar wurde. Namens- und
	// Formelanalogie zu provider_error_*/briefing_dispatch_error_* ist Absicht:
	// die externe Eskalation rechnet unverändert now - <streak_since>.
	var anchorRejectedStreakSince any
	anchorRejectedRecentCount := 0
	if s.store != nil {
		if since, recent := analyzeAlertAnchorRejections(s.store.DataDir, time.Now().UTC()); since != "" || recent > 0 {
			if since != "" {
				anchorRejectedStreakSince = since
			}
			anchorRejectedRecentCount = recent
		}
	}

	return map[string]any{
		"open_pending_briefings":                openCount,
		"degraded_segments_total":               degradedTotal,
		"oldest_pending_age_hours":              oldestAgeHours,
		"last_provider_error_at":                lastProviderErrorAt,
		"provider_error_streak_since":           providerErrorStreakSince,
		"provider_errors_recent_count":          providerErrorsRecentCount,
		"corrupt_trips_total":                   corruptTripsTotal,
		"corrupt_trips_last_run_at":             corruptTripsLastRunAt,
		"briefing_dispatch_error_streak_since":  dispatchErrorStreakSince,
		"briefing_dispatch_errors_recent_count": dispatchErrorsRecentCount,
		"alert_anchor_rejected_streak_since":    anchorRejectedStreakSince,
		"alert_anchor_rejected_recent_count":    anchorRejectedRecentCount,
	}
}

// alertAnchorRejectedGapThreshold is the maximum gap between two consecutive
// alert-anchor rejections that still counts as one contiguous outage.
//
// Deliberately NEITHER dispatchErrorStreakGapThreshold (26h) NOR
// providerErrorStreakGapThreshold (2h): the deviation alert runs every 15
// minutes, so a rejection that repeats has at most a quarter-hour spacing. With
// 26h the very failure this signal exists for would stay invisible for days
// (that is exactly how the 08.08.2026 outage went unnoticed for ~16h), with 2h
// it would still be silent for eight consecutive blind runs. An hour without a
// new rejection means an anchor became usable again — the series is over.
const alertAnchorRejectedGapThreshold = 60 * time.Minute

// anchorRejectedEntry mirrors one line of
// users/<uid>/diagnostics/alert_anchor_rejected.jsonl, written by
// src/services/alert_briefing_anchor.py's record_alert_anchor_rejected
// (Issue #1661). Privacy (#252): only the timestamp is decoded — NEVER
// entity_id or reason. Both are present in the file (they are what makes the
// journal useful on the Python side) and must not cross this boundary.
type anchorRejectedEntry struct {
	Ts string `json:"ts"`
}

// analyzeAlertAnchorRejections scans every user's anchor-rejection journal and
// derives the same two signals as analyzeBriefingDispatchErrors, for Issue
// #1661 AC-11/AC-12:
//   - streakSince: earliest timestamp (RFC3339) of the current contiguous
//     rejection streak (adjacent rejections no more than
//     alertAnchorRejectedGapThreshold apart), so now-streakSince GROWS with the
//     outage. Empty once the streak has lapsed — a usable anchor writes no line,
//     so the forward gap against now is what ends a series.
//   - recentCount: rejections within the last 24h.
//
// Fail-soft: missing/corrupt files or lines are skipped, never a panic.
func analyzeAlertAnchorRejections(dataDir string, now time.Time) (string, int) {
	var rejectionTimes []time.Time
	matches, _ := filepath.Glob(filepath.Join(dataDir, "users", "*", "diagnostics", "alert_anchor_rejected.jsonl"))
	for _, match := range matches {
		f, err := os.Open(match)
		if err != nil {
			continue // fail-soft: one unreadable user must not break the aggregate
		}
		scanner := bufio.NewScanner(f)
		for scanner.Scan() {
			var entry anchorRejectedEntry
			if err := json.Unmarshal(scanner.Bytes(), &entry); err != nil {
				continue // skip corrupt line, keep scanning
			}
			ts, err := time.Parse(time.RFC3339, entry.Ts)
			if err != nil {
				continue
			}
			rejectionTimes = append(rejectionTimes, ts)
		}
		f.Close()
	}
	if len(rejectionTimes) == 0 {
		return "", 0
	}

	sort.Slice(rejectionTimes, func(i, j int) bool { return rejectionTimes[i].Before(rejectionTimes[j]) })

	recentCount := 0
	cutoff := now.Add(-24 * time.Hour)
	for _, ts := range rejectionTimes {
		if ts.After(cutoff) {
			recentCount++
		}
	}

	newest := rejectionTimes[len(rejectionTimes)-1]
	if now.Sub(newest) > alertAnchorRejectedGapThreshold {
		return "", recentCount
	}

	streakStart := newest
	for i := len(rejectionTimes) - 1; i > 0; i-- {
		if rejectionTimes[i].Sub(rejectionTimes[i-1]) > alertAnchorRejectedGapThreshold {
			break
		}
		streakStart = rejectionTimes[i-1]
	}
	return streakStart.Format(time.RFC3339), recentCount
}

// dispatchErrorStreakGapThreshold is the maximum gap between two consecutive
// briefing DISPATCH failures that still counts as one contiguous outage.
//
// Deliberately NOT providerErrorStreakGapThreshold (2h): provider calls happen
// many times per briefing run, dispatch happens once per briefing SLOT —
// morning and evening, i.e. roughly every 12h, for some users only once a day.
// With a 2h threshold every failure would be a streak of exactly one entry and
// the forward check against now would erase the signal two hours after the
// failure — precisely the "Kaschieren" ADR-0018 forbids. 26h covers a daily
// rhythm plus slack, so a genuinely ongoing outage keeps growing, while a
// single failure followed by a successful briefing (which writes no line at
// all) lets the streak lapse on its own.
const dispatchErrorStreakGapThreshold = 26 * time.Hour

// dispatchFailureEntry mirrors one line of
// users/<uid>/diagnostics/briefing_dispatch_failures.jsonl, written by
// src/services/alert_briefing_anchor.py's record_briefing_dispatch_failure
// (Issue #1629). Privacy (#252): only the timestamp is decoded — never
// entity_id, kind or the error text.
type dispatchFailureEntry struct {
	Ts string `json:"ts"`
}

// analyzeBriefingDispatchErrors scans every user's dispatch-failure journal and
// derives the same two signals as analyzeBriefingProviderErrors, for Issue
// #1629 AC-8:
//   - streakSince: earliest timestamp (RFC3339) of the current contiguous
//     failure streak (adjacent failures no more than
//     dispatchErrorStreakGapThreshold apart), so now-streakSince GROWS with the
//     outage. Empty once the streak has lapsed — a successful dispatch writes
//     no line, so the forward gap against now is what ends a series.
//   - recentCount: dispatch failures within the last 24h.
//
// Fail-soft: missing/corrupt files or lines are skipped, never a panic.
func analyzeBriefingDispatchErrors(dataDir string, now time.Time) (string, int) {
	var failureTimes []time.Time
	matches, _ := filepath.Glob(filepath.Join(dataDir, "users", "*", "diagnostics", "briefing_dispatch_failures.jsonl"))
	for _, match := range matches {
		f, err := os.Open(match)
		if err != nil {
			continue // fail-soft: one unreadable user must not break the aggregate
		}
		scanner := bufio.NewScanner(f)
		for scanner.Scan() {
			var entry dispatchFailureEntry
			if err := json.Unmarshal(scanner.Bytes(), &entry); err != nil {
				continue // skip corrupt line, keep scanning
			}
			ts, err := time.Parse(time.RFC3339, entry.Ts)
			if err != nil {
				continue
			}
			failureTimes = append(failureTimes, ts)
		}
		f.Close()
	}
	if len(failureTimes) == 0 {
		return "", 0
	}

	sort.Slice(failureTimes, func(i, j int) bool { return failureTimes[i].Before(failureTimes[j]) })

	recentCount := 0
	cutoff := now.Add(-24 * time.Hour)
	for _, ts := range failureTimes {
		if ts.After(cutoff) {
			recentCount++
		}
	}

	newest := failureTimes[len(failureTimes)-1]
	if now.Sub(newest) > dispatchErrorStreakGapThreshold {
		return "", recentCount
	}

	streakStart := newest
	for i := len(failureTimes) - 1; i > 0; i-- {
		if failureTimes[i].Sub(failureTimes[i-1]) > dispatchErrorStreakGapThreshold {
			break
		}
		streakStart = failureTimes[i-1]
	}
	return streakStart.Format(time.RFC3339), recentCount
}

// corruptTripsDiagnostics mirrors one users/<uid>/diagnostics/corrupt_trips.json
// file, written by src/services/trip_report_scheduler.py's
// record_corrupt_trip_observability (Issue #1262). Only the fields needed for
// the privacy-safe aggregate are decoded — never the "notified" filenames.
type corruptTripsDiagnostics struct {
	LastSkippedCount int    `json:"last_skipped_count"`
	LastRun          string `json:"last_run"`
}

// aggregateCorruptTrips sums last_skipped_count across ALL users'
// diagnostics/corrupt_trips.json (Issue #1262 AC-4) and returns the most
// recent last_run timestamp. Fail-soft: a missing or unparseable file is
// skipped, never a panic. Privacy (#252): only counts and a timestamp are
// read — never the per-file "notified" filenames or user_id.
func aggregateCorruptTrips(dataDir string) (int, string) {
	total := 0
	lastRun := ""
	matches, _ := filepath.Glob(filepath.Join(dataDir, "users", "*", "diagnostics", "corrupt_trips.json"))
	for _, match := range matches {
		data, err := os.ReadFile(match)
		if err != nil {
			continue // fail-soft: one unreadable file must not break the aggregate
		}
		var entry corruptTripsDiagnostics
		if err := json.Unmarshal(data, &entry); err != nil {
			continue
		}
		total += entry.LastSkippedCount
		if entry.LastRun > lastRun {
			lastRun = entry.LastRun
		}
	}
	return total, lastRun
}

// providerErrorStreakGapThreshold is the maximum gap between two consecutive
// briefing provider errors that still counts as one contiguous outage streak.
// It marks where "ongoing outage" ends and "over" begins, both looking back
// from the newest error (streak start) and forward to now (streak end,
// Issue #1421). Chosen deliberately short: without it, a single brief
// external-provider hiccup would otherwise keep reporting an outage for
// hours (the #1421 incident). This does NOT create a monitoring gap between
// briefing slots (which run morning/evening, ~12h apart, not hourly) —
// check-gregor20.sh polls all weather sources directly every 5 minutes on
// the same heartbeat, independent of this counter, so a genuinely ongoing
// outage is still caught even while no briefing is running. This signal
// answers a narrower question: are briefings themselves currently affected?
const providerErrorStreakGapThreshold = 2 * time.Hour

// analyzeBriefingProviderErrors scans the diagnostics log for briefing provider
// errors and derives two signals for Issue #1115 AC-4:
//   - streakSince: earliest timestamp (RFC3339) of the current contiguous error
//     streak (adjacent errors no more than providerErrorStreakGapThreshold
//     apart) — the start of the ongoing outage, so now-streakSince grows with
//     duration. Empty when no errors are logged.
//   - recentCount: number of briefing errors within the last 24h.
//
// Fail-soft: missing/corrupt file yields ("", 0), never a panic. Privacy
// (#252): only timestamps and counts are read — never user_id/trip_id.
func analyzeBriefingProviderErrors(dataDir string, now time.Time) (string, int) {
	path := filepath.Join(dataDir, "diagnostics", "openmeteo_calls.jsonl")
	f, err := os.Open(path)
	if err != nil {
		return "", 0
	}
	defer f.Close()

	var errorTimes []time.Time
	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		var entry diagnosticsCallEntry
		if err := json.Unmarshal(scanner.Bytes(), &entry); err != nil {
			continue // skip corrupt line, keep scanning
		}
		if !entry.isBriefingProviderError() {
			continue
		}
		ts, err := time.Parse(time.RFC3339, entry.Ts)
		if err != nil {
			continue
		}
		errorTimes = append(errorTimes, ts)
	}
	if len(errorTimes) == 0 {
		return "", 0
	}

	sort.Slice(errorTimes, func(i, j int) bool { return errorTimes[i].Before(errorTimes[j]) })

	// recentCount: briefing errors within the last 24h.
	recentCount := 0
	cutoff := now.Add(-24 * time.Hour)
	for _, ts := range errorTimes {
		if ts.After(cutoff) {
			recentCount++
		}
	}

	// Issue #1421: the gap threshold must also apply FORWARD, against "now".
	// If the most recent error is itself further in the past than the
	// threshold, the streak has ended — no ongoing outage to report, even
	// though errorTimes is non-empty and recentCount may still be >0.
	newest := errorTimes[len(errorTimes)-1]
	if now.Sub(newest) > providerErrorStreakGapThreshold {
		return "", recentCount
	}

	// streakSince: walk back from the most recent error while adjacent errors
	// stay within the gap threshold — the start of the ongoing outage.
	streakStart := newest
	for i := len(errorTimes) - 1; i > 0; i-- {
		if errorTimes[i].Sub(errorTimes[i-1]) > providerErrorStreakGapThreshold {
			break
		}
		streakStart = errorTimes[i-1]
	}
	return streakStart.Format(time.RFC3339), recentCount
}

// findLastBriefingProviderError scans data/diagnostics/openmeteo_calls.jsonl
// for the most recent entry from a core briefing source (see
// coreBriefingSources: "briefing" or "briefing_nacht") that is a provider
// outage (see isBriefingProviderError: HTTP 5xx OR a populated network error).
// Fail-soft: missing file or unparseable lines yield "" (no error found),
// never a panic or process abort.
func findLastBriefingProviderError(dataDir string) string {
	path := filepath.Join(dataDir, "diagnostics", "openmeteo_calls.jsonl")
	f, err := os.Open(path)
	if err != nil {
		return ""
	}
	defer f.Close()

	latest := ""
	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		var entry diagnosticsCallEntry
		if err := json.Unmarshal(scanner.Bytes(), &entry); err != nil {
			continue // skip corrupt line, keep scanning
		}
		if !entry.isBriefingProviderError() {
			continue
		}
		if entry.Ts > latest {
			latest = entry.Ts
		}
	}
	return latest
}
