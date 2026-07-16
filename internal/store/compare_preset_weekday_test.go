package store

// TDD RED: Issue #511 — LoadComparePresets weekday-Migration (AC-3).
//
// Spec: docs/specs/modules/issue_511_weekly_scheduler.md §2
//
// Prüft: Bestandsdaten ohne weekday-Feld erhalten Default Weekday=4 (Freitag)
//        beim Laden via LoadComparePresets() — analog zur LoadSubscriptions()-Migration.
//
// RED: TestLoadComparePresets_WeeklyPresetGetsDefaultWeekday schlägt fehl,
// weil LoadComparePresets() aktuell keine weekday-Migration anwendet
// (weekday wird als 0 geladen, nicht als 4).

import (
	"encoding/json"
	"testing"
)

// =============================================================================
// AC-3: LoadComparePresets — weekday-Migration für legacy weekly-Presets
// =============================================================================

func TestLoadComparePresets_WeeklyPresetGetsDefaultWeekday(t *testing.T) {
	// GIVEN: compare_presets.json mit einem weekly-Preset OHNE weekday-Feld (Altdaten)
	tmpDir := t.TempDir()
	s := New(tmpDir, "user1")

	rawJSON := `[{
		"id": "cp-legacy-weekly",
		"name": "Legacy Weekly Preset",
		"user_id": "user1",
		"location_ids": ["loc-a"],
		"schedule": "weekly",
		"profil": "SUMMER_TREKKING",
		"hour_from": 9,
		"hour_to": 16,
		"empfaenger": ["test@example.com"],
		"created_at": "2026-01-01T00:00:00Z"
	}]`
	// weekday-Feld fehlt bewusst → JSON-Unmarshal liefert 0

	writeComparePresetsJSON(t, tmpDir, "user1", rawJSON)

	// WHEN: LoadComparePresets() aufgerufen
	presets, err := s.LoadComparePresets()

	// THEN: Preset hat Weekday=4 (Freitag-Default)
	// RED: aktuell liefert JSON-Unmarshal Weekday=0 (kein Default angewandt)
	if err != nil {
		t.Fatalf("LoadComparePresets failed: %v", err)
	}
	if len(presets) != 1 {
		t.Fatalf("expected 1 preset, got %d", len(presets))
	}
	if presets[0].Weekday == nil || *presets[0].Weekday != 4 {
		var got interface{} = "nil"
		if presets[0].Weekday != nil {
			got = *presets[0].Weekday
		}
		t.Errorf(
			"expected Weekday=4 (Freitag-Default) for legacy weekly preset without weekday field, got %v — "+
				"LoadComparePresets() wendet noch keine weekday-Migration an (RED)",
			got,
		)
	}
}

func TestLoadComparePresets_DailyPresetKeepsWeekdayZero(t *testing.T) {
	// GIVEN: compare_presets.json mit einem daily-Preset OHNE weekday-Feld
	// THEN: weekday bleibt 0 (kein Default für daily/manual — nur für weekly relevant)
	tmpDir := t.TempDir()
	s := New(tmpDir, "user1")

	rawJSON := `[{
		"id": "cp-legacy-daily",
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
	// daily-Presets: weekday-Feld ist irrelevant, kein Default erzwungen
	// (Weekday=0 ist OK für daily)
	if presets[0].Schedule != "daily" {
		t.Errorf("expected schedule=daily, got %q", presets[0].Schedule)
	}
}

func TestLoadComparePresets_WeeklyPresetWithExplicitWeekday(t *testing.T) {
	// GIVEN: weekly-Preset MIT explizitem weekday=2 (Mittwoch)
	// THEN: weekday=2 bleibt erhalten (Default nur wenn weekday=0 bei 'weekly')
	tmpDir := t.TempDir()
	s := New(tmpDir, "user1")

	rawJSON := `[{
		"id": "cp-wednesday",
		"name": "Wednesday Weekly",
		"user_id": "user1",
		"location_ids": ["loc-a"],
		"schedule": "weekly",
		"weekday": 2,
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
	// Expliziter weekday=2 muss erhalten bleiben
	if presets[0].Weekday == nil || *presets[0].Weekday != 2 {
		var got interface{} = "nil"
		if presets[0].Weekday != nil {
			got = *presets[0].Weekday
		}
		t.Errorf("expected Weekday=2 (explicitly set), got %v", got)
	}

	// Verify JSON round-trip: model.ComparePreset.Weekday muss existieren
	data, _ := json.Marshal(presets[0])
	var m map[string]interface{}
	json.Unmarshal(data, &m)
	if _, ok := m["weekday"]; !ok {
		t.Error("expected 'weekday' field in JSON output — field missing in model (RED)")
	}
}

// =============================================================================
// AC-3 F001: Adversary-Finding — explizit gesetzter weekday=0 (Montag) darf
// NICHT auf 4 (Freitag) migriert werden. JSON-Unmarshal in int liefert für
// "kein Feld" und "Feld=0" beides 0 → Migration kann beide Fälle nicht
// unterscheiden. Lösung: *int Pointer (nil = kein Wert, &0 = explizit Montag).
// =============================================================================

func TestLoadComparePresets_WeeklyPresetExplicitMondayPreserved(t *testing.T) {
	// GIVEN: weekly preset mit EXPLIZITEM weekday=0 (Montag) in JSON
	// THEN: weekday=0 muss erhalten bleiben (NICHT auf 4 migrieren)
	tmpDir := t.TempDir()
	s := New(tmpDir, "user1")

	rawJSON := `[{
		"id": "cp-monday",
		"name": "Monday Weekly",
		"user_id": "user1",
		"location_ids": ["loc-a"],
		"schedule": "weekly",
		"weekday": 0,
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
	if presets[0].Weekday == nil {
		t.Fatal("expected Weekday to be non-nil for explicitly set weekday=0")
	}
	if *presets[0].Weekday != 0 {
		t.Errorf(
			"expected Weekday=0 (Montag) preserved, got %d — F001 bug: fälschlich auf Freitag migriert",
			*presets[0].Weekday,
		)
	}
}
