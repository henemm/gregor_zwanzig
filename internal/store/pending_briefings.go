package store

import (
	"encoding/json"
	"os"
	"path/filepath"
)

// PendingBriefingEntry represents one open catch-up marker written by the
// Python scheduler when a briefing was sent with degraded (missing) weather
// segments. Issue #1114.
type PendingBriefingEntry struct {
	TripID           string   `json:"trip_id"`
	ReportType       string   `json:"report_type"`
	Date             string   `json:"date"`
	SlotHour         int      `json:"slot_hour"`
	FailedSegmentIDs []string `json:"failed_segment_ids"`
	Attempts         int      `json:"attempts"`
	CreatedAt        string   `json:"created_at"` // RFC3339
}

type pendingBriefingsFile struct {
	Entries []PendingBriefingEntry `json:"entries"`
}

// LoadPendingBriefingsForUser reads data/users/<userID>/pending_briefings.json.
// Fail-soft, analog to LoadBriefingLog: a missing or corrupt file yields an
// empty slice, never an error. Issue #1114.
func LoadPendingBriefingsForUser(dataDir, userID string) ([]PendingBriefingEntry, error) {
	path := filepath.Join(dataDir, "users", userID, "pending_briefings.json")
	b, err := os.ReadFile(path)
	if os.IsNotExist(err) {
		return []PendingBriefingEntry{}, nil
	}
	if err != nil {
		return nil, err
	}
	var f pendingBriefingsFile
	if err := json.Unmarshal(b, &f); err != nil {
		return []PendingBriefingEntry{}, nil
	}
	if f.Entries == nil {
		return []PendingBriefingEntry{}, nil
	}
	return f.Entries, nil
}
