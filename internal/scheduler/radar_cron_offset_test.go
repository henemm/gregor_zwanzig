package scheduler

// Issue #1628, S0 (AC-1): radar_alert_checks + compare_radar_alert_checks
// muessen auf "7,22,37,52 * * * *" verschoben werden (weg von den
// Lastspitzen-Minuten :00/:30 eines Fremddienstes), alle anderen Jobs
// bleiben unveraendert. RED-Nachweis: heute registriert scheduler.go beide
// Jobs mit "*/15 * * * *" -- die erste Feuer-Minute nach einer vollen
// Stunde ist dann 0, nicht 7.
//
// SPEC: docs/specs/modules/fix_1628_nowcast_datenluecke.md AC-1
//
// Ausfuehrung ueber go-Overlay (edit_gate/RED-Gate-Zwickmuehle, s. Spec):
//   go test -count=1 -overlay=<overlay.json> \
//     -run TestRadarJobsCronOffsetMinutes ./internal/scheduler/...

import (
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/config"
)

func TestRadarJobsCronOffsetMinutes(t *testing.T) {
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

	base := time.Date(2026, 7, 7, 10, 0, 0, 0, time.UTC)

	// AC-1: genau diese zwei Jobs feuern zu 7/22/37/52 statt 0/15/30/45.
	for _, id := range []string{"radar_alert_checks", "compare_radar_alert_checks"} {
		var schedule cronSchedule
		for _, e := range sched.cron.Entries() {
			if meta, ok := sched.entryMap[e.ID]; ok && meta.id == id {
				schedule = e.Schedule
				break
			}
		}
		if schedule == nil {
			t.Fatalf("%s nicht im entryMap gefunden", id)
		}
		next := schedule.Next(base)
		if next.Minute() != 7 {
			t.Fatalf(
				"%s: erste Feuer-Minute nach %v ist %v (Minute %d) -- "+
					"erwartet Minute 7 (Cron \"7,22,37,52 * * * *\")",
				id, base, next, next.Minute(),
			)
		}
	}

	// Gegenprobe (AC-1, F001-Haertung): ALLE fuenf laut Spec unveraenderten
	// Jobs (die vier weiteren "*/15"-Jobs + briefing_dispatch) bleiben bei
	// ihrer bisherigen Feuer-Minute -- Schutz gegen eine zu breite
	// Umsetzung, die versehentlich einen dieser Jobs mit auf den neuen
	// Versatz verschiebt (Adversary-Finding F001,
	// docs/artifacts/fix-1628-nowcast-datenluecke/adversary-dialog.md:
	// vorher deckte diese Gegenprobe nur data_write_selftest ab,
	// compare_alert_checks und briefing_dispatch waren ungeschuetzt).
	//
	// base liegt exakt auf einer */15-Grenze (10:00:00); nach
	// robfig/cron/v3-Semantik (spec.go: Next() startet bei t+1s, liefert
	// also NIE denselben Zeitpunkt wie das Argument) ist die erste
	// tatsaechliche Feuer-Minute danach fuer "*/15 * * * *" 15, nicht 0.
	// briefing_dispatch ("0 * * * *") feuert dagegen zur naechsten vollen
	// Stunde, also Minute 0 (11:00 Uhr) -- eigene erwartete Minute je Job,
	// nicht ein gemeinsamer Wert fuer alle.
	untouchedExpectations := map[string]int{
		"alert_checks":                  15,
		"data_write_selftest":           15,
		"compare_alert_checks":          15,
		"compare_official_alert_checks": 15,
		"briefing_dispatch":             0,
	}
	for id, wantMinute := range untouchedExpectations {
		var schedule cronSchedule
		for _, e := range sched.cron.Entries() {
			if meta, ok := sched.entryMap[e.ID]; ok && meta.id == id {
				schedule = e.Schedule
				break
			}
		}
		if schedule == nil {
			t.Fatalf("%s nicht im entryMap gefunden", id)
		}
		if got := schedule.Next(base).Minute(); got != wantMinute {
			t.Fatalf(
				"%s: erwartet unveraendert Minute %d, got %d -- "+
					"(S0 darf NUR radar_alert_checks/compare_radar_alert_checks verschieben)",
				id, wantMinute, got,
			)
		}
	}
}
