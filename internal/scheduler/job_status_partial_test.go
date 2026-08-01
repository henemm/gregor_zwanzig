package scheduler

import (
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/henemm/gregor-api/internal/config"
)

// ---------------------------------------------------------------------------
// Issue #1447 Scheibe S2a — Teil B: Teilerfolg durchreichen
//
// Spec: docs/specs/modules/fix_1447_s2a_scheduler_ueberlappung_teilerfolg.md
//
// Ein `status: "partial"` aus dem Python-Kern (Scheibe S1, ohne `failed`)
// muss als jobResult.Status "partial" verbucht werden statt als "ok" (bisher)
// oder "error". `failed > 0` bleibt unveraendert "error" — Regressionsschutz
// fuer #1012 AC-5 (bestehender TestTriggerEndpoint_FailedBodyTreatedAsError
// in scheduler_test.go).
// ---------------------------------------------------------------------------

const partialBody = `{"status":"partial","count":1,"checked":3,"skipped":2,"duration_s":90.02,"reason":"deadline"}`

// TestTriggerEndpointForUser_PartialWithoutFailed_ReturnsPartialNotHardError (AC-5, AC-6)
func TestTriggerEndpointForUser_PartialWithoutFailed_ReturnsPartialNotHardError(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		fmt.Fprint(w, partialBody)
	}))
	defer server.Close()

	cfg := &config.Config{
		PythonCoreURL:     server.URL,
		SchedulerTimezone: "Europe/Vienna",
	}
	sched, err := New(cfg, testStore(t))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}

	err = sched.triggerEndpointForUser("/api/scheduler/alert-checks", "default")
	if err == nil {
		t.Fatal("expected non-nil error for status=partial without failed, so recordRun " +
			"can classify it separately from a hard error")
	}

	var pe *partialRunError
	if !errors.As(err, &pe) {
		t.Fatalf("expected error to be classifiable as *partialRunError via errors.As, "+
			"got %T: %v", err, err)
	}
}

// TestAlertChecks_PartialResponse_RecordedAsPartialStatus (AC-5) — End-to-End
// ueber sched.alertChecks() und sched.Status().
func TestAlertChecks_PartialResponse_RecordedAsPartialStatus(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		fmt.Fprint(w, partialBody)
	}))
	defer server.Close()

	cfg := &config.Config{
		PythonCoreURL:     server.URL,
		SchedulerTimezone: "Europe/Vienna",
	}
	sched, err := New(cfg, testStore(t))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}
	sched.Start()
	defer sched.Stop()

	sched.alertChecks()

	status := sched.Status()
	jobs, ok := status["jobs"].([]map[string]any)
	if !ok {
		t.Fatalf("status jobs should be []map[string]any, got %T", status["jobs"])
	}
	var job map[string]any
	for _, j := range jobs {
		if j["id"] == "alert_checks" {
			job = j
		}
	}
	if job == nil {
		t.Fatal("alert_checks job not found in status")
	}
	lr, ok := job["last_run"].(map[string]any)
	if !ok || lr == nil {
		t.Fatal("expected last_run to be present after alertChecks() ran")
	}
	if lr["status"] != "partial" {
		t.Fatalf("expected last_run.status='partial', got %v (error=%v)", lr["status"], lr["error"])
	}
}

// TestRunForAllUsers_MixedUserResults_ErrorRanksAbovePartial (AC-7) —
// Rangfolge error > partial > ok bei gemischten Nutzer-Ergebnissen.
func TestRunForAllUsers_MixedUserResults_ErrorRanksAbovePartial(t *testing.T) {
	cases := []struct {
		name       string
		aliceBody  string
		aliceCode  int
		bobBody    string
		bobCode    int
		wantStatus string
	}{
		{
			name:       "partial+error=error",
			aliceBody:  partialBody,
			aliceCode:  http.StatusOK,
			bobBody:    `{"error":"boom"}`,
			bobCode:    http.StatusInternalServerError,
			wantStatus: "error",
		},
		{
			name:       "ok+partial=partial",
			aliceBody:  `{"status":"ok","count":2}`,
			aliceCode:  http.StatusOK,
			bobBody:    partialBody,
			bobCode:    http.StatusOK,
			wantStatus: "partial",
		},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				switch r.URL.Query().Get("user_id") {
				case "alice":
					w.WriteHeader(tc.aliceCode)
					fmt.Fprint(w, tc.aliceBody)
				case "bob":
					w.WriteHeader(tc.bobCode)
					fmt.Fprint(w, tc.bobBody)
				default:
					w.WriteHeader(http.StatusOK)
					fmt.Fprint(w, `{"status":"ok"}`)
				}
			}))
			defer server.Close()

			cfg := &config.Config{
				PythonCoreURL:     server.URL,
				SchedulerTimezone: "Europe/Vienna",
			}
			sched, err := New(cfg, testStoreWithUsers(t, "alice", "bob"))
			if err != nil {
				t.Fatalf("New() error: %v", err)
			}

			sched.recordRun("mixed_job", func() error {
				return sched.runForAllUsers("mixed_job", "/api/scheduler/alert-checks")
			})

			sched.mu.RLock()
			lr := sched.lastRuns["mixed_job"]
			sched.mu.RUnlock()
			if lr == nil {
				t.Fatal("expected lastRuns entry for mixed_job")
			}
			if lr.Status != tc.wantStatus {
				t.Fatalf("expected status %q, got %q (error=%q)", tc.wantStatus, lr.Status, lr.Error)
			}
		})
	}
}
