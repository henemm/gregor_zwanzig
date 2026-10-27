package scheduler

// ---------------------------------------------------------------------------
// Fix #2149 Scheibe B — Laufbudget je Job, Rotation der Nutzerreihenfolge,
// Job-Rang/#1346, Status-Zahlen ohne Nutzerkennung, Heartbeat-Gating.
//
// Spec: docs/specs/modules/fix_2149_scheduler_budget_teilb.md (Abschnitte 4,
// 5, 7, 9). Helfer: user_call_wait_budget_test.go.
//
// Hinweis AC-10: die Spec nennt "bestehender #1346-Regressionstest ergaenzt";
// das Budget-Szenario steht bewusst hier als eigener Test, damit keine
// committete Testdatei angefasst wird.
// ---------------------------------------------------------------------------

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
	"time"
)

// numField liest eine Zahl aus einem Status-Feld (int oder float64).
func numField(t *testing.T, m map[string]any, key string) int {
	t.Helper()
	v, ok := m[key]
	if !ok {
		t.Fatalf("expected field %q in %v", key, m)
	}
	switch n := v.(type) {
	case int:
		return n
	case int64:
		return int(n)
	case float64:
		return int(n)
	default:
		t.Fatalf("field %q has non-numeric type %T (%v)", key, v, v)
	}
	return 0
}

func usersOf(t *testing.T, sched *Scheduler, jobID string) map[string]any {
	t.Helper()
	job := statusJob(t, sched, jobID)
	users, ok := job["users"].(map[string]any)
	if !ok || users == nil {
		t.Fatalf("expected users{} on %s, got %v", jobID, job["users"])
	}
	return users
}

// AC-7: Das Laufbudget ist nach zwei langsamen Nutzern erschoepft -- der
// dritte bekommt KEINEN POST, wird als "not_reached" gebucht (zaehlt in
// ConsecutivePartial, nicht ConsecutiveFailures), der Job rankt "partial",
// Status zeigt not_reached_budget=1. Welcher Nutzer dritter ist, haengt von
// der Rotation ab -- geprueft wird "genau einer ohne POST".
func TestRunBudget_ExhaustedMarksRemainingUserNotReached(t *testing.T) {
	bs := newBudgetServer(t)
	for _, uid := range []string{"alice", "bob", "carol"} {
		bs.setHang(uid, true)
	}

	sched, _, _ := newBudgetScheduler(t, bs.srv.URL, "alice", "bob", "carol")
	sched.alertWaitBudget = 80 * time.Millisecond
	sched.alertRunBudget = 120 * time.Millisecond

	sched.alertChecks()

	var notReached []string
	for _, uid := range []string{"alice", "bob", "carol"} {
		if bs.count(uid) == 0 {
			notReached = append(notReached, uid)
		}
	}
	if len(notReached) != 1 {
		t.Fatalf("expected exactly 1 user without any POST once the run budget is exhausted (AC-7), got %v", notReached)
	}
	nr := mustUserRecord(t, sched, "alert_checks", notReached[0])
	if nr.LastStatus != "not_reached" {
		t.Fatalf("expected %s booked as 'not_reached' (AC-7/Spec 4), got %q", notReached[0], nr.LastStatus)
	}
	if nr.ConsecutiveFailures != 0 || nr.ConsecutivePartial != 1 {
		t.Fatalf("expected not_reached to leave failures unchanged and count partial (0/1, AC-7), got failures=%d partial=%d",
			nr.ConsecutiveFailures, nr.ConsecutivePartial)
	}
	if lr := lastRunOf(sched, "alert_checks"); lr == nil || lr.Status != "partial" {
		t.Fatalf("expected job run ranked 'partial' (AC-7), got %+v", lr)
	}
	if got := numField(t, usersOf(t, sched, "alert_checks"), "not_reached_budget"); got != 1 {
		t.Fatalf("expected users.not_reached_budget=1 (AC-7), got %d", got)
	}
}

// AC-8: Drei Laeufe mit Laufbudget fuer nur zwei von drei Nutzern -- der
// nicht erreichte Nutzer wechselt, jeder Nutzer ist in genau einem der drei
// Laeufe der nicht erreichte (Rotation Startindex = Laufzaehler mod N; ob der
// erste Lauf bei 0 oder 1 beginnt, ist bewusst nicht festgelegt).
func TestRunBudget_RotationChangesNotReachedUser(t *testing.T) {
	bs := newBudgetServer(t)
	users := []string{"alice", "bob", "carol"}
	for _, uid := range users {
		bs.setDelay(uid, 150*time.Millisecond)
	}

	sched, _, _ := newBudgetScheduler(t, bs.srv.URL, users...)
	sched.alertWaitBudget = 80 * time.Millisecond
	sched.alertRunBudget = 120 * time.Millisecond

	seen := map[string]int{}
	for run := 1; run <= 3; run++ {
		sched.alertChecks()
		contacted := bs.takeOrder()
		if len(contacted) != 2 {
			t.Fatalf("run %d: expected exactly 2 contacted users under the run budget, got %v", run, contacted)
		}
		hit := map[string]bool{}
		for _, uid := range contacted {
			hit[uid] = true
		}
		for _, uid := range users {
			if !hit[uid] {
				seen[uid]++
				if r := mustUserRecord(t, sched, "alert_checks", uid); r.LastStatus != "not_reached" {
					t.Fatalf("run %d: expected %s 'not_reached', got %q", run, uid, r.LastStatus)
				}
			}
		}
		// Spaete Antworten abwarten und ernten lassen, damit der naechste
		// Lauf keine skipped_in_flight-Faelle (ohne Zeitverbrauch) bekommt.
		bs.waitFinished(t, 2)
		time.Sleep(300 * time.Millisecond)
	}
	for _, uid := range users {
		if seen[uid] != 1 {
			t.Fatalf("expected every user to be the not_reached one exactly once across 3 runs "+
				"(rotation, AC-8), got %v", seen)
		}
	}
}

// AC-10: trip_reports_hourly mit einem Budget-Nutzer und zwei ok-Nutzern --
// last_run.status "partial", lastHardStatus unveraendert, KEIN #1346-
// Totalausfall-Alarm.
func TestRunBudget_TripReportsBudgetUserNoTotalOutageAlarm(t *testing.T) {
	bs := newBudgetServer(t)
	bs.setHang("bob", true)

	sched, rec, _ := newBudgetScheduler(t, bs.srv.URL, "alice", "bob", "carol")
	sched.briefingWaitBudget = 50 * time.Millisecond
	sched.mu.Lock()
	sched.lastHardStatus["trip_reports_hourly"] = "ok"
	sched.mu.Unlock()

	sched.tripReports()

	if lr := lastRunOf(sched, "trip_reports_hourly"); lr == nil || lr.Status != "partial" {
		t.Fatalf("expected trip_reports_hourly ranked 'partial' with one budget user (AC-10), got %+v", lr)
	}
	sched.mu.RLock()
	hard := sched.lastHardStatus["trip_reports_hourly"]
	sched.mu.RUnlock()
	if hard != "ok" {
		t.Fatalf("expected lastHardStatus to stay 'ok' after a budget run (AC-10), got %q", hard)
	}
	rec.mu.Lock()
	var high int
	for _, p := range rec.priority {
		if p == "high" {
			high++
		}
	}
	rec.mu.Unlock()
	if high != 0 {
		t.Fatalf("expected 0 high-priority notifications (no #1346 alarm, AC-10), got %d", high)
	}
	if bob := mustUserRecord(t, sched, "trip_reports_hourly", "bob"); bob.LastStatus != "budget" {
		t.Fatalf("test setup: expected bob 'budget' in trip_reports_hourly, got %q", bob.LastStatus)
	}
	if got := bs.count("bob"); got != 1 {
		t.Fatalf("test setup: expected 1 POST for bob, got %d", got)
	}
}

// AC-11: Nach Laeufen mit in_flight, skipped_in_flight und not_reached_budget
// traegt der Status alle drei Zahlen unter users{} -- und die GESAMTE
// Status-Antwort (inkl. last_run.error) enthaelt keine user_id und keine URL.
func TestRunBudget_StatusCountsWithoutUserIDs(t *testing.T) {
	bs := newBudgetServer(t)
	ids := []string{"hikerjbq", "hikerkwz", "hikerpxv", "hikeryfm"}
	bs.setHang("hikerjbq", true)

	sched, _, _ := newBudgetScheduler(t, bs.srv.URL, ids...)
	sched.alertWaitBudget = 50 * time.Millisecond

	sched.alertChecks() // Lauf 1: hikerjbq in flight

	for _, uid := range ids {
		bs.setHang(uid, true)
	}
	sched.alertWaitBudget = 60 * time.Millisecond
	sched.alertRunBudget = 90 * time.Millisecond
	sched.alertChecks() // Lauf 2: 1 skipped, 2 budget/in flight, 1 not_reached

	users := usersOf(t, sched, "alert_checks")
	if got := numField(t, users, "in_flight"); got < 1 {
		t.Fatalf("expected users.in_flight >= 1 (AC-11), got %d", got)
	}
	if got := numField(t, users, "skipped_in_flight"); got != 1 {
		t.Fatalf("expected users.skipped_in_flight=1 (AC-11), got %d", got)
	}
	if got := numField(t, users, "not_reached_budget"); got != 1 {
		t.Fatalf("expected users.not_reached_budget=1 (AC-11), got %d", got)
	}

	// Beide Status()-Zweige tragen die drei Felder auch bei 0 (Spec 9).
	for _, jobID := range []string{"compare_alert_checks", "trip_reports_hourly"} {
		u := usersOf(t, sched, jobID)
		for _, key := range []string{"in_flight", "skipped_in_flight", "not_reached_budget"} {
			if got := numField(t, u, key); got != 0 {
				t.Fatalf("expected %s.users.%s=0 for a job without runs, got %d", jobID, key, got)
			}
		}
	}

	raw, err := json.Marshal(sched.Status())
	if err != nil {
		t.Fatalf("marshal status: %v", err)
	}
	doc := string(raw)
	for _, uid := range ids {
		if strings.Contains(doc, uid) {
			t.Fatalf("expected no user_id %q anywhere in the status response (AC-11), got %s", uid, doc)
		}
	}
	for _, leak := range []string{"?user_id=", "user_id", bs.srv.URL, strings.TrimPrefix(bs.srv.URL, "http://")} {
		if strings.Contains(doc, leak) {
			t.Fatalf("expected no %q in the status response (AC-11), got %s", leak, doc)
		}
	}
}

// AC-13: briefingDispatch mit ECHTER Heartbeat-URL (httptest). Gegenprobe:
// ein voll erfolgreicher Lauf pingt genau einmal. Danach haengt ein Nutzer
// (budget) -- der Folgelauf pingt NICHT.
func TestRunBudget_BriefingDispatchBudgetUserSkipsHeartbeat(t *testing.T) {
	bs := newBudgetServer(t)

	var heartbeatCalls atomic.Int32
	hb := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		heartbeatCalls.Add(1)
		w.WriteHeader(http.StatusOK)
		fmt.Fprint(w, "ok")
	}))
	t.Cleanup(hb.Close)

	sched, _, _ := newBudgetScheduler(t, bs.srv.URL, "alice", "bob")
	sched.heartbeatComparePresets = hb.URL + "/heartbeat-token"
	sched.briefingWaitBudget = 50 * time.Millisecond

	sched.briefingDispatch()
	if got := heartbeatCalls.Load(); got != 1 {
		t.Fatalf("test setup: expected 1 heartbeat ping after a fully successful dispatch, got %d", got)
	}

	bs.setHang("bob", true)
	sched.briefingDispatch()

	if bob := mustUserRecord(t, sched, "trip_reports_hourly", "bob"); bob.LastStatus != "budget" {
		t.Fatalf("test setup: expected bob 'budget' in trip_reports_hourly, got %q", bob.LastStatus)
	}
	if got := heartbeatCalls.Load(); got != 1 {
		t.Fatalf("expected no heartbeat ping when a sub-job has a budget user (AC-13), got %d pings total", got)
	}
}

// F004 (Spec Abschnitt 7): Ein Lauf, in dem ein Nutzer "ok" ist und der
// andere ausschliesslich "not_reached" (kein budget/skip/partial/error), rankt
// trotzdem "partial" -- und briefingDispatch pingt den Heartbeat nicht.
//
// Deterministische Konstruktion: der Test haelt userState.mu, sodass die
// Buchung des ersten (sofort antwortenden, also "ok") Nutzers blockiert, bis
// das Laufbudget sicher verstrichen ist. Der zweite Nutzer findet dann ein
// erschoepftes Laufbudget vor und wird nicht kontaktiert.
func TestRunBudget_OnlyNotReachedUserRanksPartialAndSkipsHeartbeat(t *testing.T) {
	bs := newBudgetServer(t)

	var heartbeatCalls atomic.Int32
	hb := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		heartbeatCalls.Add(1)
		w.WriteHeader(http.StatusOK)
		fmt.Fprint(w, "ok")
	}))
	t.Cleanup(hb.Close)

	sched, _, _ := newBudgetScheduler(t, bs.srv.URL, "alice", "bob")
	sched.heartbeatComparePresets = hb.URL + "/heartbeat-token"
	sched.briefingWaitBudget = 5 * time.Second
	sched.briefingRunBudget = 300 * time.Millisecond

	sched.userState.mu.Lock()
	locked := true
	t.Cleanup(func() {
		if locked {
			sched.userState.mu.Unlock()
		}
	})

	start := time.Now()
	done := make(chan struct{})
	go func() {
		defer close(done)
		sched.briefingDispatch()
	}()

	var first string
	select {
	case first = <-bs.finished:
	case <-time.After(5 * time.Second):
		t.Fatalf("test setup: first user's call never finished")
	}
	if wait := sched.briefingRunBudget + 300*time.Millisecond - time.Since(start); wait > 0 {
		time.Sleep(wait)
	}
	sched.userState.mu.Unlock()
	locked = false

	select {
	case <-done:
	case <-time.After(10 * time.Second):
		t.Fatalf("briefingDispatch did not return")
	}

	second := "alice"
	if first == "alice" {
		second = "bob"
	}
	if r := mustUserRecord(t, sched, "trip_reports_hourly", first); r.LastStatus != "ok" {
		t.Fatalf("test setup: expected first user %s 'ok', got %q", first, r.LastStatus)
	}
	if r := mustUserRecord(t, sched, "trip_reports_hourly", second); r.LastStatus != "not_reached" {
		t.Fatalf("test setup: expected second user %s 'not_reached', got %q", second, r.LastStatus)
	}
	if lr := lastRunOf(sched, "compare_presets_daily"); lr == nil || lr.Status != "ok" {
		t.Fatalf("test setup: expected compare_presets_daily 'ok' so the heartbeat hinges on trip_reports only, got %+v", lr)
	}
	if lr := lastRunOf(sched, "trip_reports_hourly"); lr == nil || lr.Status != "partial" {
		t.Fatalf("expected a run whose only non-ok user is 'not_reached' ranked 'partial' (Spec 7, F004), got %+v", lr)
	}
	if got := heartbeatCalls.Load(); got != 0 {
		t.Fatalf("expected no heartbeat ping when a user was not reached (F004/AC-13), got %d", got)
	}
}
