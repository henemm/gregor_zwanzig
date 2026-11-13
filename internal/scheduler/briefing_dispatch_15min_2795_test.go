package scheduler

// Issue #2795 S3b Teil 1a — Viertelstunden-Raster fuer Briefing-Zeiten.
// SPEC: docs/specs/modules/feat_2795_s3b_teil1_zustellung.md §4.1 „Takt (Go)",
// AC-5 (Versand beim ersten Takt ab 06:45) und AC-6 (mehrere Ticks im Fenster).
//
// Geprueft wird am ECHTEN Cron-Eintrag (robfig-Parser ueber Schedule.Next),
// nicht am Ausdrucks-Text: briefing_dispatch muss an jeder Viertelstunde
// feuern (:00, :15, :30, :45), sonst kann ein auf 06:45 gestelltes Briefing
// fruehestens um 07:00 rausgehen.
//
// RED heute: "0 * * * *" -> Abstand 60 Minuten, Feuer-Minuten nur 0.
//
// Hinweis fuer GREEN: radar_cron_offset_test.go erwartet fuer
// briefing_dispatch noch die Feuer-Minute 0 nach 10:00 (stuendlich). Mit dem
// 15-Minuten-Takt ist die naechste Feuer-Minute nach 10:00:00 die 15 -- jene
// Erwartung ist mitzuziehen (keine Abschwaechung, nur der neue Takt).
//
// Ausfuehrung: go test ./internal/scheduler -run 2795 -v

import (
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/config"
)

func TestBriefingDispatch_2795_FeuertJedeViertelstunde(t *testing.T) {
	cfg := &config.Config{
		PythonCoreURL:     "http://localhost:8000",
		SchedulerTimezone: "Europe/Vienna",
	}
	sched, err := New(cfg, testStore(t))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}
	sched.Start()
	defer sched.Stop()

	schedule := radarEntrySchedule(t, sched, "briefing_dispatch")

	// Start knapp vor 06:00 Ortszeit-Wiener-Uhr: die Ticks muessen 06:00,
	// 06:15, 06:30, 06:45, 07:00 ... treffen -- je 15 Minuten Abstand und
	// immer auf einer vollen Viertelstunde.
	base := time.Date(2026, 8, 20, 3, 59, 0, 0, time.UTC)
	tick := schedule.Next(base)
	gesehen := map[int]bool{}
	for i := 0; i < 12; i++ { // drei Stunden = 12 Ticks (Nachholfenster)
		if tick.Minute()%15 != 0 || tick.Second() != 0 {
			t.Fatalf("AC-5: briefing_dispatch feuert um %v -- nicht auf einer Viertelstunde", tick)
		}
		gesehen[tick.Minute()] = true
		next := schedule.Next(tick)
		if gap := next.Sub(tick); gap != 15*time.Minute {
			t.Fatalf("AC-5/AC-6: briefing_dispatch Abstand %v -> %v ist %v, erwartet 15m "+
				"(sonst geht ein 06:45-Briefing erst um 07:00 raus)", tick, next, gap)
		}
		tick = next
	}
	for _, m := range []int{0, 15, 30, 45} {
		if !gesehen[m] {
			t.Errorf("AC-5: Feuer-Minute %02d fehlt in drei Stunden Ticks (gesehen: %v)", m, gesehen)
		}
	}
}
