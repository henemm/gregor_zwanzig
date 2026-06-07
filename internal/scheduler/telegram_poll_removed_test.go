package scheduler

// TDD RED: Issue #637 — AC-4: Polling-Deaktivierung.
// Spec: docs/specs/modules/telegram_webhook_inbound.md
//
// Muss FEHLSCHLAGEN solange der Job `inbound_telegram_poll` registriert ist.
// Ausführung: go test ./internal/scheduler/... -run TestScheduler_NoInboundTelegramPollJob -v

import (
	"testing"

	"github.com/henemm/gregor-api/internal/config"
)

// AC-4: Nach der Webhook-Migration darf der Scheduler keinen
// inbound_telegram_poll-Job mehr führen (keine periodischen getUpdates-Calls).
func TestScheduler_NoInboundTelegramPollJob(t *testing.T) {
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
		t.Fatalf("Status()[\"jobs\"] hat unerwarteten Typ: %T", status["jobs"])
	}

	for _, j := range jobs {
		if id, _ := j["id"].(string); id == "inbound_telegram_poll" {
			t.Fatal("Job 'inbound_telegram_poll' muss nach der Webhook-Migration entfernt sein, ist aber noch registriert")
		}
	}
}
