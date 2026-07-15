package store

import (
	"encoding/json"
	"os"
	"path/filepath"
	"time"

	"github.com/henemm/gregor-api/internal/model"
)

func (s *Store) comparePresetsFile() string {
	return filepath.Join(s.DataDir, "users", s.UserID, "compare_presets.json")
}

// NormalizeComparePreset coerces nil slice fields (Corridors, LocationIDs,
// Empfaenger) to empty slices in place. Single source of truth for the read
// path (LoadComparePresets), the write path (SaveComparePresets), AND the
// handler package, which needs to normalize a preset before echoing it back
// in an HTTP response — a slice element mutated inside SaveComparePresets
// does not retroactively fix a separate local `preset` variable the handler
// already holds (Issue #1244 F001).
func NormalizeComparePreset(p *model.ComparePreset) {
	if p.Corridors == nil {
		p.Corridors = []model.Corridor{}
	}
	if p.LocationIDs == nil {
		p.LocationIDs = []string{}
	}
	if p.Empfaenger == nil {
		p.Empfaenger = []string{}
	}
	// Issue #1250 Scheibe 2 — Dual-Write-Invariante, Entpausen-Haelfte:
	// schedule!="manual" loescht einen gesetzten paused_at. Deterministisch
	// (keine time.Now()), darum sicher auf JEDEM Aufrufpfad — auch dem
	// Lese-Pfad (LoadComparePresets) ohne Write-Back. Die SET-Haelfte
	// (schedule=="manual" -> paused_at setzen) lebt NICHT hier, sondern in
	// MaterializePausedAt (s.u.), die nur vom Schreib-Pfad mit injizierter
	// Zeit gerufen wird — sonst wuerde time.Now() bei jedem GET einen neuen,
	// nie persistierten Zeitstempel erfinden (Adversary-Fund F001 CRITICAL).
	if p.Schedule != "manual" {
		p.PausedAt = nil
	}
}

// MaterializePausedAt setzt paused_at beim SCHREIBEN (nicht beim Laden),
// damit der Zeitstempel stabil persistiert und nicht bei jedem GET driftet
// (Issue #1250 Scheibe 2, Adversary-Fund F001). `now` wird injiziert
// (Aufrufer: Handler mit time.Now().UTC()) fuer deterministische Tests.
// Der PausedAt==nil-Guard bewahrt einen bestehenden Zeitstempel (springt
// sonst bei jedem unrelated Save auf "jetzt").
func MaterializePausedAt(p *model.ComparePreset, now time.Time) {
	if p.Schedule == "manual" && p.PausedAt == nil {
		p.PausedAt = &now
	}
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
		// Issue #1244 F002: Read-Path-Coercion symmetrisch zu
		// SaveComparePresets — sonst liefert GET auf eine unmigrierte
		// Legacy-Datei weiterhin "corridors":null.
		NormalizeComparePreset(&presets[i])
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
	// Issue #1244 F001: einzige Normalisierungsquelle (analog normalizeTrip
	// in SaveTrip) — Corridors/LocationIDs/Empfaenger dürfen pro Preset nie
	// als "null" persistiert werden.
	for i := range presets {
		NormalizeComparePreset(&presets[i])
	}
	data, err := json.MarshalIndent(presets, "", "  ")
	if err != nil {
		return err
	}
	return writeFileLogged(s.comparePresetsFile(), data)
}
