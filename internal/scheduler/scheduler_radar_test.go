package scheduler

import (
	"testing"

	"github.com/henemm/gregor-api/internal/config"
)

// TDD RED — Issue #773 AC-1:
// Der proaktive Radar-/Gewitter-Alert (TripAlertService.check_radar_alerts) ist
// implementiert, wird aber von keinem Scheduler-Job aufgerufen. Dieser Test
// verlangt, dass ein Cron-Job "radar_alert_checks" registriert ist und im
// Status()-Output mit last_run-Feld erscheint (Observability-Pflicht).
//
// RED vor Fix: Job ist nicht registriert → kein Eintrag im jobs-Array.
func TestRadarAlertJobRegistered(t *testing.T) {
	cfg := &config.Config{
		PythonCoreURL:     "http://localhost:8000",
		SchedulerTimezone: "Europe/Vienna",
	}
	sched, err := New(cfg, testStore(t))
	if err != nil {
		t.Fatalf("New() returned error: %v", err)
	}

	status := sched.Status()
	jobs, ok := status["jobs"].([]map[string]any)
	if !ok {
		t.Fatalf("Status()[jobs] hat unerwarteten Typ: %T", status["jobs"])
	}

	var found map[string]any
	for _, j := range jobs {
		if j["id"] == "radar_alert_checks" {
			found = j
			break
		}
	}
	if found == nil {
		t.Fatalf("Job 'radar_alert_checks' nicht registriert (Radar-Alert feuert nie). Jobs: %v", jobIDs(jobs))
	}

	// Observability: name nicht leer + last_run-Feld vorhanden (darf nil sein).
	if name, _ := found["name"].(string); name == "" {
		t.Error("Job 'radar_alert_checks' hat leeren name")
	}
	if _, present := found["last_run"]; !present {
		t.Error("Job 'radar_alert_checks' hat kein last_run-Feld (Monitoring-Pflicht)")
	}
}

func jobIDs(jobs []map[string]any) []any {
	ids := make([]any, 0, len(jobs))
	for _, j := range jobs {
		ids = append(ids, j["id"])
	}
	return ids
}
