package store

import (
	"encoding/json"
	"os"
	"path/filepath"

	"github.com/henemm/gregor-api/internal/model"
)

func (s *Store) comparePresetsFile() string {
	return filepath.Join(s.DataDir, "users", s.UserID, "compare_presets.json")
}

func (s *Store) LoadComparePresets() ([]model.ComparePreset, error) {
	data, err := os.ReadFile(s.comparePresetsFile())
	if os.IsNotExist(err) {
		return []model.ComparePreset{}, nil
	}
	if err != nil {
		return nil, err
	}
	var presets []model.ComparePreset
	if err := json.Unmarshal(data, &presets); err != nil {
		return nil, err
	}
	if presets == nil {
		presets = []model.ComparePreset{}
	}
	four := 4
	for i := range presets {
		// Issue #511 F001: *int statt int — nil bedeutet "Feld fehlt in JSON" (Altdaten),
		// 0 bedeutet "User hat explizit Montag gewählt". Migration darf nur nil-Fälle
		// auf Freitag-Default setzen, niemals einen expliziten Montag (0) überschreiben.
		if presets[i].Weekday == nil && presets[i].Schedule == "weekly" {
			presets[i].Weekday = &four
		}
		// Issue #764: Legacy-Presets ohne forecast_hours-Feld → Go-Zero-Value 0 → Default 48.
		// 0 ist kein gültiger Horizont; 24/48/72 sind die einzigen gültigen Werte.
		if presets[i].ForecastHours == 0 {
			presets[i].ForecastHours = 48
		}
		migrateComparePresetSlots(&presets[i])
	}
	return presets, nil
}

// migrateComparePresetSlots (Issue #1232 Scheibe 2a): idempotente
// Zeitplan-Migration. Marker "nie migriert" ist MorningTime == nil (Pointer-
// Feld fehlte im JSON). Der Alt-Wert von Schedule entscheidet ueber die
// Nutzer-Intention (KL-6): "daily_evening" → Abend-Slot aktiv, alle anderen
// Alt-Werte ("daily", "weekly", "manual", leer/unbekannt, "daily_morning")
// → Morgen-Slot aktiv (verhaltensidentisch zum bisherigen 06:00-Cron).
// Bereits migrierte Presets (MorningTime gesetzt) werden NICHT erneut
// angefasst — auch ein explizites morning_enabled=false bleibt erhalten.
func migrateComparePresetSlots(p *model.ComparePreset) {
	if p.MorningTime != nil {
		return
	}
	falseVal := false
	trueVal := true
	morningTime := "06:00:00"
	eveningTime := "18:00:00"
	p.MorningTime = &morningTime
	p.EveningTime = &eveningTime
	if p.Schedule == "daily_evening" {
		p.MorningEnabled = &falseVal
		p.EveningEnabled = &trueVal
	} else {
		p.MorningEnabled = &trueVal
		p.EveningEnabled = &falseVal
	}
}

func (s *Store) SaveComparePresets(presets []model.ComparePreset) error {
	dir := filepath.Join(s.DataDir, "users", s.UserID)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return err
	}
	if presets == nil {
		presets = []model.ComparePreset{}
	}
	data, err := json.MarshalIndent(presets, "", "  ")
	if err != nil {
		return err
	}
	return writeFileLogged(s.comparePresetsFile(), data)
}
