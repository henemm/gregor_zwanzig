package scheduler

import (
	"bufio"
	"encoding/json"
	"os"
	"path/filepath"
	"time"

	"github.com/henemm/gregor-api/internal/store"
)

// diagnosticsCallEntry mirrors one line of data/diagnostics/openmeteo_calls.jsonl
// (written by src/providers/call_log.py). Only the fields needed for
// last_provider_error_at are decoded.
type diagnosticsCallEntry struct {
	Ts     string  `json:"ts"`
	Source string  `json:"source"`
	Error  *string `json:"error"`
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
	if s.store != nil {
		if ts := findLastBriefingProviderError(s.store.DataDir); ts != "" {
			lastProviderErrorAt = ts
		}
	}

	return map[string]any{
		"open_pending_briefings":   openCount,
		"degraded_segments_total":  degradedTotal,
		"oldest_pending_age_hours": oldestAgeHours,
		"last_provider_error_at":   lastProviderErrorAt,
	}
}

// findLastBriefingProviderError scans data/diagnostics/openmeteo_calls.jsonl
// for the most recent entry with source=="briefing" and a non-empty error.
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
		if entry.Source != "briefing" || entry.Error == nil || *entry.Error == "" {
			continue
		}
		if entry.Ts > latest {
			latest = entry.Ts
		}
	}
	return latest
}
