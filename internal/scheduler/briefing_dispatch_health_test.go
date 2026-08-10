package scheduler

import (
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

// TDD — Issue #1629 AC-8: ein anhaltender Briefing-VERSANDfehler wird am
// Status-Endpunkt als mit der Ausfalldauer WACHSENDES Signal sichtbar.
//
// Spec: docs/specs/modules/fix_1629_briefing_anker_versandfehler.md (AC-8).
//
// Quelle ist die Diagnose-Spur, die der Python-Kern im except-Zweig des
// Versandaufrufs fail-soft schreibt (`record_briefing_dispatch_failure`,
// src/services/alert_briefing_anchor.py):
// users/<uid>/diagnostics/briefing_dispatch_failures.jsonl.
//
// KEINE Mocks: echte Dateien in t.TempDir(), echter httptest-Roundtrip gegen
// den realen Handler (Muster briefing_health_test.go).

// writeDispatchFailureJournal writes a real
// users/<uid>/diagnostics/briefing_dispatch_failures.jsonl with one line per
// given timestamp — exactly the shape the Python writer produces.
func writeDispatchFailureJournal(t *testing.T, tmpDir, userID string, times ...time.Time) {
	t.Helper()
	dir := filepath.Join(tmpDir, "users", userID, "diagnostics")
	if err := os.MkdirAll(dir, 0755); err != nil {
		t.Fatalf("mkdir diagnostics: %v", err)
	}
	var b strings.Builder
	for _, ts := range times {
		b.WriteString(`{"ts":"` + ts.Format(time.RFC3339Nano) +
			`","kind":"route","entity_id":"trip-1629","error":"[email] Versand blockiert"}` + "\n")
	}
	path := filepath.Join(dir, "briefing_dispatch_failures.jsonl")
	if err := os.WriteFile(path, []byte(b.String()), 0644); err != nil {
		t.Fatalf("write journal: %v", err)
	}
}

// AC-8 (Kern): der Startzeitpunkt der Serie bleibt der ERSTE Fehlschlag —
// weitere Fehlschläge verschieben ihn nicht nach vorne, das Signal wächst also
// mit der Ausfalldauer (ADR-0018 Punkt 3).
func TestAnalyzeBriefingDispatchErrorsStreakStartsAtFirstFailure(t *testing.T) {
	tmpDir := t.TempDir()
	now := time.Now().UTC()
	seriesStart := now.Add(-25 * time.Hour)

	writeDispatchFailureJournal(t, tmpDir, "tdd-1629-a",
		seriesStart, now.Add(-13*time.Hour), now.Add(-1*time.Hour))

	since, recent := analyzeBriefingDispatchErrors(tmpDir, now)
	if since == "" {
		t.Fatalf("streak_since fehlt — ein laufender Versandausfall muss einen Serienbeginn melden")
	}
	got, err := time.Parse(time.RFC3339, since)
	if err != nil {
		t.Fatalf("streak_since nicht als RFC3339 lesbar (%q): %v", since, err)
	}
	if !got.Equal(seriesStart.Truncate(time.Second)) {
		t.Errorf("streak_since: want %v (erster Fehlschlag der Serie), got %v",
			seriesStart.Truncate(time.Second), got)
	}
	if recent != 2 {
		t.Errorf("recent_count (letzte 24h): want 2, got %d", recent)
	}
}

// AC-8 (Lücken-Logik): ein weit zurückliegender Einzelfehler VOR einer großen
// Lücke gehört nicht zur laufenden Serie — streak_since bleibt am jüngeren
// Serienbeginn stehen.
func TestAnalyzeBriefingDispatchErrorsIgnoresFailureBeforeLargeGap(t *testing.T) {
	tmpDir := t.TempDir()
	now := time.Now().UTC()
	seriesStart := now.Add(-13 * time.Hour)

	writeDispatchFailureJournal(t, tmpDir, "tdd-1629-a",
		now.Add(-30*24*time.Hour), seriesStart, now.Add(-1*time.Hour))

	since, _ := analyzeBriefingDispatchErrors(tmpDir, now)
	got, err := time.Parse(time.RFC3339, since)
	if err != nil {
		t.Fatalf("streak_since nicht als RFC3339 lesbar (%q): %v", since, err)
	}
	if !got.Equal(seriesStart.Truncate(time.Second)) {
		t.Errorf("streak_since: want %v (Beginn der LAUFENDEN Serie), got %v",
			seriesStart.Truncate(time.Second), got)
	}
}

// AC-8 (Serienende): ein danach erfolgreicher Versand schreibt keine Zeile —
// die Serie endet dadurch über die Zeit-Lücke nach vorn, gemessen gegen "jetzt".
func TestAnalyzeBriefingDispatchErrorsStreakEndsAfterSuccessfulDispatch(t *testing.T) {
	tmpDir := t.TempDir()
	now := time.Now().UTC()

	writeDispatchFailureJournal(t, tmpDir, "tdd-1629-a",
		now.Add(-40*time.Hour), now.Add(-28*time.Hour))

	since, recent := analyzeBriefingDispatchErrors(tmpDir, now)
	if since != "" {
		t.Errorf("streak_since: want \"\" (Serie beendet, seither ging wieder etwas raus), got %q", since)
	}
	if recent != 0 {
		t.Errorf("recent_count: want 0 (kein Fehlschlag in den letzten 24h), got %d", recent)
	}
}

// Fail-soft + Mandanten-Aggregation: kaputte Zeilen werden übersprungen,
// mehrere Nutzer werden zusammengezählt, ein fehlendes Journal ist kein Fehler.
func TestAnalyzeBriefingDispatchErrorsAggregatesUsersFailSoft(t *testing.T) {
	tmpDir := t.TempDir()
	now := time.Now().UTC()

	writeDispatchFailureJournal(t, tmpDir, "tdd-1629-a", now.Add(-2*time.Hour))
	writeDispatchFailureJournal(t, tmpDir, "tdd-1629-b", now.Add(-3*time.Hour))
	// Nutzer C: kaputte Zeile + gültige Zeile in derselben Datei.
	dir := filepath.Join(tmpDir, "users", "tdd-1629-c", "diagnostics")
	if err := os.MkdirAll(dir, 0755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	body := "{kaputt\n" + `{"ts":"` + now.Add(-4*time.Hour).Format(time.RFC3339) + `"}` + "\n"
	if err := os.WriteFile(filepath.Join(dir, "briefing_dispatch_failures.jsonl"),
		[]byte(body), 0644); err != nil {
		t.Fatalf("write: %v", err)
	}

	_, recent := analyzeBriefingDispatchErrors(tmpDir, now)
	if recent != 3 {
		t.Errorf("recent_count über alle Nutzer: want 3, got %d", recent)
	}

	if since, recent := analyzeBriefingDispatchErrors(filepath.Join(tmpDir, "leer"), now); since != "" || recent != 0 {
		t.Errorf("fehlendes Journal muss (\"\", 0) liefern, got (%q, %d)", since, recent)
	}
}

// AC-8 (Wirkort): die beiden Felder hängen tatsächlich am ausgelieferten
// Status-Endpunkt — und tragen weiterhin keine Nutzer-/Trip-Kennung (#252).
func TestBriefingHealthExposesDispatchErrorFields(t *testing.T) {
	tmpDir := t.TempDir()
	sched := newBriefingHealthTestScheduler(t, tmpDir, "tdd-1629-usera")
	now := time.Now().UTC()
	writeDispatchFailureJournal(t, tmpDir, "tdd-1629-usera",
		now.Add(-13*time.Hour), now.Add(-1*time.Hour))

	code, body, raw := callStatusEndpoint(t, sched)
	if code != http.StatusOK {
		t.Fatalf("expected 200, got %d", code)
	}
	bh, ok := body["briefing_health"].(map[string]any)
	if !ok {
		t.Fatalf("briefing_health fehlt: %v", body["briefing_health"])
	}
	if got := bh["briefing_dispatch_errors_recent_count"]; got != float64(2) {
		t.Errorf("briefing_dispatch_errors_recent_count: want 2, got %v", got)
	}
	since, ok := bh["briefing_dispatch_error_streak_since"].(string)
	if !ok || since == "" {
		t.Fatalf("briefing_dispatch_error_streak_since fehlt oder ist leer: %v",
			bh["briefing_dispatch_error_streak_since"])
	}
	if strings.Contains(raw, "tdd-1629-usera") || strings.Contains(raw, "trip-1629") {
		t.Errorf("Datenschutz (#252): der Status-Endpunkt darf keine Nutzer-/Trip-Kennung tragen: %s", raw)
	}
}

// AC-8 (Grenzwert, Adversary-Finding F002): der Lücken-Schwellenwert ist
// GENAU 26h — der Wert, der dem PO als Abweichung von den 2h des
// Provider-Pfads vorgelegt und freigegeben wurde.
//
// Bewusst mit den LITERALEN Grenzen 25h/27h formuliert statt relativ zu
// `dispatchErrorStreakGapThreshold` (so wie die Provider-Grenztests): ein
// relativer Test wandert mit jeder Änderung der Konstante mit und nagelt
// deshalb gar nichts fest. Vorher bestand JEDER Wert im Bereich (12h, 28h]
// die Suite — eine Senkung auf 13h blieb unbemerkt und hätte den Serienbeginn
// eines täglichen Briefing-Rhythmus laufend nach vorne zurückgesetzt, das
// Signal also am Wachsen gehindert.
//
// Rückwärts-Richtung: die Lücke ZWISCHEN zwei Fehlschlägen.
func TestDispatchErrorStreakGapThresholdIsTwentySixHoursBackward(t *testing.T) {
	now := time.Date(2026, 8, 9, 12, 0, 0, 0, time.UTC)

	// 25h Lücke — noch innerhalb der Schwelle: die Serie beginnt beim ÄLTEREN
	// Fehlschlag. Bei einer zu niedrig gesetzten Schwelle (z.B. 13h) würde
	// hier stattdessen der jüngere Fehlschlag gemeldet.
	tmpDir := t.TempDir()
	aelter := now.Add(-26 * time.Hour)
	juenger := now.Add(-1 * time.Hour) // Lücke: 25h
	writeDispatchFailureJournal(t, tmpDir, "tdd-1629-grenze", aelter, juenger)

	since, _ := analyzeBriefingDispatchErrors(tmpDir, now)
	if want := aelter.Format(time.RFC3339); since != want {
		t.Errorf("Lücke 25h (<= 26h) muss die Serie zusammenhalten: streak_since want %q, got %q — Schwellenwert zu niedrig?",
			want, since)
	}

	// 27h Lücke — jenseits der Schwelle: der ältere Fehlschlag gehört nicht
	// mehr zur laufenden Serie. Bei einer zu hoch gesetzten Schwelle (z.B.
	// 48h) würde hier fälschlich der ältere Fehlschlag gemeldet.
	tmpDir2 := t.TempDir()
	aelter2 := now.Add(-28 * time.Hour)
	juenger2 := now.Add(-1 * time.Hour) // Lücke: 27h
	writeDispatchFailureJournal(t, tmpDir2, "tdd-1629-grenze", aelter2, juenger2)

	since2, _ := analyzeBriefingDispatchErrors(tmpDir2, now)
	if want := juenger2.Format(time.RFC3339); since2 != want {
		t.Errorf("Lücke 27h (> 26h) muss die Serie trennen: streak_since want %q (nur der jüngere Fehlschlag), got %q — Schwellenwert zu hoch?",
			want, since2)
	}
}

// AC-8 (Grenzwert, Adversary-Finding F002), Vorwärts-Richtung: die Lücke
// zwischen dem JÜNGSTEN Fehlschlag und "jetzt" entscheidet, ob die Serie noch
// läuft. Dieselben literalen Grenzen 25h/27h — auch dieser Vergleich benutzt
// `dispatchErrorStreakGapThreshold` und muss ihn deshalb mit festnageln.
func TestDispatchErrorStreakGapThresholdIsTwentySixHoursForward(t *testing.T) {
	now := time.Date(2026, 8, 9, 12, 0, 0, 0, time.UTC)

	tmpDir := t.TempDir()
	letzter := now.Add(-25 * time.Hour)
	writeDispatchFailureJournal(t, tmpDir, "tdd-1629-grenze", letzter)

	since, _ := analyzeBriefingDispatchErrors(tmpDir, now)
	if want := letzter.Format(time.RFC3339); since != want {
		t.Errorf("letzter Fehlschlag vor 25h (<= 26h) muss als laufender Ausfall gelten: streak_since want %q, got %q — Schwellenwert zu niedrig?",
			want, since)
	}

	tmpDir2 := t.TempDir()
	letzter2 := now.Add(-27 * time.Hour)
	writeDispatchFailureJournal(t, tmpDir2, "tdd-1629-grenze", letzter2)

	if since2, _ := analyzeBriefingDispatchErrors(tmpDir2, now); since2 != "" {
		t.Errorf("letzter Fehlschlag vor 27h (> 26h) muss als beendet gelten: streak_since want \"\", got %q — Schwellenwert zu hoch?",
			since2)
	}
}

// Ohne Vorfall bleibt das Feldpaar leer — kein Dauer-Alarm aus dem Nichts.
func TestBriefingHealthDispatchFieldsNilWithoutFailures(t *testing.T) {
	tmpDir := t.TempDir()
	sched := newBriefingHealthTestScheduler(t, tmpDir, "tdd-1629-userb")

	_, body, _ := callStatusEndpoint(t, sched)
	bh := body["briefing_health"].(map[string]any)
	if got := bh["briefing_dispatch_error_streak_since"]; got != nil {
		t.Errorf("briefing_dispatch_error_streak_since: want nil, got %v", got)
	}
	if got := bh["briefing_dispatch_errors_recent_count"]; got != float64(0) {
		t.Errorf("briefing_dispatch_errors_recent_count: want 0, got %v", got)
	}
}
