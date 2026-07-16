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
			providerErrorStreakSince = since
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

	return map[string]any{
		"open_pending_briefings":       openCount,
		"degraded_segments_total":      degradedTotal,
		"oldest_pending_age_hours":     oldestAgeHours,
		"last_provider_error_at":       lastProviderErrorAt,
		"provider_error_streak_since":  providerErrorStreakSince,
		"provider_errors_recent_count": providerErrorsRecentCount,
		"corrupt_trips_total":          corruptTripsTotal,
		"corrupt_trips_last_run_at":    corruptTripsLastRunAt,
	}
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
// Chosen at 2h: briefing slots fire on roughly hourly cadence, so a genuinely
// persistent channel outage produces errors well within 2h of each other,
// while an isolated older error starts a fresh streak rather than inflating an
// ongoing one.
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

	// streakSince: walk back from the most recent error while adjacent errors
	// stay within the gap threshold — the start of the ongoing outage.
	streakStart := errorTimes[len(errorTimes)-1]
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
