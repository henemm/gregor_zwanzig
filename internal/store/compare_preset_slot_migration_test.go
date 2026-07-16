package store

// TDD (inline): Issue #1232 Scheibe 2a — ComparePreset-Zeitplan-Reshape,
// LoadComparePresets-Slot-Migration.
//
// Spec: docs/specs/modules/compare_preset_zeitplan.md §Implementation Details Pkt. 2
//
// Prüft: Bestandsdaten ohne die 5 Slot-Felder (Marker: morning_time fehlt)
// bekommen beim Laden via LoadComparePresets() die Migrations-Fallback-Werte
// aus der Spec-Tabelle; bereits migrierte Presets (morning_time gesetzt)
// werden nicht erneut angefasst (Idempotenz), auch ein explizites
// morning_enabled=false bleibt erhalten.

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

// writeComparePresetsJSON legt die als JSON-Array uebergebene Preset-Fixture
// aus (geteilte Test-Helper-Quelle im store-Paket). Seit Issue #1250 Scheibe 7b
// liest LoadComparePresets briefings/<id>.json (kind="vergleich") statt
// compare_presets.json — die Array-Fixture wird deshalb pro Element als eigene
// kind-getaggte Datei geschrieben (analog writeRawTripJSON1258 aus S7a).
func writeComparePresetsJSON(t *testing.T, tmpDir, userID, rawJSON string) {
	t.Helper()
	briefingsDir := filepath.Join(tmpDir, "users", userID, "briefings")
	if err := os.MkdirAll(briefingsDir, 0755); err != nil {
		t.Fatalf("MkdirAll: %v", err)
	}
	var arr []map[string]interface{}
	if err := json.Unmarshal([]byte(rawJSON), &arr); err != nil {
		t.Fatalf("Unmarshal fixture array: %v", err)
	}
	for _, elem := range arr {
		if _, ok := elem["kind"]; !ok {
			elem["kind"] = "vergleich"
		}
		id, _ := elem["id"].(string)
		if id == "" {
			t.Fatalf("fixture element missing id: %v", elem)
		}
		data, err := json.Marshal(elem)
		if err != nil {
			t.Fatalf("Marshal fixture element: %v", err)
		}
		if err := os.WriteFile(filepath.Join(briefingsDir, id+".json"), data, 0644); err != nil {
			t.Fatalf("WriteFile: %v", err)
		}
	}
}

// AC-3 / KL-6: Alt-Preset ohne Slot-Felder mit schedule="daily" → Morgen-Slot
// aktiv @06:00, Abend-Slot inaktiv @18:00 (verhaltensidentisch zum bisherigen
// 06:00-Cron), end_date bleibt nil.
func TestLoadComparePresets_LegacyPresetGetsMorningSlotDefaults(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "user1")

	rawJSON := `[{
		"id": "cp-legacy",
		"name": "Legacy Daily Preset",
		"user_id": "user1",
		"location_ids": ["loc-a"],
		"schedule": "daily",
		"profil": "SUMMER_TREKKING",
		"hour_from": 9,
		"hour_to": 16,
		"empfaenger": ["test@example.com"],
		"created_at": "2026-01-01T00:00:00Z"
	}]`
	writeComparePresetsJSON(t, tmpDir, "user1", rawJSON)

	presets, err := s.LoadComparePresets()
	if err != nil {
		t.Fatalf("LoadComparePresets failed: %v", err)
	}
	if len(presets) != 1 {
		t.Fatalf("expected 1 preset, got %d", len(presets))
	}
	p := presets[0]
	if p.MorningEnabled == nil || !*p.MorningEnabled {
		t.Errorf("expected MorningEnabled=true, got %v", p.MorningEnabled)
	}
	if p.MorningTime == nil || *p.MorningTime != "06:00:00" {
		t.Errorf("expected MorningTime=06:00:00, got %v", p.MorningTime)
	}
	if p.EveningEnabled == nil || *p.EveningEnabled {
		t.Errorf("expected EveningEnabled=false, got %v", p.EveningEnabled)
	}
	if p.EveningTime == nil || *p.EveningTime != "18:00:00" {
		t.Errorf("expected EveningTime=18:00:00, got %v", p.EveningTime)
	}
	if p.EndDate != nil {
		t.Errorf("expected EndDate=nil, got %v", *p.EndDate)
	}
}

// KL-6: Alt-Preset ohne Slot-Felder mit schedule="daily_evening" →
// Abend-Slot aktiv @18:00, Morgen-Slot inaktiv @06:00 (Nutzer-Intention
// Abend, Migration behebt den Wertemengen-Mismatch).
func TestLoadComparePresets_LegacyDailyEveningGetsEveningSlotDefaults(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "user1")

	rawJSON := `[{
		"id": "cp-legacy-evening",
		"name": "Legacy Evening Preset",
		"user_id": "user1",
		"location_ids": ["loc-a"],
		"schedule": "daily_evening",
		"profil": "SUMMER_TREKKING",
		"hour_from": 9,
		"hour_to": 16,
		"empfaenger": ["test@example.com"],
		"created_at": "2026-01-01T00:00:00Z"
	}]`
	writeComparePresetsJSON(t, tmpDir, "user1", rawJSON)

	presets, err := s.LoadComparePresets()
	if err != nil {
		t.Fatalf("LoadComparePresets failed: %v", err)
	}
	p := presets[0]
	if p.MorningEnabled == nil || *p.MorningEnabled {
		t.Errorf("expected MorningEnabled=false, got %v", p.MorningEnabled)
	}
	if p.EveningEnabled == nil || !*p.EveningEnabled {
		t.Errorf("expected EveningEnabled=true, got %v", p.EveningEnabled)
	}
	if p.EveningTime == nil || *p.EveningTime != "18:00:00" {
		t.Errorf("expected EveningTime=18:00:00, got %v", p.EveningTime)
	}
}

// Idempotenz: ein bereits migriertes Preset mit explizitem
// morning_enabled=false wird NICHT erneut angefasst — die Migration darf
// diesen bewusst gesetzten Wert nicht überschreiben.
func TestLoadComparePresets_AlreadyMigratedPresetNotOverwritten(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "user1")

	rawJSON := `[{
		"id": "cp-migrated",
		"name": "Already Migrated",
		"user_id": "user1",
		"location_ids": ["loc-a"],
		"schedule": "daily",
		"profil": "SUMMER_TREKKING",
		"hour_from": 9,
		"hour_to": 16,
		"empfaenger": ["test@example.com"],
		"created_at": "2026-01-01T00:00:00Z",
		"morning_enabled": false,
		"morning_time": "09:30:00",
		"evening_enabled": true,
		"evening_time": "20:00:00",
		"end_date": "2026-12-31"
	}]`
	writeComparePresetsJSON(t, tmpDir, "user1", rawJSON)

	presets, err := s.LoadComparePresets()
	if err != nil {
		t.Fatalf("LoadComparePresets failed: %v", err)
	}
	p := presets[0]
	if p.MorningEnabled == nil || *p.MorningEnabled {
		t.Errorf("expected explicit MorningEnabled=false to survive re-load, got %v", p.MorningEnabled)
	}
	// Issue #1280: Read-Heilung kappt die krumme Bestandszeit (09:30) beim
	// Laden auf die volle Stunde (09:00) — das Feld selbst (morning_time
	// gesetzt statt Migrations-Default) bleibt unangetastet/idempotent, nur
	// der Minutenanteil wird an die stundengenaue Sende-Realitaet angeglichen.
	if p.MorningTime == nil || *p.MorningTime != "09:00:00" {
		t.Errorf("expected explicit MorningTime=09:30:00 truncated to 09:00:00 to survive re-load, got %v", p.MorningTime)
	}
	if p.EveningTime == nil || *p.EveningTime != "20:00:00" {
		t.Errorf("expected explicit EveningTime=20:00:00 to survive re-load, got %v", p.EveningTime)
	}
	if p.EndDate == nil || *p.EndDate != "2026-12-31" {
		t.Errorf("expected explicit EndDate=2026-12-31 to survive re-load, got %v", p.EndDate)
	}
}

// Schedule selbst bleibt beim Laden unverändert (nur die Pause-Semantik).
func TestLoadComparePresets_ScheduleFieldUnchangedAfterMigration(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "user1")

	rawJSON := `[{
		"id": "cp-manual",
		"name": "Manual Preset",
		"user_id": "user1",
		"location_ids": ["loc-a"],
		"schedule": "manual",
		"profil": "SUMMER_TREKKING",
		"hour_from": 9,
		"hour_to": 16,
		"empfaenger": ["test@example.com"],
		"created_at": "2026-01-01T00:00:00Z"
	}]`
	writeComparePresetsJSON(t, tmpDir, "user1", rawJSON)

	presets, err := s.LoadComparePresets()
	if err != nil {
		t.Fatalf("LoadComparePresets failed: %v", err)
	}
	if presets[0].Schedule != "manual" {
		t.Errorf("expected Schedule=manual unchanged, got %q", presets[0].Schedule)
	}
	// Manual-Preset bekommt trotzdem Slot-Fallback-Defaults (Pause-Guard lebt
	// im Dispatch, nicht in der Migration).
	if presets[0].MorningTime == nil || *presets[0].MorningTime != "06:00:00" {
		t.Errorf("expected MorningTime fallback default even for manual schedule, got %v", presets[0].MorningTime)
	}
}
