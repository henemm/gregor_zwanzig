package store

// TDD (inline): Issue #1258 Scheibe S1 — Go-Batch-Migration
// MigrateAllOfficialWarnings, Vorbild migrate_1257.go / Python-Pendant
// scripts/migrate_1258_official_warnings.py.
//
// Spec: docs/specs/modules/issue_1258_alarme_tab_official_warnings.md
// „Implementation Details" Nr. 2 (Migration) + AC-1..AC-3.

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	"github.com/henemm/gregor-api/internal/model"
)

func writeRawTripJSON1258(t *testing.T, tmpDir, userID, tripID, rawJSON string) {
	t.Helper()
	tripsDir := filepath.Join(tmpDir, "users", userID, "trips")
	if err := os.MkdirAll(tripsDir, 0755); err != nil {
		t.Fatalf("MkdirAll: %v", err)
	}
	if err := os.WriteFile(filepath.Join(tripsDir, tripID+".json"), []byte(rawJSON), 0644); err != nil {
		t.Fatalf("WriteFile: %v", err)
	}
}

func readTripRaw(t *testing.T, tmpDir, userID, tripID string) map[string]interface{} {
	t.Helper()
	raw, err := os.ReadFile(filepath.Join(tmpDir, "users", userID, "trips", tripID+".json"))
	if err != nil {
		t.Fatalf("ReadFile: %v", err)
	}
	var m map[string]interface{}
	if err := json.Unmarshal(raw, &m); err != nil {
		t.Fatalf("Unmarshal: %v", err)
	}
	return m
}

// AC-1: Trip ohne official_alert_triggers_enabled (fehlend) -> official_warnings.enabled=true.
func TestMigrateAllOfficialWarnings_UnsetLegacyMigratesToEnabledTrue(t *testing.T) {
	tmpDir := t.TempDir()
	writeRawTripJSON1258(t, tmpDir, "user1", "trip-ac1-unset", `{
		"id": "trip-ac1-unset", "name": "Unset", "stages": []
	}`)

	migrated, err := MigrateAllOfficialWarnings(tmpDir)
	if err != nil {
		t.Fatalf("MigrateAllOfficialWarnings: %v", err)
	}
	if migrated < 1 {
		t.Fatalf("expected at least 1 migrated, got %d", migrated)
	}

	raw := readTripRaw(t, tmpDir, "user1", "trip-ac1-unset")
	ow, ok := raw["official_warnings"].(map[string]interface{})
	if !ok || ow["enabled"] != true {
		t.Fatalf("expected official_warnings.enabled=true, got %v", raw["official_warnings"])
	}
	if _, hasLegacy := raw["official_alert_triggers_enabled"]; hasLegacy {
		t.Errorf("legacy field must NOT be added where it was absent, got %v", raw["official_alert_triggers_enabled"])
	}
}

// AC-2: Trip mit official_alert_triggers_enabled=false -> official_warnings.enabled=false,
// Legacy-Feld bleibt unveraendert erhalten.
func TestMigrateAllOfficialWarnings_FalseLegacyMigratesToEnabledFalse(t *testing.T) {
	tmpDir := t.TempDir()
	writeRawTripJSON1258(t, tmpDir, "user1", "trip-ac2-false", `{
		"id": "trip-ac2-false", "name": "False", "stages": [],
		"official_alert_triggers_enabled": false
	}`)

	if _, err := MigrateAllOfficialWarnings(tmpDir); err != nil {
		t.Fatalf("MigrateAllOfficialWarnings: %v", err)
	}

	raw := readTripRaw(t, tmpDir, "user1", "trip-ac2-false")
	ow, ok := raw["official_warnings"].(map[string]interface{})
	if !ok || ow["enabled"] != false {
		t.Fatalf("expected official_warnings.enabled=false, got %v", raw["official_warnings"])
	}
	if raw["official_alert_triggers_enabled"] != false {
		t.Errorf("expected legacy field preserved as false, got %v", raw["official_alert_triggers_enabled"])
	}
}

// AC-3: zweiter Lauf ist idempotent — ein bereits migrierter (und danach
// manuell veraenderter) Trip/Preset wird NICHT ueberschrieben.
func TestMigrateAllOfficialWarnings_SecondRunIsIdempotent(t *testing.T) {
	tmpDir := t.TempDir()
	writeRawTripJSON1258(t, tmpDir, "user1", "trip-ac3", `{
		"id": "trip-ac3", "name": "Idempotent", "stages": [],
		"official_alert_triggers_enabled": true
	}`)

	if _, err := MigrateAllOfficialWarnings(tmpDir); err != nil {
		t.Fatalf("MigrateAllOfficialWarnings run 1: %v", err)
	}
	raw1 := readTripRaw(t, tmpDir, "user1", "trip-ac3")
	if ow, _ := raw1["official_warnings"].(map[string]interface{}); ow["enabled"] != true {
		t.Fatalf("expected enabled=true after run 1, got %v", raw1["official_warnings"])
	}

	// Simuliert eine nachtraegliche manuelle Aenderung via UI/API.
	s := New(tmpDir, "user1")
	trip, err := s.LoadTrip("trip-ac3")
	if err != nil || trip == nil {
		t.Fatalf("LoadTrip: %v", err)
	}
	trip.OfficialWarnings = &model.OfficialWarningsConfig{Enabled: false}
	if err := s.SaveTrip(trip); err != nil {
		t.Fatalf("SaveTrip: %v", err)
	}

	if _, err := MigrateAllOfficialWarnings(tmpDir); err != nil {
		t.Fatalf("MigrateAllOfficialWarnings run 2: %v", err)
	}
	raw2 := readTripRaw(t, tmpDir, "user1", "trip-ac3")
	ow2, _ := raw2["official_warnings"].(map[string]interface{})
	if ow2["enabled"] != false {
		t.Fatalf("second run must NOT overwrite a manually changed official_warnings, expected enabled=false, got %v", raw2["official_warnings"])
	}
}

// AC-3 (ComparePreset-Analogon): dieselbe Idempotenz gilt fuer Presets.
func TestMigrateAllOfficialWarnings_ComparePresetIdempotent(t *testing.T) {
	tmpDir := t.TempDir()
	writeComparePresetsJSON(t, tmpDir, "user1", `[{
		"id": "cp-ac3", "name": "Preset", "user_id": "user1",
		"location_ids": ["loc-a"], "schedule": "manual",
		"empfaenger": ["a@example.com"],
		"official_alert_triggers_enabled": false
	}]`)

	if _, err := MigrateAllOfficialWarnings(tmpDir); err != nil {
		t.Fatalf("MigrateAllOfficialWarnings run 1: %v", err)
	}
	s := New(tmpDir, "user1")
	presets1, err := s.LoadComparePresets()
	if err != nil || len(presets1) != 1 {
		t.Fatalf("LoadComparePresets run 1: %v, len=%d", err, len(presets1))
	}
	if presets1[0].OfficialWarnings == nil || presets1[0].OfficialWarnings.Enabled != false {
		t.Fatalf("expected enabled=false after run 1, got %+v", presets1[0].OfficialWarnings)
	}

	if _, err := MigrateAllOfficialWarnings(tmpDir); err != nil {
		t.Fatalf("MigrateAllOfficialWarnings run 2: %v", err)
	}
	presets2, err := s.LoadComparePresets()
	if err != nil || len(presets2) != 1 {
		t.Fatalf("LoadComparePresets run 2: %v, len=%d", err, len(presets2))
	}
	if presets2[0].OfficialWarnings == nil || presets2[0].OfficialWarnings.Enabled != false {
		t.Fatalf("second run must not change already-migrated preset, got %+v", presets2[0].OfficialWarnings)
	}
}

// Fix-Loop F003: ein Trip mit `"official_warnings": {}` (kein "enabled"-
// Schluessel — Datenmuell/abgebrochene Migration) muss weiterhin als
// UNMIGRIERT gelten (nicht "!= nil" -> "bereits migriert"/fail closed), sonst
// bleibt Enabled dauerhaft am Go-Zero-Value `false` haengen statt der
// Formel zu folgen.
func TestMigrateAllOfficialWarnings_EmptyObjectTreatedAsUnmigrated(t *testing.T) {
	tmpDir := t.TempDir()
	writeRawTripJSON1258(t, tmpDir, "user1", "trip-f003-empty", `{
		"id": "trip-f003-empty", "name": "Empty", "stages": [],
		"official_alert_triggers_enabled": true,
		"official_warnings": {}
	}`)

	migrated, err := MigrateAllOfficialWarnings(tmpDir)
	if err != nil {
		t.Fatalf("MigrateAllOfficialWarnings: %v", err)
	}
	if migrated < 1 {
		t.Fatalf("expected the {} trip to be (re-)migrated, got migrated=%d", migrated)
	}

	raw := readTripRaw(t, tmpDir, "user1", "trip-f003-empty")
	ow, ok := raw["official_warnings"].(map[string]interface{})
	if !ok || ow["enabled"] != true {
		t.Fatalf("F003: expected official_warnings.enabled=true (formula from legacy=true), got %v", raw["official_warnings"])
	}
}

// Fix-Loop F003 (ComparePreset-Analogon).
func TestMigrateAllOfficialWarnings_ComparePresetEmptyObjectTreatedAsUnmigrated(t *testing.T) {
	tmpDir := t.TempDir()
	writeComparePresetsJSON(t, tmpDir, "user1", `[{
		"id": "cp-f003-empty", "name": "Preset", "user_id": "user1",
		"location_ids": ["loc-a"], "schedule": "manual",
		"empfaenger": ["a@example.com"],
		"official_alert_triggers_enabled": false,
		"official_warnings": {}
	}]`)

	migrated, err := MigrateAllOfficialWarnings(tmpDir)
	if err != nil {
		t.Fatalf("MigrateAllOfficialWarnings: %v", err)
	}
	if migrated < 1 {
		t.Fatalf("expected the {} preset to be (re-)migrated, got migrated=%d", migrated)
	}

	s := New(tmpDir, "user1")
	presets, err := s.LoadComparePresets()
	if err != nil || len(presets) != 1 {
		t.Fatalf("LoadComparePresets: %v, len=%d", err, len(presets))
	}
	if presets[0].OfficialWarnings == nil || presets[0].OfficialWarnings.Enabled != false {
		t.Fatalf("F003: expected official_warnings.enabled=false (formula from legacy=false), got %+v", presets[0].OfficialWarnings)
	}
}
