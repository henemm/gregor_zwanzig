package scheduler

// Epic #2261, Scheibe A-2 S2 (AC-1): die zwei Radar-Jobs laufen im
// 5-Minuten-Takt (`3-58/5 * * * *`, Startminuten 3, 8, 13 ... 58). Vorgaenger
// war Issue #1628 S0 (`7,22,37,52`, 15-Min-Takt, weg von :00/:30).
//
// SPEC: docs/specs/modules/feat_2261_a2s2_radar_takt.md AC-1
//
// Geprueft wird am ECHTEN Cron-Eintrag des Schedulers (robfig-Parser ueber
// `e.Schedule.Next`), nicht am Ausdrucks-Text. Rueckmutation auf
// `7,22,37,52` (Abstand 15/8/15/22) oder `*/5` (Minute durch 5 teilbar) wird
// rot. RED heute: Abstand 15 Min bzw. 15/15/15/7 statt 5.

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

	// AC-1: genau diese zwei Jobs feuern im 5-Minuten-Takt, Startminute nicht
	// durch 5 teilbar (kein Zusammenfallen mit */5-, */15-Jobs und
	// briefing_dispatch).
	for _, id := range []string{"radar_alert_checks", "compare_radar_alert_checks"} {
		schedule := radarEntrySchedule(t, sched, id)
		tick := schedule.Next(base)
		for i := 0; i < 24; i++ { // zwei Stunden: deckt den Stundenwechsel ab
			if tick.Minute()%5 == 0 {
				t.Fatalf("%s: Feuer-Minute %d (%v) ist durch 5 teilbar -- "+
					"kollidiert mit */5-/*/15-Jobs bzw. briefing_dispatch", id, tick.Minute(), tick)
			}
			next := schedule.Next(tick)
			if gap := next.Sub(tick); gap != 5*time.Minute {
				t.Fatalf("%s: Abstand %v -> %v ist %v, erwartet genau 5m "+
					"(Cron \"3-58/5 * * * *\")", id, tick, next, gap)
			}
			tick = next
		}
	}

	// Jobzahl bleibt: 9 Cron-Eintraege, 10 logische Jobs (briefing_dispatch = 2 Zeilen).
	if n := len(sched.cron.Entries()); n != 9 {
		t.Fatalf("erwartet 9 Cron-Eintraege, got %d", n)
	}
	if jobs, _ := sched.Status()["jobs"].([]map[string]any); len(jobs) != 10 {
		t.Fatalf("erwartet 10 Jobs im Status, got %d", len(jobs))
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
