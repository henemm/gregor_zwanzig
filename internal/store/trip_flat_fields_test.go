package store

// Issue #1250 Scheibe 4 (Trip-Konvergenz): additive flache Slot-/Kanal-Felder
// werden bei jedem Load aus report_config abgeleitet (Dual-Read), EndDate aus
// max(stage.date). report_config bleibt die einzige Wahrheit fuer den Versand
// -- die Ableitung darf sie NICHT veraendern.
//
// Spec: docs/specs/modules/issue_1250_briefing_subscription.md, AC-13/AC-14.
// Keine Mocks -- echter Filesystem-Roundtrip via t.TempDir().

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	"github.com/henemm/gregor-api/internal/model"
)

func TestLoadTrip_DerivesFlatSlotChannelFieldsFromReportConfig(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "test")

	trip := model.Trip{
		ID:   "flat-fields-trip",
		Name: "Flat Fields Trip",
		Stages: []model.Stage{
			{ID: "S1", Name: "Etappe 1", Date: "2026-07-10"},
			{ID: "S3", Name: "Etappe 3 (letztes Datum)", Date: "2026-07-12"},
			{ID: "S2", Name: "Etappe 2 (unsortiert)", Date: "2026-07-11"},
		},
		ReportConfig: map[string]interface{}{
			"trip_id":       "flat-fields-trip",
			"enabled":       true,
			"morning_time":  "07:30:00",
			"evening_time":  "18:15:00",
			"send_email":    true,
			"send_sms":      true,
			"send_telegram": false,
		},
	}

	if err := s.SaveTrip(&trip); err != nil {
		t.Fatalf("SaveTrip failed: %v", err)
	}

	loaded, err := s.LoadTrip("flat-fields-trip")
	if err != nil {
		t.Fatalf("LoadTrip failed: %v", err)
	}
	if loaded == nil {
		t.Fatal("expected trip, got nil")
	}

	// Issue #1280: Read-Heilung kappt die abgeleiteten Flach-Felder beim Laden
	// auf die volle Stunde (07:30 -> 07:00, 18:15 -> 18:00) — die Ableitung aus
	// report_config selbst (Dual-Read) bleibt unveraendert, nur der
	// Minutenanteil wird an die stundengenaue Sende-Realitaet angeglichen.
	if loaded.MorningTime == nil || *loaded.MorningTime != "07:00:00" {
		t.Errorf("MorningTime = %v, want 07:00:00 (07:30 truncated)", loaded.MorningTime)
	}
	if loaded.EveningTime == nil || *loaded.EveningTime != "18:00:00" {
		t.Errorf("EveningTime = %v, want 18:00:00 (18:15 truncated)", loaded.EveningTime)
	}
	if loaded.SendSms == nil || *loaded.SendSms != true {
		t.Errorf("SendSms = %v, want true", loaded.SendSms)
	}
	if loaded.SendTelegram == nil || *loaded.SendTelegram != false {
		t.Errorf("SendTelegram = %v, want false", loaded.SendTelegram)
	}
	if loaded.MorningEnabled == nil || *loaded.MorningEnabled != true {
		t.Errorf("MorningEnabled = %v, want true (aus report_config.enabled)", loaded.MorningEnabled)
	}
	if loaded.EveningEnabled == nil || *loaded.EveningEnabled != true {
		t.Errorf("EveningEnabled = %v, want true (aus report_config.enabled)", loaded.EveningEnabled)
	}

	// AC-14: EndDate == max(stage.date) trotz unsortiert einliefernder Stages.
	if loaded.EndDate == nil || *loaded.EndDate != "2026-07-12" {
		t.Errorf("EndDate = %v, want 2026-07-12", loaded.EndDate)
	}

	// AC-13: report_config bleibt unveraendert (byte-identisch auf Disk).
	written, err := os.ReadFile(filepath.Join(tmpDir, "users", "test", "briefings", "flat-fields-trip.json"))
	if err != nil {
		t.Fatalf("read written: %v", err)
	}
	var onDisk map[string]interface{}
	if err := json.Unmarshal(written, &onDisk); err != nil {
		t.Fatalf("unmarshal written: %v", err)
	}
	rc, ok := onDisk["report_config"].(map[string]interface{})
	if !ok {
		t.Fatal("report_config fehlt oder falscher Typ im geschriebenen File")
	}
	if rc["morning_time"] != "07:30:00" || rc["send_sms"] != true || rc["send_telegram"] != false {
		t.Errorf("report_config wurde durch die Ableitung veraendert: %v", rc)
	}
}

func TestLoadTrip_NoReportConfigLeavesFlatFieldsNil(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "test")

	trip := model.Trip{
		ID:   "no-report-config-trip",
		Name: "No ReportConfig Trip",
		// ReportConfig absichtlich nicht gesetzt -> nil.
	}

	if err := s.SaveTrip(&trip); err != nil {
		t.Fatalf("SaveTrip failed: %v", err)
	}

	loaded, err := s.LoadTrip("no-report-config-trip")
	if err != nil {
		t.Fatalf("LoadTrip failed: %v", err)
	}
	if loaded == nil {
		t.Fatal("expected trip, got nil")
	}
	if loaded.MorningTime != nil {
		t.Errorf("MorningTime = %v, want nil (kein report_config)", *loaded.MorningTime)
	}
	if loaded.MorningEnabled != nil {
		t.Errorf("MorningEnabled = %v, want nil (kein report_config)", *loaded.MorningEnabled)
	}
	// Keine Stages -> EndDate bleibt nil.
	if loaded.EndDate != nil {
		t.Errorf("EndDate = %v, want nil (keine Stages)", *loaded.EndDate)
	}
}

// TestLoadTrip_EndDateNotStaleWhenStagesClearedToEmpty — Adversary-Fix-Loop
// F001 (BROKEN-Verdict): deriveFlatFields SETZTE die abgeleiteten Felder
// vormals nur, LOESCHTE sie nie -- ein Trip, dem ueber den Editor alle Stages
// entzogen werden (leere Stages sind erlaubt), behielt ein STALES EndDate
// (und stale flache Slot-/Kanal-Felder) sowohl in-memory als auch nach dem
// naechsten Reload von Platte. Reproduziert den befuellt->leer-Uebergang.
func TestLoadTrip_EndDateNotStaleWhenStagesClearedToEmpty(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "test")

	trip := model.Trip{
		ID:   "stale-end-date-trip",
		Name: "Stale EndDate Trip",
		Stages: []model.Stage{
			{ID: "S1", Name: "Etappe 1", Date: "2026-07-10"},
			{ID: "S2", Name: "Etappe 2", Date: "2026-07-12"},
		},
		ReportConfig: map[string]interface{}{
			"trip_id":       "stale-end-date-trip",
			"enabled":       true,
			"morning_time":  "07:30:00",
			"evening_time":  "18:15:00",
			"send_email":    true,
			"send_sms":      true,
			"send_telegram": false,
		},
	}
	if err := s.SaveTrip(&trip); err != nil {
		t.Fatalf("SaveTrip (befuellt) failed: %v", err)
	}

	loaded, err := s.LoadTrip("stale-end-date-trip")
	if err != nil {
		t.Fatalf("LoadTrip (befuellt) failed: %v", err)
	}
	if loaded == nil || loaded.EndDate == nil || *loaded.EndDate != "2026-07-12" {
		t.Fatalf("Sanity: EndDate nach befuelltem Save/Load = %v, want 2026-07-12", loaded)
	}

	// Stages UND ReportConfig entziehen (Quelle verschwindet) -> speichern.
	loaded.Stages = []model.Stage{}
	loaded.ReportConfig = nil
	if err := s.SaveTrip(loaded); err != nil {
		t.Fatalf("SaveTrip (geleert) failed: %v", err)
	}

	// In-memory: derselbe Pointer, muss nach diesem SaveTrip bereits nil sein.
	if loaded.EndDate != nil {
		t.Errorf("In-memory EndDate nach Leeren = %v, want nil (stale!)", *loaded.EndDate)
	}
	if loaded.MorningTime != nil {
		t.Errorf("In-memory MorningTime nach Leeren = %v, want nil (stale!)", *loaded.MorningTime)
	}

	// Reload von Platte: darf NICHT den alten Wert konservieren.
	reloaded, err := s.LoadTrip("stale-end-date-trip")
	if err != nil {
		t.Fatalf("LoadTrip (geleert) failed: %v", err)
	}
	if reloaded == nil {
		t.Fatal("expected trip, got nil")
	}
	if reloaded.EndDate != nil {
		t.Errorf("EndDate nach Reload = %v, want nil (stale von Platte gelesen!)", *reloaded.EndDate)
	}
	if reloaded.MorningTime != nil {
		t.Errorf("MorningTime nach Reload = %v, want nil (stale von Platte gelesen!)", *reloaded.MorningTime)
	}
	if reloaded.SendSms != nil {
		t.Errorf("SendSms nach Reload = %v, want nil (stale von Platte gelesen!)", *reloaded.SendSms)
	}
}
