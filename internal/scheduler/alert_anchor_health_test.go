package scheduler

import (
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

// TDD — Issue #1661 Teil C, AC-11 (Go-Hälfte) / AC-12 / AC-16: ein verworfener
// oder fehlender Alarm-Anker wird am Status-Endpunkt als mit der Ausfalldauer
// WACHSENDES Signal sichtbar.
//
// Spec: docs/specs/modules/fix_1661_anker_vom_falschen_tag.md (AC-11, AC-12, AC-16).
//
// Quelle ist die Diagnose-Spur, die der Python-Kern beim Verwerfen fail-soft
// schreibt (`record_alert_anchor_rejected`, src/services/alert_briefing_anchor.py):
// users/<uid>/diagnostics/alert_anchor_rejected.jsonl.
//
// KEINE Mocks: echte Dateien in t.TempDir(), echter httptest-Roundtrip gegen
// den realen Handler (Muster briefing_dispatch_health_test.go).

// writeAnchorRejectedJournal writes a real
// users/<uid>/diagnostics/alert_anchor_rejected.jsonl with one line per given
// timestamp — exactly the shape the Python writer produces, INCLUDING the
// entity_id/reason fields that must never cross the Go boundary (#252).
func writeAnchorRejectedJournal(t *testing.T, tmpDir, userID string, times ...time.Time) {
	t.Helper()
	dir := filepath.Join(tmpDir, "users", userID, "diagnostics")
	if err := os.MkdirAll(dir, 0755); err != nil {
		t.Fatalf("mkdir diagnostics: %v", err)
	}
	var b strings.Builder
	for _, ts := range times {
		b.WriteString(`{"ts":"` + ts.Format(time.RFC3339Nano) +
			`","entity_id":"trip-1661-khw403","reason":"wrong_day"}` + "\n")
	}
	path := filepath.Join(dir, "alert_anchor_rejected.jsonl")
	if err := os.WriteFile(path, []byte(b.String()), 0644); err != nil {
		t.Fatalf("write journal: %v", err)
	}
}

// AC-11 (Go-Hälfte): eine einzige echte Ablehnung — wie sie der Python-Test
// test_alert_anchor_day_guard.py::test_ac11_* erzeugt — ist hier als
// recentCount >= 1 sichtbar. Ohne diesen Nachweis endet die Spur im Dateisystem
// und niemand erfährt vom Ausfall (R5: ein Signal ohne Leser versandet).
func TestAnalyzeAlertAnchorRejectionsSeesASingleRejection(t *testing.T) {
	tmpDir := t.TempDir()
	now := time.Now().UTC()
	writeAnchorRejectedJournal(t, tmpDir, "tdd-1661-a", now.Add(-5*time.Minute))

	since, recent := analyzeAlertAnchorRejections(tmpDir, now)
	if recent < 1 {
		t.Fatalf("recent_count: want >= 1 (eine verworfene Anker-Ablehnung), got %d", recent)
	}
	if since == "" {
		t.Errorf("streak_since fehlt — eine gerade laufende Ablehnungsserie muss einen Serienbeginn melden")
	}
}

// AC-12 (Serienbeginn): der Startzeitpunkt bleibt der ERSTE Fehlschlag der
// laufenden Serie — weitere Ablehnungen schieben ihn nicht nach vorne, das
// Signal wächst also mit der Ausfalldauer (ADR-0018 Punkt 3).
func TestAnalyzeAlertAnchorRejectionsStreakStartsAtFirstRejection(t *testing.T) {
	tmpDir := t.TempDir()
	now := time.Now().UTC()
	seriesStart := now.Add(-60 * time.Minute)

	// Viertelstundentakt des Alarm-Laufs: Abstände von 15 min, alle innerhalb
	// der 60-min-Schwelle. Genau das Bild vom 08.08.2026 (~28 stille Läufe).
	writeAnchorRejectedJournal(t, tmpDir, "tdd-1661-a",
		seriesStart, seriesStart.Add(15*time.Minute), seriesStart.Add(30*time.Minute),
		seriesStart.Add(45*time.Minute))

	since, recent := analyzeAlertAnchorRejections(tmpDir, now)
	got, err := time.Parse(time.RFC3339, since)
	if err != nil {
		t.Fatalf("streak_since nicht als RFC3339 lesbar (%q): %v", since, err)
	}
	if !got.Equal(seriesStart.Truncate(time.Second)) {
		t.Errorf("streak_since: want %v (erste Ablehnung der Serie), got %v",
			seriesStart.Truncate(time.Second), got)
	}
	if recent != 4 {
		t.Errorf("recent_count (letzte 24h): want 4, got %d", recent)
	}
}

// AC-12 (Lücken-Logik): ein weit zurückliegender Einzelfall VOR einer Lücke von
// mehr als 60 Minuten gehört nicht zur laufenden Serie.
func TestAnalyzeAlertAnchorRejectionsIgnoresRejectionBeforeLargeGap(t *testing.T) {
	tmpDir := t.TempDir()
	now := time.Now().UTC()
	seriesStart := now.Add(-30 * time.Minute)

	writeAnchorRejectedJournal(t, tmpDir, "tdd-1661-a",
		now.Add(-20*time.Hour), seriesStart, now.Add(-5*time.Minute))

	since, _ := analyzeAlertAnchorRejections(tmpDir, now)
	got, err := time.Parse(time.RFC3339, since)
	if err != nil {
		t.Fatalf("streak_since nicht als RFC3339 lesbar (%q): %v", since, err)
	}
	if !got.Equal(seriesStart.Truncate(time.Second)) {
		t.Errorf("streak_since: want %v (Beginn der LAUFENDEN Serie), got %v",
			seriesStart.Truncate(time.Second), got)
	}
}

// AC-12 (Schwellenwert 60 min, GENAU): bewusst mit den LITERALEN Grenzen
// 55 min / 65 min formuliert statt relativ zur Konstante — ein relativer Test
// wanderte mit jeder Änderung mit und nagelte gar nichts fest (Lehre aus
// Adversary-Finding F002 der #1629-Scheibe). Rückwärts-Richtung: die Lücke
// ZWISCHEN zwei Ablehnungen.
func TestAlertAnchorRejectedGapThresholdIsSixtyMinutesBackward(t *testing.T) {
	now := time.Date(2026, 8, 10, 12, 0, 0, 0, time.UTC)

	// 55 min Lücke — innerhalb der Schwelle: die Serie beginnt beim ÄLTEREN
	// Eintrag. Bei einer zu niedrig gesetzten Schwelle (z.B. 30 min) käme hier
	// der jüngere.
	tmpDir := t.TempDir()
	aelter := now.Add(-60 * time.Minute)
	juenger := now.Add(-5 * time.Minute) // Lücke: 55 min
	writeAnchorRejectedJournal(t, tmpDir, "tdd-1661-grenze", aelter, juenger)

	since, _ := analyzeAlertAnchorRejections(tmpDir, now)
	if want := aelter.Format(time.RFC3339); since != want {
		t.Errorf("Lücke 55 min (<= 60 min) muss die Serie zusammenhalten: streak_since want %q, got %q — Schwellenwert zu niedrig?",
			want, since)
	}

	// 65 min Lücke — jenseits der Schwelle: der ältere Eintrag gehört nicht
	// mehr zur laufenden Serie. Bei einer zu hoch gesetzten Schwelle (z.B. den
	// 26 h der Briefing-Diagnose) käme hier fälschlich der ältere.
	tmpDir2 := t.TempDir()
	aelter2 := now.Add(-70 * time.Minute)
	juenger2 := now.Add(-5 * time.Minute) // Lücke: 65 min
	writeAnchorRejectedJournal(t, tmpDir2, "tdd-1661-grenze", aelter2, juenger2)

	since2, _ := analyzeAlertAnchorRejections(tmpDir2, now)
	if want := juenger2.Format(time.RFC3339); since2 != want {
		t.Errorf("Lücke 65 min (> 60 min) muss die Serie trennen: streak_since want %q (nur der jüngere Eintrag), got %q — Schwellenwert zu hoch?",
			want, since2)
	}
}

// AC-12 (Serienende, Vorwärts-Richtung): die Lücke zwischen der JÜNGSTEN
// Ablehnung und "jetzt" entscheidet, ob die Serie noch läuft. Ein wieder
// gültiger Anker schreibt keine Zeile — genau daran endet die Serie.
func TestAlertAnchorRejectedGapThresholdIsSixtyMinutesForward(t *testing.T) {
	now := time.Date(2026, 8, 10, 12, 0, 0, 0, time.UTC)

	tmpDir := t.TempDir()
	letzte := now.Add(-55 * time.Minute)
	writeAnchorRejectedJournal(t, tmpDir, "tdd-1661-grenze", letzte)

	since, _ := analyzeAlertAnchorRejections(tmpDir, now)
	if want := letzte.Format(time.RFC3339); since != want {
		t.Errorf("letzte Ablehnung vor 55 min (<= 60 min) muss als laufender Ausfall gelten: streak_since want %q, got %q — Schwellenwert zu niedrig?",
			want, since)
	}

	tmpDir2 := t.TempDir()
	letzte2 := now.Add(-65 * time.Minute)
	writeAnchorRejectedJournal(t, tmpDir2, "tdd-1661-grenze", letzte2)

	if since2, _ := analyzeAlertAnchorRejections(tmpDir2, now); since2 != "" {
		t.Errorf("letzte Ablehnung vor 65 min (> 60 min) muss als beendet gelten: streak_since want \"\", got %q — Schwellenwert zu hoch?",
			since2)
	}
}

// AC-12: die Schwelle ist bewusst NICHT die der Nachbar-Diagnosen. Der
// Abweichungs-Alarm läuft alle 15 Minuten; mit den 26 h der Briefing-Diagnose
// bliebe derselbe Fehler tagelang unsichtbar, mit den 2 h des Provider-Pfads
// wäre er immer noch acht Läufe lang stumm.
func TestAlertAnchorRejectedThresholdDiffersFromNeighbours(t *testing.T) {
	if alertAnchorRejectedGapThreshold == dispatchErrorStreakGapThreshold {
		t.Errorf("Lücken-Schwelle darf nicht die der Briefing-Diagnose sein (%v)",
			dispatchErrorStreakGapThreshold)
	}
	if alertAnchorRejectedGapThreshold == providerErrorStreakGapThreshold {
		t.Errorf("Lücken-Schwelle darf nicht die der Provider-Diagnose sein (%v)",
			providerErrorStreakGapThreshold)
	}
}

// Fail-soft + Mandanten-Aggregation: kaputte Zeilen werden übersprungen,
// mehrere Nutzer werden zusammengezählt, ein fehlendes Journal ist kein Fehler.
func TestAnalyzeAlertAnchorRejectionsAggregatesUsersFailSoft(t *testing.T) {
	tmpDir := t.TempDir()
	now := time.Now().UTC()

	writeAnchorRejectedJournal(t, tmpDir, "tdd-1661-a", now.Add(-10*time.Minute))
	writeAnchorRejectedJournal(t, tmpDir, "tdd-1661-b", now.Add(-20*time.Minute))
	dir := filepath.Join(tmpDir, "users", "tdd-1661-c", "diagnostics")
	if err := os.MkdirAll(dir, 0755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	body := "{kaputt\n" + `{"ts":"` + now.Add(-30*time.Minute).Format(time.RFC3339) + `"}` + "\n"
	if err := os.WriteFile(filepath.Join(dir, "alert_anchor_rejected.jsonl"),
		[]byte(body), 0644); err != nil {
		t.Fatalf("write: %v", err)
	}

	_, recent := analyzeAlertAnchorRejections(tmpDir, now)
	if recent != 3 {
		t.Errorf("recent_count über alle Nutzer: want 3, got %d", recent)
	}

	if since, recent := analyzeAlertAnchorRejections(filepath.Join(tmpDir, "leer"), now); since != "" || recent != 0 {
		t.Errorf("fehlendes Journal muss (\"\", 0) liefern, got (%q, %d)", since, recent)
	}
}

// AC-16 (Privacy #252 am WIRKORT): weder entity_id noch reason dürfen den
// Rückgabewert oder BriefingHealth() erreichen — nur zeitstempel-abgeleitete
// Werte. Geprüft am ausgelieferten Status-Endpunkt, nicht am Zwischenstand.
func TestBriefingHealthExposesAlertAnchorFieldsWithoutIdentifiers(t *testing.T) {
	tmpDir := t.TempDir()
	sched := newBriefingHealthTestScheduler(t, tmpDir, "tdd-1661-usera")
	now := time.Now().UTC()
	writeAnchorRejectedJournal(t, tmpDir, "tdd-1661-usera",
		now.Add(-45*time.Minute), now.Add(-15*time.Minute))

	since, recent := analyzeAlertAnchorRejections(tmpDir, now)
	if strings.Contains(since, "trip-1661-khw403") || strings.Contains(since, "wrong_day") {
		t.Errorf("Datenschutz (#252): der Rückgabewert trägt eine Kennung: %q", since)
	}
	if recent != 2 {
		t.Errorf("recent_count: want 2, got %d", recent)
	}

	code, body, raw := callStatusEndpoint(t, sched)
	if code != http.StatusOK {
		t.Fatalf("expected 200, got %d", code)
	}
	bh, ok := body["briefing_health"].(map[string]any)
	if !ok {
		t.Fatalf("briefing_health fehlt: %v", body["briefing_health"])
	}
	if got := bh["alert_anchor_rejected_recent_count"]; got != float64(2) {
		t.Errorf("alert_anchor_rejected_recent_count: want 2, got %v", got)
	}
	streak, ok := bh["alert_anchor_rejected_streak_since"].(string)
	if !ok || streak == "" {
		t.Fatalf("alert_anchor_rejected_streak_since fehlt oder ist leer: %v",
			bh["alert_anchor_rejected_streak_since"])
	}
	for _, verboten := range []string{"tdd-1661-usera", "trip-1661-khw403", "wrong_day"} {
		if strings.Contains(raw, verboten) {
			t.Errorf("Datenschutz (#252): der Status-Endpunkt darf %q nicht tragen: %s",
				verboten, raw)
		}
	}
}

// Ohne Vorfall bleibt das Feldpaar leer — kein Dauer-Alarm aus dem Nichts.
func TestBriefingHealthAlertAnchorFieldsNilWithoutRejections(t *testing.T) {
	tmpDir := t.TempDir()
	sched := newBriefingHealthTestScheduler(t, tmpDir, "tdd-1661-userb")

	_, body, _ := callStatusEndpoint(t, sched)
	bh := body["briefing_health"].(map[string]any)
	if got := bh["alert_anchor_rejected_streak_since"]; got != nil {
		t.Errorf("alert_anchor_rejected_streak_since: want nil, got %v", got)
	}
	if got := bh["alert_anchor_rejected_recent_count"]; got != float64(0) {
		t.Errorf("alert_anchor_rejected_recent_count: want 0, got %v", got)
	}
}
