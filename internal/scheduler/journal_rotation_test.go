package scheduler

// Issue #2883 AC-9: Rotation GENAU zwischen dem Oeffnen der aktuellen Datei und
// dem Oeffnen von .1, ueber die gemeinsame Test-Naht journalBetweenOpens des
// Helfers openJournalGenerations (internal/scheduler/journal_rotation.go).
// Die aktuelle Datei wird ZUERST geoeffnet; sie wird zu .1, per os.SameFile
// erkannt und genau einmal gelesen. Echte Dateien, echte Umbenennung.

import (
	"os"
	"path/filepath"
	"testing"
	"time"
)

func rotateBetweenOpens2883(t *testing.T, cur, newBody string) *bool {
	t.Helper()
	rotated := false
	journalBetweenOpens = func() {
		if rotated {
			return // nur die erste Oeffnung rotiert
		}
		rotated = true
		if err := os.Rename(cur, cur+".1"); err != nil {
			t.Errorf("rotate: %v", err)
			return
		}
		if err := os.WriteFile(cur, []byte(newBody), 0644); err != nil {
			t.Errorf("write new current: %v", err)
		}
	}
	t.Cleanup(func() { journalBetweenOpens = nil })
	return &rotated
}

func TestEnrichmentHealth2883_RotationZwischenDenOeffnungen(t *testing.T) {
	base := time.Date(2026, 11, 1, 8, 0, 0, 0, time.UTC)
	dir := t.TempDir()
	sched := newEnrichmentHealthTestScheduler(t, dir)
	writeEnrichmentJournal(t, dir,
		enrichmentLine(base, "thunder", "ok", ""),
		enrichmentLine(base.Add(time.Hour), "radar_nowcast", "fallback", "eu_direct"))
	cur := filepath.Join(dir, "diagnostics", "enrichment_calls.jsonl")
	rotated := rotateBetweenOpens2883(t, cur,
		enrichmentLine(base.Add(2*time.Hour), "thunder", "unavailable", "")+"\n")

	h := sched.EnrichmentHealth()
	if !*rotated {
		t.Fatalf("Test-Naht journalBetweenOpens wurde nicht zwischen den Oeffnungen gerufen")
	}
	if _, exists := h["journal_read_error"]; exists {
		t.Errorf("journal_read_error darf nicht gesetzt sein: %v", h["journal_read_error"])
	}
	if got := enrichmentEntry(t, h, "thunder")["last_success_at"]; got != base.Format(time.RFC3339) {
		t.Errorf("Erfolg aus der zuerst geoeffneten Datei muss erhalten bleiben, got %v", got)
	}
	if got := enrichmentEntry(t, h, "radar_nowcast")["last_fallback_detail"]; got != "eu_direct" {
		t.Errorf("radar_nowcast aus der zuerst geoeffneten Datei fehlt, got %v", got)
	}
}

func TestBriefingHealth2883_RotationZwischenDenOeffnungenKeinDoppelzaehlen(t *testing.T) {
	now := time.Now().UTC().Truncate(time.Second)
	dir := t.TempDir()
	writeDiagnosticsLog(t, dir,
		omLine(now.Add(-3*time.Hour), "briefing", 503),
		omLine(now.Add(-2*time.Hour), "briefing", 503))
	cur := filepath.Join(dir, "diagnostics", "openmeteo_calls.jsonl")
	rotated := rotateBetweenOpens2883(t, cur, omLine(now.Add(-time.Hour), "briefing", 200)+"\n")

	_, count := analyzeBriefingProviderErrors(dir, now)
	if !*rotated {
		t.Fatalf("Test-Naht journalBetweenOpens wurde nicht zwischen den Oeffnungen gerufen")
	}
	if count != 2 {
		t.Errorf("provider_errors_recent_count: want 2 (rotierte Datei genau einmal gelesen), got %d", count)
	}
}
