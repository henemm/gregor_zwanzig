package store

import (
	"encoding/json"
	"os"
	"path/filepath"

	"github.com/henemm/gregor-api/internal/model"
)

// briefingsDir returns data/users/<uid>/briefings (Issue #1250 Scheibe 5,
// ADR-0023). Per-file layout, analog TripsDir. Since Scheibe 7a (route
// cutover) LoadTrip/LoadTrips/SaveTrip/DeleteTrip (trip.go) and since Scheibe
// 7b (vergleich cutover) LoadComparePresets/LoadComparePreset/SaveComparePreset/
// DeleteComparePreset (compare_preset.go) read/write here instead of TripsDir()/
// compare_presets.json -- die Dateien sind per kind getrennt (route vs.
// vergleich), kein Union-Modell, LoadBriefing/SaveBriefing bleiben ungenutzt
// (KL-7/KL-8).
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
