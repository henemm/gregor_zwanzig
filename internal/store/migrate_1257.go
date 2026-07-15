package store

import (
	"os"
	"path/filepath"
	"strings"
)

// MigrateAllTripsAlertRules materialisiert Issue #1257 rückwirkend: pro Trip
// unter data/users/*/briefings/*.json (Issue #1250 Scheibe 7a Cutover)
// LoadTrip (Self-Heal) + SaveTrip (Persistenz) — identisch zum nächsten
// regulären Save. Idempotent (SyncAlertRules ist read-modify-write).
// Best-effort, bricht bei Einzelfehlern nicht ab.
func MigrateAllTripsAlertRules(dataDir string) (int, error) {
	entries, err := os.ReadDir(filepath.Join(dataDir, "users"))
	if err != nil {
		if os.IsNotExist(err) {
			return 0, nil
		}
		return 0, err
	}
	migrated := 0
	for _, u := range entries {
		if !u.IsDir() {
			continue
		}
		s := New(dataDir, u.Name())
		// Issue #1250 Scheibe 7a: LoadTrip/SaveTrip lesen/schreiben briefingsDir()
		// -- die Enumeration muss von dort ausgehen, sonst findet LoadTrip die
		// per Dateiname aufgezaehlten IDs nicht mehr (stiller No-Op).
		tripEntries, err := os.ReadDir(s.briefingsDir())
		if err != nil {
			continue
		}
		for _, te := range tripEntries {
			if te.IsDir() || !strings.HasSuffix(te.Name(), ".json") {
				continue
			}
			id := strings.TrimSuffix(te.Name(), ".json")
			trip, err := s.LoadTrip(id)
			if err != nil || trip == nil {
				continue
			}
			if s.SaveTrip(trip) == nil {
				migrated++
			}
		}
	}
	return migrated, nil
}
