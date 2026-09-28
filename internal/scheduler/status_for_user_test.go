package scheduler

// TDD RED — Issue #2155 Scheibe S2 (Admin-Rolle), AC-4 (Scheduler-Seite).
//
// Spec: docs/specs/modules/admin_rolle_s2_status_token.md, Abschnitt 4.
//
// Festgelegte Namen (von der Spec offen gelassen, hier verbindlich):
//   - userRunState.UserRecord(jobID, userID string) (userJobRecord, bool)
//     — Rueckgabe PER WERT unter u.mu
//   - (*Scheduler).StatusForUser(userID string) map[string]any
//     — liefert {"jobs": [ {id, name, next_run, last_run} ]} nur fuer
//       trip_reports_hourly; last_run aus dem Pro-Nutzer-Zustand, nie aus
//       s.lastRuns (globaler Fan-out-Text).
//
// Nur hier laesst sich s.lastRuns["trip_reports_hourly"] setzen — der
// Router-Test (internal/router/scheduler_status_me_test.go) kann den
// globalen Text nicht vorbelegen. Dieser Test bewacht daher die Mutation
// "Getter liefert den globalen statt den Pro-Nutzer-Zustand".
//
// RED-Signal heute: UserRecord und StatusForUser existieren nicht
// (Uebersetzungsfehler).

import (
	"encoding/json"
	"strings"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/store"
)

const globalerFanoutText = "GLOBAL-FANOUT 2 von 3 Nutzern fehlgeschlagen"

func neuerStatusFuerNutzerScheduler(t *testing.T) *Scheduler {
	t.Helper()
	tmpDir := t.TempDir()
	mkUsers(t, tmpDir, "alice", "bob")
	cfg := &config.Config{PythonCoreURL: "http://127.0.0.1:1", SchedulerTimezone: "Europe/Vienna"}
	sched, err := New(cfg, store.New(tmpDir, "alice"))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}
	t.Cleanup(sched.Stop)
	sched.lastRuns["trip_reports_hourly"] = &jobResult{
		Time:   time.Now(),
		Status: "error",
		Error:  globalerFanoutText,
	}
	sched.userState.Record("trip_reports_hourly", "alice", "partial", "alice-eigen")
	sched.userState.Record("alert_checks", "bob", "error", "bob-alert")
	return sched
}

func TestUserRecord_ReturnsOwnRecordByValue(t *testing.T) {
	sched := neuerStatusFuerNutzerScheduler(t)

	rec, ok := sched.userState.UserRecord("trip_reports_hourly", "alice")
	if !ok {
		t.Fatalf("alice: Eintrag fuer trip_reports_hourly erwartet")
	}
	if rec.LastStatus != "partial" || rec.LastError != "alice-eigen" {
		t.Errorf("alice: erwartet partial/alice-eigen, bekommen %q/%q", rec.LastStatus, rec.LastError)
	}

	// Per Wert: Aenderung an der Kopie wirkt nicht auf den Zustand zurueck.
	rec.LastError = "manipuliert"
	again, _ := sched.userState.UserRecord("trip_reports_hourly", "alice")
	if again.LastError != "alice-eigen" {
		t.Errorf("UserRecord darf keinen geteilten Zeiger herausgeben, Zustand ist jetzt %q", again.LastError)
	}

	// bob hat nur einen alert_checks-Eintrag — der Getter filtert nach jobID.
	if _, ok := sched.userState.UserRecord("trip_reports_hourly", "bob"); ok {
		t.Errorf("bob: kein trip_reports_hourly-Eintrag erwartet")
	}
	if _, ok := sched.userState.UserRecord("trip_reports_hourly", "unbekannt"); ok {
		t.Errorf("unbekannter Nutzer: kein Eintrag erwartet")
	}
}

func TestStatusForUser_NeverShowsGlobalFanoutText(t *testing.T) {
	sched := neuerStatusFuerNutzerScheduler(t)

	for _, uid := range []string{"alice", "bob"} {
		raw, err := json.Marshal(sched.StatusForUser(uid))
		if err != nil {
			t.Fatalf("%s: json.Marshal: %v", uid, err)
		}
		body := string(raw)
		if strings.Contains(body, "GLOBAL-FANOUT") {
			t.Errorf("%s: StatusForUser zeigt den globalen Fan-out-Text: %s", uid, body)
		}

		var dto struct {
			Jobs []map[string]json.RawMessage `json:"jobs"`
		}
		if err := json.Unmarshal(raw, &dto); err != nil {
			t.Fatalf("%s: kein JSON: %v", uid, err)
		}
		if len(dto.Jobs) != 1 {
			t.Fatalf("%s: erwartet genau 1 Job, bekommen %d: %s", uid, len(dto.Jobs), body)
		}
		var id string
		_ = json.Unmarshal(dto.Jobs[0]["id"], &id)
		if id != "trip_reports_hourly" {
			t.Errorf("%s: Job-id erwartet trip_reports_hourly, bekommen %q", uid, id)
		}

		lr := strings.TrimSpace(string(dto.Jobs[0]["last_run"]))
		switch uid {
		case "alice":
			var got struct {
				Status string `json:"status"`
				Error  string `json:"error"`
			}
			if err := json.Unmarshal([]byte(lr), &got); err != nil || lr == "null" {
				t.Fatalf("alice: last_run muss ein Objekt sein, bekommen %s", lr)
			}
			if got.Status != "partial" || got.Error != "alice-eigen" {
				t.Errorf("alice: last_run erwartet partial/alice-eigen, bekommen %q/%q", got.Status, got.Error)
			}
		case "bob":
			if lr != "null" {
				t.Errorf("bob: last_run erwartet null (kein eigener Lauf), bekommen %s", lr)
			}
			if strings.Contains(body, "bob-alert") {
				t.Errorf("bob: Fehlertext eines anderen Jobs darf nicht erscheinen: %s", body)
			}
		}
	}
}
