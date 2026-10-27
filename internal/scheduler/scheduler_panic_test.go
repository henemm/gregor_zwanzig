package scheduler

// ---------------------------------------------------------------------------
// Fix #2217 — Panic-Abschottung im Go-Scheduler (AC-7, AC-8).
//
// Spec: docs/specs/modules/fix_2217_stapellauf_abschotten.md
//
// WICHTIG zur Ausfuehrung: Die AC-8-Tests loesen den Panic in der vom
// Scheduler gestarteten Nutzer-Goroutine aus. Ein Panic in einer fremden
// Goroutine kann ein Test von aussen NICHT per recover abfangen — heute (RED)
// reisst er das ganze Test-Binary ab. Das ist als RED akzeptiert; die Tests
// werden deshalb isoliert ausgefuehrt:
//   go test ./internal/scheduler -run 'TestPanicInUserCall_ReturnsError' -count=1
//   go test ./internal/scheduler -run 'TestPanicInUserCall_OtherUsers' -count=1
// Nach dem Fix (recover in der Nutzer-Goroutine) laufen sie regulaer gruen.
// ---------------------------------------------------------------------------

import (
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

// panickingRoundTripper loest fuer user_id == panicUID einen Panic aus,
// alle anderen Aufrufe gehen an den echten Transport (httptest-Server).
type panickingRoundTripper struct {
	panicUID string
	next     http.RoundTripper
}

func (p *panickingRoundTripper) RoundTrip(r *http.Request) (*http.Response, error) {
	if r.URL.Query().Get("user_id") == p.panicUID {
		panic("boom in user call")
	}
	return p.next.RoundTrip(r)
}

// AC-7: Panic in der Job-Funktion darf recordRun nicht verlassen; Status
// "error" mit exakt "panic in <jobID>" (kein Stack), Sperre frei.
func TestPanicInRecordRun_RecordedAsErrorAndLockReleased(t *testing.T) {
	sched := newOverlapTestScheduler(t)
	const jobID = "panic_job"

	func() {
		defer func() {
			if r := recover(); r != nil {
				t.Fatalf("panic propagated out of recordRun: %v", r)
			}
		}()
		sched.recordRun(jobID, func() error { panic("boom") })
	}()

	lr := lastRunOf(sched, jobID)
	if lr == nil {
		t.Fatal("lastRuns[panic_job] fehlt nach panickender Job-Funktion")
	}
	if lr.Status != "error" {
		t.Fatalf("Status = %q, erwartet \"error\"", lr.Status)
	}
	if lr.Error != "panic in "+jobID {
		t.Fatalf("Error = %q, erwartet exakt %q (kein Stack im halb-oeffentlichen Status)", lr.Error, "panic in "+jobID)
	}

	ran := false
	sched.recordRun(jobID, func() error { ran = true; return nil })
	if !ran {
		t.Fatal("zweiter Lauf desselben Jobs wurde uebersprungen: Ueberlappungssperre nicht freigegeben")
	}
	if lr2 := lastRunOf(sched, jobID); lr2 == nil || lr2.Status != "ok" {
		t.Fatalf("Status nach zweitem Lauf = %+v, erwartet ok", lr2)
	}
}

// AC-8 (a): Panic im Aufruf eines Nutzers -> Aufrufer bekommt sofort einen
// Fehler (weit unter dem Wartebudget), Budget-Marker haengt nicht.
// Heute: Test-Binary stuerzt ab (Panic in fremder Goroutine) — isoliert laufen.
func TestPanicInUserCall_ReturnsErrorImmediatelyAndReleasesMarker(t *testing.T) {
	b := newBudgetServer(t)
	sched, _, _ := newBudgetScheduler(t, b.srv.URL, "alice", "bob")
	sched.client = &http.Client{
		Timeout:   10 * time.Second,
		Transport: &panickingRoundTripper{panicUID: "bob", next: http.DefaultTransport},
	}
	const jobID = "trip_reports_hourly"
	const wait = 5 * time.Second

	start := time.Now()
	err := sched.callUserWithBudget(jobID, "/api/scheduler/trip-reports", "bob", wait, 0)
	elapsed := time.Since(start)

	if err == nil {
		t.Fatal("erwartet Fehler nach Panic im Nutzeraufruf, bekam nil")
	}
	// PO-Entscheid 2026-10-07: nach aussen nur "panic in <jobID>", kein Panic-Wert.
	if err.Error() != "panic in "+jobID {
		t.Fatalf("Fehlertext = %q, erwartet exakt %q (kein Panic-Wert)", err.Error(), "panic in "+jobID)
	}
	var be *budgetExceededError
	if errors.As(err, &be) {
		t.Fatalf("Fehler ist budgetExceededError (Wartebudget abgelaufen) statt sofortiger Panic-Fehler: %v", err)
	}
	if elapsed > wait/5 {
		t.Fatalf("Rueckkehr nach %v, erwartet deutlich unter Wartebudget %v", elapsed, wait)
	}
	if sched.callBudget.IsInFlight(jobID, "bob") {
		t.Fatal("Budget-Marker fuer bob haengt nach Panic")
	}
}

// AC-8 (b): Panic bei einem Nutzer darf die uebrigen Nutzer derselben Runde
// nicht beeintraechtigen.
// Heute: Test-Binary stuerzt ab — isoliert laufen.
func TestPanicInUserCall_OtherUsersStillServed(t *testing.T) {
	b := newBudgetServer(t)
	sched, _, _ := newBudgetScheduler(t, b.srv.URL, "alice", "bob", "carol")
	sched.client = &http.Client{
		Timeout:   10 * time.Second,
		Transport: &panickingRoundTripper{panicUID: "bob", next: http.DefaultTransport},
	}
	const jobID = "trip_reports_hourly"

	start := time.Now()
	runErr := sched.runForAllUsers(jobID, "/api/scheduler/trip-reports")
	elapsed := time.Since(start)

	if runErr == nil {
		t.Fatal("Lauf mit panickendem Nutzer muss als Fehler enden, bekam nil")
	}
	if elapsed > 2*time.Second {
		t.Fatalf("Lauf dauerte %v, erwartet sofortige Rueckkehr (Wartebudget %v)", elapsed, sched.briefingWaitBudget)
	}
	for _, uid := range []string{"alice", "carol"} {
		if b.count(uid) != 1 {
			t.Fatalf("Nutzer %s wurde %d-mal bedient, erwartet 1", uid, b.count(uid))
		}
	}
	if sched.callBudget.IsInFlight(jobID, "bob") {
		t.Fatal("Budget-Marker fuer bob haengt nach Panic")
	}
}

// Regressionsschutz (darf heute gruen sein): failed>0 ist IMMER ein harter
// Fehler, nie *partialRunError — weder bei status=partial noch bei status=ok.
// Faengt die Mutation "failed>0 als partial melden". (Der bestehende Test
// TestTriggerEndpoint_FailedBodyTreatedAsError prueft nur err != nil.)
func TestTriggerResponseBody_FailedIsHardErrorNotPartial(t *testing.T) {
	cases := map[string]string{
		"partial_failed": `{"status":"partial","count":1,"failed":1}`,
		"ok_failed":      `{"status":"ok","count":1,"failed":1}`,
	}
	for name, body := range cases {
		t.Run(name, func(t *testing.T) {
			srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				w.WriteHeader(http.StatusOK)
				fmt.Fprint(w, body)
			}))
			defer srv.Close()
			sched := newOverlapTestScheduler(t)
			sched.pythonURL = srv.URL

			err := sched.triggerEndpointForUser("/api/scheduler/trip-reports", "default")
			if err == nil {
				t.Fatal("erwartet harten Fehler bei failed>0, bekam nil")
			}
			var pe *partialRunError
			if errors.As(err, &pe) {
				t.Fatalf("failed>0 darf kein partialRunError sein: %v", err)
			}
			if !strings.Contains(err.Error(), "failed") {
				t.Fatalf("Fehlertext nennt failed nicht: %v", err)
			}
		})
	}
}
