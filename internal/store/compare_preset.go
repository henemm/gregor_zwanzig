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
	}
	return presets, nil
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
