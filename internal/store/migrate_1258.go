package store

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"

	"github.com/henemm/gregor-api/internal/model"
)

// MigrateAllOfficialWarnings materialisiert Issue #1258 rückwirkend: pro
// Trip/ComparePreset unter data/users/*/briefings/*.json (seit Cutover S7a
// route + S7b vergleich, kind-getaggt) -- LoadTrip/LoadComparePreset
// (Self-Heal) + Save (RMW), analog
// migrate_1257.go. Formel (PO-Entscheidung F1):
// official_warnings.enabled := (official_alert_triggers_enabled != false),
// d.h. fehlend/true -> true, false -> false (Ist-Verhalten, kein
// Verhaltenswechsel für Bestand). Idempotent (AC-3): ein bereits gesetztes
// OfficialWarnings-Feld wird NICHT überschrieben, auch wenn es seither
// manuell verändert wurde. Best-effort, bricht bei Einzelfehlern nicht ab.
func MigrateAllOfficialWarnings(dataDir string) (int, error) {
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
		migrated += migrateUserTripsOfficialWarnings(s)
		if migrateUserComparePresetsOfficialWarnings(s) {
			migrated++
		}
	}
	return migrated, nil
}

// officialWarningsEnabledFromLegacy implementiert die Migrationsformel
// (s. Docstring oben) — geteilt zwischen Trip- und ComparePreset-Migration.
func officialWarningsEnabledFromLegacy(legacy *bool) bool {
	return legacy == nil || *legacy
}

// officialWarningsRawHasEnabledKey prüft an den rohen JSON-Bytes, ob
// "official_warnings" ein Objekt MIT "enabled"-Schlüssel ist. Fix-Loop F003:
// `OfficialWarningsConfig.Enabled` ist `bool` (kein Pointer) — typisiertes
// Unmarshal macht ein leeres `{}` (unmigrierter Datenmüll/Schreibfehler)
// von einem bewussten `{"enabled": false}` ununterscheidbar (`!= nil` wäre
// bei beiden true -> "bereits migriert", fail closed). Rohes Nachsehen auf
// den "enabled"-Schlüssel gleicht das an die Python-Migration an
// (scripts/migrate_1258_official_warnings.py), die `{}` als unmigriert
// behandelt.
func officialWarningsRawHasEnabledKey(raw []byte) bool {
	var generic struct {
		OfficialWarnings map[string]interface{} `json:"official_warnings"`
	}
	if err := json.Unmarshal(raw, &generic); err != nil || generic.OfficialWarnings == nil {
		return false
	}
	_, ok := generic.OfficialWarnings["enabled"]
	return ok
}

func migrateUserTripsOfficialWarnings(s *Store) int {
	// Issue #1250 Scheibe 7a: LoadTrip/SaveTrip lesen/schreiben briefingsDir()
	// -- die Enumeration muss von dort ausgehen (sonst findet LoadTrip die per
	// Dateiname aufgezaehlten IDs nicht mehr). briefingsDir() traegt auch
	// kind="vergleich"-Eintraege (S5-Migration); LoadTrip liefert dafuer
	// bereits nil (kein Trip) -- der `trip == nil`-Skip unten deckt das ab.
	tripEntries, err := os.ReadDir(s.briefingsDir())
	if err != nil {
		return 0
	}
	migrated := 0
	for _, te := range tripEntries {
		if te.IsDir() || !strings.HasSuffix(te.Name(), ".json") {
			continue
		}
		id := strings.TrimSuffix(te.Name(), ".json")
		trip, err := s.LoadTrip(id)
		if err != nil || trip == nil {
			continue
		}
		alreadyMigrated := trip.OfficialWarnings != nil
		if alreadyMigrated {
			if raw, rerr := os.ReadFile(filepath.Join(s.briefingsDir(), te.Name())); rerr == nil {
				alreadyMigrated = officialWarningsRawHasEnabledKey(raw)
			}
		}
		if alreadyMigrated {
			continue // AC-3: bereits migriert -> unangetastet lassen
		}
		trip.OfficialWarnings = &model.OfficialWarningsConfig{
			Enabled: officialWarningsEnabledFromLegacy(trip.OfficialAlertTriggersEnabled),
		}
		if s.SaveTrip(trip) == nil {
			migrated++
		}
	}
	return migrated
}

func migrateUserComparePresetsOfficialWarnings(s *Store) bool {
	// Issue #1250 Scheibe 7b: LoadComparePreset/SaveComparePreset lesen/schreiben
	// per-Datei briefings/<id>.json (kind=vergleich) — die Enumeration geht von
	// dort aus, analog migrateUserTripsOfficialWarnings. LoadComparePreset
	// liefert nil fuer kind!="vergleich" (route/leer); der preset==nil-Skip
	// deckt das ab. Der rohe comparePresetsFile()-Index-Hack entfaellt.
	entries, err := os.ReadDir(s.briefingsDir())
	if err != nil {
		return false
	}
	changed := false
	for _, e := range entries {
		if e.IsDir() || !strings.HasSuffix(e.Name(), ".json") {
			continue
		}
		id := strings.TrimSuffix(e.Name(), ".json")
		preset, err := s.LoadComparePreset(id)
		if err != nil || preset == nil {
			continue
		}
		alreadyMigrated := preset.OfficialWarnings != nil
		if alreadyMigrated {
			// Fix-Loop F003: rohe Bytes fuer den "enabled"-Schluessel-Check
			// (s. officialWarningsRawHasEnabledKey) — `{}` gilt als unmigriert.
			if raw, rerr := os.ReadFile(filepath.Join(s.briefingsDir(), e.Name())); rerr == nil {
				alreadyMigrated = officialWarningsRawHasEnabledKey(raw)
			}
		}
		if alreadyMigrated {
			continue // AC-3: bereits migriert -> unangetastet lassen
		}
		preset.OfficialWarnings = &model.OfficialWarningsConfig{
			Enabled: officialWarningsEnabledFromLegacy(preset.OfficialAlertTriggersEnabled),
		}
		if s.SaveComparePreset(*preset) == nil {
			changed = true
		}
	}
	return changed
}
