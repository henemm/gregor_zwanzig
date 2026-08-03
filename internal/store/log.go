package store

import (
	"encoding/json"
	"os"
	"path/filepath"
)

// BriefingLogEntry represents one briefing send event (Issue #393).
type BriefingLogEntry struct {
	TripID   string   `json:"trip_id"`
	Kind     string   `json:"kind"`
	SentAt   string   `json:"sent_at"`
	Channels []string `json:"channels"`
}

type briefingLogFile struct {
	Entries []BriefingLogEntry `json:"entries"`
}

// LoadBriefingLog reads the user's briefing_log.json. Returns an empty slice
// if the file is missing or corrupt (fail-soft). Issue #393.
func (s *Store) LoadBriefingLog() ([]BriefingLogEntry, error) {
	path := filepath.Join(s.DataDir, "users", s.UserID, "briefing_log.json")
	b, err := os.ReadFile(path)
	if os.IsNotExist(err) {
		return []BriefingLogEntry{}, nil
	}
	if err != nil {
		return nil, err
	}
	var f briefingLogFile
	if err := json.Unmarshal(b, &f); err != nil {
		return []BriefingLogEntry{}, nil
	}
	if f.Entries == nil {
		return []BriefingLogEntry{}, nil
	}
	return f.Entries, nil
}

// AlertLogEntry represents one alert fire event (Issue #393).
//
// Issue #1467 S1: the entry carries ONE identifier (EntityID) plus a type
// (EntityType, "trip" | "compare"). TripID stays as a READ-ONLY legacy field —
// existing log files still carry it — but is never written by the Python side
// any more and is omitted from the API response when absent.
type AlertLogEntry struct {
	EntityID     string `json:"entity_id"`
	EntityType   string `json:"entity_type"`
	TripID       string `json:"trip_id,omitempty"`
	SentAt       string `json:"sent_at"`
	ChangesCount int    `json:"changes_count"`
	Severity     string `json:"severity"`
}

type alertLogFile struct {
	Entries []AlertLogEntry `json:"entries"`
}

// LoadAlertLog reads the user's alert_log.json. Returns an empty slice if the
// file is missing or corrupt (fail-soft). Issue #393.
func (s *Store) LoadAlertLog() ([]AlertLogEntry, error) {
	path := filepath.Join(s.DataDir, "users", s.UserID, "alert_log.json")
	b, err := os.ReadFile(path)
	if os.IsNotExist(err) {
		return []AlertLogEntry{}, nil
	}
	if err != nil {
		return nil, err
	}
	var f alertLogFile
	if err := json.Unmarshal(b, &f); err != nil {
		return []AlertLogEntry{}, nil
	}
	if f.Entries == nil {
		return []AlertLogEntry{}, nil
	}
	// Issue #1467 S1 — read rule instead of file migration: legacy entries only
	// have trip_id. They are translated on load; the file itself is never
	// rewritten (BUG-DATALOSS-GR221: rewriting history is the only way a bug
	// destroys it irreversibly).
	for i := range f.Entries {
		if f.Entries[i].EntityID == "" {
			f.Entries[i].EntityID = f.Entries[i].TripID
		}
		if f.Entries[i].EntityType == "" {
			f.Entries[i].EntityType = "trip"
		}
	}
	return f.Entries, nil
}

// BriefingCountByTrip returns a map[tripID]count of all briefing-log entries
// per trip for the user-scoped store (Issue #396). Fail-soft: on load error it
// returns an empty map and no error so the archive view never 500s.
func (s *Store) BriefingCountByTrip() (map[string]int, error) {
	entries, err := s.LoadBriefingLog()
	if err != nil {
		return map[string]int{}, nil
	}
	counts := make(map[string]int)
	for _, e := range entries {
		counts[e.TripID]++
	}
	return counts, nil
}

// AlertCountByEntity returns a map["<type>:<id>"]count of all alert-log entries
// per entity for the user-scoped store (Issue #396, key form since #1467 S1).
// The composite key keeps trips and compare presets apart without relying on
// the two independent ID spaces never colliding — before #1467 every compare
// entry landed in one shared bucket under the empty key. No time filter — every
// historical alert is counted (the 48h-retention was removed in the Python
// writer). Fail-soft: on load error it returns an empty map and no error.
func (s *Store) AlertCountByEntity() (map[string]int, error) {
	entries, err := s.LoadAlertLog()
	if err != nil {
		return map[string]int{}, nil
	}
	counts := make(map[string]int)
	for _, e := range entries {
		// No entry is ever dropped: an entry without any identifier is counted
		// under "trip:" rather than silently swallowed (AC-12).
		counts[e.EntityType+":"+e.EntityID]++
	}
	return counts, nil
}
