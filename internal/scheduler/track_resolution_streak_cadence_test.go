package scheduler

// Issue #2218 Scheibe C, Eintrag C5-47 (AC-20, Go-Seite).
//
// Spec: docs/specs/modules/fix_2218_scheibe_c_observability.md
//
// Der Python-Schreiber daempft "implausible_measurement" auf hoechstens eine
// Zeile je Etappe und 12 h. Dieser Test haelt die Gegenseite fest: eine
// Zeilenfolge im 12-h-Abstand, 72 h lang, laesst den Streak
// (track_resolution_failure_streak_since) NICHT abreissen — die Luecken-
// Schwelle (26 h) liegt klar ueber dem Schreibertakt. Waechter gegen eine
// kuenftige Verkuerzung der Schwelle oder eine Verlaengerung des Takts.
//
// Heute schon gruen (die Leseseite aendert sich nicht) — bewusste Schutzprobe,
// kein RED-Kandidat. Echte Journaldatei im tmp-Verzeichnis, keine Mocks.

import (
	"testing"
	"time"
)

func TestTrackResolutionStreak_SurvivesTwelveHourWriterCadenceOver72h(t *testing.T) {
	tmpDir := t.TempDir()
	now := time.Now().UTC().Truncate(time.Second)

	// Zeilen bei now-72h, -60h, ..., -12h und -0h-5min (7 Zeilen, Takt 12 h).
	var lines []string
	first := now.Add(-72 * time.Hour)
	for i := 0; i <= 5; i++ {
		lines = append(lines, trackResolutionFailureLine(
			first.Add(time.Duration(i)*12*time.Hour), "trip-a", "T1", "implausible_measurement"))
	}
	lines = append(lines, trackResolutionFailureLine(
		now.Add(-5*time.Minute), "trip-a", "T1", "implausible_measurement"))
	writeTrackResolutionJournal(t, tmpDir, "tdd-2218c-streak", lines...)

	since, _ := analyzeTrackResolutionFailures(tmpDir, now)

	if want := first.Format(time.RFC3339); since != want {
		t.Errorf("streakSince: want %s (Streak reisst bei 12-h-Takt nicht ab), got %q", want, since)
	}
}
