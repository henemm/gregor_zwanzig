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
type AlertLogEntry struct {
	TripID       string `json:"trip_id"`
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

// AlertCountByTrip returns a map[tripID]count of all alert-log entries per trip
// for the user-scoped store (Issue #396). No time filter — every historical
// alert is counted (the 48h-retention was removed in the Python writer).
// Fail-soft: on load error it returns an empty map and no error.
func (s *Store) AlertCountByTrip() (map[string]int, error) {
	entries, err := s.LoadAlertLog()
	if err != nil {
		return map[string]int{}, nil
	}
	counts := make(map[string]int)
	for _, e := range entries {
		counts[e.TripID]++
	}
	return counts, nil
}
