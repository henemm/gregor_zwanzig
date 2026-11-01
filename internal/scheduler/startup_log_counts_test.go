package scheduler

// TDD RED — Issue #2163 Scheibe 1, AC-14 (Scheduler-Startlog, Punkt 9).
// Spec: docs/specs/modules/auth_haertung_go_2163.md
//
// Die Startzeile "[scheduler] Started: N cron entries (M jobs), ..." muss die
// tatsaechliche Zahl registrierter Cron-Eintraege (heute 8) und Statuszeilen
// (heute 9, briefing_dispatch expandiert zu zwei) nennen — berechnet aus den
// Eintraegen, nicht hart kodiert. Ermittelt wird die Erwartung aus dem echten
// Scheduler-Aufbau (cron.Entries(), Status()["jobs"]).
//
// Zweiter Test: zusaetzliche Test-Eintraege veraendern die Zahl mit. Bewusst
// ZWEI Eintraege (einer davon mit zwei Teiljobs) -> 10 Eintraege / 12 Zeilen,
// damit die Erwartung nie zufaellig auf den heute hart kodierten 9/10 landet.
//
// RED-Signal heute: Start() loggt fest "9 cron entries (10 jobs)".

import (
	"bytes"
	"log"
	"regexp"
	"strconv"
	"sync"
	"testing"

	"github.com/henemm/gregor-api/internal/config"
)

var startupLineRe = regexp.MustCompile(`\[scheduler\] Started: (\d+) cron entries \((\d+) jobs\)`)

// startAndCaptureCounts startet den Scheduler, liest die Startzeile und liefert
// die geloggten Zahlen; danach wird gestoppt.
func startAndCaptureCounts(t *testing.T, s *Scheduler) (entries, jobs int) {
	t.Helper()
	var logMu sync.Mutex
	var logBuf bytes.Buffer
	prev := log.Writer()
	log.SetOutput(&syncWriter{mu: &logMu, w: &logBuf})
	s.Start()
	log.SetOutput(prev)
	s.Stop()

	logMu.Lock()
	out := logBuf.String()
	logMu.Unlock()
	m := startupLineRe.FindStringSubmatch(out)
	if m == nil {
		t.Fatalf("Startzeile im Format %q nicht gefunden, Log: %q", startupLineRe.String(), out)
	}
	entries, _ = strconv.Atoi(m[1])
	jobs, _ = strconv.Atoi(m[2])
	return entries, jobs
}

func newStartupCountScheduler(t *testing.T) *Scheduler {
	t.Helper()
	cfg := &config.Config{PythonCoreURL: "http://127.0.0.1:1", SchedulerTimezone: "Europe/Vienna"}
	s, err := New(cfg, testStore(t))
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	s.notifier = func(_, _, _, _, _ string) error { return nil }
	return s
}

func statusLineCount(t *testing.T, s *Scheduler) int {
	t.Helper()
	jobs, ok := s.Status()["jobs"].([]map[string]any)
	if !ok {
		t.Fatalf("Status()[\"jobs\"] hat unerwarteten Typ: %T", s.Status()["jobs"])
	}
	return len(jobs)
}

// AC-14: Startzeile nennt die echten Zahlen (8 Eintraege, 9 Statuszeilen).
func TestSchedulerStartlog_NenntRegistrierteEintraegeUndStatuszeilen_AC14(t *testing.T) {
	s := newStartupCountScheduler(t)
	wantEntries := len(s.cron.Entries())
	wantJobs := statusLineCount(t, s)
	// Ist-Stand laut Spec — faellt auf, falls der Aufbau sich unbemerkt aendert.
	if wantEntries != 8 || wantJobs != 9 {
		t.Fatalf("Vorbedingung: erwartet 8 Cron-Eintraege / 9 Statuszeilen, Aufbau hat %d / %d", wantEntries, wantJobs)
	}

	gotEntries, gotJobs := startAndCaptureCounts(t, s)
	if gotEntries != wantEntries || gotJobs != wantJobs {
		t.Errorf("AC-14: Startzeile meldet %d cron entries (%d jobs), registriert sind %d Eintraege / %d Statuszeilen",
			gotEntries, gotJobs, wantEntries, wantJobs)
	}
}

// AC-14: zusaetzliche Eintraege veraendern die geloggte Zahl mit.
func TestSchedulerStartlog_ZusaetzlicheEintraegeAendernZahl_AC14(t *testing.T) {
	s := newStartupCountScheduler(t)

	eid1, err := s.cron.AddFunc("0 3 * * *", func() {})
	if err != nil {
		t.Fatalf("AddFunc: %v", err)
	}
	eid2, err := s.cron.AddFunc("0 4 * * *", func() {})
	if err != nil {
		t.Fatalf("AddFunc: %v", err)
	}
	s.mu.Lock()
	s.entryMap[eid1] = jobMeta{id: "test_extra_einzeln", name: "Test Extra (einzeln)"}
	s.entryMap[eid2] = jobMeta{id: "test_extra_buendel", name: "Test Extra (Buendel)", subs: []jobMeta{
		{id: "test_extra_teil_a", name: "Teil A"},
		{id: "test_extra_teil_b", name: "Teil B"},
	}}
	s.mu.Unlock()

	wantEntries := len(s.cron.Entries())
	wantJobs := statusLineCount(t, s)
	if wantEntries != 10 || wantJobs != 12 {
		t.Fatalf("Vorbedingung: nach zwei Zusatz-Eintraegen erwartet 10 / 12, Aufbau hat %d / %d", wantEntries, wantJobs)
	}

	gotEntries, gotJobs := startAndCaptureCounts(t, s)
	if gotEntries != wantEntries || gotJobs != wantJobs {
		t.Errorf("AC-14: Startzeile meldet %d cron entries (%d jobs), registriert sind %d Eintraege / %d Statuszeilen "+
			"(Zahl muss aus den Eintraegen berechnet werden)", gotEntries, gotJobs, wantEntries, wantJobs)
	}
}
