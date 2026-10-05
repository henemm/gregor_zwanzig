package scheduler

// Epic #2261, Scheibe A-2 S2 (AC-2, AC-3 Go-Seite): Budget je Alarmart.
//
// SPEC: docs/specs/modules/feat_2261_a2s2_radar_takt.md AC-2/AC-3, Abschnitt 5
//
// Die Radar-Jobs bekommen Wartebudget 240 s / Laufbudget 270 s / Deckel 600 s
// (an den 5-Minuten-Takt gebunden), alle uebrigen Alarm-Jobs behalten
// 300/720/1800 (ihre Python-Grenze ALERT_RUN_DEADLINE_SECONDS=180 braucht
// Wartebudget >= 300), Briefing-Teiljobs 600/1440/0.
//
// Bewusst ueber `budgetsFor(jobID)` geprueft, NICHT ueber neue Felder
// (`radarWaitBudget` o.ae.): so kompiliert das Paket vor der Umsetzung, und
// die Tests werden per Assertion rot (300 != 240), nicht per Build-Fehler.

import (
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/config"
)

// radarTaktTestScheduler baut einen echten Scheduler (Definition einmalig,
// geteilt mit radar_schwellen_echtzeit_test.go und radar_cron_offset_test.go).
func radarTaktTestScheduler(t *testing.T) *Scheduler {
	t.Helper()
	cfg := &config.Config{PythonCoreURL: "http://localhost:8000", SchedulerTimezone: "Europe/Vienna"}
	sched, err := New(cfg, testStore(t))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}
	return sched
}

// radarEntrySchedule liefert den ECHTEN Cron-Zeitplan des Jobs aus dem
// Scheduler (robfig-Parser), kein Textvergleich.
func radarEntrySchedule(t *testing.T, sched *Scheduler, id string) cronSchedule {
	t.Helper()
	for _, e := range sched.cron.Entries() {
		if meta, ok := sched.entryMap[e.ID]; ok && meta.id == id {
			return e.Schedule
		}
	}
	t.Fatalf("%s nicht im entryMap gefunden", id)
	return nil
}

// radarTaktAbstand ist der aus dem echten Cron-Eintrag abgeleitete Takt
// (Abstand zweier aufeinanderfolgender Ausloesungen).
func radarTaktAbstand(t *testing.T, sched *Scheduler, id string) time.Duration {
	t.Helper()
	schedule := radarEntrySchedule(t, sched, id)
	base := time.Date(2026, 7, 7, 10, 0, 0, 0, time.UTC)
	first := schedule.Next(base)
	return schedule.Next(first).Sub(first)
}

func TestBudgetsFor_RadarJobsHabenEigenesBudget(t *testing.T) {
	sched := radarTaktTestScheduler(t)
	for _, id := range []string{"radar_alert_checks", "compare_radar_alert_checks"} {
		wait, run, callCap := sched.budgetsFor(id)
		if wait != 240*time.Second || run != 270*time.Second || callCap != 600*time.Second {
			t.Errorf("%s: erwartet Wait/Run/Cap 240/270/600 s, got %v/%v/%v", id, wait, run, callCap)
		}
	}
}

func TestBudgetsFor_AndereAlarmJobsUndBriefingUnveraendert(t *testing.T) {
	sched := radarTaktTestScheduler(t)
	for _, id := range []string{"alert_checks", "compare_alert_checks", "compare_official_alert_checks"} {
		wait, run, callCap := sched.budgetsFor(id)
		if wait != 300*time.Second || run != 720*time.Second || callCap != 1800*time.Second {
			t.Errorf("%s: erwartet unveraendert 300/720/1800 s, got %v/%v/%v", id, wait, run, callCap)
		}
	}
	for _, id := range []string{"trip_reports_hourly", "compare_presets_daily"} {
		wait, run, callCap := sched.budgetsFor(id)
		if wait != 600*time.Second || run != 1440*time.Second || callCap != 0 {
			t.Errorf("%s: erwartet unveraendert 600/1440/0 s, got %v/%v/%v", id, wait, run, callCap)
		}
	}
}

// AC-3 (Go-Seite). Der Takt wird aus dem echten Cron-Eintrag abgeleitet.
// Die Teil-Invariante Wait <= Run ist schon heute gruen ("Waechter, gruen
// erwartet"); rot wird die Kette, sobald Cron-Abstand und Budget
// auseinanderlaufen: Run + 10 s < Abstand und Deckel = 2 x Abstand.
func TestRadarBudget_UngleichungsketteAusEchtenKonstanten(t *testing.T) {
	sched := radarTaktTestScheduler(t)
	const nacharbeit = 10 * time.Second
	for _, id := range []string{"radar_alert_checks", "compare_radar_alert_checks"} {
		wait, run, callCap := sched.budgetsFor(id)
		takt := radarTaktAbstand(t, sched, id)
		if takt != 5*time.Minute {
			t.Errorf("%s: Takt aus echtem Cron-Abstand erwartet 5m, got %v", id, takt)
		}
		if wait > run {
			t.Errorf("%s: Wartebudget %v darf das Laufbudget %v nicht ueberschreiten", id, wait, run)
		}
		if run+nacharbeit >= takt {
			t.Errorf("%s: Laufbudget %v + 10 s Nacharbeit muss unter dem Takt %v liegen "+
				"(Ueberlappungsinvariante, sonst ueberspringt recordRun den Folgetick)", id, run, takt)
		}
		if callCap != 2*takt {
			t.Errorf("%s: Deckel %v muss 2 x Takt (%v) sein", id, callCap, 2*takt)
		}
	}
}
