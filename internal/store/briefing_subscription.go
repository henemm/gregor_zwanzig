package store

import (
	"encoding/json"
	"os"
	"path/filepath"

	"github.com/henemm/gregor-api/internal/model"
)

// briefingsDir returns data/users/<uid>/briefings (Issue #1250 Scheibe 5,
// ADR-0023). Per-file layout, analog TripsDir. Since Scheibe 7a (route
// cutover), LoadTrip/LoadTrips/SaveTrip/DeleteTrip (trip.go) read/write here
// instead of TripsDir() -- ComparePresets remain on compare_presets.json
// (AC-30, KL-7: no union model, no LoadBriefing/SaveBriefing usage).
func (s *Store) briefingsDir() string {
	return filepath.Join(s.DataDir, "users", s.UserID, "briefings")
}

// BriefingsDir exposes briefingsDir() for cross-package callers (test
// helpers analog TripsDir(), Issue #1250 Scheibe 7a).
func (s *Store) BriefingsDir() string {
	return s.briefingsDir()
}

// LoadBriefing loads a single briefings/<id>.json file. Returns nil, nil if
// the file does not exist (mirrors LoadTrip).
func (s *Store) LoadBriefing(id string) (*model.BriefingSubscription, error) {
	path := filepath.Join(s.briefingsDir(), id+".json")

	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, err
	}

	var b model.BriefingSubscription
	if err := json.Unmarshal(data, &b); err != nil {
		return nil, err
	}
	return &b, nil
}

// SaveBriefing persists a BriefingSubscription to briefings/<id>.json
// (per-file, analog SaveTrip). Lossless — model.BriefingSubscription's
// MarshalJSON round-trips every field via the raw catch-all (Issue #1250
// Scheibe 5, ADR-0023).
func (s *Store) SaveBriefing(b *model.BriefingSubscription) error {
	dir := s.briefingsDir()
	if err := os.MkdirAll(dir, 0755); err != nil {
		return err
	}

	data, err := json.MarshalIndent(b, "", "  ")
	if err != nil {
		return err
	}

	return writeFileLogged(filepath.Join(dir, b.ID+".json"), data)
}
