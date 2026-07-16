package store

import (
	"encoding/json"
	"log"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/henemm/gregor-api/internal/model"
)

// NormalizeComparePreset coerces nil slice fields (Corridors, LocationIDs,
// Empfaenger) to empty slices in place. Single source of truth for the read
// path (LoadComparePresets/LoadComparePreset), the write path
// (SaveComparePreset), AND the handler package, which needs to normalize a
// preset before echoing it back in an HTTP response — a slice element mutated
// inside SaveComparePreset does not retroactively fix a separate local
// `preset` variable the handler already holds (Issue #1244 F001).
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

// normalizeLoadedComparePreset wendet die Lese-Pfad-Migration/Normalisierung
// auf ein einzelnes geladenes Preset an (Weekday-Default #511, ForecastHours-
// Default #764, Slot-Migration #1232, nil-Coercion #1244). Geteilte Quelle
// zwischen LoadComparePresets (Glob) und LoadComparePreset (Einzeldatei),
// Issue #1250 Scheibe 7b.
func normalizeLoadedComparePreset(p *model.ComparePreset) {
	four := 4
	// Issue #511 F001: *int statt int — nil bedeutet "Feld fehlt in JSON"
	// (Altdaten), 0 bedeutet "User hat explizit Montag gewaehlt". Migration
	// darf nur nil-Faelle auf Freitag-Default setzen.
	if p.Weekday == nil && p.Schedule == "weekly" {
		p.Weekday = &four
	}
	// Issue #764: Legacy-Presets ohne forecast_hours-Feld -> Go-Zero-Value 0
	// -> Default 48. 0 ist kein gueltiger Horizont; 24/48/72 sind gueltig.
	if p.ForecastHours == 0 {
		p.ForecastHours = 48
	}
	migrateComparePresetSlots(p)
	// Issue #1244 F002: Read-Path-Coercion symmetrisch zu SaveComparePreset —
	// sonst liefert GET auf eine unmigrierte Legacy-Datei weiterhin
	// "corridors":null.
	NormalizeComparePreset(p)
}

// LoadComparePresets liest seit Issue #1250 Scheibe 7b (ADR-0023, KL-8) NICHT
// mehr compare_presets.json, sondern globt briefings/*.json und filtert INVERS
// auf kind=="vergleich" (route/leer bleibt ausgeschlossen — Trip beansprucht
// kind==""/"route", AC-31). Spiegelt LoadTrips (trip.go), nur der kind-Filter
// ist invertiert (dort wird kind=="vergleich" uebersprungen).
func (s *Store) LoadComparePresets() ([]model.ComparePreset, error) {
	dir := s.briefingsDir()

	entries, err := os.ReadDir(dir)
	if err != nil {
		return []model.ComparePreset{}, nil
	}

	var presets []model.ComparePreset
	for _, entry := range entries {
		if entry.IsDir() || !strings.HasSuffix(entry.Name(), ".json") {
			continue
		}

		data, err := os.ReadFile(filepath.Join(dir, entry.Name()))
		if err != nil {
			log.Printf("skip %s: read error: %v", entry.Name(), err)
			continue
		}

		var p model.ComparePreset
		if err := json.Unmarshal(data, &p); err != nil {
			log.Printf("skip %s: json error: %v", entry.Name(), err)
			continue
		}
		if p.Kind != "vergleich" {
			continue // route/leer -> Trip, kein Preset (AC-31)
		}

		normalizeLoadedComparePreset(&p)
		// Issue #1280 (Tech-Lead-Entscheidung, Adversary-Nachtrag): Read-Heilung
		// zentralisiert HIER im Load-Pfad — jeder Aufrufer, der ein ueber
		// LoadComparePresets geladenes Preset encodiert, bekommt automatisch
		// geheilte Zeiten. NIEMALS LetzterVersand/TopOrtLetzterVersand (#1268).
		HealComparePresetSlotTimes(&p)
		presets = append(presets, p)
	}

	// os.ReadDir liefert Eintraege lexikalisch nach Dateiname (== ID) sortiert
	// -> deterministische Reihenfolge ohne separaten Sort.
	if presets == nil {
		presets = []model.ComparePreset{}
	}
	return presets, nil
}

// LoadComparePreset liest ein einzelnes briefings/<id>.json und liefert es nur,
// wenn kind=="vergleich" (sonst nil,nil — eine route/leer-Datei ist ein Trip,
// kein Preset). Spiegelt LoadTrip (trip.go) mit invertiertem kind-Guard
// (Issue #1250 Scheibe 7b, AC-31).
func (s *Store) LoadComparePreset(id string) (*model.ComparePreset, error) {
	path := filepath.Join(s.briefingsDir(), id+".json")

	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, err
	}

	var p model.ComparePreset
	if err := json.Unmarshal(data, &p); err != nil {
		return nil, err
	}
	if p.Kind != "vergleich" {
		return nil, nil // route/leer -> Trip, kein Preset
	}

	normalizeLoadedComparePreset(&p)
	// Issue #1280 (Tech-Lead-Entscheidung, Adversary-Nachtrag): Read-Heilung
	// zentralisiert HIER im Load-Pfad (siehe LoadComparePresets fuer Rationale).
	HealComparePresetSlotTimes(&p)
	return &p, nil
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

// SaveComparePreset persistiert EIN Preset per-Datei nach briefings/<id>.json
// (Issue #1250 Scheibe 7b, ADR-0023). kind wird — analog SaveTrip fuer route —
// UNBEDINGT auf "vergleich" gesetzt (jeder Go-Schreibpfad ist per Definition
// eine vergleich-Entitaet), sonst wuerde LoadComparePresets die frisch
// geschriebene Datei durch den invers-kind-Filter wieder verwerfen. Die
// Alt-Datei compare_presets.json wird NICHT mehr angefasst (Rollback-
// Faehigkeit, AC-32). Kein Array. Spiegelt SaveTrip (trip.go).
func (s *Store) SaveComparePreset(p model.ComparePreset) error {
	dir := s.briefingsDir()
	if err := os.MkdirAll(dir, 0755); err != nil {
		return err
	}

	p.Kind = "vergleich"
	// Issue #1244 F001: einzige Normalisierungsquelle (Corridors/LocationIDs/
	// Empfaenger) — pro Preset nie als "null" persistieren.
	NormalizeComparePreset(&p)

	data, err := json.MarshalIndent(p, "", "  ")
	if err != nil {
		return err
	}
	return writeFileLogged(filepath.Join(dir, p.ID+".json"), data)
}

// SaveComparePresets bleibt als DUENNER Kompat-Wrapper fuer die vielen
// Bestands-Array-Aufrufer (Handler-Schreibpfade + ~40 Test-Call-Sites): es
// schreibt jedes Preset per SaveComparePreset in seine eigene briefings/-Datei
// und LOESCHT NICHTS (Issue #1250 Scheibe 7b). Ein entferntes Preset wird NIE
// ueber diesen Wrapper geloescht — DELETE laeuft ausschliesslich ueber
// DeleteComparePreset (echtes os.Remove, F-A).
func (s *Store) SaveComparePresets(presets []model.ComparePreset) error {
	for i := range presets {
		if err := s.SaveComparePreset(presets[i]); err != nil {
			return err
		}
	}
	return nil
}

// DeleteComparePreset entfernt briefings/<id>.json TATSAECHLICH (echtes
// os.Remove, F-A) — nicht nur ein Array-Filtern, das die Datei auf der Platte
// liegen liesse (Wiederauferstehen beim naechsten Load). Spiegelt DeleteTrip
// mit invertiertem kind-Guard: eine kind!="vergleich"-Datei (route/leer = Trip)
// darf ueber diesen Pfad NIE geloescht werden, auch wenn ihre ID zufaellig mit
// der angefragten Preset-ID kollidiert (Issue #1250 Scheibe 7b, AC-33). Eine
// nicht als JSON lesbare Datei (Datenmuell) faellt fail-open durch zum Remove.
// Nicht existierende Datei ist kein Fehler (idempotent).
func (s *Store) DeleteComparePreset(id string) error {
	path := filepath.Join(s.briefingsDir(), id+".json")

	if data, rerr := os.ReadFile(path); rerr == nil {
		var probe struct {
			Kind string `json:"kind"`
		}
		if json.Unmarshal(data, &probe) == nil && probe.Kind != "vergleich" {
			return nil // route/leer -> Trip, ueber Preset-Delete unantastbar
		}
	}

	err := os.Remove(path)
	if os.IsNotExist(err) {
		return nil
	}
	return err
}
